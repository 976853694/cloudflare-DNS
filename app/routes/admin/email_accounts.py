"""
邮箱账户管理 API
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import User, Setting, OperationLog
from app.models.email_account import EmailAccount
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.ip_utils import get_real_ip

bp = Blueprint('email_accounts', __name__, url_prefix='/api/admin/email-accounts')


@bp.route('', methods=['GET'])
@admin_required
def get_accounts():
    """获取所有邮箱账户列表"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    # 演示用户禁止查看
    if user and user.role == 'demo':
        return jsonify({
            'code': 403,
            'message': '演示用户无权查看邮箱账户'
        }), 403
    
    accounts = EmailAccount.get_all_accounts()
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'accounts': [a.to_dict(include_config=True) for a in accounts]
        }
    })


@bp.route('', methods=['POST'])
@admin_required
@demo_forbidden
def create_account():
    """添加新邮箱账户"""
    data = request.get_json()
    
    # 验证必填字段
    name = data.get('name', '').strip()
    account_type = data.get('type', '').strip()
    config = data.get('config', {})
    
    if not name:
        return jsonify({'code': 400, 'message': '账户名称不能为空'}), 400
    
    if account_type not in [EmailAccount.TYPE_SMTP, EmailAccount.TYPE_ALIYUN]:
        return jsonify({'code': 400, 'message': '不支持的账户类型'}), 400
    
    # 验证配置
    is_valid, error = EmailAccount.validate_config(account_type, config)
    if not is_valid:
        return jsonify({'code': 400, 'message': error}), 400
    
    # 创建账户
    account = EmailAccount(
        name=name,
        type=account_type,
        daily_limit=int(data.get('daily_limit', 500)),
        priority=int(data.get('priority', 10)),
        enabled=bool(data.get('enabled', True))
    )
    account.set_config(config)
    
    db.session.add(account)
    db.session.commit()
    
    # 记录操作日志
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_CREATE,
        target_type='email_account',
        target_id=account.id,
        detail=f'添加邮箱账户: {name}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '账户添加成功',
        'data': {'account': account.to_dict(include_config=True)}
    })


@bp.route('/<int:account_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_account(account_id):
    """更新邮箱账户"""
    account = EmailAccount.query.get(account_id)
    if not account:
        return jsonify({'code': 404, 'message': '账户不存在'}), 404
    
    data = request.get_json()
    
    # 更新名称
    if 'name' in data:
        name = data['name'].strip()
        if not name:
            return jsonify({'code': 400, 'message': '账户名称不能为空'}), 400
        account.name = name
    
    # 更新类型和配置
    if 'type' in data or 'config' in data:
        account_type = data.get('type', account.type)
        config = data.get('config', account.get_config())
        
        if account_type not in [EmailAccount.TYPE_SMTP, EmailAccount.TYPE_ALIYUN]:
            return jsonify({'code': 400, 'message': '不支持的账户类型'}), 400
        
        # 如果配置中有密码占位符，保留原密码
        old_config = account.get_config()
        if config.get('password') == '******':
            config['password'] = old_config.get('password', '')
        if config.get('access_key_secret') == '******':
            config['access_key_secret'] = old_config.get('access_key_secret', '')
        
        # 验证配置
        is_valid, error = EmailAccount.validate_config(account_type, config)
        if not is_valid:
            return jsonify({'code': 400, 'message': error}), 400
        
        account.type = account_type
        account.set_config(config)
    
    # 更新其他字段
    if 'daily_limit' in data:
        account.daily_limit = int(data['daily_limit'])
    if 'priority' in data:
        account.priority = int(data['priority'])
    if 'enabled' in data:
        account.enabled = bool(data['enabled'])
    
    db.session.commit()
    
    # 记录操作日志
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='email_account',
        target_id=account.id,
        detail=f'更新邮箱账户: {account.name}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '账户更新成功',
        'data': {'account': account.to_dict(include_config=True)}
    })


@bp.route('/<int:account_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_account(account_id):
    """删除邮箱账户"""
    account = EmailAccount.query.get(account_id)
    if not account:
        return jsonify({'code': 404, 'message': '账户不存在'}), 404
    
    account_name = account.name
    db.session.delete(account)
    db.session.commit()
    
    # 记录操作日志
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_DELETE,
        target_type='email_account',
        target_id=account_id,
        detail=f'删除邮箱账户: {account_name}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '账户删除成功'
    })


@bp.route('/<int:account_id>/test', methods=['POST'])
@admin_required
@demo_forbidden
def test_account(account_id):
    """测试邮箱账户连接"""
    from app.services.email import EmailService
    
    account = EmailAccount.query.get(account_id)
    if not account:
        return jsonify({'code': 404, 'message': '账户不存在'}), 404
    
    success, msg = EmailService.test_account(account)
    
    if success:
        return jsonify({'code': 200, 'message': msg})
    return jsonify({'code': 500, 'message': msg}), 500


@bp.route('/<int:account_id>/send-test', methods=['POST'])
@admin_required
@demo_forbidden
def send_test_email(account_id):
    """通过指定账户发送测试邮件"""
    from app.services.email import EmailService
    
    account = EmailAccount.query.get(account_id)
    if not account:
        return jsonify({'code': 404, 'message': '账户不存在'}), 404
    
    data = request.get_json() or {}
    to_email = data.get('email', '')
    
    # 如果没有指定邮箱，使用当前管理员邮箱
    if not to_email:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user or not user.email:
            return jsonify({'code': 400, 'message': '请指定测试邮箱地址'}), 400
        to_email = user.email
    
    # 验证邮箱格式
    is_valid, msg = EmailService.validate_email_format(to_email)
    if not is_valid:
        return jsonify({'code': 400, 'message': msg}), 400
    
    # 发送测试邮件
    subject = '六趣DNS - 邮箱账户测试'
    html_content = f'''
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #4F46E5;">邮箱账户测试</h2>
        <p>这是一封测试邮件，用于验证邮箱账户 <strong>{account.name}</strong> 配置是否正确。</p>
        <p>账户类型: {account.type.upper()}</p>
        <p>如果您收到这封邮件，说明该账户配置成功！</p>
        <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 20px 0;">
        <p style="color: #6B7280; font-size: 14px;">此邮件由六趣DNS系统自动发送，请勿回复。</p>
    </div>
    '''
    
    success, msg = EmailService.send_via_account(account, to_email, subject, html_content)
    
    if success:
        return jsonify({'code': 200, 'message': f'测试邮件已发送至 {to_email}'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500


@bp.route('/import-legacy', methods=['POST'])
@admin_required
@demo_forbidden
def import_legacy_config():
    """导入旧配置为新账户"""
    from app.services.email import EmailService
    
    # 检查是否有旧配置
    provider = EmailService.get_email_provider()
    
    if provider == 'aliyun':
        config = EmailService.get_aliyun_config()
        if not config['access_key_id'] or not config['access_key_secret'] or not config['account_name']:
            return jsonify({'code': 400, 'message': '没有可导入的阿里云配置'}), 400
        
        account_type = EmailAccount.TYPE_ALIYUN
        account_name = '阿里云邮件推送 (导入)'
    else:
        config = EmailService.get_smtp_config()
        if not config['host'] or not config['user'] or not config['password']:
            return jsonify({'code': 400, 'message': '没有可导入的SMTP配置'}), 400
        
        account_type = EmailAccount.TYPE_SMTP
        account_name = f'SMTP - {config["host"]} (导入)'
    
    # 检查是否已存在同名账户
    existing = EmailAccount.query.filter_by(name=account_name).first()
    if existing:
        return jsonify({'code': 400, 'message': '已存在同名账户，请先删除或重命名'}), 400
    
    # 创建账户
    account = EmailAccount(
        name=account_name,
        type=account_type,
        daily_limit=500,
        priority=10,
        enabled=True
    )
    account.set_config(config)
    
    db.session.add(account)
    db.session.commit()
    
    # 记录操作日志
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_CREATE,
        target_type='email_account',
        target_id=account.id,
        detail=f'导入旧配置为邮箱账户: {account_name}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '配置导入成功',
        'data': {'account': account.to_dict(include_config=True)}
    })


@bp.route('/batch', methods=['POST'])
@admin_required
@demo_forbidden
def batch_create_accounts():
    """批量添加邮箱账户"""
    data = request.get_json()
    
    account_type = data.get('type', '').strip()
    content = data.get('content', '').strip()
    daily_limit = int(data.get('daily_limit', 0))
    enabled = bool(data.get('enabled', True))
    
    if account_type not in [EmailAccount.TYPE_SMTP, EmailAccount.TYPE_ALIYUN]:
        return jsonify({'code': 400, 'message': '不支持的账户类型'}), 400
    
    if not content:
        return jsonify({'code': 400, 'message': '请输入账户信息'}), 400
    
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    if not lines:
        return jsonify({'code': 400, 'message': '请输入账户信息'}), 400
    
    success_count = 0
    failed_count = 0
    errors = []
    
    # 获取当前最大优先级
    max_priority = db.session.query(db.func.max(EmailAccount.priority)).scalar() or 0
    
    for i, line in enumerate(lines, 1):
        try:
            parts = line.split(':')
            
            if account_type == EmailAccount.TYPE_SMTP:
                # SMTP格式: host:port:user:password:from_name
                if len(parts) < 4:
                    errors.append(f'第{i}行格式错误，至少需要4个字段')
                    failed_count += 1
                    continue
                
                host = parts[0].strip()
                port = int(parts[1].strip())
                user = parts[2].strip()
                password = parts[3].strip()
                from_name = parts[4].strip() if len(parts) > 4 else ''
                
                config = {
                    'host': host,
                    'port': port,
                    'user': user,
                    'password': password,
                    'from_name': from_name,
                    'ssl': '1' if port in [465, 587] else '0'
                }
                account_name = f'SMTP - {user}'
                
            else:  # aliyun
                # 阿里云格式: access_key_id:access_key_secret:account:from_name:region
                if len(parts) < 3:
                    errors.append(f'第{i}行格式错误，至少需要3个字段')
                    failed_count += 1
                    continue
                
                access_key_id = parts[0].strip()
                access_key_secret = parts[1].strip()
                account = parts[2].strip()
                from_name = parts[3].strip() if len(parts) > 3 else ''
                region = parts[4].strip() if len(parts) > 4 else 'cn-hangzhou'
                
                config = {
                    'access_key_id': access_key_id,
                    'access_key_secret': access_key_secret,
                    'account': account,
                    'from_name': from_name,
                    'region': region
                }
                account_name = f'阿里云 - {account}'
            
            # 检查是否已存在同名账户
            existing = EmailAccount.query.filter_by(name=account_name).first()
            if existing:
                account_name = f'{account_name} ({i})'
            
            # 创建账户
            max_priority += 1
            email_account = EmailAccount(
                name=account_name,
                type=account_type,
                daily_limit=daily_limit,
                priority=max_priority,
                enabled=enabled
            )
            email_account.set_config(config)
            
            db.session.add(email_account)
            success_count += 1
            
        except Exception as e:
            errors.append(f'第{i}行处理失败: {str(e)}')
            failed_count += 1
    
    if success_count > 0:
        db.session.commit()
        
        # 记录操作日志
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        OperationLog.log(
            user_id=user_id,
            username=user.username if user else None,
            action=OperationLog.ACTION_CREATE,
            target_type='email_account',
            target_id=0,
            detail=f'批量添加邮箱账户: 成功{success_count}个，失败{failed_count}个',
            ip_address=get_real_ip()
        )
    
    return jsonify({
        'code': 200,
        'message': f'批量添加完成，成功{success_count}个，失败{failed_count}个',
        'data': {
            'success': success_count,
            'failed': failed_count,
            'errors': errors
        }
    })
