"""
管理员优惠券管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import datetime
from app import db
from app.models import User, OperationLog
from app.models.coupon import Coupon, CouponUsage
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/coupons', methods=['GET'])
@admin_required
def get_coupons():
    """获取优惠券列表"""
    current_user_id = int(get_jwt_identity())
    current_user = User.query.get(current_user_id)
    mask_private = current_user and current_user.role == 'demo'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', type=int)
    search = request.args.get('search', '').strip()
    
    query = Coupon.query
    
    if status is not None:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(
            db.or_(
                Coupon.code.ilike(f'%{search}%'),
                Coupon.name.ilike(f'%{search}%')
            )
        )
    
    pagination = query.order_by(Coupon.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'code': 200,
        'data': {
            'coupons': [c.to_dict(mask_private=mask_private) for c in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })


@admin_bp.route('/coupons', methods=['POST'])
@admin_required
@demo_forbidden
def create_coupon():
    """创建优惠券"""
    data = request.get_json()
    
    name = data.get('name', '').strip()
    coupon_type = data.get('type', Coupon.TYPE_PERCENT)
    value = data.get('value')
    
    if not name or value is None:
        return jsonify({'code': 400, 'message': '请填写优惠券名称和优惠值'}), 400
    
    # 生成优惠码
    code = data.get('code', '').strip().upper()
    if not code:
        code = Coupon.generate_code()
    elif Coupon.query.filter_by(code=code).first():
        return jsonify({'code': 409, 'message': '优惠码已存在'}), 409
    
    # 处理日期
    starts_at = None
    expires_at = None
    if data.get('starts_at'):
        starts_at = datetime.fromisoformat(data['starts_at'].replace('Z', '+00:00'))
    if data.get('expires_at'):
        expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
    
    coupon = Coupon(
        code=code,
        name=name,
        type=coupon_type,
        value=value,
        min_amount=data.get('min_amount', 0),
        max_discount=data.get('max_discount'),
        total_count=data.get('total_count', -1),
        per_user_limit=data.get('per_user_limit', 1),
        applicable_type=data.get('applicable_type', 'all'),
        starts_at=starts_at,
        expires_at=expires_at
    )
    
    # 设置排除域名
    if 'excluded_domains' in data and data['excluded_domains']:
        coupon.set_excluded_domains(data['excluded_domains'])
    
    db.session.add(coupon)
    db.session.commit()
    
    # 记录日志
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_CREATE,
        target_type='coupon',
        target_id=coupon.id,
        detail=f'创建优惠券: {coupon.name} ({coupon.code})',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 201,
        'message': '优惠券创建成功',
        'data': {'coupon': coupon.to_dict()}
    }), 201


@admin_bp.route('/coupons/<int:coupon_id>', methods=['PUT'])
@admin_required
@demo_forbidden
def update_coupon(coupon_id):
    """更新优惠券"""
    coupon = Coupon.query.get(coupon_id)
    if not coupon:
        return jsonify({'code': 404, 'message': '优惠券不存在'}), 404
    
    data = request.get_json()
    
    if 'name' in data:
        coupon.name = data['name']
    if 'value' in data:
        coupon.value = data['value']
    if 'min_amount' in data:
        coupon.min_amount = data['min_amount']
    if 'max_discount' in data:
        coupon.max_discount = data['max_discount']
    if 'total_count' in data:
        coupon.total_count = data['total_count']
    if 'per_user_limit' in data:
        coupon.per_user_limit = data['per_user_limit']
    if 'status' in data:
        coupon.status = data['status']
    if 'expires_at' in data:
        if data['expires_at']:
            coupon.expires_at = datetime.fromisoformat(data['expires_at'].replace('Z', '+00:00'))
        else:
            coupon.expires_at = None
    if 'excluded_domains' in data:
        coupon.set_excluded_domains(data['excluded_domains'] if data['excluded_domains'] else None)
    if 'applicable_type' in data:
        coupon.applicable_type = data['applicable_type']
    
    db.session.commit()
    
    return jsonify({
        'code': 200,
        'message': '优惠券更新成功',
        'data': {'coupon': coupon.to_dict()}
    })


@admin_bp.route('/coupons/<int:coupon_id>', methods=['DELETE'])
@admin_required
@demo_forbidden
def delete_coupon(coupon_id):
    """删除优惠券"""
    coupon = Coupon.query.get(coupon_id)
    if not coupon:
        return jsonify({'code': 404, 'message': '优惠券不存在'}), 404
    
    code = coupon.code
    
    # 删除使用记录
    CouponUsage.query.filter_by(coupon_id=coupon_id).delete()
    db.session.delete(coupon)
    db.session.commit()
    
    # 记录日志
    current_user_id = int(get_jwt_identity())
    admin = User.query.get(current_user_id)
    OperationLog.log(
        user_id=current_user_id,
        username=admin.username if admin else None,
        action=OperationLog.ACTION_DELETE,
        target_type='coupon',
        target_id=coupon_id,
        detail=f'删除优惠券: {code}',
        ip_address=get_real_ip()
    )
    
    return jsonify({'code': 200, 'message': '优惠券删除成功'})


@admin_bp.route('/coupons/<int:coupon_id>/usages', methods=['GET'])
@admin_required
def get_coupon_usages(coupon_id):
    """获取优惠券使用记录"""
    coupon = Coupon.query.get(coupon_id)
    if not coupon:
        return jsonify({'code': 404, 'message': '优惠券不存在'}), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = CouponUsage.query.filter_by(coupon_id=coupon_id).order_by(
        CouponUsage.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'code': 200,
        'data': {
            'coupon': coupon.to_dict(),
            'usages': [u.to_dict() for u in pagination.items],
            'pagination': {
                'page': pagination.page,
                'per_page': pagination.per_page,
                'total': pagination.total,
                'pages': pagination.pages
            }
        }
    })
