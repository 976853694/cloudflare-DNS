"""
IP黑名单管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import timedelta
from app import db
from app.models import User, OperationLog
from app.models.ip_blacklist import IPBlacklist
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.timezone import now as beijing_now
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/ip-blacklist', methods=['GET'])
@admin_required
def get_ip_blacklist():
    """获取IP黑名单列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()
    
    query = IPBlacklist.query
    
    if search:
        query = query.filter(IPBlacklist.ip_address.ilike(f'%{search}%'))
    
    pagination = query.order_by(IPBlacklist.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'data': {
            'items': [item.to_dict() for item in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/ip-blacklist', methods=['POST'])
@admin_required
@demo_forbidden
def add_ip_blacklist():
    """添加IP到黑名单"""
    data = request.get_json()
    ip_address = data.get('ip_address', '').strip()
    reason = data.get('reason', '').strip()
    duration_days = data.get('duration_days')  # None表示永久
    
    if not ip_address:
        return jsonify({'code': 400, 'message': '请输入IP地址'}), 400
    
    # 检查是否已存在
    if IPBlacklist.query.filter_by(ip_address=ip_address).first():
        return jsonify({'code': 409, 'message': '该IP已在黑名单中'}), 409
    
    current_user_id = int(get_jwt_identity())
    expires_at = None
    if duration_days and duration_days > 0:
        expires_at = beijing_now() + timedelta(days=duration_days)
    
    IPBlacklist.block(
        ip_address=ip_address,
        reason=reason,
        blocked_by=current_user_id,
        expires_at=expires_at
    )
    
    # 记录日志
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_CREATE,
        target_type='ip_blacklist',
        detail=f'封禁IP: {ip_address}, 原因: {reason or "无"}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 201,
        'message': f'IP {ip_address} 已添加到黑名单'
    }), 201


@admin_bp.route('/ip-blacklist/<int:id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def remove_ip_blacklist(id):
    """从黑名单移除IP"""
    record = IPBlacklist.query.get(id)
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'}), 404
    
    ip_address = record.ip_address
    
    db.session.delete(record)
    db.session.commit()
    
    # 记录日志
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_DELETE,
        target_type='ip_blacklist',
        detail=f'解除IP封禁: {ip_address}',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': f'IP {ip_address} 已从黑名单移除'})


@admin_bp.route('/ip-blacklist/check', methods=['GET'])
@admin_required
def check_ip_blocked():
    """检查IP是否被封禁"""
    ip_address = request.args.get('ip', '').strip()
    
    if not ip_address:
        return jsonify({'code': 400, 'message': '请提供IP地址'}), 400
    
    is_blocked = IPBlacklist.is_blocked(ip_address)
    record = IPBlacklist.query.filter_by(ip_address=ip_address).first()
    
    return jsonify({
        'code': 200,
        'data': {
            'ip_address': ip_address,
            'is_blocked': is_blocked,
            'record': record.to_dict() if record else None
        }
    })
