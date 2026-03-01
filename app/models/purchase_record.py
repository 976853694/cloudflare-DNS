from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class PurchaseRecord(db.Model):
    """套餐购买记录模型"""
    __tablename__ = 'purchase_records'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    subdomain_id = db.Column(db.Integer, db.ForeignKey('subdomains.id', ondelete='SET NULL'), nullable=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id', ondelete='SET NULL'), nullable=True)
    
    # 快照信息（防止套餐删除后丢失信息）
    plan_name = db.Column(db.String(50), nullable=False)
    domain_name = db.Column(db.String(100), nullable=False)
    subdomain_name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    
    # 支付信息
    payment_method = db.Column(db.String(20), default='balance', nullable=False)  # balance=余额支付
    
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    # 关联
    user = db.relationship('User', backref=db.backref('purchase_records', lazy='dynamic', cascade='all, delete-orphan'))
    subdomain = db.relationship('Subdomain', backref=db.backref('purchase_record', uselist=False))
    plan = db.relationship('Plan', backref=db.backref('purchase_records', lazy='dynamic'))
    
    def to_dict(self, include_user=False, mask_private=False):
        """
        转换为字典
        Args:
            include_user: 是否包含用户信息
            mask_private: 是否隐藏敏感信息（演示用户使用）
        """
        MASKED = '******'
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'subdomain_id': self.subdomain_id,
            'plan_id': self.plan_id,
            'plan_name': self.plan_name,
            'domain_name': MASKED if mask_private else self.domain_name,
            'subdomain_name': MASKED if mask_private else self.subdomain_name,
            'price': float(self.price),
            'price_text': '免费' if self.price == 0 else f'¥{self.price}',
            'duration_days': self.duration_days,
            'duration_text': '永久' if self.duration_days == -1 else f'{self.duration_days}天',
            'payment_method': self.payment_method,
            'payment_method_text': '余额支付' if self.payment_method == 'balance' else self.payment_method,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_user and self.user:
            data['user'] = {
                'id': self.user.id,
                'username': MASKED if mask_private else self.user.username,
                'email': MASKED if mask_private else self.user.email
            }
        return data
