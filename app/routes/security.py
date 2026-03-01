"""
安全设置路由
双因素认证、IP限制等
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models import User, OperationLog, SmsVerification
from app.services.totp_service import TOTPService
from app.routes.admin.decorators import demo_forbidden
from app.utils.ip_utils import get_real_ip

security_bp = Blueprint('security', __name__)


@security_bp.route('/2fa/setup', methods=['POST'])
@jwt_required()
@demo_forbidden
def setup_2fa():
    """初始化2FA设置，生成密钥和二维码"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if user.is_totp_enabled:
        return jsonify({'code': 400, 'message': '已启用双因素认证'}), 400
    
    # 生成密钥
    secret = TOTPService.generate_secret()
    
    # 生成配置URI
    uri = TOTPService.get_provisioning_uri(secret, user.email)
    
    # 生成二维码
    qr_code = TOTPService.generate_qr_code(uri)
    
    # 暂存密钥（未验证前不启用）
    user.totp_secret = secret
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'data': {
            'secret': secret,
            'uri': uri,
            'qr_code': qr_code
        }
    })


@security_bp.route('/2fa/enable', methods=['POST'])
@jwt_required()
@demo_forbidden
def enable_2fa():
    """验证并启用2FA"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if user.is_totp_enabled:
        return jsonify({'code': 400, 'message': '已启用双因素认证'}), 400
    
    if not user.totp_secret:
        return jsonify({'code': 400, 'message': '请先初始化2FA设置'}), 400
    
    data = request.get_json()
    code = data.get('code', '').strip()
    
    if not code:
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400
    
    # 验证码
    if not TOTPService.verify(user.totp_secret, code):
        return jsonify({'code': 400, 'message': '验证码错误'}), 400
    
    # 生成备用码
    backup_codes = TOTPService.generate_backup_codes()
    
    # 启用2FA
    user.totp_enabled = 1
    user.set_backup_codes(backup_codes)
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='security',
        detail='启用双因素认证',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '双因素认证已启用',
        'data': {
            'backup_codes': backup_codes
        }
    })


@security_bp.route('/2fa/disable', methods=['POST'])
@jwt_required()
@demo_forbidden
def disable_2fa():
    """禁用2FA"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if not user.is_totp_enabled:
        return jsonify({'code': 400, 'message': '未启用双因素认证'}), 400
    
    data = request.get_json()
    password = data.get('password', '')
    code = data.get('code', '').strip()
    
    # 验证密码
    if not user.check_password(password):
        return jsonify({'code': 400, 'message': '密码错误'}), 400
    
    # 验证2FA码
    if not TOTPService.verify(user.totp_secret, code):
        return jsonify({'code': 400, 'message': '验证码错误'}), 400
    
    # 禁用2FA
    user.totp_enabled = 0
    user.totp_secret = None
    user.backup_codes = None
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='security',
        detail='禁用双因素认证',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': '双因素认证已禁用'})


@security_bp.route('/2fa/status', methods=['GET'])
@jwt_required()
def get_2fa_status():
    """获取2FA状态"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    backup_codes_count = len(user.get_backup_codes())
    
    return jsonify({
        'code': 200,
        'data': {
            'enabled': user.is_totp_enabled,
            'backup_codes_remaining': backup_codes_count
        }
    })


@security_bp.route('/2fa/backup-codes', methods=['POST'])
@jwt_required()
@demo_forbidden
def regenerate_backup_codes():
    """重新生成备用码"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if not user.is_totp_enabled:
        return jsonify({'code': 400, 'message': '请先启用双因素认证'}), 400
    
    data = request.get_json()
    code = data.get('code', '').strip()
    
    # 验证2FA码
    if not TOTPService.verify(user.totp_secret, code):
        return jsonify({'code': 400, 'message': '验证码错误'}), 400
    
    # 生成新的备用码
    backup_codes = TOTPService.generate_backup_codes()
    user.set_backup_codes(backup_codes)
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '备用码已重新生成',
        'data': {
            'backup_codes': backup_codes
        }
    })


@security_bp.route('/ip-restriction', methods=['GET'])
@jwt_required()
def get_ip_restriction():
    """获取IP限制设置"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': {
            'allowed_ips': user.get_allowed_ips(),
            'current_ip': get_real_ip()
        }
    })


@security_bp.route('/ip-restriction', methods=['PUT'])
@jwt_required()
@demo_forbidden
def update_ip_restriction():
    """更新IP限制设置"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    data = request.get_json()
    allowed_ips = data.get('allowed_ips', [])
    
    # 验证IP格式
    import ipaddress
    valid_ips = []
    for ip in allowed_ips:
        ip = ip.strip()
        if ip:
            try:
                ipaddress.ip_address(ip)
                valid_ips.append(ip)
            except ValueError:
                return jsonify({'code': 400, 'message': f'无效的IP地址: {ip}'}), 400
    
    user.set_allowed_ips(valid_ips)
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='security',
        detail=f'更新IP限制: {len(valid_ips)}个IP',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': 'IP限制已更新',
        'data': {
            'allowed_ips': valid_ips
        }
    })


@security_bp.route('/sessions', methods=['GET'])
@jwt_required()
def get_login_history():
    """获取登录历史"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    # 获取登录日志
    logs = OperationLog.query.filter_by(
        user_id=user_id,
        action=OperationLog.ACTION_LOGIN
    ).order_by(OperationLog.created_at.desc()).limit(20).all()
    
    return jsonify({
        'code': 200,
        'data': {
            'last_login_at': user.last_login_at.isoformat() if user.last_login_at else None,
            'last_login_ip': user.last_login_ip,
            'history': [log.to_dict() for log in logs]
        }
    })


# ========== API密钥管理 ==========

@security_bp.route('/api-keys', methods=['GET'])
@jwt_required()
def get_api_keys():
    """获取API密钥信息"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': {
            'api_key': user.api_key,
            'api_secret': '******' if user.api_secret else None,  # 不直接返回secret
            'api_enabled': user.api_enabled == 1,
            'api_ip_whitelist': user.get_api_ip_whitelist()
        }
    })


@security_bp.route('/api-keys/generate', methods=['POST'])
@jwt_required()
@demo_forbidden
def generate_api_keys():
    """生成/重置API密钥"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    # 如果已有密钥，需要验证密码
    if user.api_key:
        data = request.get_json() or {}
        password = data.get('password', '')
        if not user.check_password(password):
            return jsonify({'code': 400, 'message': '密码错误'}), 400
    
    # 生成新密钥
    api_key, api_secret = user.generate_api_keys()
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='api_key',
        detail='生成API密钥',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': 'API密钥已生成',
        'data': {
            'api_key': api_key,
            'api_secret': api_secret  # 只在生成时返回一次
        }
    })


@security_bp.route('/api-keys/toggle', methods=['POST'])
@jwt_required()
@demo_forbidden
def toggle_api():
    """启用/禁用API"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if not user.api_key:
        return jsonify({'code': 400, 'message': '请先生成API密钥'}), 400
    
    data = request.get_json() or {}
    enabled = data.get('enabled', not user.api_enabled)
    
    user.api_enabled = 1 if enabled else 0
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='api_key',
        detail=f'{"启用" if enabled else "禁用"}API',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': f'API已{"启用" if enabled else "禁用"}',
        'data': {
            'api_enabled': user.api_enabled == 1
        }
    })


@security_bp.route('/api-keys/whitelist', methods=['PUT'])
@jwt_required()
@demo_forbidden
def update_api_whitelist():
    """更新API IP白名单"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    data = request.get_json()
    ip_list = data.get('ip_whitelist', [])
    
    # 验证IP格式
    import ipaddress
    valid_ips = []
    for ip in ip_list:
        ip = ip.strip()
        if ip:
            try:
                ipaddress.ip_address(ip)
                valid_ips.append(ip)
            except ValueError:
                return jsonify({'code': 400, 'message': f'无效的IP地址: {ip}'}), 400
    
    user.set_api_ip_whitelist(valid_ips)
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='api_key',
        detail=f'更新API IP白名单: {len(valid_ips)}个IP',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': 'IP白名单已更新',
        'data': {
            'api_ip_whitelist': valid_ips
        }
    })


@security_bp.route('/api-keys/secret', methods=['POST'])
@jwt_required()
@demo_forbidden
def view_api_secret():
    """查看API Secret（需要密码验证）"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if not user.api_secret:
        return jsonify({'code': 400, 'message': '请先生成API密钥'}), 400
    
    data = request.get_json() or {}
    password = data.get('password', '')
    
    if not user.check_password(password):
        return jsonify({'code': 400, 'message': '密码错误'}), 400
    
    return jsonify({
        'code': 200,
        'data': {
            'api_secret': user.api_secret
        }
    })


# ========== 手机号绑定 ==========

@security_bp.route('/phone/bindable', methods=['GET'])
@jwt_required()
def get_phone_bindable():
    """获取手机绑定状态"""
    from app.services.sms import SmsService
    
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': {
            'sms_enabled': SmsService.is_enabled(),
            'phone': user.phone,
            'phone_bound': bool(user.phone),
            'phone_masked': mask_phone(user.phone) if user.phone else None
        }
    })


@security_bp.route('/phone/send-code', methods=['POST'])
@jwt_required()
@demo_forbidden
def send_phone_bind_code():
    """发送绑定/换绑手机验证码"""
    from app.services.sms import SmsService
    from app.models import SmsVerification
    
    if not SmsService.is_enabled():
        return jsonify({'code': 500, 'message': '短信服务未启用'}), 500
    
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    data = request.get_json()
    phone = data.get('phone', '').strip()
    action = data.get('action', 'bind')  # bind: 绑定新手机, verify: 验证当前手机
    
    # 验证手机号格式
    import re
    if not phone or not re.match(r'^1[3-9]\d{9}$', phone):
        return jsonify({'code': 400, 'message': '请输入正确的手机号'}), 400
    
    if action == 'bind':
        # 绑定新手机号，检查是否已被使用
        existing = User.query.filter_by(phone=phone).first()
        if existing and existing.id != user.id:
            return jsonify({'code': 400, 'message': '该手机号已被其他账户绑定'}), 400
        scene = 'bind'
        template_type = SmsService.TEMPLATE_BIND_PHONE
    elif action == 'verify':
        # 验证当前手机号（换绑前验证）
        if user.phone != phone:
            return jsonify({'code': 400, 'message': '请输入当前绑定的手机号'}), 400
        scene = 'verify'
        template_type = SmsService.TEMPLATE_VERIFY_PHONE
    else:
        return jsonify({'code': 400, 'message': '无效的操作类型'}), 400
    
    # 检查发送频率
    can_send, wait = SmsVerification.can_send(phone, scene)
    if not can_send:
        return jsonify({'code': 429, 'message': f'请{wait}秒后再试'}), 429
    
    # 生成并发送验证码
    code = SmsService.generate_code()
    success, msg = SmsService.send_code(phone, code, template_type)
    
    if not success:
        return jsonify({'code': 500, 'message': msg}), 500
    
    # 保存验证码
    expire_minutes = SmsService.get_code_expire_minutes()
    SmsVerification.create(phone, code, scene, user_id=user.id, expire_minutes=expire_minutes)
    
    return jsonify({'code': 200, 'message': '验证码已发送'})


@security_bp.route('/phone/bind', methods=['POST'])
@jwt_required()
@demo_forbidden
def bind_phone():
    """绑定手机号"""
    from app.models import SmsVerification
    
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    data = request.get_json()
    phone = data.get('phone', '').strip()
    code = data.get('code', '').strip()
    
    # 验证手机号格式
    import re
    if not phone or not re.match(r'^1[3-9]\d{9}$', phone):
        return jsonify({'code': 400, 'message': '请输入正确的手机号'}), 400
    
    if not code:
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400
    
    # 检查手机号是否已被使用
    existing = User.query.filter_by(phone=phone).first()
    if existing and existing.id != user.id:
        return jsonify({'code': 400, 'message': '该手机号已被其他账户绑定'}), 400
    
    # 验证验证码
    valid, result = SmsVerification.verify(phone, code, 'bind')
    if not valid:
        return jsonify({'code': 400, 'message': result}), 400
    
    # 绑定手机号
    user.phone = phone
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='security',
        detail=f'绑定手机号: {mask_phone(phone)}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '手机号绑定成功',
        'data': {
            'phone': phone,
            'phone_masked': mask_phone(phone)
        }
    })


@security_bp.route('/phone/unbind', methods=['POST'])
@jwt_required()
@demo_forbidden
def unbind_phone():
    """解绑手机号"""
    from app.models import SmsVerification
    
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if not user.phone:
        return jsonify({'code': 400, 'message': '未绑定手机号'}), 400
    
    data = request.get_json()
    code = data.get('code', '').strip()
    
    if not code:
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400
    
    # 检查是否有其他登录方式
    if not user.password_hash and not user.github_id and not user.google_id and not user.nodeloc_id:
        return jsonify({'code': 400, 'message': '至少保留一种登录方式'}), 400
    
    # 验证验证码
    valid, result = SmsVerification.verify(user.phone, code, 'verify')
    if not valid:
        return jsonify({'code': 400, 'message': result}), 400
    
    old_phone = user.phone
    user.phone = None
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='security',
        detail=f'解绑手机号: {mask_phone(old_phone)}',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': '手机号解绑成功'})


@security_bp.route('/phone/change', methods=['POST'])
@jwt_required()
@demo_forbidden
def change_phone():
    """换绑手机号（需要先验证旧手机）"""
    from app.models import SmsVerification
    
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    if not user.phone:
        return jsonify({'code': 400, 'message': '请先绑定手机号'}), 400
    
    data = request.get_json()
    old_code = data.get('old_code', '').strip()
    new_phone = data.get('new_phone', '').strip()
    new_code = data.get('new_code', '').strip()
    
    # 验证新手机号格式
    import re
    if not new_phone or not re.match(r'^1[3-9]\d{9}$', new_phone):
        return jsonify({'code': 400, 'message': '请输入正确的新手机号'}), 400
    
    if not old_code or not new_code:
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400
    
    # 检查新手机号是否已被使用
    existing = User.query.filter_by(phone=new_phone).first()
    if existing and existing.id != user.id:
        return jsonify({'code': 400, 'message': '该手机号已被其他账户绑定'}), 400
    
    # 验证旧手机验证码
    valid, result = SmsVerification.verify(user.phone, old_code, 'verify')
    if not valid:
        return jsonify({'code': 400, 'message': f'原手机验证失败: {result}'}), 400
    
    # 验证新手机验证码
    valid, result = SmsVerification.verify(new_phone, new_code, 'bind')
    if not valid:
        return jsonify({'code': 400, 'message': f'新手机验证失败: {result}'}), 400
    
    old_phone = user.phone
    user.phone = new_phone
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='security',
        detail=f'换绑手机号: {mask_phone(old_phone)} -> {mask_phone(new_phone)}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '手机号换绑成功',
        'data': {
            'phone': new_phone,
            'phone_masked': mask_phone(new_phone)
        }
    })


def mask_phone(phone):
    """手机号脱敏"""
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + '****' + phone[-4:]


# ========== Telegram 绑定 ==========

@security_bp.route('/telegram/status', methods=['GET'])
@jwt_required()
def get_telegram_status():
    """获取 Telegram 绑定状态"""
    user_id = int(get_jwt_identity())
    
    from app.models.telegram import TelegramUser, TelegramBot
    
    # 检查是否有启用的机器人
    bot = TelegramBot.get_enabled_bot()
    
    # 获取绑定信息
    tg_user = TelegramUser.get_by_user_id(user_id)
    
    return jsonify({
        'code': 200,
        'data': {
            'enabled': bot is not None,
            'bot_username': bot.username if bot else None,
            'bound': tg_user is not None and tg_user.user_id is not None,
            'telegram_username': tg_user.telegram_username if tg_user else None,
            'telegram_first_name': tg_user.telegram_first_name if tg_user else None
        }
    })


@security_bp.route('/telegram/bind-code', methods=['POST'])
@jwt_required()
@demo_forbidden
def generate_telegram_bind_code():
    """生成 Telegram 绑定码"""
    user_id = int(get_jwt_identity())
    
    from app.models.telegram import TelegramUser, TelegramBot, TelegramBindCode
    
    # 检查是否有启用的机器人
    bot = TelegramBot.get_enabled_bot()
    if not bot:
        return jsonify({'code': 400, 'message': 'Telegram 机器人未启用'}), 400
    
    # 检查是否已绑定
    tg_user = TelegramUser.get_by_user_id(user_id)
    if tg_user and tg_user.user_id:
        return jsonify({'code': 400, 'message': '您已绑定 Telegram 账号'}), 400
    
    # 生成绑定码（5分钟有效）
    bind_code = TelegramBindCode.generate_code(user_id, expires_minutes=5)
    
    return jsonify({
        'code': 200,
        'message': '绑定码已生成',
        'data': {
            'code': bind_code.code,
            'expires_in': 300,  # 5分钟
            'bot_username': bot.username
        }
    })


@security_bp.route('/telegram/unbind', methods=['POST'])
@jwt_required()
@demo_forbidden
def unbind_telegram():
    """解绑 Telegram"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    from app.models.telegram import TelegramUser
    
    tg_user = TelegramUser.get_by_user_id(user_id)
    if not tg_user or not tg_user.user_id:
        return jsonify({'code': 400, 'message': '您尚未绑定 Telegram 账号'}), 400
    
    tg_user.user_id = None
    db.session.commit()
    
    # 记录日志
    OperationLog.log(
        user_id=user_id,
        username=user.username,
        action=OperationLog.ACTION_UPDATE,
        target_type='security',
        detail='解绑 Telegram 账号',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '解绑成功'
    })
