"""
积分和邀请相关路由
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.points_service import PointsService
from app.services.slider_captcha import SliderCaptchaService
from app.services.turnstile import TurnstileService
from app.models import Setting

points_bp = Blueprint('points', __name__)


@points_bp.route('/api/points', methods=['GET'])
@jwt_required()
def get_points():
    """获取用户积分信息"""
    user_id = get_jwt_identity()
    
    try:
        data = PointsService.get_user_points(user_id)
        return jsonify({'code': 200, 'data': data})
    except ValueError as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取积分信息失败'}), 500


@points_bp.route('/api/points/signin', methods=['POST'])
@jwt_required()
def signin():
    """每日签到"""
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    
    # 检查是否需要验证码
    captcha_signin = Setting.get('captcha_signin', '0') == '1'
    
    if captcha_signin:
        # 获取验证码类型
        captcha_type = Setting.get('captcha_type', 'slider')
        
        # Turnstile 验证
        if captcha_type == 'turnstile' and TurnstileService.is_enabled():
            turnstile_token = data.get('turnstile_token', '')
            if not turnstile_token:
                return jsonify({'code': 400, 'message': '请完成人机验证'}), 400
            success, msg = TurnstileService.verify(turnstile_token)
            if not success:
                return jsonify({'code': 400, 'message': msg}), 400
        # 滑块验证码验证（前端已验证，后端只检查标记）
        elif captcha_type == 'slider':
            slider_verified = data.get('slider_verified', False)
            if not slider_verified:
                return jsonify({'code': 400, 'message': '请完成滑块验证'}), 400
    
    try:
        result = PointsService.signin(user_id)
        return jsonify({'code': 200, 'data': result, 'message': '签到成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '签到失败'}), 500


@points_bp.route('/api/points/signin/status', methods=['GET'])
@jwt_required()
def get_signin_status():
    """获取签到状态"""
    user_id = get_jwt_identity()
    
    try:
        data = PointsService.get_signin_status(user_id)
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取签到状态失败'}), 500


@points_bp.route('/api/points/exchange', methods=['POST'])
@jwt_required()
def exchange():
    """积分兑换余额"""
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    
    points = data.get('points')
    if not points or not isinstance(points, int) or points <= 0:
        return jsonify({'code': 400, 'message': '请输入有效的积分数量'}), 400
    
    try:
        result = PointsService.exchange(user_id, points)
        return jsonify({'code': 200, 'data': result, 'message': '兑换成功'})
    except ValueError as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '兑换失败'}), 500


@points_bp.route('/api/points/records', methods=['GET'])
@jwt_required()
def get_records():
    """获取积分记录"""
    user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    type_filter = request.args.get('type', None)
    
    try:
        data = PointsService.get_records(user_id, type_filter, page, per_page)
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取积分记录失败'}), 500


@points_bp.route('/api/invite/info', methods=['GET'])
@jwt_required()
def get_invite_info():
    """获取邀请信息"""
    user_id = get_jwt_identity()
    
    try:
        data = PointsService.get_invite_info(user_id)
        return jsonify({'code': 200, 'data': data})
    except ValueError as e:
        return jsonify({'code': 400, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取邀请信息失败'}), 500


@points_bp.route('/api/invite/list', methods=['GET'])
@jwt_required()
def get_invite_list():
    """获取邀请记录列表"""
    user_id = get_jwt_identity()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    try:
        data = PointsService.get_invite_list(user_id, page, per_page)
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取邀请记录失败'}), 500



@points_bp.route('/api/points/captcha-config', methods=['GET'])
@jwt_required()
def get_signin_captcha_config():
    """获取签到验证码配置"""
    captcha_signin = Setting.get('captcha_signin', '0') == '1'
    captcha_type = Setting.get('captcha_type', 'slider')
    
    # 如果选择了 Turnstile 但未配置，回退到滑块
    if captcha_type == 'turnstile' and not TurnstileService.is_enabled():
        captcha_type = 'slider'
    
    return jsonify({
        'code': 200,
        'data': {
            'enabled': captcha_signin,
            'type': captcha_type if captcha_signin else None,
            'turnstile_site_key': TurnstileService.get_site_key() if captcha_type == 'turnstile' and captcha_signin else ''
        }
    })
