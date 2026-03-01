"""
管理后台 - 空置域名管理
"""
from flask import jsonify, request
from app import db
from app.models import Subdomain, User, Setting
from app.services.idle_domain_checker import IdleDomainChecker
from app.utils.timezone import now as beijing_now
from app.routes.admin import admin_bp
from .decorators import admin_required
from datetime import timedelta


@admin_bp.route('/idle-domains/stats', methods=['GET'])
@admin_required
def get_idle_domains_stats():
    """获取空置域名统计"""
    try:
        # 检查功能是否启用
        enabled = Setting.get('idle_domain_check_enabled', '1') == '1'
        reminder_days = int(Setting.get('idle_domain_reminder_days', '7'))
        delete_days = int(Setting.get('idle_domain_delete_days', '10'))
        
        # 计算各阶段域名数量
        now = beijing_now()
        reminder_target = now - timedelta(days=reminder_days)
        delete_target = now - timedelta(days=delete_days)
        
        # 待提醒的域名(注册>=提醒天数,未发送提醒,无记录)
        pending_reminder = Subdomain.query.filter(
            Subdomain.created_at <= reminder_target,
            Subdomain.ns_mode == 0,
            Subdomain.idle_reminder_sent_at.is_(None),
            Subdomain.status == 1
        ).all()
        pending_reminder = [s for s in pending_reminder if s.records.count() == 0]
        
        # 已提醒的域名(已发送提醒,但未到删除时间)
        reminded = Subdomain.query.filter(
            Subdomain.idle_reminder_sent_at.isnot(None),
            Subdomain.created_at > delete_target,
            Subdomain.ns_mode == 0,
            Subdomain.status == 1
        ).all()
        reminded = [s for s in reminded if s.records.count() == 0]
        
        # 待删除的域名(注册>=删除天数,无记录)
        pending_deletion = Subdomain.query.filter(
            Subdomain.created_at <= delete_target,
            Subdomain.ns_mode == 0,
            Subdomain.status == 1
        ).all()
        pending_deletion = [s for s in pending_deletion if s.records.count() == 0]
        
        # 所有空置域名(无记录,未转移NS)
        all_idle = Subdomain.query.filter(
            Subdomain.ns_mode == 0,
            Subdomain.status == 1
        ).all()
        all_idle = [s for s in all_idle if s.records.count() == 0]
        
        return jsonify({
            'code': 200,
            'data': {
                'enabled': enabled,
                'reminder_days': reminder_days,
                'delete_days': delete_days,
                'pending_reminder_count': len(pending_reminder),
                'reminded_count': len(reminded),
                'pending_deletion_count': len(pending_deletion),
                'total_idle_count': len(all_idle)
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取统计失败: {str(e)}'})


@admin_bp.route('/idle-domains/list', methods=['GET'])
@admin_required
def get_idle_domains_list():
    """获取空置域名列表"""
    try:
        status = request.args.get('status', 'all')  # all/pending_reminder/reminded/pending_deletion
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        reminder_days = int(Setting.get('idle_domain_reminder_days', '7'))
        delete_days = int(Setting.get('idle_domain_delete_days', '10'))
        now = beijing_now()
        reminder_target = now - timedelta(days=reminder_days)
        delete_target = now - timedelta(days=delete_days)
        
        # 基础查询
        query = Subdomain.query.filter(
            Subdomain.ns_mode == 0,
            Subdomain.status == 1
        )
        
        # 搜索过滤
        if search:
            query = query.filter(
                db.or_(
                    Subdomain.name.like(f'%{search}%'),
                    Subdomain.full_name.like(f'%{search}%')
                )
            )
        
        # 状态过滤
        if status == 'pending_reminder':
            query = query.filter(
                Subdomain.created_at <= reminder_target,
                Subdomain.idle_reminder_sent_at.is_(None)
            )
        elif status == 'reminded':
            query = query.filter(
                Subdomain.idle_reminder_sent_at.isnot(None),
                Subdomain.created_at > delete_target
            )
        elif status == 'pending_deletion':
            query = query.filter(
                Subdomain.created_at <= delete_target
            )
        
        # 获取所有结果
        all_subdomains = query.order_by(Subdomain.created_at.asc()).all()
        
        # 过滤出真正没有记录的域名
        idle_subdomains = [s for s in all_subdomains if s.records.count() == 0]
        
        # 手动分页
        total = len(idle_subdomains)
        start = (page - 1) * per_page
        end = start + per_page
        page_subdomains = idle_subdomains[start:end]
        
        # 构建返回数据
        items = []
        for subdomain in page_subdomains:
            user = User.query.get(subdomain.user_id)
            idle_days = (now - subdomain.created_at).days
            
            items.append({
                'id': subdomain.id,
                'full_name': subdomain.full_name,
                'prefix': subdomain.name,
                'domain_name': subdomain.domain.name if subdomain.domain else '',
                'user_id': subdomain.user_id,
                'username': user.username if user else '',
                'user_email': user.email if user else '',
                'created_at': subdomain.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'idle_days': idle_days,
                'idle_reminder_sent_at': subdomain.idle_reminder_sent_at.strftime('%Y-%m-%d %H:%M:%S') if subdomain.idle_reminder_sent_at else None,
                'status': 'pending_deletion' if idle_days >= delete_days else ('reminded' if subdomain.idle_reminder_sent_at else 'pending_reminder')
            })
        
        return jsonify({
            'code': 200,
            'data': {
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': (total + per_page - 1) // per_page
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'获取列表失败: {str(e)}'})


@admin_bp.route('/idle-domains/<int:subdomain_id>/send-reminder', methods=['POST'])
@admin_required
def send_idle_domain_reminder(subdomain_id):
    """手动发送提醒邮件"""
    try:
        subdomain = Subdomain.query.get(subdomain_id)
        if not subdomain:
            return jsonify({'code': 404, 'message': '域名不存在'})
        
        # 检查是否有DNS记录
        if subdomain.records.count() > 0:
            return jsonify({'code': 400, 'message': '该域名已有DNS记录,无需提醒'})
        
        # 发送提醒
        success = IdleDomainChecker.send_reminder(subdomain)
        
        if success:
            return jsonify({'code': 200, 'message': '提醒邮件发送成功'})
        else:
            return jsonify({'code': 500, 'message': '提醒邮件发送失败'})
    except Exception as e:
        return jsonify({'code': 500, 'message': f'发送失败: {str(e)}'})


@admin_bp.route('/idle-domains/<int:subdomain_id>/delete', methods=['DELETE'])
@admin_required
def delete_idle_domain(subdomain_id):
    """手动删除空置域名"""
    try:
        subdomain = Subdomain.query.get(subdomain_id)
        if not subdomain:
            return jsonify({'code': 404, 'message': '域名不存在'})
        
        # 删除域名
        success = IdleDomainChecker.delete_idle_domain(subdomain)
        
        if success:
            return jsonify({'code': 200, 'message': '域名删除成功'})
        else:
            return jsonify({'code': 500, 'message': '域名删除失败'})
    except Exception as e:
        return jsonify({'code': 500, 'message': f'删除失败: {str(e)}'})


@admin_bp.route('/idle-domains/batch-send-reminder', methods=['POST'])
@admin_required
def batch_send_idle_domain_reminder():
    """批量发送提醒邮件"""
    try:
        data = request.get_json()
        subdomain_ids = data.get('subdomain_ids', [])
        
        if not subdomain_ids:
            return jsonify({'code': 400, 'message': '请选择要发送提醒的域名'})
        
        success_count = 0
        failed_count = 0
        
        for subdomain_id in subdomain_ids:
            subdomain = Subdomain.query.get(subdomain_id)
            if subdomain and subdomain.records.count() == 0:
                if IdleDomainChecker.send_reminder(subdomain):
                    success_count += 1
                else:
                    failed_count += 1
        
        return jsonify({
            'code': 200,
            'message': f'批量发送完成: 成功{success_count}个, 失败{failed_count}个',
            'data': {
                'success_count': success_count,
                'failed_count': failed_count
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'批量发送失败: {str(e)}'})


@admin_bp.route('/idle-domains/batch-delete', methods=['POST'])
@admin_required
def batch_delete_idle_domains():
    """批量删除空置域名"""
    try:
        data = request.get_json()
        subdomain_ids = data.get('subdomain_ids', [])
        
        if not subdomain_ids:
            return jsonify({'code': 400, 'message': '请选择要删除的域名'})
        
        success_count = 0
        failed_count = 0
        
        for subdomain_id in subdomain_ids:
            subdomain = Subdomain.query.get(subdomain_id)
            if subdomain:
                if IdleDomainChecker.delete_idle_domain(subdomain):
                    success_count += 1
                else:
                    failed_count += 1
        
        return jsonify({
            'code': 200,
            'message': f'批量删除完成: 成功{success_count}个, 失败{failed_count}个',
            'data': {
                'success_count': success_count,
                'failed_count': failed_count
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'批量删除失败: {str(e)}'})


@admin_bp.route('/idle-domains/manual-check', methods=['POST'])
@admin_required
def manual_check_idle_domains():
    """手动触发空置域名检测"""
    try:
        # 检查需要提醒的域名
        reminder_domains = IdleDomainChecker.check_for_reminder()
        
        # 检查需要删除的域名
        deletion_domains = IdleDomainChecker.check_for_deletion()
        
        return jsonify({
            'code': 200,
            'message': '检测完成',
            'data': {
                'reminder_count': len(reminder_domains),
                'deletion_count': len(deletion_domains),
                'reminder_domains': [
                    {
                        'id': s.id,
                        'full_name': s.full_name,
                        'created_at': s.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'idle_days': (beijing_now() - s.created_at).days
                    } for s in reminder_domains[:10]  # 只返回前10个
                ],
                'deletion_domains': [
                    {
                        'id': s.id,
                        'full_name': s.full_name,
                        'created_at': s.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'idle_days': (beijing_now() - s.created_at).days
                    } for s in deletion_domains[:10]  # 只返回前10个
                ]
            }
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'检测失败: {str(e)}'})
