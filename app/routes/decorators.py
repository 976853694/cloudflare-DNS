"""
通用路由装饰器
"""
from functools import wraps
from flask import jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User
from app.services.phone_binding import PhoneBindingService


def phone_binding_required(fn):
    """
    手机号绑定检查装饰器
    当系统启用强制绑定手机号时，检查用户是否已绑定手机号
    未绑定则拒绝购买操作
    
    注意：此装饰器应放在 jwt_required 或 login_required 之后
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # 优先从 g.user 获取用户（vhost 路由使用 login_required 设置）
        user = getattr(g, 'user', None)
        
        # 如果 g.user 不存在，从 JWT 获取
        if not user:
            user_id = get_jwt_identity()
            if user_id:
                user = User.query.get(int(user_id))
        
        if not user:
            return jsonify({'code': 404, 'message': '用户不存在'}), 404
        
        # 检查是否允许购买
        allowed, error_message = PhoneBindingService.check_purchase_allowed(user)
        
        if not allowed:
            return jsonify({
                'code': 403,
                'error_type': 'phone_binding_required',
                'message': error_message,
                'bind_url': '/user/security'
            }), 403
        
        return fn(*args, **kwargs)
    return wrapper
