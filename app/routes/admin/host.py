"""
管理员托管商管理路由
处理托管申请审核、托管商管理、提现管理、托管设置
"""
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, Setting, Domain, DnsChannel, Plan
from app.models.host_application import HostApplication
from app.models.host_withdrawal import HostWithdrawal
from app.models.host_transaction import HostTransaction
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required
from app.utils.timezone import now as beijing_now
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ==================== 托管申请审核 ====================

@admin_bp.route('/host/applications', methods=['GET'])
@admin_required
def list_host_applications():
    """获取托管申请列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    
    query = HostApplication.query
    
    if status:
        query = query.filter_by(status=status)
    
    query = query.order_by(HostApplication.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'code': 200,
        'data': {
            'items': [a.to_dict(include_user=True) for a in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@admin_bp.route('/host/applications/<int:id>', methods=['GET'])
@admin_required
def get_host_application(id):
    """获取托管申请详情"""
    application = HostApplication.query.get_or_404(id)
    return jsonify({
        'code': 200,
        'data': application.to_dict(include_user=True)
    })


@admin_bp.route('/host/applications/<int:id>/approve', methods=['POST'])
@admin_required
def approve_host_application(id):
    """审核通过托管申请"""
    application = HostApplication.query.get_or_404(id)
    
    if not application.is_pending:
        return jsonify({'code': 400, 'message': '该申请已处理'}), 400
    
    admin_id = get_jwt_identity()
    data = request.get_json() or {}
    remark = data.get('remark', '')
    commission_rate = data.get('commission_rate')
    
    # 更新申请状态
    application.approve(admin_id, remark)
    
    # 更新用户状态
    user = application.user
    user.host_status = User.HOST_STATUS_APPROVED
    user.host_approved_at = beijing_now()
    
    # 设置抽成比例
    if commission_rate is not None:
        user.host_commission_rate = commission_rate
    else:
        # 使用系统默认
        default_rate = Setting.get('host_default_commission', 10)
        user.host_commission_rate = default_rate
    
    db.session.commit()
    
    logger.info(f"管理员 {admin_id} 审核通过托管商申请 {id}")
    
    # 发送邮件通知用户
    try:
        if user.email:
            from app.services.email import EmailService
            from app.services.email_templates import EmailTemplateService
            
            site_url = request.host_url.rstrip('/')
            commission_rate = user.get_effective_commission_rate(Setting.get('host_default_commission', 10))
            
            subject, html = EmailTemplateService.render_email('host_application_approved', {
                'username': user.username,
                'reviewed_at': application.reviewed_at.strftime('%Y-%m-%d %H:%M:%S'),
                'commission_rate': commission_rate,
                'admin_remark': remark if remark else '',
                'site_url': site_url
            })
            if subject and html:
                success, msg = EmailService.send(user.email, subject, html)
                if success:
                    logger.info(f"已发送审核通过邮件给用户: {user.email}")
                else:
                    logger.error(f"发送审核通过邮件失败: {msg}")
            else:
                logger.error(f"邮件模板 host_application_approved 渲染失败")
    except Exception as e:
        logger.error(f"发送审核通过邮件失败: {e}", exc_info=True)
    
    return jsonify({
        'code': 200,
        'message': '审核通过',
        'data': application.to_dict(include_user=True)
    })


@admin_bp.route('/host/applications/<int:id>/reject', methods=['POST'])
@admin_required
def reject_host_application(id):
    """审核拒绝托管申请"""
    application = HostApplication.query.get_or_404(id)
    
    if not application.is_pending:
        return jsonify({'code': 400, 'message': '该申请已处理'}), 400
    
    admin_id = get_jwt_identity()
    data = request.get_json() or {}
    remark = data.get('remark', '').strip()
    
    if not remark:
        return jsonify({'code': 400, 'message': '请填写拒绝原因'}), 400
    
    # 更新申请状态
    application.reject(admin_id, remark)
    
    # 更新用户状态
    user = application.user
    user.host_status = User.HOST_STATUS_REJECTED
    
    db.session.commit()
    
    logger.info(f"管理员 {admin_id} 拒绝托管商申请 {id}")
    
    # 发送邮件通知用户
    try:
        if user.email:
            from app.services.email import EmailService
            from app.services.email_templates import EmailTemplateService
            
            subject, html = EmailTemplateService.render_email('host_application_rejected', {
                'username': user.username,
                'rejection_reason': remark
            })
            if subject and html:
                success, msg = EmailService.send(user.email, subject, html)
                if success:
                    logger.info(f"已发送审核拒绝邮件给用户: {user.email}")
                else:
                    logger.error(f"发送审核拒绝邮件失败: {msg}")
            else:
                logger.error(f"邮件模板 host_application_rejected 渲染失败")
    except Exception as e:
        logger.error(f"发送审核拒绝邮件失败: {e}", exc_info=True)
    
    return jsonify({
        'code': 200,
        'message': '已拒绝',
        'data': application.to_dict(include_user=True)
    })


@admin_bp.route('/host/applications/<int:id>', methods=['DELETE'])
@admin_required
def delete_host_application(id):
    """删除托管申请记录"""
    application = HostApplication.query.get_or_404(id)
    
    db.session.delete(application)
    db.session.commit()
    
    logger.info(f"管理员 {get_jwt_identity()} 删除托管申请记录 {id}")
    
    return jsonify({
        'code': 200,
        'message': '删除成功'
    })


@admin_bp.route('/host/applications/batch-delete', methods=['POST'])
@admin_required
def batch_delete_host_applications():
    """批量删除托管申请记录"""
    data = request.get_json() or {}
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'code': 400, 'message': '请选择要删除的记录'}), 400
    
    deleted_count = HostApplication.query.filter(HostApplication.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    
    logger.info(f"管理员 {get_jwt_identity()} 批量删除托管申请记录 {ids}")
    
    return jsonify({
        'code': 200,
        'message': f'成功删除 {deleted_count} 条记录',
        'data': {'deleted_count': deleted_count}
    })


# ==================== 托管商管理 ====================

@admin_bp.route('/host/hosts', methods=['GET'])
@admin_required
def list_hosts():
    """获取托管商列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    keyword = request.args.get('keyword', '').strip()
    
    query = User.query.filter(User.host_status.in_([
        User.HOST_STATUS_APPROVED,
        User.HOST_STATUS_SUSPENDED,
        User.HOST_STATUS_REVOKED
    ]))
    
    if status:
        query = query.filter_by(host_status=status)
    
    if keyword:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{keyword}%'),
                User.email.ilike(f'%{keyword}%')
            )
        )
    
    query = query.order_by(User.host_approved_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # 获取每个托管商的统计数据
    items = []
    for user in pagination.items:
        data = user.to_host_dict()
        data['channels_count'] = DnsChannel.query.filter_by(owner_id=user.id).count()
        data['domains_count'] = Domain.query.filter_by(owner_id=user.id).count()
        data['plans_count'] = Plan.query.filter_by(owner_id=user.id).count()
        items.append(data)
    
    return jsonify({
        'code': 200,
        'data': {
            'items': items,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@admin_bp.route('/host/hosts/<int:id>', methods=['GET'])
@admin_required
def get_host(id):
    """获取托管商详情"""
    user = User.query.get_or_404(id)
    
    if user.host_status == User.HOST_STATUS_NONE:
        return jsonify({'code': 404, 'message': '该用户不是托管商'}), 404
    
    data = user.to_host_dict()
    data['channels_count'] = DnsChannel.query.filter_by(owner_id=user.id).count()
    data['domains_count'] = Domain.query.filter_by(owner_id=user.id).count()
    data['plans_count'] = Plan.query.filter_by(owner_id=user.id).count()
    
    return jsonify({
        'code': 200,
        'data': data
    })


@admin_bp.route('/host/hosts/<int:id>', methods=['PUT'])
@admin_required
def update_host(id):
    """更新托管商信息"""
    user = User.query.get_or_404(id)
    
    if not user.is_host:
        return jsonify({'code': 400, 'message': '该用户不是托管商'}), 400
    
    data = request.get_json() or {}
    
    if 'host_commission_rate' in data:
        rate = data['host_commission_rate']
        if rate is not None:
            try:
                rate = float(rate)
                if rate < 0 or rate > 100:
                    return jsonify({'code': 400, 'message': '抽成比例必须在0-100之间'}), 400
            except (ValueError, TypeError):
                return jsonify({'code': 400, 'message': '抽成比例格式错误'}), 400
        user.host_commission_rate = rate
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '更新成功',
        'data': user.to_host_dict()
    })


@admin_bp.route('/host/hosts/<int:id>/suspend', methods=['POST'])
@admin_required
def suspend_host(id):
    """暂停托管商"""
    user = User.query.get_or_404(id)
    
    if user.host_status != User.HOST_STATUS_APPROVED:
        return jsonify({'code': 400, 'message': '只能暂停已通过的托管商'}), 400
    
    data = request.get_json() or {}
    reason = data.get('reason', '').strip()
    
    if not reason:
        return jsonify({'code': 400, 'message': '请填写暂停原因'}), 400
    
    # 更新用户状态
    user.host_status = User.HOST_STATUS_SUSPENDED
    user.host_suspended_at = beijing_now()
    user.host_suspended_reason = reason
    
    # 禁用所有域名
    Domain.query.filter_by(owner_id=user.id).update({'status': 0})
    
    db.session.commit()
    
    logger.info(f"管理员 {get_jwt_identity()} 暂停托管商 {id}，原因: {reason}")
    
    return jsonify({
        'code': 200,
        'message': '托管商已暂停',
        'data': user.to_host_dict()
    })


@admin_bp.route('/host/hosts/<int:id>/restore', methods=['POST'])
@admin_required
def restore_host(id):
    """恢复托管商"""
    user = User.query.get_or_404(id)
    
    if user.host_status != User.HOST_STATUS_SUSPENDED:
        return jsonify({'code': 400, 'message': '只能恢复已暂停的托管商'}), 400
    
    # 更新用户状态
    user.host_status = User.HOST_STATUS_APPROVED
    user.host_suspended_at = None
    user.host_suspended_reason = None
    
    # 恢复所有域名
    Domain.query.filter_by(owner_id=user.id).update({'status': 1})
    
    db.session.commit()
    
    logger.info(f"管理员 {get_jwt_identity()} 恢复托管商 {id}")
    
    return jsonify({
        'code': 200,
        'message': '托管商已恢复',
        'data': user.to_host_dict()
    })


@admin_bp.route('/host/hosts/<int:id>/revoke', methods=['POST'])
@admin_required
def revoke_host(id):
    """撤销托管权限"""
    user = User.query.get_or_404(id)
    
    if user.host_status not in [User.HOST_STATUS_APPROVED, User.HOST_STATUS_SUSPENDED]:
        return jsonify({'code': 400, 'message': '无法撤销该托管商'}), 400
    
    data = request.get_json() or {}
    reason = data.get('reason', '').strip()
    
    if not reason:
        return jsonify({'code': 400, 'message': '请填写撤销原因'}), 400
    
    # 更新用户状态
    user.host_status = User.HOST_STATUS_REVOKED
    user.host_suspended_at = beijing_now()
    user.host_suspended_reason = reason
    
    # 禁用所有资源
    DnsChannel.query.filter_by(owner_id=user.id).update({'status': 0})
    Domain.query.filter_by(owner_id=user.id).update({'status': 0, 'allow_register': 0})
    Plan.query.filter_by(owner_id=user.id).update({'status': 0})
    
    db.session.commit()
    
    logger.info(f"管理员 {get_jwt_identity()} 撤销托管商 {id}，原因: {reason}")
    
    return jsonify({
        'code': 200,
        'message': '托管权限已撤销',
        'data': user.to_host_dict()
    })


@admin_bp.route('/host/hosts/<int:id>/channels', methods=['GET'])
@admin_required
def get_host_channels(id):
    """获取托管商的渠道列表"""
    user = User.query.get_or_404(id)
    
    if user.host_status == User.HOST_STATUS_NONE:
        return jsonify({'code': 404, 'message': '该用户不是托管商'}), 404
    
    channels = DnsChannel.query.filter_by(owner_id=user.id).all()
    
    return jsonify({
        'code': 200,
        'data': {
            'items': [c.to_dict() for c in channels],
            'total': len(channels)
        }
    })


@admin_bp.route('/host/hosts/<int:id>/domains', methods=['GET'])
@admin_required
def get_host_domains(id):
    """获取托管商的域名列表"""
    user = User.query.get_or_404(id)
    
    if user.host_status == User.HOST_STATUS_NONE:
        return jsonify({'code': 404, 'message': '该用户不是托管商'}), 404
    
    domains = Domain.query.filter_by(owner_id=user.id).all()
    
    return jsonify({
        'code': 200,
        'data': {
            'items': [d.to_admin_dict() for d in domains],
            'total': len(domains)
        }
    })


@admin_bp.route('/host/hosts/<int:id>/plans', methods=['GET'])
@admin_required
def get_host_plans(id):
    """获取托管商的套餐列表"""
    user = User.query.get_or_404(id)
    
    if user.host_status == User.HOST_STATUS_NONE:
        return jsonify({'code': 404, 'message': '该用户不是托管商'}), 404
    
    plans = Plan.query.filter_by(owner_id=user.id).all()
    
    return jsonify({
        'code': 200,
        'data': {
            'items': [p.to_dict() for p in plans],
            'total': len(plans)
        }
    })


# ==================== 提现管理 ====================

@admin_bp.route('/host/withdrawals', methods=['GET'])
@admin_required
def list_withdrawals():
    """获取提现申请列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    host_id = request.args.get('host_id', type=int)
    
    query = HostWithdrawal.query
    
    if status:
        query = query.filter_by(status=status)
    if host_id:
        query = query.filter_by(host_id=host_id)
    
    query = query.order_by(HostWithdrawal.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'code': 200,
        'data': {
            'items': [w.to_dict(include_host=True) for w in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }
    })


@admin_bp.route('/host/withdrawals/<int:id>', methods=['GET'])
@admin_required
def get_withdrawal(id):
    """获取提现申请详情"""
    withdrawal = HostWithdrawal.query.get_or_404(id)
    return jsonify({
        'code': 200,
        'data': withdrawal.to_dict(include_host=True)
    })


@admin_bp.route('/host/withdrawals/<int:id>/approve', methods=['POST'])
@admin_required
def approve_withdrawal(id):
    """审核通过提现申请"""
    withdrawal = HostWithdrawal.query.get_or_404(id)
    
    if not withdrawal.is_pending:
        return jsonify({'code': 400, 'message': '该申请已处理'}), 400
    
    admin_id = get_jwt_identity()
    data = request.get_json() or {}
    remark = data.get('remark', '')
    
    withdrawal.approve(admin_id, remark)
    db.session.commit()
    
    logger.info(f"管理员 {admin_id} 审核通过提现申请 {id}，金额: ¥{withdrawal.amount}")
    
    return jsonify({
        'code': 200,
        'message': '审核通过',
        'data': withdrawal.to_dict(include_host=True)
    })


@admin_bp.route('/host/withdrawals/<int:id>/reject', methods=['POST'])
@admin_required
def reject_withdrawal(id):
    """审核拒绝提现申请"""
    withdrawal = HostWithdrawal.query.get_or_404(id)
    
    if not withdrawal.is_pending:
        return jsonify({'code': 400, 'message': '该申请已处理'}), 400
    
    admin_id = get_jwt_identity()
    data = request.get_json() or {}
    remark = data.get('remark', '').strip()
    
    if not remark:
        return jsonify({'code': 400, 'message': '请填写拒绝原因'}), 400
    
    withdrawal.reject(admin_id, remark)
    
    # 返还余额
    user = withdrawal.host
    if user:
        user.host_balance += withdrawal.amount
    
    db.session.commit()
    
    logger.info(f"管理员 {admin_id} 拒绝提现申请 {id}，金额: ¥{withdrawal.amount}，原因: {remark}")
    
    return jsonify({
        'code': 200,
        'message': '已拒绝，金额已返还',
        'data': withdrawal.to_dict(include_host=True)
    })


@admin_bp.route('/host/withdrawals/<int:id>/complete', methods=['POST'])
@admin_required
def complete_withdrawal(id):
    """完成提现（标记为已打款）"""
    withdrawal = HostWithdrawal.query.get_or_404(id)
    
    if not withdrawal.is_approved:
        return jsonify({'code': 400, 'message': '该申请未通过审核'}), 400
    
    admin_id = get_jwt_identity()
    
    withdrawal.complete()
    db.session.commit()
    
    logger.info(f"管理员 {admin_id} 完成提现申请 {id}，金额: ¥{withdrawal.amount}")
    
    return jsonify({
        'code': 200,
        'message': '已标记为完成',
        'data': withdrawal.to_dict(include_host=True)
    })


# ==================== 托管设置 ====================

@admin_bp.route('/host/settings', methods=['GET'])
@admin_required
def get_host_settings():
    """获取托管设置"""
    return jsonify({
        'code': 200,
        'data': {
            'host_enabled': Setting.get('host_enabled', True),
            'host_default_commission': Setting.get('host_default_commission', 10),
            'host_min_withdraw': Setting.get('host_min_withdraw', 100),
            'host_max_channels': Setting.get('host_max_channels', 10),
            'host_max_domains': Setting.get('host_max_domains', 50),
            'host_auto_approve': Setting.get('host_auto_approve', False)
        }
    })


@admin_bp.route('/host/settings', methods=['PUT'])
@admin_required
def update_host_settings():
    """更新托管设置"""
    data = request.get_json() or {}
    
    if 'host_enabled' in data:
        Setting.set('host_enabled', bool(data['host_enabled']))
    
    if 'host_default_commission' in data:
        try:
            rate = float(data['host_default_commission'])
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '抽成比例格式无效'}), 400
        if rate < 0 or rate > 100:
            return jsonify({'code': 400, 'message': '抽成比例必须在0-100之间'}), 400
        Setting.set('host_default_commission', rate)
    
    if 'host_min_withdraw' in data:
        try:
            min_withdraw = float(data['host_min_withdraw'])
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '最低提现金额格式无效'}), 400
        if min_withdraw < 0:
            return jsonify({'code': 400, 'message': '最低提现金额不能为负数'}), 400
        Setting.set('host_min_withdraw', min_withdraw)
    
    if 'host_max_channels' in data:
        try:
            max_channels = int(data['host_max_channels'])
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '最大渠道数格式无效'}), 400
        if max_channels < 1:
            return jsonify({'code': 400, 'message': '最大渠道数必须大于0'}), 400
        Setting.set('host_max_channels', max_channels)
    
    if 'host_max_domains' in data:
        try:
            max_domains = int(data['host_max_domains'])
        except (ValueError, TypeError):
            return jsonify({'code': 400, 'message': '最大域名数格式无效'}), 400
        if max_domains < 1:
            return jsonify({'code': 400, 'message': '最大域名数必须大于0'}), 400
        Setting.set('host_max_domains', max_domains)
    
    if 'host_auto_approve' in data:
        Setting.set('host_auto_approve', bool(data['host_auto_approve']))
    
    return jsonify({
        'code': 200,
        'message': '设置已更新',
        'data': {
            'host_enabled': Setting.get('host_enabled', True),
            'host_default_commission': Setting.get('host_default_commission', 10),
            'host_min_withdraw': Setting.get('host_min_withdraw', 100),
            'host_max_channels': Setting.get('host_max_channels', 10),
            'host_max_domains': Setting.get('host_max_domains', 50),
            'host_auto_approve': Setting.get('host_auto_approve', False)
        }
    })


# ==================== 托管统计 ====================

@admin_bp.route('/host/stats', methods=['GET'])
@admin_required
def get_host_stats():
    """获取托管统计数据"""
    # 托管商数量统计
    total_hosts = User.query.filter(User.host_status.in_([
        User.HOST_STATUS_APPROVED,
        User.HOST_STATUS_SUSPENDED,
        User.HOST_STATUS_REVOKED
    ])).count()
    
    active_hosts = User.query.filter_by(host_status=User.HOST_STATUS_APPROVED).count()
    pending_applications = HostApplication.query.filter_by(status='pending').count()
    
    # 托管资源统计
    host_channels = DnsChannel.query.filter(DnsChannel.owner_id.isnot(None)).count()
    host_domains = Domain.query.filter(Domain.owner_id.isnot(None)).count()
    host_plans = Plan.query.filter(Plan.owner_id.isnot(None)).count()
    
    # 收益统计
    total_platform_fee = db.session.query(db.func.sum(HostTransaction.platform_fee)).scalar() or 0
    total_host_earnings = db.session.query(db.func.sum(HostTransaction.host_earnings)).scalar() or 0
    total_transactions = db.session.query(db.func.sum(HostTransaction.total_amount)).scalar() or 0
    
    # 提现统计
    pending_withdrawals = HostWithdrawal.query.filter_by(status=HostWithdrawal.STATUS_PENDING).count()
    approved_withdrawals = HostWithdrawal.query.filter_by(status=HostWithdrawal.STATUS_APPROVED).count()
    total_withdrawn = db.session.query(db.func.sum(HostWithdrawal.amount)).filter(
        HostWithdrawal.status == HostWithdrawal.STATUS_COMPLETED
    ).scalar() or 0
    pending_withdrawal_amount = db.session.query(db.func.sum(HostWithdrawal.amount)).filter(
        HostWithdrawal.status.in_([HostWithdrawal.STATUS_PENDING, HostWithdrawal.STATUS_APPROVED])
    ).scalar() or 0
    
    return jsonify({
        'code': 200,
        'data': {
            'total_hosts': total_hosts,
            'active_hosts': active_hosts,
            'pending_applications': pending_applications,
            'host_channels': host_channels,
            'host_domains': host_domains,
            'host_plans': host_plans,
            'total_transactions': float(total_transactions),
            'total_platform_fee': float(total_platform_fee),
            'total_host_earnings': float(total_host_earnings),
            'pending_withdrawals': pending_withdrawals,
            'approved_withdrawals': approved_withdrawals,
            'total_withdrawn': float(total_withdrawn),
            'pending_withdrawal_amount': float(pending_withdrawal_amount)
        }
    })
