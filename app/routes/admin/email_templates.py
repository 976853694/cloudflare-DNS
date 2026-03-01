"""
管理员邮件模板路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import User, OperationLog
from app.models.email_template import EmailTemplate
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/email-templates', methods=['GET'])
@admin_required
def get_email_templates():
    """获取所有邮件模板"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user and user.role == 'demo':
        return jsonify({'code': 403, 'message': '演示用户无权查看'}), 403
    
    # 获取数据库中的模板
    db_templates = {t.code: t for t in EmailTemplate.query.all()}
    
    # 合并默认模板和数据库模板
    templates = []
    for code, default in EmailTemplate.DEFAULT_TEMPLATES.items():
        if code in db_templates:
            templates.append(db_templates[code].to_dict())
        else:
            # 使用默认模板
            import json
            templates.append({
                'id': None,
                'code': code,
                'name': default['name'],
                'subject': default['subject'],
                'content': default['content'],
                'variables': json.loads(default['variables']) if default['variables'] else {},
                'status': 1,
                'is_default': True
            })
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {'list': templates}
    })


@admin_bp.route('/email-templates/<code>', methods=['GET'])
@admin_required
def get_email_template(code):
    """获取单个邮件模板"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user and user.role == 'demo':
        return jsonify({'code': 403, 'message': '演示用户无权查看'}), 403
    
    template = EmailTemplate.get_template(code)
    if not template:
        return jsonify({'code': 404, 'message': '模板不存在'}), 404
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': template.to_dict()
    })


@admin_bp.route('/email-templates/<code>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_email_template(code):
    """更新邮件模板"""
    data = request.get_json()
    
    if code not in EmailTemplate.DEFAULT_TEMPLATES:
        return jsonify({'code': 400, 'message': '无效的模板代码'}), 400
    
    template = EmailTemplate.query.filter_by(code=code).first()
    
    if template:
        # 更新现有模板
        template.subject = data.get('subject', template.subject)
        template.content = data.get('content', template.content)
        template.status = data.get('status', template.status)
    else:
        # 创建新模板（基于默认模板）
        default = EmailTemplate.DEFAULT_TEMPLATES[code]
        template = EmailTemplate(
            code=code,
            name=default['name'],
            subject=data.get('subject', default['subject']),
            content=data.get('content', default['content']),
            variables=default['variables'],
            status=data.get('status', 1)
        )
        db.session.add(template)
    
    db.session.commit()
    
    # 记录操作日志
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='email_template',
        target_id=template.id,
        target_name=template.name,
        detail=f'更新邮件模板: {template.name}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '保存成功',
        'data': template.to_dict()
    })


@admin_bp.route('/email-templates/<code>/reset', methods=['POST'])
@admin_required
@demo_forbidden
def reset_email_template(code):
    """重置邮件模板为默认"""
    if code not in EmailTemplate.DEFAULT_TEMPLATES:
        return jsonify({'code': 400, 'message': '无效的模板代码'}), 400
    
    template = EmailTemplate.query.filter_by(code=code).first()
    if template:
        db.session.delete(template)
        db.session.commit()
    
    # 记录操作日志
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='email_template',
        target_name=code,
        detail=f'重置邮件模板为默认: {code}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '已重置为默认模板'
    })


@admin_bp.route('/email-templates/<code>/preview', methods=['POST'])
@admin_required
def preview_email_template(code):
    """预览邮件模板"""
    from app.models import Setting
    
    data = request.get_json() or {}
    subject = data.get('subject', '')
    content = data.get('content', '')
    
    # 使用示例变量
    site_name = Setting.get('site_name', '六趣DNS')
    site_url = Setting.get('site_url', 'https://example.com')
    
    example_vars = {
        'site_name': site_name,
        'verify_url': f'{site_url}/verify?token=example_token',
        'token': 'example_token',
        'domain_name': 'test.example.com',
        'days_remaining': '3',
        'expires_at': '2025-01-01 00:00',
        'deleted_at': '2025-01-04 03:00',
        'renew_url': f'{site_url}/user/domains/1',
        'new_domain_url': f'{site_url}/user/domains/new',
        'domain_url': f'{site_url}/user/domains/1',
        'plan_name': '月付套餐',
        'price': '10.00',
        'new_expires_at': '2025-02-01 00:00',
        'balance': '90.00',
        'reason': '余额不足'
    }
    
    # 替换变量
    for key, value in example_vars.items():
        placeholder = '{{' + key + '}}'
        subject = subject.replace(placeholder, str(value))
        content = content.replace(placeholder, str(value))
    
    # 包装 HTML
    html = EmailTemplate._wrap_html(content)
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'subject': subject,
            'html': html
        }
    })


@admin_bp.route('/email-templates/<code>/test', methods=['POST'])
@admin_required
@demo_forbidden
def test_email_template(code):
    """发送测试邮件"""
    from app.services.email import EmailService
    from app.models import Setting
    
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user or not user.email:
        return jsonify({'code': 400, 'message': '无法获取管理员邮箱'}), 400
    
    if not EmailService.is_configured():
        return jsonify({'code': 400, 'message': 'SMTP未配置'}), 400
    
    # 使用示例变量渲染
    site_name = Setting.get('site_name', '六趣DNS')
    site_url = Setting.get('site_url', 'https://example.com')
    
    example_vars = {
        'site_name': site_name,
        'verify_url': f'{site_url}/verify?token=test_token',
        'token': 'test_token',
        'domain_name': 'test.example.com',
        'days_remaining': '3',
        'expires_at': '2025-01-01 00:00',
        'deleted_at': '2025-01-04 03:00',
        'renew_url': f'{site_url}/user/domains/1',
        'new_domain_url': f'{site_url}/user/domains/new',
        'domain_url': f'{site_url}/user/domains/1',
        'plan_name': '月付套餐',
        'price': '10.00',
        'new_expires_at': '2025-02-01 00:00',
        'balance': '90.00',
        'reason': '余额不足'
    }
    
    subject, html = EmailTemplate.render(code, example_vars)
    if not subject:
        return jsonify({'code': 400, 'message': '模板不存在'}), 400
    
    subject = f'[测试] {subject}'
    success, msg = EmailService.send(user.email, subject, html)
    
    if success:
        return jsonify({'code': 200, 'message': f'测试邮件已发送至 {user.email}'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500
