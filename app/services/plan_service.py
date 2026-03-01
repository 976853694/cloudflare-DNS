"""
套餐服务
提供套餐购买、续费相关的业务逻辑
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional

from app import db
from app.models import User, Plan, Subdomain
from app.models.purchase_record import PurchaseRecord
from app.utils.timezone import now as beijing_now

logger = logging.getLogger(__name__)


class PlanService:
    """套餐服务"""
    
    @classmethod
    def get_user_purchase_count(cls, user_id: int, plan_id: int) -> int:
        """
        获取用户对某套餐的购买次数
        
        Args:
            user_id: 用户ID
            plan_id: 套餐ID
            
        Returns:
            int: 购买次数
        """
        return PurchaseRecord.query.filter_by(
            user_id=user_id,
            plan_id=plan_id
        ).count()
    
    @classmethod
    def can_purchase(cls, user_id: int, plan_id: int) -> Tuple[bool, str, Dict]:
        """
        检查用户是否可以购买该套餐
        
        Args:
            user_id: 用户ID
            plan_id: 套餐ID
            
        Returns:
            Tuple[bool, str, Dict]: (是否可购买, 错误信息, 额外数据)
        """
        plan = Plan.query.get(plan_id)
        if not plan:
            return False, 'PLAN_NOT_FOUND|套餐不存在', {}
        
        if not plan.is_active:
            return False, 'PLAN_INACTIVE|套餐已下架', {}
        
        # 检查购买次数限制
        if plan.max_purchase_count > 0:
            purchase_count = cls.get_user_purchase_count(user_id, plan_id)
            if purchase_count >= plan.max_purchase_count:
                return False, f'PURCHASE_LIMIT_EXCEEDED|该套餐您已购买过 {purchase_count} 次，无法再次购买', {
                    'purchase_count': purchase_count,
                    'max_purchase_count': plan.max_purchase_count
                }
        
        return True, '', {}
    
    @classmethod
    def get_remaining_days(cls, subdomain: Subdomain) -> int:
        """
        获取子域名剩余天数
        
        Args:
            subdomain: 子域名对象
            
        Returns:
            int: 剩余天数（永久返回-1，已过期返回0）
        """
        if not subdomain.expires_at:
            return -1  # 永久
        
        now = beijing_now()
        if subdomain.expires_at <= now:
            return 0  # 已过期
        
        remaining = (subdomain.expires_at - now).days
        return max(0, remaining)
    
    @classmethod
    def can_renew(cls, subdomain_id: int, plan_id: int = None) -> Tuple[bool, str, Dict]:
        """
        检查子域名是否可以续费
        
        Args:
            subdomain_id: 子域名ID
            plan_id: 套餐ID（可选，默认使用子域名关联的套餐）
            
        Returns:
            Tuple[bool, str, Dict]: (是否可续费, 错误信息, 额外数据)
        """
        subdomain = Subdomain.query.get(subdomain_id)
        if not subdomain:
            return False, 'SUBDOMAIN_NOT_FOUND|子域名不存在', {}
        
        # 获取套餐
        if plan_id:
            plan = Plan.query.get(plan_id)
        else:
            plan = subdomain.plan
        
        if not plan:
            return False, 'PLAN_NOT_FOUND|套餐不存在', {}
        
        if not plan.is_active:
            return False, 'PLAN_INACTIVE|套餐已下架', {}
        
        # 检查续费时间窗口
        if plan.renew_before_days > 0:
            remaining_days = cls.get_remaining_days(subdomain)
            
            # 永久套餐不需要续费
            if remaining_days == -1:
                return False, 'RENEW_NOT_NEEDED|永久套餐无需续费', {
                    'remaining_days': -1
                }
            
            # 检查是否在续费窗口内
            if remaining_days > plan.renew_before_days:
                renew_available_date = subdomain.expires_at - timedelta(days=plan.renew_before_days)
                return False, f'RENEW_NOT_AVAILABLE|该套餐需在到期前 {plan.renew_before_days} 天内才能续费，当前剩余 {remaining_days} 天', {
                    'remaining_days': remaining_days,
                    'renew_before_days': plan.renew_before_days,
                    'renew_available_date': renew_available_date.strftime('%Y-%m-%d')
                }
        
        # 注意：续费不检查购买次数限制
        # max_purchase_count 只限制首次购买/申请次数，续费不受此限制
        
        return True, '', {
            'remaining_days': cls.get_remaining_days(subdomain)
        }
    
    @classmethod
    def get_renewal_info(cls, subdomain_id: int, user_id: int) -> Tuple[bool, str, Dict]:
        """
        获取续费信息
        
        Args:
            subdomain_id: 子域名ID
            user_id: 用户ID
            
        Returns:
            Tuple[bool, str, Dict]: (是否成功, 错误信息, 续费信息)
        """
        subdomain = Subdomain.query.get(subdomain_id)
        if not subdomain:
            return False, 'SUBDOMAIN_NOT_FOUND|子域名不存在', {}
        
        if subdomain.user_id != user_id:
            return False, 'NOT_OWNER|您不是该子域名的所有者', {}
        
        plan = subdomain.plan
        if not plan:
            return False, 'PLAN_NOT_FOUND|套餐不存在', {}
        
        user = User.query.get(user_id)
        if not user:
            return False, 'USER_NOT_FOUND|用户不存在', {}
        
        # 基础信息
        remaining_days = cls.get_remaining_days(subdomain)
        
        # 检查是否可以续费
        can_renew, renew_error, renew_data = cls.can_renew(subdomain_id, plan.id)
        
        # 购买次数信息
        purchase_count = cls.get_user_purchase_count(user_id, plan.id)
        max_purchase = plan.max_purchase_count
        remaining_purchases = max_purchase - purchase_count if max_purchase > 0 else -1  # -1表示不限
        
        # 续费时间窗口信息
        renew_window = None
        if plan.renew_before_days > 0:
            if subdomain.expires_at:
                renew_available_date = subdomain.expires_at - timedelta(days=plan.renew_before_days)
                renew_window = {
                    'renew_before_days': plan.renew_before_days,
                    'renew_available_date': renew_available_date.strftime('%Y-%m-%d'),
                    'is_in_window': remaining_days <= plan.renew_before_days and remaining_days >= 0
                }
            else:
                renew_window = {
                    'renew_before_days': plan.renew_before_days,
                    'renew_available_date': None,
                    'is_in_window': False
                }
        
        return True, '', {
            'subdomain': {
                'id': subdomain.id,
                'name': subdomain.full_name,
                'expires_at': subdomain.expires_at.strftime('%Y-%m-%d %H:%M:%S') if subdomain.expires_at else None,
                'remaining_days': remaining_days
            },
            'plan': {
                'id': plan.id,
                'name': plan.name,
                'price': float(plan.price),
                'duration_days': plan.duration_days,
                'is_free': plan.is_free,
                'is_active': plan.is_active
            },
            'purchase_info': {
                'purchase_count': purchase_count,
                'max_purchase_count': max_purchase,
                'remaining_purchases': remaining_purchases
            },
            'renew_window': renew_window,
            'can_renew': can_renew,
            'renew_error': renew_error if not can_renew else None
        }
