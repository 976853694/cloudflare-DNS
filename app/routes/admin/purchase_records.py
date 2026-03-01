"""
管理员购买记录管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import User, PurchaseRecord, OperationLog
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/purchase-records', methods=['GET'])
@admin_required
def get_purchase_records():
    """获取购买记录列表"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    user_id = request.args.get('user_id', type=int)
    search = request.args.get('search', '').strip()
    
    query = PurchaseRecord.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    
    if search:
        query = query.filter(
            db.or_(
                PurchaseRecord.subdomain_name.ilike(f'%{search}%'),
                PurchaseRecord.plan_name.ilike(f'%{search}%')
            )
        )
    
    pagination = query.order_by(PurchaseRecord.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'records': [r.to_dict(include_user=True, mask_private=mask_private) for r in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/purchase-records/<int:record_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_purchase_record(record_id):
    """删除购买记录"""
    record = PurchaseRecord.query.get(record_id)
    
    if not record:
        return jsonify({'code': 404, 'message': '记录不存在'}), 404
    
    current_user_id = int(get_jwt_identity())
    subdomain_name = record.subdomain_name
    
    db.session.delete(record)
    db.session.commit()
    
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_DELETE,
        target_type='purchase_record',
        target_id=record_id,
        detail=f'删除购买记录: {subdomain_name}',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': '记录删除成功'})


@admin_bp.route('/purchase-records/batch-delete', methods=['POST'])
@admin_required
@demo_forbidden
def batch_delete_purchase_records():
    """批量删除购买记录"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'code': 400, 'message': '请选择要删除的记录'}), 400
    
    current_user_id = int(get_jwt_identity())
    deleted_count = PurchaseRecord.query.filter(PurchaseRecord.id.in_(ids)).delete(synchronize_session=False)
    db.session.commit()
    
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_DELETE,
        target_type='purchase_record',
        detail=f'批量删除购买记录: {deleted_count}条',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': f'成功删除 {deleted_count} 条记录'})
