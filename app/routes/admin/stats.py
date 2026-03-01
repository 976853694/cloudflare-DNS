"""
管理员统计数据路由
"""
import requests
from flask import jsonify, current_app, request
from datetime import timedelta
from app import db
from app.models import User, CloudflareAccount, Domain, Subdomain, DnsRecord, OperationLog, Plan, RedeemCode
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required
from app.utils.timezone import now as beijing_now


@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_stats():
    """获取统计数据"""
    # 获取今日开始和结束时间（北京时间）
    today_start = beijing_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = beijing_now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # 今日登录数
    today_logins = OperationLog.query.filter(
        OperationLog.action == OperationLog.ACTION_LOGIN,
        OperationLog.created_at >= today_start,
        OperationLog.created_at <= today_end
    ).count()
    
    # 卡密统计
    redeem_codes_total = RedeemCode.query.count()
    redeem_codes_unused = RedeemCode.query.filter_by(status=RedeemCode.STATUS_UNUSED).count()
    redeem_codes_used = RedeemCode.query.filter_by(status=RedeemCode.STATUS_USED).count()
    
    # 套餐统计
    plans_count = Plan.query.filter_by(status=1).count()
    
    # 渠道数（DNS服务商）
    from app.models import DnsChannel
    channels_count = DnsChannel.query.count()
    
    # 即将到期的域名（7天内，仅统计正常状态）
    expiring_soon = Subdomain.query.filter(
        Subdomain.status == 1,
        Subdomain.expires_at != None,
        Subdomain.expires_at <= beijing_now() + timedelta(days=7),
        Subdomain.expires_at > beijing_now()
    ).count()
    
    stats = {
        'users_count': User.query.filter(User.status != User.STATUS_BANNED).count(),
        'domains_count': Domain.query.count(),
        'subdomains_count': Subdomain.query.filter(Subdomain.status == 1).count(),
        'records_count': DnsRecord.query.count(),
        'today_new_users': User.query.filter(
            User.created_at >= today_start,
            User.created_at <= today_end
        ).count(),
        'today_new_subdomains': Subdomain.query.filter(
            Subdomain.created_at >= today_start,
            Subdomain.created_at <= today_end
        ).count(),
        'today_logins': today_logins,
        'redeem_codes_total': redeem_codes_total,
        'redeem_codes_unused': redeem_codes_unused,
        'redeem_codes_used': redeem_codes_used,
        'plans_count': plans_count,
        'channels_count': channels_count,
        'expiring_soon': expiring_soon
    }
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': stats
    })


@admin_bp.route('/pending-tasks', methods=['GET'])
@admin_required
def get_pending_tasks():
    """获取待办事项"""
    from app.models import FreePlanApplication, Ticket, HostApplication
    
    # 获取今日开始和结束时间（北京时间）
    today_start = beijing_now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = beijing_now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # 免费套餐申请待审核
    free_plan_pending = FreePlanApplication.query.filter_by(status='pending').count()
    
    # 即将到期的域名（7天内，仅统计正常状态）
    expiring_soon = Subdomain.query.filter(
        Subdomain.status == 1,
        Subdomain.expires_at != None,
        Subdomain.expires_at <= beijing_now() + timedelta(days=7),
        Subdomain.expires_at > beijing_now()
    ).count()
    
    # 待回复工单
    pending_tickets = Ticket.query.filter_by(status='open').count()
    
    # 托管商申请待审核
    host_pending = HostApplication.query.filter_by(status='pending').count()
    
    # 今日新用户
    today_new_users = User.query.filter(
        User.created_at >= today_start,
        User.created_at <= today_end
    ).count()
    
    # 今日新域名
    today_new_subdomains = Subdomain.query.filter(
        Subdomain.created_at >= today_start,
        Subdomain.created_at <= today_end
    ).count()
    
    tasks = {
        'free_plan_pending': free_plan_pending,
        'expiring_soon': expiring_soon,
        'pending_tickets': pending_tickets,
        'host_pending': host_pending,
        'today_new_users': today_new_users,
        'today_new_subdomains': today_new_subdomains
    }
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': tasks
    })


@admin_bp.route('/recent-activities', methods=['GET'])
@admin_required
def get_recent_activities():
    """获取最近活动"""
    limit = request.args.get('limit', 10, type=int)
    
    # 获取最近的操作日志
    logs = OperationLog.query.order_by(
        OperationLog.created_at.desc()
    ).limit(limit).all()
    
    activities = []
    for log in logs:
        activity = {
            'id': log.id,
            'action': log.action,
            'detail': log.detail,
            'user_id': log.user_id,
            'username': log.user.username if log.user else '系统',
            'created_at': log.created_at.isoformat() if log.created_at else None,
            'ip_address': log.ip_address
        }
        activities.append(activity)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'activities': activities
        }
    })


@admin_bp.route('/check-update', methods=['GET'])
@admin_required
def check_update():
    """
    检查版本更新
    远程 API 响应格式:
    {
        "hasVersion": true,
        "version": "1.2.0",
        "changelog": "## 更新内容\n- 功能1",
        "changelogHtml": "<h2>更新内容</h2>\n<ul><li>功能1</li></ul>",
        "downloadUrl": "https://example.com/download",
        "forceUpdate": false,
        "createdAt": "2026-01-01T00:00:00.000Z"
    }
    """
    try:
        current_version = current_app.config.get('APP_VERSION', '1.0')
        check_url = current_app.config.get('VERSION_CHECK_URL')
        
        if not check_url:
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {'has_update': False}
            })
        
        # 请求远程版本信息
        response = requests.get(check_url, timeout=5)
        if response.status_code != 200:
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {'has_update': False}
            })
        
        remote_data = response.json()
        
        # 检查是否有版本信息
        if not remote_data.get('hasVersion', False):
            return jsonify({
                'code': 200,
                'message': 'success',
                'data': {'has_update': False}
            })
        
        latest_version = remote_data.get('version', '0')
        
        # 比较版本号
        def compare_version(v1, v2):
            """比较版本号，v1 < v2 返回 True (表示有更新)"""
            try:
                parts1 = [int(x) for x in str(v1).split('.')]
                parts2 = [int(x) for x in str(v2).split('.')]
                for i in range(max(len(parts1), len(parts2))):
                    num1 = parts1[i] if i < len(parts1) else 0
                    num2 = parts2[i] if i < len(parts2) else 0
                    if num1 < num2:
                        return True
                    if num1 > num2:
                        return False
                return False
            except (ValueError, AttributeError):
                return False
        
        has_update = compare_version(current_version, latest_version)
        
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {
                'has_update': has_update,
                'current_version': current_version,
                'latest_version': latest_version,
                'changelog_html': remote_data.get('changelogHtml', ''),
                'download_url': remote_data.get('downloadUrl', ''),
                'force_update': remote_data.get('forceUpdate', False),
                'created_at': remote_data.get('createdAt', '')
            }
        })
    except Exception as e:
        current_app.logger.error(f'版本检查失败: {str(e)}')
        return jsonify({
            'code': 200,
            'message': 'success',
            'data': {'has_update': False}
        })
