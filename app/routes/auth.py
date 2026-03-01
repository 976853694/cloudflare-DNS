from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from app.models import User, Setting, EmailVerification
from app.services.email import EmailService
from app.services.captcha import CaptchaService
from app.services.slider_captcha import SliderCaptchaService
from app.services.turnstile import TurnstileService
from app.utils.validators import validate_email, validate_username, validate_password
from app.utils.ip_utils import get_real_ip
from app.routes.admin.decorators import demo_forbidden

auth_bp = Blueprint('auth', __name__)


def is_captcha_required(scene: str) -> bool:
    """
    检查指定场景是否需要验证码
    :param scene: 场景名称 (login, register, forgot_password, change_password, change_email)
    :return: 是否需要验证码
    """
    setting_key = f'captcha_{scene}'
    # 默认开启验证码
    return Setting.get(setting_key, '1') == '1'


def validate_email_suffix(email: str) -> tuple[bool, str]:
    """
    验证邮箱后缀是否允许
    :param email: 邮箱地址
    :return: (是否允许, 错误信息)
    """
    # 检查是否启用邮箱后缀限制
    if Setting.get('email_suffix_enabled', '0') != '1':
        return True, ''
    
    # 获取邮箱后缀
    if '@' not in email:
        return False, '邮箱格式不正确'
    
    email_suffix = email.split('@')[1].lower()
    
    # 获取后缀列表
    suffix_list_str = Setting.get('email_suffix_list', '')
    if not suffix_list_str.strip():
        return True, ''  # 列表为空则不限制
    
    suffix_list = [s.strip().lower() for s in suffix_list_str.split('\n') if s.strip()]
    if not suffix_list:
        return True, ''
    
    # 获取模式
    mode = Setting.get('email_suffix_mode', 'whitelist')
    
    if mode == 'whitelist':
        # 白名单模式：只允许列表中的后缀
        if email_suffix in suffix_list:
            return True, ''
        return False, f'不支持该邮箱后缀，请使用以下邮箱：{", ".join(suffix_list[:5])}{"..." if len(suffix_list) > 5 else ""}'
    else:
        # 黑名单模式：禁止列表中的后缀
        if email_suffix in suffix_list:
            return False, '该邮箱后缀已被禁止使用'
        return True, ''


def is_app_client() -> bool:
    """
    检查是否为 APP 客户端请求
    APP 客户端需要在请求头中添加 X-Client-Type: app
    """
    return request.headers.get('X-Client-Type', '').lower() == 'app'


def verify_captcha(data: dict, scene: str = None) -> tuple[bool, str]:
    """
    统一验证码验证逻辑
    根据后台设置的 captcha_type 决定使用哪种验证码
    APP 客户端（X-Client-Type: app）强制使用图形验证码
    
    :param data: 请求数据
    :param scene: 场景名称，用于检查是否需要验证码
    Returns:
        (success, error_message)
    """
    # 如果指定了场景，检查是否需要验证码
    if scene and not is_captcha_required(scene):
        return True, ''
    
    # APP 客户端强制使用图形验证码（无法使用 Turnstile 和滑块）
    if is_app_client():
        captcha_id = data.get('captcha_id', '')
        captcha_code = data.get('captcha_code', '')
        if not captcha_id or not captcha_code:
            return False, '请输入验证码'
        if not CaptchaService.verify(captcha_id, captcha_code):
            return False, '验证码错误'
        return True, ''
    
    # 获取后台配置的验证码类型
    captcha_type = Setting.get('captcha_type', 'slider')
    
    # 根据配置的类型验证
    if captcha_type == 'turnstile' and TurnstileService.is_enabled():
        turnstile_token = data.get('turnstile_token', '')
        if not turnstile_token:
            return False, '请完成人机验证'
        remote_ip = get_real_ip()
        success, msg = TurnstileService.verify(turnstile_token, remote_ip)
        return success, msg
    
    if captcha_type == 'slider':
        slider_token = data.get('slider_token', '')
        if slider_token:
            return True, ''
        return False, '请完成滑块验证'
    
    # 图形验证码
    captcha_id = data.get('captcha_id', '')
    captcha_code = data.get('captcha_code', '')
    if not captcha_id or not captcha_code:
        return False, '请输入验证码'
    if not CaptchaService.verify(captcha_id, captcha_code):
        return False, '验证码错误'
    return True, ''


@auth_bp.route('/captcha', methods=['GET'])
def get_captcha():
    """获取图形验证码"""
    captcha_id = request.args.get('id', '')
    data = CaptchaService.generate(captcha_id if captcha_id else None)
    return jsonify({'code': 200, 'data': data})


@auth_bp.route('/slider-captcha', methods=['GET'])
def get_slider_captcha():
    """获取滑块验证码"""
    data = SliderCaptchaService.generate()
    return jsonify({'code': 200, 'data': data})


@auth_bp.route('/slider-captcha/verify', methods=['POST'])
def verify_slider_captcha():
    """验证滑块验证码"""
    data = request.get_json()
    token = data.get('token', '')
    position = data.get('position', 0)
    trajectory = data.get('trajectory', [])
    
    try:
        position = int(position)
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '位置参数无效'}), 400
    
    success, message = SliderCaptchaService.verify(token, position, trajectory)
    
    if success:
        return jsonify({'code': 200, 'data': {'success': True}, 'message': message})
    return jsonify({'code': 400, 'message': message}), 400


@auth_bp.route('/captcha-config', methods=['GET'])
def get_captcha_config():
    """
    获取验证码配置（前端根据此决定显示哪种验证码）
    APP 客户端（X-Client-Type: app）强制返回图形验证码类型
    根据后台设置的 captcha_type 返回对应类型
    """
    turnstile_config = TurnstileService.get_config()
    
    # 获取各场景的验证码开关
    scenes = {
        'login': Setting.get('captcha_login', '1') == '1',
        'register': Setting.get('captcha_register', '1') == '1',
        'forgot_password': Setting.get('captcha_forgot_password', '1') == '1',
        'change_password': Setting.get('captcha_change_password', '1') == '1',
        'change_email': Setting.get('captcha_change_email', '1') == '1',
    }
    
    # APP 客户端强制使用图形验证码
    if is_app_client():
        return jsonify({
            'code': 200,
            'data': {
                'type': 'image',
                'turnstile_site_key': '',
                'scenes': scenes
            }
        })
    
    # 获取后台配置的验证码类型，默认为滑块验证码
    captcha_type = Setting.get('captcha_type', 'slider')
    
    # 如果选择了 Turnstile 但未配置密钥，回退到滑块验证码
    if captcha_type == 'turnstile' and not turnstile_config['enabled']:
        captcha_type = 'slider'
    
    return jsonify({
        'code': 200,
        'data': {
            'type': captcha_type,
            'turnstile_site_key': turnstile_config.get('site_key', '') if captcha_type == 'turnstile' else '',
            'scenes': scenes
        }
    })


def get_site_url():
    """获取站点URL"""
    return Setting.get('site_url', request.host_url.rstrip('/'))


@auth_bp.route('/register/send', methods=['POST'])
def register_send():
    """发送注册验证邮件"""
    # 检查是否开放注册
    if Setting.get('allow_register', '1') != '1':
        return jsonify({'code': 403, 'message': '系统暂未开放注册'}), 403
    
    # 检查是否允许邮箱注册
    if Setting.get('allow_email_register', '1') != '1':
        return jsonify({'code': 403, 'message': '系统仅支持快捷登录注册，请使用 GitHub/Google/NodeLoc 登录'}), 403
    
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    invite_code = data.get('invite_code', '').strip().upper()  # 获取邀请码
    
    # 统一验证码验证
    captcha_ok, captcha_msg = verify_captcha(data, 'register')
    if not captcha_ok:
        return jsonify({'code': 400, 'message': captcha_msg}), 400
    
    if not validate_email(email):
        return jsonify({'code': 400, 'message': '邮箱格式不正确'}), 400
    
    # 验证邮箱后缀
    suffix_ok, suffix_msg = validate_email_suffix(email)
    if not suffix_ok:
        return jsonify({'code': 400, 'message': suffix_msg}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'code': 409, 'message': '邮箱已被注册'}), 409
    
    # 验证邀请码（如果提供）
    if invite_code:
        inviter = User.query.filter_by(invite_code=invite_code).first()
        if not inviter:
            return jsonify({'code': 400, 'message': '邀请码无效'}), 400
    
    if not EmailService.is_configured():
        return jsonify({'code': 500, 'message': '邮件服务未配置'}), 500
    
    can_send, wait = EmailVerification.can_send(email, 'register')
    if not can_send:
        return jsonify({'code': 429, 'message': f'请{wait}秒后再试'}), 429
    
    # 创建验证记录，保存邀请码
    verification = EmailVerification.create(email, 'register', invite_code=invite_code if invite_code else None)
    success, msg = EmailService.send_verification(email, verification.token, 'register', get_site_url(), invite_code=invite_code if invite_code else None)
    
    if success:
        return jsonify({'code': 200, 'message': '验证邮件已发送，请查收'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500


@auth_bp.route('/register/complete', methods=['POST'])
def register_complete():
    """完成注册（验证邮箱后设置用户名和密码）"""
    # 检查是否开放注册
    if Setting.get('allow_register', '1') != '1':
        return jsonify({'code': 403, 'message': '系统暂未开放注册'}), 403
    
    # 检查是否允许邮箱注册
    if Setting.get('allow_email_register', '1') != '1':
        return jsonify({'code': 403, 'message': '系统仅支持快捷登录注册，请使用 GitHub/Google/NodeLoc 登录'}), 403
    
    data = request.get_json()
    token = data.get('token', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    invite_code = data.get('invite_code', '').strip().upper()
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    verification = EmailVerification.get_by_token(token)
    if not verification or verification.type != 'register':
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    if not verification.is_valid:
        return jsonify({'code': 400, 'message': '验证链接已过期或已使用'}), 400
    
    if not validate_username(username):
        return jsonify({'code': 400, 'message': '用户名需为3-20个字符，只能包含字母、数字和下划线'}), 400
    
    if not validate_password(password):
        return jsonify({'code': 400, 'message': '密码需为6-32个字符'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 409, 'message': '用户名已被占用'}), 409
    
    if User.query.filter_by(email=verification.email).first():
        return jsonify({'code': 409, 'message': '邮箱已被注册'}), 409
    
    # 验证邀请码（如果提供）
    inviter = None
    if invite_code:
        inviter = User.query.filter_by(invite_code=invite_code).first()
        if not inviter:
            return jsonify({'code': 400, 'message': '邀请码无效'}), 400
    
    # 获取后台设置的默认域名配额
    default_max_domains = int(Setting.get('default_max_domains', '5'))
    
    user = User(username=username, email=verification.email, max_domains=default_max_domains)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # 获取用户ID
    
    # 处理邀请奖励
    if inviter:
        from app.services.points_service import PointsService
        PointsService.process_invite_register(inviter.id, user.id, invite_code)
    
    verification.mark_used()
    
    access_token = create_access_token(identity=str(user.id))
    return jsonify({
        'code': 201,
        'message': '注册成功',
        'data': {'access_token': access_token, 'user': user.to_dict()}
    }), 201


@auth_bp.route('/register', methods=['POST'])
def register():
    """传统注册（兼容旧版，SMTP未配置时使用）"""
    # 检查是否开放注册
    if Setting.get('allow_register', '1') != '1':
        return jsonify({'code': 403, 'message': '系统暂未开放注册'}), 403
    
    # 检查是否允许邮箱注册
    if Setting.get('allow_email_register', '1') != '1':
        return jsonify({'code': 403, 'message': '系统仅支持快捷登录注册，请使用 GitHub/Google/NodeLoc 登录'}), 403
    
    data = request.get_json()
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    invite_code = data.get('invite_code', '').strip().upper()
    
    errors = []
    if not validate_username(username):
        errors.append('用户名需为3-20个字符，只能包含字母、数字和下划线')
    if not validate_email(email):
        errors.append('邮箱格式不正确')
    if not validate_password(password):
        errors.append('密码需为6-32个字符')
    
    if errors:
        return jsonify({'code': 400, 'message': '参数错误', 'errors': errors}), 400
    
    # 验证邮箱后缀
    suffix_ok, suffix_msg = validate_email_suffix(email)
    if not suffix_ok:
        return jsonify({'code': 400, 'message': suffix_msg}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 409, 'message': '用户名已被占用'}), 409
    
    if User.query.filter_by(email=email).first():
        return jsonify({'code': 409, 'message': '邮箱已被注册'}), 409
    
    # 验证邀请码（如果提供）
    inviter = None
    if invite_code:
        inviter = User.query.filter_by(invite_code=invite_code).first()
        if not inviter:
            return jsonify({'code': 400, 'message': '邀请码无效'}), 400
    
    # 获取后台设置的默认域名配额
    default_max_domains = int(Setting.get('default_max_domains', '5'))
    
    user = User(username=username, email=email, max_domains=default_max_domains)
    user.set_password(password)
    
    db.session.add(user)
    db.session.flush()  # 获取用户ID
    
    # 处理邀请奖励
    if inviter:
        from app.services.points_service import PointsService
        PointsService.process_invite_register(inviter.id, user.id, invite_code)
    
    db.session.commit()
    
    return jsonify({
        'code': 201,
        'message': '注册成功',
        'data': {'user': user.to_dict()}
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    totp_code = data.get('totp_code', '')  # 2FA验证码
    
    if not email or not password:
        return jsonify({'code': 400, 'message': '请输入邮箱和密码', 'need_captcha': True}), 400
    
    # 统一验证码验证
    captcha_ok, captcha_msg = verify_captcha(data, 'login')
    if not captcha_ok:
        return jsonify({'code': 400, 'message': captcha_msg, 'need_captcha': True}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.check_password(password):
        return jsonify({'code': 401, 'message': '邮箱或密码错误', 'need_captcha': True}), 401
    
    # 检查封禁状态
    if user.is_banned:
        return jsonify({'code': 403, 'message': '账户已被禁用'}), 403
    
    # 检查沉睡状态
    if user.is_sleeping:
        # 邮箱脱敏显示
        email_parts = user.email.split('@')
        if len(email_parts) == 2:
            local = email_parts[0]
            domain = email_parts[1]
            if len(local) > 3:
                masked_email = local[:3] + '***@' + domain
            else:
                masked_email = local[0] + '***@' + domain
        else:
            masked_email = user.email[:3] + '***'
        
        return jsonify({
            'code': 403,
            'message': '账户处于沉睡状态，请验证邮箱后登录',
            'data': {
                'need_reactivate': True,
                'email': masked_email
            }
        }), 403
    
    # 检查是否启用了2FA
    if user.totp_enabled and user.totp_secret:
        if not totp_code:
            # 需要2FA验证码
            return jsonify({
                'code': 200,
                'message': '请输入双因素认证验证码',
                'data': {'require_2fa': True, 'email': email}
            })
        
        # 验证2FA
        from app.services.totp_service import TOTPService
        if not TOTPService.verify(user.totp_secret, totp_code):
            # 检查是否是备用码
            if not user.use_backup_code(totp_code):
                return jsonify({'code': 401, 'message': '双因素认证验证码错误'}), 401
    
    # 更新最后登录信息
    from app.utils.timezone import now as beijing_now
    user.last_login_at = beijing_now()
    user.last_login_ip = get_real_ip()
    db.session.commit()
    
    # 记录登录活动
    from app.services.activity_tracker import ActivityTracker
    ActivityTracker.log(user.id, 'login', {'ip': get_real_ip()})
    
    # 记录登录日志到OperationLog
    from app.models import OperationLog
    OperationLog.log(
        user_id=user.id,
        action=OperationLog.ACTION_LOGIN,
        target_type='user',
        target_id=user.id,
        detail=f'用户 {user.username} 登录成功',
        ip_address=get_real_ip()
    )
    
    access_token = create_access_token(identity=str(user.id))
    
    return jsonify({
        'code': 200,
        'message': '登录成功',
        'data': {
            'access_token': access_token,
            'token_type': 'Bearer',
            'user': user.to_dict()
        }
    })


@auth_bp.route('/login/captcha-status', methods=['GET'])
def login_captcha_status():
    """检查登录是否需要验证码（始终需要）"""
    return jsonify({'code': 200, 'data': {'need_captcha': True}})


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': user.to_dict(include_stats=True, include_host=True)
    })


@auth_bp.route('/password', methods=['PUT'])
@jwt_required()
@demo_forbidden
def change_password():
    """传统修改密码（验证旧密码）"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not user.check_password(old_password):
        return jsonify({'code': 400, 'message': '原密码错误'}), 400
    
    if not validate_password(new_password):
        return jsonify({'code': 400, 'message': '新密码需为6-32个字符'}), 400
    
    user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '密码修改成功'})


@auth_bp.route('/change-password/send', methods=['POST'])
@jwt_required()
@demo_forbidden
def change_password_send():
    """发送修改密码验证邮件"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    data = request.get_json() or {}
    
    # 统一验证码验证
    captcha_ok, captcha_msg = verify_captcha(data, 'change_password')
    if not captcha_ok:
        return jsonify({'code': 400, 'message': captcha_msg}), 400
    
    if not EmailService.is_configured():
        return jsonify({'code': 500, 'message': '邮件服务未配置'}), 500
    
    can_send, wait = EmailVerification.can_send(user.email, 'change_password')
    if not can_send:
        return jsonify({'code': 429, 'message': f'请{wait}秒后再试'}), 429
    
    verification = EmailVerification.create(user.email, 'change_password', user_id=user.id)
    success, msg = EmailService.send_verification(user.email, verification.token, 'change_password', get_site_url())
    
    if success:
        return jsonify({'code': 200, 'message': '验证邮件已发送至您的邮箱'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500


@auth_bp.route('/change-password/confirm', methods=['POST'])
def change_password_confirm():
    """通过邮件验证修改密码"""
    data = request.get_json()
    token = data.get('token', '').strip()
    password = data.get('password', '')
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    verification = EmailVerification.get_by_token(token)
    if not verification or verification.type != 'change_password':
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    if not verification.is_valid:
        return jsonify({'code': 400, 'message': '验证链接已过期或已使用'}), 400
    
    if not verification.user_id:
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    if not validate_password(password):
        return jsonify({'code': 400, 'message': '密码需为6-32个字符'}), 400
    
    user = User.query.get(verification.user_id)
    if not user:
        return jsonify({'code': 400, 'message': '用户不存在'}), 400
    
    user.set_password(password)
    verification.mark_used()
    
    return jsonify({'code': 200, 'message': '密码修改成功'})


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """发送重置密码邮件"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    # 统一验证码验证
    captcha_ok, captcha_msg = verify_captcha(data, 'forgot_password')
    if not captcha_ok:
        return jsonify({'code': 400, 'message': captcha_msg}), 400
    
    if not validate_email(email):
        return jsonify({'code': 400, 'message': '邮箱格式不正确'}), 400
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'code': 200, 'message': '如果邮箱已注册，验证邮件将发送至该邮箱'})
    
    if not EmailService.is_configured():
        return jsonify({'code': 500, 'message': '邮件服务未配置'}), 500
    
    can_send, wait = EmailVerification.can_send(email, 'reset_password')
    if not can_send:
        return jsonify({'code': 429, 'message': f'请{wait}秒后再试'}), 429
    
    verification = EmailVerification.create(email, 'reset_password', user_id=user.id)
    EmailService.send_verification(email, verification.token, 'reset_password', get_site_url())
    
    return jsonify({'code': 200, 'message': '如果邮箱已注册，验证邮件将发送至该邮箱'})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """重置密码"""
    data = request.get_json()
    token = data.get('token', '').strip()
    password = data.get('password', '')
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的重置链接'}), 400
    
    verification = EmailVerification.get_by_token(token)
    if not verification or verification.type != 'reset_password':
        return jsonify({'code': 400, 'message': '无效的重置链接'}), 400
    
    if not verification.is_valid:
        return jsonify({'code': 400, 'message': '重置链接已过期或已使用'}), 400
    
    if not validate_password(password):
        return jsonify({'code': 400, 'message': '密码需为6-32个字符'}), 400
    
    user = User.query.filter_by(email=verification.email).first()
    if not user:
        return jsonify({'code': 400, 'message': '用户不存在'}), 400
    
    user.set_password(password)
    verification.mark_used()
    
    return jsonify({'code': 200, 'message': '密码重置成功，请使用新密码登录'})


# ========== 账号激活（沉睡用户） ==========

@auth_bp.route('/reactivate/send', methods=['POST'])
def reactivate_send():
    """发送账号激活邮件（沉睡用户）"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    # 统一验证码验证
    captcha_ok, captcha_msg = verify_captcha(data, 'login')
    if not captcha_ok:
        return jsonify({'code': 400, 'message': captcha_msg}), 400
    
    if not validate_email(email):
        return jsonify({'code': 400, 'message': '邮箱格式不正确'}), 400
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'code': 200, 'message': '如果邮箱已注册，激活邮件将发送至该邮箱'})
    
    # 只有沉睡状态的用户才能激活
    if not user.is_sleeping:
        return jsonify({'code': 400, 'message': '账户状态正常，无需激活'}), 400
    
    if not EmailService.is_configured():
        return jsonify({'code': 500, 'message': '邮件服务未配置'}), 500
    
    can_send, wait = EmailVerification.can_send(email, 'reactivate')
    if not can_send:
        return jsonify({'code': 429, 'message': f'请{wait}秒后再试'}), 429
    
    verification = EmailVerification.create(email, 'reactivate', user_id=user.id)
    success, msg = EmailService.send_verification(email, verification.token, 'reactivate', get_site_url())
    
    if success:
        return jsonify({'code': 200, 'message': '激活邮件已发送，请查收'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500


@auth_bp.route('/reactivate/confirm', methods=['POST'])
def reactivate_confirm():
    """确认激活账号"""
    data = request.get_json()
    token = data.get('token', '').strip()
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的激活链接'}), 400
    
    verification = EmailVerification.get_by_token(token)
    if not verification or verification.type != 'reactivate':
        return jsonify({'code': 400, 'message': '无效的激活链接'}), 400
    
    if not verification.is_valid:
        return jsonify({'code': 400, 'message': '激活链接已过期或已使用'}), 400
    
    user = User.query.filter_by(email=verification.email).first()
    if not user:
        return jsonify({'code': 400, 'message': '用户不存在'}), 400
    
    # 将用户状态从沉睡改为正常
    user.status = User.STATUS_ACTIVE
    verification.mark_used()
    
    return jsonify({'code': 200, 'message': '账号激活成功，请重新登录'})


@auth_bp.route('/reactivate/check', methods=['GET'])
def reactivate_check():
    """检查激活链接是否有效"""
    token = request.args.get('token', '').strip()
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的激活链接'}), 400
    
    verification = EmailVerification.get_by_token(token)
    if not verification or verification.type != 'reactivate':
        return jsonify({'code': 400, 'message': '无效的激活链接'}), 400
    
    if not verification.is_valid:
        return jsonify({'code': 400, 'message': '激活链接已过期或已使用'}), 400
    
    return jsonify({'code': 200, 'message': '激活链接有效', 'data': {'email': verification.email}})


@auth_bp.route('/change-email/send', methods=['POST'])
@jwt_required()
@demo_forbidden
def change_email_send():
    """发送修改邮箱验证邮件到原邮箱"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    data = request.get_json() or {}
    
    # 统一验证码验证
    captcha_ok, captcha_msg = verify_captcha(data, 'change_email')
    if not captcha_ok:
        return jsonify({'code': 400, 'message': captcha_msg}), 400
    
    if not EmailService.is_configured():
        return jsonify({'code': 500, 'message': '邮件服务未配置'}), 500
    
    # 发送验证到原邮箱
    can_send, wait = EmailVerification.can_send(user.email, 'change_email_verify')
    if not can_send:
        return jsonify({'code': 429, 'message': f'请{wait}秒后再试'}), 429
    
    verification = EmailVerification.create(user.email, 'change_email_verify', user_id=user.id)
    success, msg = EmailService.send_verification(user.email, verification.token, 'change_email_verify', get_site_url())
    
    if success:
        return jsonify({'code': 200, 'message': '验证邮件已发送至原邮箱，请查收'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500


@auth_bp.route('/change-email/verify', methods=['POST'])
def change_email_verify():
    """验证原邮箱后设置新邮箱"""
    data = request.get_json()
    token = data.get('token', '').strip()
    new_email = data.get('new_email', '').strip().lower()
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    if not validate_email(new_email):
        return jsonify({'code': 400, 'message': '邮箱格式不正确'}), 400
    
    verification = EmailVerification.get_by_token(token)
    if not verification or verification.type != 'change_email_verify':
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    if not verification.is_valid:
        return jsonify({'code': 400, 'message': '验证链接已过期或已使用'}), 400
    
    if not verification.user_id:
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    user = User.query.get(verification.user_id)
    if not user:
        return jsonify({'code': 400, 'message': '用户不存在'}), 400
    
    if User.query.filter_by(email=new_email).first():
        return jsonify({'code': 409, 'message': '该邮箱已被使用'}), 409
    
    # 直接修改邮箱
    user.email = new_email
    verification.mark_used()
    
    return jsonify({'code': 200, 'message': '邮箱修改成功'})


@auth_bp.route('/change-email/check', methods=['GET'])
def change_email_check():
    """检查修改邮箱验证链接是否有效"""
    token = request.args.get('token', '').strip()
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    verification = EmailVerification.get_by_token(token)
    if not verification or verification.type != 'change_email_verify':
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    if not verification.is_valid:
        return jsonify({'code': 400, 'message': '验证链接已过期或已使用'}), 400
    
    return jsonify({'code': 200, 'message': '验证链接有效', 'data': {'email': verification.email}})


@auth_bp.route('/verify', methods=['GET'])
def verify_token():
    """验证token有效性"""
    token = request.args.get('token', '').strip()
    v_type = request.args.get('type', '').strip()
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    verification = EmailVerification.get_by_token(token)
    if not verification:
        return jsonify({'code': 400, 'message': '无效的验证链接'}), 400
    
    if v_type and verification.type != v_type:
        return jsonify({'code': 400, 'message': '验证类型不匹配'}), 400
    
    if not verification.is_valid:
        return jsonify({'code': 400, 'message': '验证链接已过期或已使用'}), 400
    
    # 准备返回数据
    response_data = {
        'email': verification.email,
        'type': verification.type
    }
    
    # 如果有邀请码，返回邀请码和邀请人信息
    if verification.invite_code:
        response_data['invite_code'] = verification.invite_code
        inviter = User.query.filter_by(invite_code=verification.invite_code).first()
        if inviter:
            response_data['inviter_name'] = inviter.username
    
    return jsonify({
        'code': 200,
        'message': '验证链接有效',
        'data': response_data
    })


@auth_bp.route('/smtp-status', methods=['GET'])
def smtp_status():
    """检查SMTP是否已配置"""
    return jsonify({
        'code': 200,
        'data': {'configured': EmailService.is_configured()}
    })


@auth_bp.route('/register-status', methods=['GET'])
def register_status():
    """检查是否开放注册"""
    return jsonify({
        'code': 200,
        'data': {
            'allowed': Setting.get('allow_register', '1') == '1',
            'email_register_allowed': Setting.get('allow_email_register', '1') == '1'
        }
    })


# ========== GitHub OAuth ==========

@auth_bp.route('/github', methods=['GET'])
def github_login():
    """重定向到 GitHub 授权页面"""
    from app.services.github_oauth import GitHubOAuthService
    
    if not GitHubOAuthService.is_configured():
        return jsonify({'code': 500, 'message': 'GitHub OAuth 未配置'}), 500
    
    # 构建回调地址
    redirect_uri = get_site_url() + '/api/auth/github/callback'
    
    # 生成随机 state 防止 CSRF
    import secrets
    state = secrets.token_urlsafe(16)
    
    authorize_url = GitHubOAuthService.get_authorize_url(redirect_uri, state)
    return jsonify({
        'code': 200,
        'data': {'url': authorize_url, 'state': state}
    })


@auth_bp.route('/github/callback', methods=['GET'])
def github_callback():
    """GitHub OAuth 回调 - 处理登录和绑定"""
    from flask import redirect as flask_redirect
    from app.services.github_oauth import GitHubOAuthService
    from app.utils.timezone import now as beijing_now
    
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state', '')
    
    # 检查是否是绑定操作
    is_bind = state.startswith('bind_')
    
    if error:
        if is_bind:
            return flask_redirect('/user/security?bind_error=github_denied')
        return flask_redirect(f'/login?error=github_denied')
    
    if not code:
        if is_bind:
            return flask_redirect('/user/security?bind_error=github_no_code')
        return flask_redirect(f'/login?error=github_no_code')
    
    redirect_uri = get_site_url() + '/api/auth/github/callback'
    
    # 获取 access_token
    access_token, err = GitHubOAuthService.get_access_token(code, redirect_uri)
    if not access_token:
        if is_bind:
            return flask_redirect('/user/security?bind_error=github_token_failed')
        return flask_redirect(f'/login?error=github_token_failed')
    
    # 获取用户信息
    user_info, err = GitHubOAuthService.get_user_info(access_token)
    if not user_info:
        if is_bind:
            return flask_redirect('/user/security?bind_error=github_user_failed')
        return flask_redirect(f'/login?error=github_user_failed')
    
    github_id = user_info['github_id']
    email = user_info.get('email')
    username = user_info.get('username')
    
    # 绑定操作
    if is_bind:
        parts = state.split('_')
        if len(parts) < 3:
            return flask_redirect('/user/security?bind_error=invalid_state')
        
        user_id = parts[1]
        user = User.query.get(user_id)
        if not user:
            return flask_redirect('/user/security?bind_error=user_not_found')
        
        # 检查是否已被其他用户绑定
        existing = User.query.filter_by(github_id=github_id).first()
        if existing and existing.id != user.id:
            return flask_redirect('/user/security?bind_error=github_already_bound')
        
        user.github_id = github_id
        db.session.commit()
        
        return flask_redirect('/user/security?bind_success=github')
    
    # 登录操作
    # 查找已绑定的用户
    user = User.query.filter_by(github_id=github_id).first()
    
    if not user and email:
        # 查找邮箱匹配的用户，自动绑定
        user = User.query.filter_by(email=email).first()
        if user:
            user.github_id = github_id
    
    if not user:
        # 创建新用户
        if not email:
            return flask_redirect(f'/login?error=github_no_email')
        
        # 生成唯一用户名
        base_username = username or f'gh_{github_id}'
        final_username = base_username
        counter = 1
        while User.query.filter_by(username=final_username).first():
            final_username = f'{base_username}_{counter}'
            counter += 1
        
        # 获取默认域名配额
        default_max_domains = int(Setting.get('default_max_domains', '5'))
        
        user = User(
            username=final_username,
            email=email,
            github_id=github_id,
            max_domains=default_max_domains
        )
        db.session.add(user)
    
    # 检查用户状态
    if user.is_banned:
        # 记录被拒绝的登录尝试
        from app.models import OperationLog
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} GitHub OAuth登录被拒绝：账户已封禁',
            ip_address=get_real_ip()
        )
        return flask_redirect('/login?error=account_banned')
    
    if user.is_sleeping:
        # 记录被拒绝的登录尝试
        from app.models import OperationLog
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} GitHub OAuth登录被拒绝：账户未激活',
            ip_address=get_real_ip()
        )
        return flask_redirect('/login?error=account_sleeping')
    
    # 更新登录信息
    user.last_login_at = beijing_now()
    user.last_login_ip = get_real_ip()
    db.session.commit()
    
    # 生成 JWT token
    access_token = create_access_token(identity=str(user.id))
    
    # 重定向到前端，带上 token
    return flask_redirect(f'/login?github_token={access_token}')


@auth_bp.route('/github/status', methods=['GET'])
def github_oauth_status():
    """检查 GitHub OAuth 是否已配置"""
    from app.services.github_oauth import GitHubOAuthService
    return jsonify({
        'code': 200,
        'data': {'configured': GitHubOAuthService.is_configured()}
    })


# ========== Google OAuth ==========

@auth_bp.route('/google', methods=['GET'])
def google_login():
    """重定向到 Google 授权页面"""
    from app.services.google_oauth import GoogleOAuthService
    
    if not GoogleOAuthService.is_configured():
        return jsonify({'code': 500, 'message': 'Google OAuth 未配置'}), 500
    
    # 构建回调地址
    redirect_uri = get_site_url() + '/api/auth/google/callback'
    
    # 生成随机 state 防止 CSRF
    import secrets
    state = secrets.token_urlsafe(16)
    
    authorize_url = GoogleOAuthService.get_authorize_url(redirect_uri, state)
    return jsonify({
        'code': 200,
        'data': {'url': authorize_url, 'state': state}
    })


@auth_bp.route('/google/callback', methods=['GET'])
def google_callback():
    """Google OAuth 回调 - 处理登录和绑定"""
    from flask import redirect as flask_redirect
    from app.services.google_oauth import GoogleOAuthService
    from app.utils.timezone import now as beijing_now
    
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state', '')
    
    # 检查是否是绑定操作
    is_bind = state.startswith('bind_')
    
    if error:
        if is_bind:
            return flask_redirect('/user/security?bind_error=google_denied')
        return flask_redirect(f'/login?error=google_denied')
    
    if not code:
        if is_bind:
            return flask_redirect('/user/security?bind_error=google_no_code')
        return flask_redirect(f'/login?error=google_no_code')
    
    redirect_uri = get_site_url() + '/api/auth/google/callback'
    
    # 获取 access_token
    access_token, err = GoogleOAuthService.get_access_token(code, redirect_uri)
    if not access_token:
        if is_bind:
            return flask_redirect('/user/security?bind_error=google_token_failed')
        return flask_redirect(f'/login?error=google_token_failed')
    
    # 获取用户信息
    user_info, err = GoogleOAuthService.get_user_info(access_token)
    if not user_info:
        if is_bind:
            return flask_redirect('/user/security?bind_error=google_user_failed')
        return flask_redirect(f'/login?error=google_user_failed')
    
    google_id = user_info['google_id']
    email = user_info.get('email')
    name = user_info.get('name')
    
    # 绑定操作
    if is_bind:
        parts = state.split('_')
        if len(parts) < 3:
            return flask_redirect('/user/security?bind_error=invalid_state')
        
        user_id = parts[1]
        user = User.query.get(user_id)
        if not user:
            return flask_redirect('/user/security?bind_error=user_not_found')
        
        # 检查是否已被其他用户绑定
        existing = User.query.filter_by(google_id=google_id).first()
        if existing and existing.id != user.id:
            return flask_redirect('/user/security?bind_error=google_already_bound')
        
        user.google_id = google_id
        db.session.commit()
        
        return flask_redirect('/user/security?bind_success=google')
    
    # 登录操作
    # 查找已绑定的用户
    user = User.query.filter_by(google_id=google_id).first()
    
    if not user and email:
        # 查找邮箱匹配的用户，自动绑定
        user = User.query.filter_by(email=email).first()
        if user:
            user.google_id = google_id
    
    if not user:
        # 创建新用户
        if not email:
            return flask_redirect(f'/login?error=google_no_email')
        
        # 生成唯一用户名
        base_username = name.replace(' ', '_') if name else f'google_{google_id}'
        final_username = base_username
        counter = 1
        while User.query.filter_by(username=final_username).first():
            final_username = f'{base_username}_{counter}'
            counter += 1
        
        # 获取默认域名配额
        default_max_domains = int(Setting.get('default_max_domains', '5'))
        
        user = User(
            username=final_username,
            email=email,
            google_id=google_id,
            max_domains=default_max_domains
        )
        db.session.add(user)
    
    # 检查用户状态
    if user.is_banned:
        # 记录被拒绝的登录尝试
        from app.models import OperationLog
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} Google OAuth登录被拒绝：账户已封禁',
            ip_address=get_real_ip()
        )
        return flask_redirect('/login?error=account_banned')
    
    if user.is_sleeping:
        # 记录被拒绝的登录尝试
        from app.models import OperationLog
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} Google OAuth登录被拒绝：账户未激活',
            ip_address=get_real_ip()
        )
        return flask_redirect('/login?error=account_sleeping')
    
    # 更新登录信息
    user.last_login_at = beijing_now()
    user.last_login_ip = get_real_ip()
    db.session.commit()
    
    # 生成 JWT token
    access_token = create_access_token(identity=str(user.id))
    
    # 重定向到前端，带上 token
    return flask_redirect(f'/login?google_token={access_token}')


@auth_bp.route('/google/status', methods=['GET'])
def google_oauth_status():
    """检查 Google OAuth 是否已配置"""
    from app.services.google_oauth import GoogleOAuthService
    return jsonify({
        'code': 200,
        'data': {'configured': GoogleOAuthService.is_configured()}
    })


# ========== NodeLoc OAuth ==========

@auth_bp.route('/nodeloc', methods=['GET'])
def nodeloc_login():
    """重定向到 NodeLoc 授权页面"""
    from app.services.nodeloc_oauth import NodeLocOAuthService
    
    if not NodeLocOAuthService.is_configured():
        return jsonify({'code': 500, 'message': 'NodeLoc OAuth 未配置'}), 500
    
    # 构建回调地址
    redirect_uri = get_site_url() + '/api/auth/nodeloc/callback'
    
    # 生成随机 state 防止 CSRF
    import secrets
    state = secrets.token_urlsafe(16)
    
    authorize_url = NodeLocOAuthService.get_authorize_url(redirect_uri, state)
    return jsonify({
        'code': 200,
        'data': {'url': authorize_url, 'state': state}
    })


@auth_bp.route('/nodeloc/callback', methods=['GET'])
def nodeloc_callback():
    """NodeLoc OAuth 回调 - 处理登录和绑定"""
    from flask import redirect as flask_redirect
    from app.services.nodeloc_oauth import NodeLocOAuthService
    from app.utils.timezone import now as beijing_now
    
    code = request.args.get('code')
    error = request.args.get('error')
    state = request.args.get('state', '')
    
    # 检查是否是绑定操作
    is_bind = state.startswith('bind_')
    
    if error:
        if is_bind:
            return flask_redirect('/user/security?bind_error=nodeloc_denied')
        return flask_redirect(f'/login?error=nodeloc_denied')
    
    if not code:
        if is_bind:
            return flask_redirect('/user/security?bind_error=nodeloc_no_code')
        return flask_redirect(f'/login?error=nodeloc_no_code')
    
    redirect_uri = get_site_url() + '/api/auth/nodeloc/callback'
    
    # 获取 access_token
    access_token, err = NodeLocOAuthService.get_access_token(code, redirect_uri)
    if not access_token:
        if is_bind:
            return flask_redirect('/user/security?bind_error=nodeloc_token_failed')
        return flask_redirect(f'/login?error=nodeloc_token_failed')
    
    # 获取用户信息
    user_info, err = NodeLocOAuthService.get_user_info(access_token)
    if not user_info:
        if is_bind:
            return flask_redirect('/user/security?bind_error=nodeloc_user_failed')
        return flask_redirect(f'/login?error=nodeloc_user_failed')
    
    nodeloc_id = user_info['nodeloc_id']
    email = user_info.get('email')
    username = user_info.get('username')
    name = user_info.get('name')
    
    # 绑定操作
    if is_bind:
        parts = state.split('_')
        if len(parts) < 3:
            return flask_redirect('/user/security?bind_error=invalid_state')
        
        user_id = parts[1]
        user = User.query.get(user_id)
        if not user:
            return flask_redirect('/user/security?bind_error=user_not_found')
        
        # 检查是否已被其他用户绑定
        existing = User.query.filter_by(nodeloc_id=nodeloc_id).first()
        if existing and existing.id != user.id:
            return flask_redirect('/user/security?bind_error=nodeloc_already_bound')
        
        user.nodeloc_id = nodeloc_id
        db.session.commit()
        
        return flask_redirect('/user/security?bind_success=nodeloc')
    
    # 登录操作
    # 查找已绑定的用户
    user = User.query.filter_by(nodeloc_id=nodeloc_id).first()
    
    if not user and email:
        # 查找邮箱匹配的用户，自动绑定
        user = User.query.filter_by(email=email).first()
        if user:
            user.nodeloc_id = nodeloc_id
    
    if not user:
        # 创建新用户
        if not email:
            return flask_redirect(f'/login?error=nodeloc_no_email')
        
        # 生成唯一用户名
        base_username = username or name or f'nodeloc_{nodeloc_id}'
        final_username = base_username
        counter = 1
        while User.query.filter_by(username=final_username).first():
            final_username = f'{base_username}_{counter}'
            counter += 1
        
        # 获取默认域名配额
        default_max_domains = int(Setting.get('default_max_domains', '5'))
        
        user = User(
            username=final_username,
            email=email,
            nodeloc_id=nodeloc_id,
            max_domains=default_max_domains
        )
        db.session.add(user)
    
    # 检查用户状态
    if user.is_banned:
        # 记录被拒绝的登录尝试
        from app.models import OperationLog
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} NodeLoc OAuth登录被拒绝：账户已封禁',
            ip_address=get_real_ip()
        )
        return flask_redirect('/login?error=account_banned')
    
    if user.is_sleeping:
        # 记录被拒绝的登录尝试
        from app.models import OperationLog
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} NodeLoc OAuth登录被拒绝：账户未激活',
            ip_address=get_real_ip()
        )
        return flask_redirect('/login?error=account_sleeping')
    
    # 更新登录信息
    user.last_login_at = beijing_now()
    user.last_login_ip = get_real_ip()
    db.session.commit()
    
    # 生成 JWT token
    access_token = create_access_token(identity=str(user.id))
    
    # 重定向到前端，带上 token
    return flask_redirect(f'/login?nodeloc_token={access_token}')


@auth_bp.route('/nodeloc/status', methods=['GET'])
def nodeloc_oauth_status():
    """检查 NodeLoc OAuth 是否已配置"""
    from app.services.nodeloc_oauth import NodeLocOAuthService
    return jsonify({
        'code': 200,
        'data': {'configured': NodeLocOAuthService.is_configured()}
    })


# ========== OAuth 绑定/解绑 ==========

@auth_bp.route('/oauth/bindable', methods=['GET'])
@jwt_required()
def get_oauth_bindable():
    """获取用户可绑定的 OAuth 账号状态"""
    from app.services.github_oauth import GitHubOAuthService
    from app.services.google_oauth import GoogleOAuthService
    from app.services.nodeloc_oauth import NodeLocOAuthService
    
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'message': '用户不存在'}), 404
    
    return jsonify({
        'code': 200,
        'data': {
            'github': {
                'enabled': GitHubOAuthService.is_configured(),
                'bound': bool(user.github_id)
            },
            'google': {
                'enabled': GoogleOAuthService.is_configured(),
                'bound': bool(user.google_id)
            },
            'nodeloc': {
                'enabled': NodeLocOAuthService.is_configured(),
                'bound': bool(user.nodeloc_id)
            }
        }
    })


@auth_bp.route('/oauth/bind/github', methods=['GET'])
@jwt_required()
def bind_github():
    """绑定 GitHub 账号 - 获取授权 URL"""
    from app.services.github_oauth import GitHubOAuthService
    import secrets
    
    if not GitHubOAuthService.is_configured():
        return jsonify({'code': 500, 'message': 'GitHub OAuth 未配置'}), 500
    
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.github_id:
        return jsonify({'code': 400, 'message': '已绑定 GitHub 账号'}), 400
    
    # 使用与登录相同的回调 URL，通过 state 区分绑定操作
    redirect_uri = get_site_url() + '/api/auth/github/callback'
    state = f'bind_{user_id}_{secrets.token_urlsafe(16)}'
    
    authorize_url = GitHubOAuthService.get_authorize_url(redirect_uri, state)
    return jsonify({
        'code': 200,
        'data': {'url': authorize_url}
    })


@auth_bp.route('/oauth/unbind/github', methods=['POST'])
@jwt_required()
def unbind_github():
    """解绑 GitHub 账号"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.github_id:
        return jsonify({'code': 400, 'message': '未绑定 GitHub 账号'}), 400
    
    # 检查是否有其他登录方式
    if not user.password_hash and not user.google_id and not user.nodeloc_id:
        return jsonify({'code': 400, 'message': '至少保留一种登录方式'}), 400
    
    user.github_id = None
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '解绑成功'})


@auth_bp.route('/oauth/bind/google', methods=['GET'])
@jwt_required()
def bind_google():
    """绑定 Google 账号 - 获取授权 URL"""
    from app.services.google_oauth import GoogleOAuthService
    import secrets
    
    if not GoogleOAuthService.is_configured():
        return jsonify({'code': 500, 'message': 'Google OAuth 未配置'}), 500
    
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.google_id:
        return jsonify({'code': 400, 'message': '已绑定 Google 账号'}), 400
    
    # 使用与登录相同的回调 URL，通过 state 区分绑定操作
    redirect_uri = get_site_url() + '/api/auth/google/callback'
    state = f'bind_{user_id}_{secrets.token_urlsafe(16)}'
    
    authorize_url = GoogleOAuthService.get_authorize_url(redirect_uri, state)
    return jsonify({
        'code': 200,
        'data': {'url': authorize_url}
    })


@auth_bp.route('/oauth/unbind/google', methods=['POST'])
@jwt_required()
def unbind_google():
    """解绑 Google 账号"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.google_id:
        return jsonify({'code': 400, 'message': '未绑定 Google 账号'}), 400
    
    # 检查是否有其他登录方式
    if not user.password_hash and not user.github_id and not user.nodeloc_id:
        return jsonify({'code': 400, 'message': '至少保留一种登录方式'}), 400
    
    user.google_id = None
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '解绑成功'})


@auth_bp.route('/oauth/bind/nodeloc', methods=['GET'])
@jwt_required()
def bind_nodeloc():
    """绑定 NodeLoc 账号 - 获取授权 URL"""
    from app.services.nodeloc_oauth import NodeLocOAuthService
    import secrets
    
    if not NodeLocOAuthService.is_configured():
        return jsonify({'code': 500, 'message': 'NodeLoc OAuth 未配置'}), 500
    
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user.nodeloc_id:
        return jsonify({'code': 400, 'message': '已绑定 NodeLoc 账号'}), 400
    
    # 使用与登录相同的回调 URL，通过 state 区分绑定操作
    redirect_uri = get_site_url() + '/api/auth/nodeloc/callback'
    state = f'bind_{user_id}_{secrets.token_urlsafe(16)}'
    
    authorize_url = NodeLocOAuthService.get_authorize_url(redirect_uri, state)
    return jsonify({
        'code': 200,
        'data': {'url': authorize_url}
    })


@auth_bp.route('/oauth/unbind/nodeloc', methods=['POST'])
@jwt_required()
def unbind_nodeloc():
    """解绑 NodeLoc 账号"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.nodeloc_id:
        return jsonify({'code': 400, 'message': '未绑定 NodeLoc 账号'}), 400
    
    # 检查是否有其他登录方式
    if not user.password_hash and not user.github_id and not user.google_id:
        return jsonify({'code': 400, 'message': '至少保留一种登录方式'}), 400
    
    user.nodeloc_id = None
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '解绑成功'})


# ========== 短信验证码登录/注册 ==========

@auth_bp.route('/sms/status', methods=['GET'])
def sms_status():
    """检查短信服务是否已启用"""
    from app.services.sms import SmsService
    return jsonify({
        'code': 200,
        'data': {'enabled': SmsService.is_enabled()}
    })


@auth_bp.route('/sms/send', methods=['POST'])
def send_sms_code():
    """发送短信验证码"""
    from app.services.sms import SmsService
    from app.models import SmsVerification
    
    if not SmsService.is_enabled():
        return jsonify({'code': 500, 'message': '短信服务未启用'}), 500
    
    data = request.get_json()
    phone = data.get('phone', '').strip()
    scene = data.get('scene', 'login')  # login/reset/bind/change/verify
    
    # 验证手机号格式
    if not phone or not validate_phone(phone):
        return jsonify({'code': 400, 'message': '请输入正确的手机号'}), 400
    
    # 统一验证码验证（防止滥用）
    captcha_ok, captcha_msg = verify_captcha(data, scene if scene in ['login', 'register'] else 'login')
    if not captcha_ok:
        return jsonify({'code': 400, 'message': captcha_msg}), 400
    
    # 检查发送频率
    can_send, wait = SmsVerification.can_send(phone, scene)
    if not can_send:
        return jsonify({'code': 429, 'message': f'请{wait}秒后再试'}), 429
    
    # 场景验证
    if scene == 'login':
        # 登录/注册场景，不需要检查手机号是否存在
        pass
    elif scene == 'reset':
        # 重置密码，需要手机号已绑定
        user = User.query.filter_by(phone=phone).first()
        if not user:
            return jsonify({'code': 400, 'message': '该手机号未绑定任何账户'}), 400
    elif scene in ['bind', 'change']:
        # 绑定新手机号，需要手机号未被使用
        existing = User.query.filter_by(phone=phone).first()
        if existing:
            return jsonify({'code': 400, 'message': '该手机号已被其他账户绑定'}), 400
    
    # 生成验证码
    code = SmsService.generate_code()
    
    # 发送短信
    template_map = {
        'login': SmsService.TEMPLATE_LOGIN,
        'reset': SmsService.TEMPLATE_RESET_PWD,
        'bind': SmsService.TEMPLATE_BIND_PHONE,
        'change': SmsService.TEMPLATE_CHANGE_PHONE,
        'verify': SmsService.TEMPLATE_VERIFY_PHONE
    }
    template_type = template_map.get(scene, SmsService.TEMPLATE_LOGIN)
    
    success, msg = SmsService.send_code(phone, code, template_type)
    if not success:
        return jsonify({'code': 500, 'message': msg}), 500
    
    # 保存验证码
    expire_minutes = SmsService.get_code_expire_minutes()
    SmsVerification.create(phone, code, scene, expire_minutes=expire_minutes)
    
    return jsonify({'code': 200, 'message': '验证码已发送'})


@auth_bp.route('/login/phone', methods=['POST'])
def login_by_phone():
    """手机号验证码登录（自动注册）"""
    from app.services.sms import SmsService
    from app.models import SmsVerification
    from app.utils.timezone import now as beijing_now
    
    if not SmsService.is_enabled():
        return jsonify({'code': 500, 'message': '短信服务未启用'}), 500
    
    data = request.get_json()
    phone = data.get('phone', '').strip()
    code = data.get('code', '').strip()
    
    if not phone or not validate_phone(phone):
        return jsonify({'code': 400, 'message': '请输入正确的手机号'}), 400
    
    if not code:
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400
    
    # 验证验证码
    valid, result = SmsVerification.verify(phone, code, 'login')
    if not valid:
        return jsonify({'code': 400, 'message': result}), 400
    
    # 查找或创建用户
    user = User.query.filter_by(phone=phone).first()
    
    if not user:
        # 检查是否开放注册
        if Setting.get('allow_register', '1') != '1':
            return jsonify({'code': 403, 'message': '系统暂未开放注册'}), 403
        
        # 自动创建用户
        import secrets
        base_username = f'user_{phone[-4:]}'
        final_username = base_username
        counter = 1
        while User.query.filter_by(username=final_username).first():
            final_username = f'{base_username}_{counter}'
            counter += 1
        
        default_max_domains = int(Setting.get('default_max_domains', '5'))
        
        user = User(
            username=final_username,
            email=f'{phone}@phone.local',  # 临时邮箱
            phone=phone,
            max_domains=default_max_domains
        )
        db.session.add(user)
    
    if not user.is_active:
        return jsonify({'code': 403, 'message': '账户已被禁用'}), 403
    
    # 更新登录信息
    user.last_login_at = beijing_now()
    user.last_login_ip = get_real_ip()
    db.session.commit()
    
    access_token = create_access_token(identity=str(user.id))
    
    return jsonify({
        'code': 200,
        'message': '登录成功',
        'data': {
            'access_token': access_token,
            'token_type': 'Bearer',
            'user': user.to_dict()
        }
    })


@auth_bp.route('/forgot-password/phone', methods=['POST'])
def forgot_password_by_phone():
    """通过手机号重置密码"""
    from app.services.sms import SmsService
    from app.models import SmsVerification
    
    if not SmsService.is_enabled():
        return jsonify({'code': 500, 'message': '短信服务未启用'}), 500
    
    data = request.get_json()
    phone = data.get('phone', '').strip()
    code = data.get('code', '').strip()
    password = data.get('password', '')
    
    if not phone or not validate_phone(phone):
        return jsonify({'code': 400, 'message': '请输入正确的手机号'}), 400
    
    if not code:
        return jsonify({'code': 400, 'message': '请输入验证码'}), 400
    
    if not validate_password(password):
        return jsonify({'code': 400, 'message': '密码需为6-32个字符'}), 400
    
    # 验证验证码
    valid, result = SmsVerification.verify(phone, code, 'reset')
    if not valid:
        return jsonify({'code': 400, 'message': result}), 400
    
    # 查找用户
    user = User.query.filter_by(phone=phone).first()
    if not user:
        return jsonify({'code': 400, 'message': '该手机号未绑定任何账户'}), 400
    
    # 重置密码
    user.set_password(password)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '密码重置成功，请使用新密码登录'})


def validate_phone(phone):
    """验证手机号格式（中国大陆手机号）"""
    import re
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))


# ========== 邮箱链接登录（Magic Link）==========

@auth_bp.route('/magic-link/config', methods=['GET'])
def magic_link_config():
    """获取 Magic Link 配置"""
    enabled = Setting.get('magic_link_enabled', '1') == '1'
    expire_minutes = int(Setting.get('magic_link_expire_minutes', '15'))
    cooldown_seconds = int(Setting.get('magic_link_cooldown_seconds', '60'))
    captcha_required = Setting.get('captcha_magic_link', '1') == '1'
    
    return jsonify({
        'code': 200,
        'data': {
            'enabled': enabled,
            'expire_minutes': expire_minutes,
            'cooldown_seconds': cooldown_seconds,
            'captcha_required': captcha_required
        }
    })


@auth_bp.route('/magic-link/send', methods=['POST'])
def magic_link_send():
    """发送邮箱链接登录邮件"""
    from app.models import MagicLinkToken
    from app.models.email_template import EmailTemplate
    
    # 检查是否启用
    if Setting.get('magic_link_enabled', '1') != '1':
        return jsonify({'code': 403, 'message': '邮箱链接登录未启用'}), 403
    
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    
    # 验证邮箱格式
    if not validate_email(email):
        return jsonify({'code': 400, 'message': '邮箱格式不正确'}), 400
    
    # 验证码验证
    captcha_ok, captcha_msg = verify_captcha(data, 'magic_link')
    if not captcha_ok:
        return jsonify({'code': 400, 'message': captcha_msg}), 400
    
    # 查找用户
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'code': 400, 'message': '该邮箱未注册'}), 400
    
    # 检查用户状态
    if user.is_banned:
        # 记录被拒绝的登录尝试
        from app.models import OperationLog
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} 魔法链接发送被拒绝：账户已封禁',
            ip_address=get_real_ip()
        )
        return jsonify({'code': 403, 'message': '账户已被禁用'}), 403
    
    if user.is_sleeping:
        # 记录被拒绝的登录尝试
        from app.models import OperationLog
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} 魔法链接发送被拒绝：账户未激活',
            ip_address=get_real_ip()
        )
        return jsonify({'code': 403, 'message': '账户未激活，请先验证邮箱'}), 403
    
    # 检查发送频率
    can_send, wait_seconds = MagicLinkToken.can_send(user.id)
    if not can_send:
        return jsonify({'code': 429, 'message': f'请{wait_seconds}秒后再试'}), 429
    
    # 检查邮件服务
    if not EmailService.is_configured():
        return jsonify({'code': 500, 'message': '邮件服务未配置'}), 500
    
    # 创建令牌
    ip_address = get_real_ip()
    magic_link = MagicLinkToken.create(user.id, ip_address)
    
    # 构建登录链接
    site_url = get_site_url()
    login_url = f'{site_url}/magic-link?token={magic_link.token}'
    
    # 获取配置
    expire_minutes = int(Setting.get('magic_link_expire_minutes', '15'))
    site_name = Setting.get('site_name', '六趣DNS')
    
    # 发送邮件
    subject, html_content = EmailTemplate.render('magic_link', {
        'site_name': site_name,
        'login_url': login_url,
        'expire_minutes': expire_minutes
    })
    
    if not subject or not html_content:
        return jsonify({'code': 500, 'message': '邮件模板不存在'}), 500
    
    success, msg = EmailService.send(email, subject, html_content)
    
    if success:
        return jsonify({'code': 200, 'message': '登录链接已发送到您的邮箱'})
    return jsonify({'code': 500, 'message': f'发送失败: {msg}'}), 500


@auth_bp.route('/magic-link/verify', methods=['GET'])
def magic_link_verify():
    """验证邮箱链接登录"""
    from app.models import MagicLinkToken, OperationLog
    from app.utils.timezone import now as beijing_now
    
    token = request.args.get('token', '').strip()
    
    if not token:
        return jsonify({'code': 400, 'message': '无效的登录链接'}), 400
    
    # 查找令牌
    magic_link = MagicLinkToken.get_by_token(token)
    if not magic_link:
        return jsonify({'code': 400, 'message': '无效的登录链接'}), 400
    
    # 检查是否已使用
    if magic_link.is_used:
        return jsonify({'code': 400, 'message': '链接已使用'}), 400
    
    # 检查是否已过期
    if magic_link.is_expired:
        return jsonify({'code': 400, 'message': '链接已过期'}), 400
    
    # 检查令牌有效性
    if not magic_link.is_valid:
        return jsonify({'code': 400, 'message': '链接无效'}), 400
    
    # 获取用户
    user = User.query.get(magic_link.user_id)
    if not user:
        return jsonify({'code': 400, 'message': '用户不存在'}), 400
    
    # 检查用户状态
    if user.is_banned:
        # 记录被拒绝的登录尝试
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} 魔法链接登录被拒绝：账户已封禁',
            ip_address=get_real_ip()
        )
        return jsonify({'code': 403, 'message': '账户已被禁用'}), 403
    
    if user.is_sleeping:
        # 记录被拒绝的登录尝试
        OperationLog.log(
            user_id=user.id,
            action='login_rejected',
            target_type='user',
            target_id=user.id,
            detail=f'用户 {user.username} 魔法链接登录被拒绝：账户未激活',
            ip_address=get_real_ip()
        )
        return jsonify({'code': 403, 'message': '账户未激活，请先验证邮箱'}), 403
    
    # 标记令牌已使用
    ip_address = get_real_ip()
    magic_link.mark_used(ip_address)
    
    # 更新用户登录信息
    user.last_login_at = beijing_now()
    user.last_login_ip = ip_address
    db.session.commit()
    
    # 记录登录活动
    from app.services.activity_tracker import ActivityTracker
    ActivityTracker.log(user.id, 'login', {'ip': ip_address, 'method': 'magic_link'})
    
    # 记录登录日志
    OperationLog.log(
        user_id=user.id,
        action=OperationLog.ACTION_LOGIN,
        target_type='user',
        target_id=user.id,
        detail=f'用户 {user.username} 通过邮箱链接登录',
        ip_address=ip_address
    )
    
    # 生成 JWT token
    access_token = create_access_token(identity=str(user.id))
    
    return jsonify({
        'code': 200,
        'message': '登录成功',
        'data': {
            'access_token': access_token,
            'token_type': 'Bearer',
            'user': user.to_dict()
        }
    })
