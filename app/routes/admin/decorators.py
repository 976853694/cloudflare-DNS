"""
管理员权限装饰器
"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User


def admin_required(fn):
    """
    管理员权限装饰器
    检查用户是否具有管理员或演示用户权限
    演示用户可以访问管理后台（只读），但写操作由 demo_forbidden 装饰器阻止
    """
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        # 允许管理员和演示用户访问后台
        if not user or (user.role != 'admin' and user.role != 'demo'):
            return jsonify({'code': 403, 'message': '需要管理员权限'}), 403
        
        return fn(*args, **kwargs)
    return wrapper


def demo_forbidden(fn):
    """
    演示用户禁止操作装饰器
    演示用户只能查看，不能进行任何修改操作
    """
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if user and user.role == 'demo':
            return jsonify({'code': 403, 'message': '演示账户无法执行此操作'}), 403
        
        return fn(*args, **kwargs)
    return wrapper
