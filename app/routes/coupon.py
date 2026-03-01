"""
优惠券用户端路由
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User
from app.models.coupon import Coupon, CouponUsage
from app.utils.ip_utils import get_real_ip

coupon_bp = Blueprint('coupon', __name__)


@coupon_bp.route('/coupon/validate', methods=['POST'])
@jwt_required()
def validate_coupon():
    """验证优惠码 - 使用统一验证器确保一致性"""
    user_id = int(get_jwt_identity())
    data = request.get_json()
    
    code = data.get('code', '').strip().upper()
    plan_id = data.get('plan_id')
    domain_id = data.get('domain_id')
    original_price = data.get('price', 0)
    product_type = data.get('product_type', 'domain')  # 产品类型: domain 或 vhost
    
    if not code:
        return jsonify({'code': 400, 'message': '请输入优惠码'}), 400
    
    # 使用统一验证器进行验证
    from app.services.coupon_validator import CouponValidator
    
    validation_result = CouponValidator.validate_coupon_for_purchase(
        coupon_code=code,
        user_id=user_id,
        original_price=original_price,
        product_type=product_type,
        plan_id=plan_id,
        domain_id=domain_id
    )
    
    # 记录验证尝试
    CouponValidator.log_validation_attempt(
        user_id=user_id,
        coupon_code=code,
        domain_id=domain_id,
        result=validation_result,
        context="validation_api",
        ip_address=get_real_ip()
    )
    
    if validation_result.is_valid:
        return jsonify({
            'code': 200,
            'data': validation_result.to_dict()
        })
    else:
        # 返回错误信息，包含错误代码和域名限制信息
        error_response = {
            'code': 400, 
            'message': validation_result.error_message,
            'error_code': validation_result.error_code
        }
        # 如果有域名限制信息，也返回给前端
        if validation_result.domain_restrictions:
            error_response['data'] = {
                'domain_restrictions': validation_result.domain_restrictions
            }
        return jsonify(error_response), 400
