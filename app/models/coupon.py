"""
优惠券模型
"""
from datetime import datetime
from decimal import Decimal
from app import db
from app.utils.timezone import now as beijing_now
import secrets
import string


class Coupon(db.Model):
    """优惠券"""
    __tablename__ = 'coupons'
    
    # 优惠类型
    TYPE_PERCENT = 'percent'  # 折扣（百分比）
    TYPE_FIXED = 'fixed'      # 固定金额减免
    
    # 适用产品类型
    APPLICABLE_ALL = 'all'      # 全部产品
    APPLICABLE_DOMAIN = 'domain'  # 仅域名
    APPLICABLE_VHOST = 'vhost'    # 仅虚拟主机
    
    # 状态
    STATUS_ACTIVE = 1
    STATUS_DISABLED = 0
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(32), unique=True, nullable=False)  # 优惠码
    name = db.Column(db.String(100), nullable=False)  # 优惠券名称
    type = db.Column(db.String(20), default=TYPE_PERCENT, nullable=False)  # 优惠类型
    value = db.Column(db.Numeric(10, 2), nullable=False)  # 优惠值（折扣百分比或固定金额）
    min_amount = db.Column(db.Numeric(10, 2), default=0, nullable=False)  # 最低消费金额
    max_discount = db.Column(db.Numeric(10, 2), nullable=True)  # 最大优惠金额（折扣券适用）
    total_count = db.Column(db.Integer, default=-1, nullable=False)  # 总发放数量，-1无限
    used_count = db.Column(db.Integer, default=0, nullable=False)  # 已使用数量
    per_user_limit = db.Column(db.Integer, default=1, nullable=False)  # 每用户限用次数
    applicable_plans = db.Column(db.Text, nullable=True)  # 适用套餐ID(JSON)，NULL表示全部
    excluded_domains = db.Column(db.Text, nullable=True)  # 排除的域名ID(JSON)，NULL表示不排除
    applicable_type = db.Column(db.String(20), default='all', nullable=False)  # 适用产品类型: all/domain
    status = db.Column(db.SmallInteger, default=STATUS_ACTIVE, nullable=False)
    starts_at = db.Column(db.DateTime, nullable=True)  # 生效时间
    expires_at = db.Column(db.DateTime, nullable=True)  # 过期时间
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    def to_dict(self, mask_private=False):
        """
        转换为字典
        Args:
            mask_private: 是否隐藏敏感信息（演示用户使用）
        """
        MASKED = '******'
        return {
            'id': self.id,
            'code': MASKED if mask_private else self.code,
            'name': self.name,
            'type': self.type,
            'type_text': '折扣' if self.type == self.TYPE_PERCENT else '满减',
            'value': float(self.value),
            'value_text': self._get_value_text(),
            'min_amount': float(self.min_amount),
            'max_discount': float(self.max_discount) if self.max_discount else None,
            'total_count': self.total_count,
            'used_count': self.used_count,
            'remaining': self.remaining_count,
            'per_user_limit': self.per_user_limit,
            'excluded_domains': self.get_excluded_domains(),
            'applicable_type': self.applicable_type or 'all',
            'applicable_type_text': self._get_applicable_type_text(),
            'status': self.status,
            'is_valid': self.is_valid,
            'starts_at': self.starts_at.isoformat() if self.starts_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def _get_value_text(self):
        if self.type == self.TYPE_PERCENT:
            return f'{self.value}折'
        return f'减¥{self.value}'
    
    def _get_applicable_type_text(self):
        """获取适用类型文本"""
        type_map = {
            'all': '全部',
            'domain': '域名',
            'vhost': '虚拟主机'
        }
        return type_map.get(self.applicable_type or 'all', '全部')
    
    def can_use_for_product(self, product_type):
        """检查是否适用于指定产品类型
        
        Args:
            product_type: 'domain' 或 'vhost'
        """
        if not self.applicable_type or self.applicable_type == 'all':
            return True
        return self.applicable_type == product_type
    
    @property
    def remaining_count(self):
        """剩余数量"""
        if self.total_count == -1:
            return -1
        return max(0, self.total_count - self.used_count)
    
    @property
    def is_valid(self):
        """是否有效"""
        now = beijing_now()
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.starts_at and now < self.starts_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        if self.total_count != -1 and self.used_count >= self.total_count:
            return False
        return True
    
    def calculate_discount(self, original_price):
        """
        计算优惠金额
        
        Args:
            original_price: 原价
            
        Returns:
            Decimal: 优惠金额
        """
        original_price = Decimal(str(original_price))
        
        if original_price < self.min_amount:
            return Decimal('0')
        
        if self.type == self.TYPE_PERCENT:
            # 折扣计算：原价 * (1 - 折扣/10)
            discount = original_price * (Decimal('10') - self.value) / Decimal('10')
            if self.max_discount:
                discount = min(discount, self.max_discount)
        else:
            # 固定金额减免
            discount = min(self.value, original_price)
        
        return discount.quantize(Decimal('0.01'))
    
    def get_final_price(self, original_price):
        """
        计算最终价格
        
        Args:
            original_price: 原价
            
        Returns:
            Decimal: 最终价格
        """
        original_price = Decimal(str(original_price))
        discount = self.calculate_discount(original_price)
        return max(Decimal('0'), original_price - discount)
    
    def can_use_for_plan(self, plan_id):
        """检查是否适用于指定套餐"""
        if not self.applicable_plans:
            return True
        import json
        try:
            plan_ids = json.loads(self.applicable_plans)
            return plan_id in plan_ids
        except:
            return True
    
    def can_use_for_domain(self, domain_id):
        """检查是否可用于指定域名（未被排除）"""
        if not self.excluded_domains:
            return True
        import json
        try:
            excluded_ids = json.loads(self.excluded_domains)
            return domain_id not in excluded_ids
        except:
            return True
    
    def get_excluded_domains(self):
        """获取排除的域名ID列表"""
        if not self.excluded_domains:
            return []
        import json
        try:
            return json.loads(self.excluded_domains)
        except:
            return []
    
    def set_excluded_domains(self, domain_ids):
        """设置排除的域名ID列表"""
        import json
        self.excluded_domains = json.dumps(domain_ids) if domain_ids else None
    
    @classmethod
    def generate_code(cls, length=8):
        """生成随机优惠码"""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(length))
            if not cls.query.filter_by(code=code).first():
                return code


class CouponUsage(db.Model):
    """优惠券使用记录"""
    __tablename__ = 'coupon_usages'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    order_id = db.Column(db.Integer, nullable=True)  # 关联订单
    original_price = db.Column(db.Numeric(10, 2), nullable=False)  # 原价
    discount_amount = db.Column(db.Numeric(10, 2), nullable=False)  # 优惠金额
    final_price = db.Column(db.Numeric(10, 2), nullable=False)  # 最终价格
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    coupon = db.relationship('Coupon', backref=db.backref('usages', lazy='dynamic', cascade='all, delete-orphan'))
    user = db.relationship('User', backref=db.backref('coupon_usages', lazy='dynamic', cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'coupon_id': self.coupon_id,
            'coupon_code': self.coupon.code if self.coupon else None,
            'user_id': self.user_id,
            'original_price': float(self.original_price),
            'discount_amount': float(self.discount_amount),
            'final_price': float(self.final_price),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def get_user_usage_count(cls, coupon_id, user_id):
        """获取用户对某优惠券的使用次数"""
        return cls.query.filter_by(coupon_id=coupon_id, user_id=user_id).count()
