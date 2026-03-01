"""
优惠码统一验证器
修复域名排除验证的安全漏洞
"""
from decimal import Decimal
from typing import Optional, Dict, Any
from dataclasses import dataclass
from app.models.coupon import Coupon, CouponUsage
from app.utils.timezone import now as beijing_now
import logging

logger = logging.getLogger(__name__)


class CouponValidationError:
    """优惠码验证错误代码"""
    COUPON_NOT_FOUND = 'coupon_not_found'
    COUPON_EXPIRED = 'coupon_expired'
    COUPON_EXHAUSTED = 'coupon_exhausted'
    USER_LIMIT_EXCEEDED = 'user_limit_exceeded'
    PRODUCT_TYPE_MISMATCH = 'product_type_mismatch'
    PLAN_NOT_APPLICABLE = 'plan_not_applicable'
    DOMAIN_EXCLUDED = 'domain_excluded'
    MINIMUM_AMOUNT_NOT_MET = 'minimum_amount_not_met'


@dataclass
class ValidationResult:
    """优惠码验证结果"""
    is_valid: bool
    coupon: Optional[Coupon] = None
    discount: Decimal = Decimal('0')
    final_price: Optional[Decimal] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    validated_domain_id: Optional[int] = None  # 验证时的域名ID
    domain_restrictions: Optional[Dict[str, Any]] = None  # 域名限制信息
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            'is_valid': self.is_valid,
            'discount': float(self.discount),
            'error_message': self.error_message,
            'error_code': self.error_code
        }
        
        if self.coupon:
            result['coupon'] = {
                'id': self.coupon.id,
                'code': self.coupon.code,
                'name': self.coupon.name,
                'type': self.coupon.type,
                'value_text': self.coupon._get_value_text()
            }
        
        if self.final_price is not None:
            result['final_price'] = float(self.final_price)
        
        # 添加验证时的域名ID
        if self.validated_domain_id is not None:
            result['validated_domain_id'] = self.validated_domain_id
        
        # 添加域名限制信息
        if self.domain_restrictions is not None:
            result['domain_restrictions'] = self.domain_restrictions
            
        return result


class CouponValidator:
    """优惠码统一验证器"""
    
    # 错误消息映射
    ERROR_MESSAGES = {
        CouponValidationError.COUPON_NOT_FOUND: '优惠码不存在',
        CouponValidationError.COUPON_EXPIRED: '优惠码已失效或已用完',
        CouponValidationError.DOMAIN_EXCLUDED: '该优惠码不适用于此域名',
        CouponValidationError.USER_LIMIT_EXCEEDED: '每人限用{limit}次，您已使用{used}次',
        CouponValidationError.MINIMUM_AMOUNT_NOT_MET: '最低消费 ¥{amount}',
        CouponValidationError.PRODUCT_TYPE_MISMATCH: '该优惠码仅适用于{type}产品',
        CouponValidationError.PLAN_NOT_APPLICABLE: '该优惠码不适用于此套餐',
        CouponValidationError.COUPON_EXHAUSTED: '优惠码已用完'
    }
    
    @staticmethod
    def validate_coupon_for_purchase(
        coupon_code: str,
        user_id: int,
        original_price: float,
        product_type: str = 'domain',
        plan_id: Optional[int] = None,
        domain_id: Optional[int] = None
    ) -> ValidationResult:
        """
        为购买操作验证优惠码
        
        Args:
            coupon_code: 优惠码
            user_id: 用户ID
            original_price: 原价
            product_type: 产品类型 ('domain' 或 'vhost')
            plan_id: 套餐ID (可选)
            domain_id: 域名ID (可选，但对于域名购买必须提供)
            
        Returns:
            ValidationResult: 验证结果对象
        """
        try:
            # 记录验证尝试
            logger.info(f"Validating coupon {coupon_code} for user {user_id}, "
                       f"product_type={product_type}, domain_id={domain_id}")
            
            # 1. 基本有效性检查
            coupon = Coupon.query.filter_by(code=coupon_code.strip().upper()).first()
            if not coupon:
                return CouponValidator._create_error_result(
                    CouponValidationError.COUPON_NOT_FOUND
                )
            
            if not coupon.is_valid:
                if coupon.total_count != -1 and coupon.used_count >= coupon.total_count:
                    error_code = CouponValidationError.COUPON_EXHAUSTED
                else:
                    error_code = CouponValidationError.COUPON_EXPIRED
                return CouponValidator._create_error_result(error_code)
            
            # 2. 产品类型检查
            if not coupon.can_use_for_product(product_type):
                type_text = '域名' if coupon.applicable_type == 'domain' else '虚拟主机'
                return CouponValidator._create_error_result(
                    CouponValidationError.PRODUCT_TYPE_MISMATCH,
                    type=type_text
                )
            
            # 3. 用户使用次数检查
            user_usage = CouponUsage.get_user_usage_count(coupon.id, user_id)
            if user_usage >= coupon.per_user_limit:
                return CouponValidator._create_error_result(
                    CouponValidationError.USER_LIMIT_EXCEEDED,
                    limit=coupon.per_user_limit,
                    used=user_usage
                )
            
            # 4. 套餐限制检查
            if plan_id and not coupon.can_use_for_plan(plan_id):
                return CouponValidator._create_error_result(
                    CouponValidationError.PLAN_NOT_APPLICABLE
                )
            
            # 5. 域名排除检查 (关键安全修复)
            if domain_id and not coupon.can_use_for_domain(domain_id):
                # 记录安全事件
                logger.warning(f"Security: User {user_id} attempted to use coupon {coupon_code} "
                             f"on excluded domain {domain_id}")
                excluded_domains = coupon.get_excluded_domains()
                return CouponValidator._create_error_result(
                    CouponValidationError.DOMAIN_EXCLUDED,
                    domain_restrictions={
                        'has_exclusions': True,
                        'excluded_domain_ids': excluded_domains
                    }
                )
            
            # 6. 最低消费检查
            if original_price < float(coupon.min_amount):
                return CouponValidator._create_error_result(
                    CouponValidationError.MINIMUM_AMOUNT_NOT_MET,
                    amount=coupon.min_amount
                )
            
            # 计算优惠
            discount = coupon.calculate_discount(original_price)
            final_price = coupon.get_final_price(original_price)
            
            # 构建域名限制信息
            excluded_domains = coupon.get_excluded_domains()
            domain_restrictions = {
                'has_exclusions': len(excluded_domains) > 0,
                'excluded_domain_ids': excluded_domains
            }
            
            # 记录成功验证
            logger.info(f"Coupon {coupon_code} validated successfully for user {user_id}, "
                       f"discount={discount}, final_price={final_price}, domain_id={domain_id}")
            
            return ValidationResult(
                is_valid=True,
                coupon=coupon,
                discount=discount,
                final_price=final_price,
                validated_domain_id=domain_id,
                domain_restrictions=domain_restrictions
            )
            
        except Exception as e:
            logger.error(f"Error validating coupon {coupon_code}: {str(e)}")
            return ValidationResult(
                is_valid=False,
                error_message="系统错误，请稍后重试",
                error_code="system_error"
            )
    
    @staticmethod
    def _create_error_result(error_code: str, domain_restrictions: Optional[Dict[str, Any]] = None, **kwargs) -> ValidationResult:
        """创建错误结果"""
        message_template = CouponValidator.ERROR_MESSAGES.get(error_code, "未知错误")
        error_message = message_template.format(**kwargs) if kwargs else message_template
        
        return ValidationResult(
            is_valid=False,
            error_message=error_message,
            error_code=error_code,
            domain_restrictions=domain_restrictions
        )
    
    @staticmethod
    def log_validation_attempt(
        user_id: int,
        coupon_code: str,
        domain_id: Optional[int],
        result: ValidationResult,
        context: str = "purchase",
        ip_address: Optional[str] = None
    ):
        """记录验证尝试的审计日志"""
        log_data = {
            'user_id': user_id,
            'coupon_code': coupon_code,
            'domain_id': domain_id,
            'is_valid': result.is_valid,
            'error_code': result.error_code,
            'context': context,
            'ip_address': ip_address,
            'validated_domain_id': result.validated_domain_id
        }
        
        if result.is_valid:
            logger.info(f"Coupon validation success: {log_data}")
        else:
            logger.warning(f"Coupon validation failed: {log_data}")
            
            # 特别记录域名排除的安全事件
            if result.error_code == CouponValidationError.DOMAIN_EXCLUDED:
                logger.error(f"SECURITY EVENT: Domain exclusion bypass attempt: {log_data}")
    
    @staticmethod
    def log_security_event(
        user_id: int,
        event_type: str,
        coupon_code: str,
        domain_id: Optional[int],
        error_code: Optional[str] = None,
        validated_domain_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ):
        """记录安全事件的详细审计日志"""
        log_data = {
            'event_type': event_type,
            'user_id': user_id,
            'coupon_code': coupon_code,
            'domain_id': domain_id,
            'validated_domain_id': validated_domain_id,
            'error_code': error_code,
            'ip_address': ip_address
        }
        
        if additional_info:
            log_data.update(additional_info)
        
        # 根据事件类型选择日志级别
        if event_type in ['domain_exclusion_bypass', 'coupon_domain_mismatch']:
            logger.error(f"SECURITY EVENT [{event_type}]: {log_data}")
        else:
            logger.warning(f"Security event [{event_type}]: {log_data}")