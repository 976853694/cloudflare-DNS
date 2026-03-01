"""
管理员卡密管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import timedelta
from app import db
from app.models import User, RedeemCode, OperationLog
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.timezone import now as beijing_now
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/redeem-codes', methods=['GET'])
@admin_required
def get_redeem_codes():
    """获取卡密列表"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', type=int)
    batch_no = request.args.get('batch_no', '').strip()
    search = request.args.get('search', '').strip()
    
    query = RedeemCode.query
    
    if status is not None:
        query = query.filter_by(status=status)
    if batch_no:
        query = query.filter_by(batch_no=batch_no)
    if search:
        query = query.filter(RedeemCode.code.ilike(f'%{search}%'))
    
    pagination = query.order_by(RedeemCode.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'codes': [c.to_dict(include_user=True, mask_private=mask_private) for c in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/redeem-codes/generate', methods=['POST'])
@admin_required
@demo_forbidden
def generate_redeem_codes():
    """批量生成卡密"""
    data = request.get_json()
    
    amount = data.get('amount')
    count = data.get('count', 1)
    expires_days = data.get('expires_days')
    
    if amount is None:
        return jsonify({'code': 400, 'message': '请设置充值金额'}), 400
    
    if amount != -1 and amount < 0:
        return jsonify({'code': 400, 'message': '金额必须是-1（无限）或大于等于0'}), 400
    
    if count < 1 or count > 100:
        return jsonify({'code': 400, 'message': '生成数量必须在1-100之间'}), 400
    
    expires_at = None
    if expires_days and expires_days > 0:
        expires_at = beijing_now() + timedelta(days=expires_days)
    
    codes, batch_no = RedeemCode.create_batch(amount, count, expires_at)
    
    for code in codes:
        db.session.add(code)
    db.session.commit()
    
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    amount_text = '无限' if amount == -1 else f'¥{amount}'
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_CREATE,
        target_type='redeem_code',
        detail=f'生成 {count} 张卡密（金额: {amount_text}），批次号: {batch_no}',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 201,
        'message': f'成功生成 {count} 张卡密',
        'data': {
            'batch_no': batch_no,
            'codes': [c.to_dict() for c in codes]
        }
    }), 201


@admin_bp.route('/redeem-codes/<int:code_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_redeem_code(code_id):
    """更新卡密状态"""
    code = RedeemCode.query.get(code_id)
    
    if not code:
        return jsonify({'code': 404, 'message': '卡密不存在'}), 404
    
    data = request.get_json()
    
    if 'status' in data:
        if code.status == RedeemCode.STATUS_USED:
            return jsonify({'code': 400, 'message': '已使用的卡密不能修改状态'}), 400
        code.status = data['status']
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '卡密更新成功',
        'data': {'code': code.to_dict(include_user=True)}
    })


@admin_bp.route('/redeem-codes/<int:code_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_redeem_code(code_id):
    """删除卡密"""
    code = RedeemCode.query.get(code_id)
    
    if not code:
        return jsonify({'code': 404, 'message': '卡密不存在'}), 404
    
    db.session.delete(code)
    db.session.commit()
    
    return jsonify({'code': 200, 'message': '卡密删除成功'})


@admin_bp.route('/redeem-codes/batch-delete', methods=['POST'])
@admin_required
@demo_forbidden
def batch_delete_redeem_codes():
    """批量删除卡密"""
    data = request.get_json()
    batch_no = data.get('batch_no')
    ids = data.get('ids', [])
    
    if not batch_no and not ids:
        return jsonify({'code': 400, 'message': '请提供批次号或卡密ID列表'}), 400
    
    deleted = 0
    
    if ids:
        for code_id in ids:
            code = RedeemCode.query.get(code_id)
            if code:
                db.session.delete(code)
                deleted += 1
    elif batch_no:
        deleted = RedeemCode.query.filter_by(
            batch_no=batch_no,
            status=RedeemCode.STATUS_UNUSED
        ).delete()
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': f'成功删除 {deleted} 张卡密'
    })


@admin_bp.route('/redeem-codes/export', methods=['GET'])
@admin_required
def export_redeem_codes():
    """导出卡密"""
    batch_no = request.args.get('batch_no', '').strip()
    status = request.args.get('status', type=int)
    
    query = RedeemCode.query
    
    if batch_no:
        query = query.filter_by(batch_no=batch_no)
    if status is not None:
        query = query.filter_by(status=status)
    
    codes = query.order_by(RedeemCode.created_at.desc()).all()
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'codes': [c.code for c in codes],
            'count': len(codes)
        }
    })
