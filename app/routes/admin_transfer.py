"""
域名转移管理员路由
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.models import User
from app.services.transfer_service import TransferService

admin_transfer_bp = Blueprint('admin_transfer', __name__)


def admin_required():
    """检查管理员权限"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or user.role not in ['admin', 'demo']:
        return False
    return True


@admin_transfer_bp.route('/api/admin/transfer/list', methods=['GET'])
@jwt_required()
def get_list():
    """获取所有转移记录"""
    if not admin_required():
        return jsonify({'code': 403, 'message': '权限不足'}), 403
    
    keyword = request.args.get('keyword', '').strip() or None
    status = request.args.get('status', type=int)
    date_from = request.args.get('date_from', '').strip() or None
    date_to = request.args.get('date_to', '').strip() or None
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 限制每页数量
    per_page = min(per_page, 100)
    
    try:
        data = TransferService.get_admin_transfers(
            keyword=keyword,
            status=status,
            date_from=date_from,
            date_to=date_to,
            page=page,
            per_page=per_page
        )
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取转移记录失败'}), 500


@admin_transfer_bp.route('/api/admin/transfer/stats', methods=['GET'])
@jwt_required()
def get_stats():
    """获取转移统计数据"""
    if not admin_required():
        return jsonify({'code': 403, 'message': '权限不足'}), 403
    
    try:
        data = TransferService.get_transfer_stats()
        return jsonify({'code': 200, 'data': data})
    except Exception as e:
        return jsonify({'code': 500, 'message': '获取统计数据失败'}), 500


@admin_transfer_bp.route('/api/admin/transfer/remark', methods=['POST'])
@jwt_required()
def add_remark():
    """添加管理员备注"""
    if not admin_required():
        return jsonify({'code': 403, 'message': '权限不足'}), 403
    
    # 检查是否为演示账户
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user and user.role == 'demo':
        return jsonify({'code': 403, 'message': '演示账户无法执行此操作'}), 403
    
    data = request.get_json() or {}
    
    transfer_id = data.get('transfer_id')
    remark = data.get('remark', '').strip()
    
    if not transfer_id:
        return jsonify({'code': 400, 'message': '转移记录ID不能为空'}), 400
    
    try:
        TransferService.add_admin_remark(transfer_id=transfer_id, remark=remark)
        return jsonify({'code': 200, 'message': '备注已保存'})
    except ValueError as e:
        error_msg = str(e)
        if '|' in error_msg:
            _, msg = error_msg.split('|', 1)
        else:
            msg = error_msg
        return jsonify({'code': 400, 'message': msg}), 400
    except Exception as e:
        return jsonify({'code': 500, 'message': '保存备注失败'}), 500
