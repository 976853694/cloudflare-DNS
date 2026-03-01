"""
管理员系统设置路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app.models import User, Setting, OperationLog
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/settings', methods=['GET'])
@admin_required
def get_settings():
    """获取系统设置"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    # 演示用户禁止查看设置
    if user and user.role == 'demo':
        return jsonify({
            'code': 403,
            'message': '演示用户无权查看系统设置'
        }), 403
    
    settings = Setting.get_all()
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'settings': settings}
    })


@admin_bp.route('/settings', methods=['PUT'])
@admin_required
@demo_forbidden
def update_settings():
    """更新系统设置"""
    data = request.get_json()
    
    for key, value in data.items():
        Setting.set(key, value)
    
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='settings',
        detail='更新系统设置',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '设置保存成功',
        'data': {'settings': Setting.get_all()}
    })


@admin_bp.route('/settings/test-smtp', methods=['POST'])
@admin_required
@demo_forbidden
def test_smtp():
    """测试SMTP发送"""
    from app.services.email import EmailService
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user or not user.email:
        return jsonify({'code': 400, 'message': '无法获取管理员邮箱'}), 400
    
    success, msg = EmailService.send(user.email, '邮件测试', '<h2>测试成功</h2><p>SMTP配置正确，此邮件由系统自动发送。</p>')
    if success:
        return jsonify({'code': 200, 'message': f'测试邮件已发送至 {user.email}'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500


@admin_bp.route('/settings/test-email', methods=['POST'])
@admin_required
@demo_forbidden
def test_email():
    """测试邮件发送（支持 SMTP 和阿里云）"""
    from app.services.email import EmailService
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user or not user.email:
        return jsonify({'code': 400, 'message': '无法获取管理员邮箱'}), 400
    
    provider = EmailService.get_email_provider()
    provider_name = '阿里云邮件推送' if provider == 'aliyun' else 'SMTP'
    
    success, msg = EmailService.send(
        user.email, 
        '邮件测试', 
        f'<h2>测试成功</h2><p>当前使用 {provider_name} 发送邮件，配置正确。</p>'
    )
    if success:
        return jsonify({'code': 200, 'message': f'测试邮件已发送至 {user.email}（{provider_name}）'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500


@admin_bp.route('/settings/test-sms', methods=['POST'])
@admin_required
@demo_forbidden
def test_sms():
    """测试短信发送"""
    from app.services.sms import SmsService
    
    data = request.get_json() or {}
    phone = data.get('phone', '')
    
    if not phone:
        return jsonify({'code': 400, 'message': '请输入测试手机号'}), 400
    
    # 验证手机号格式
    import re
    if not re.match(r'^1[3-9]\d{9}$', phone):
        return jsonify({'code': 400, 'message': '手机号格式不正确'}), 400
    
    if not SmsService.is_enabled():
        return jsonify({'code': 400, 'message': '短信服务未启用'}), 400
    
    # 生成测试验证码
    code = SmsService.generate_code()
    
    # 发送短信
    success, msg = SmsService.send_login_code(phone, code)
    
    if success:
        return jsonify({'code': 200, 'message': f'测试短信已发送至 {phone}，验证码: {code}'})
    return jsonify({'code': 500, 'message': msg}), 500


@admin_bp.route('/settings/check-expiry', methods=['POST'])
@admin_required
@demo_forbidden
def manual_check_expiry():
    """手动检测域名到期提醒"""
    from datetime import timedelta
    from app.models import Subdomain, User, Setting
    from app.models.email_template import EmailTemplate
    from app.services.email import EmailService
    from app.utils.timezone import now as beijing_now
    
    # 检查邮件服务是否配置
    if not EmailService.is_configured():
        return jsonify({'code': 400, 'message': '邮件服务未配置'}), 400
    
    site_name = Setting.get('site_name', '六趣DNS')
    site_url = Setting.get('site_url', '')
    base_url = site_url.rstrip('/') if site_url else ''
    
    # 获取提醒天数配置
    days_str = Setting.get('domain_expiry_reminder_days', '7,3,2,1')
    try:
        reminder_days = [int(d.strip()) for d in days_str.split(',') if d.strip().isdigit()]
    except:
        reminder_days = [7, 3, 2, 1]
    
    now = beijing_now()
    sent_count = 0
    checked_domains = []
    
    for days in reminder_days:
        target_date = now + timedelta(days=days)
        start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        
        expiring = Subdomain.query.filter(
            Subdomain.expires_at >= start,
            Subdomain.expires_at < end,
            Subdomain.status == 1
        ).all()
        
        for sub in expiring:
            user = User.query.get(sub.user_id)
            if user:
                renew_url = f'{base_url}/user/domains/{sub.id}' if base_url else f'/user/domains/{sub.id}'
                
                # 使用邮件模板
                subject, html = EmailTemplate.render('domain_expiry', {
                    'site_name': site_name,
                    'domain_name': sub.full_name,
                    'days_remaining': str(days),
                    'expires_at': sub.expires_at.strftime('%Y-%m-%d %H:%M'),
                    'renew_url': renew_url
                })
                
                if subject and html:
                    success, _ = EmailService.send(user.email, subject, html)
                    if success:
                        sent_count += 1
                        checked_domains.append({
                            'domain': sub.full_name,
                            'user': user.username,
                            'email': user.email,
                            'days': days,
                            'expires_at': sub.expires_at.strftime('%Y-%m-%d %H:%M')
                        })
    
    return jsonify({
        'code': 200,
        'message': f'检测完成，已发送 {sent_count} 封提醒邮件',
        'data': {
            'sent_count': sent_count,
            'reminder_days': reminder_days,
            'domains': checked_domains
        }
    })
