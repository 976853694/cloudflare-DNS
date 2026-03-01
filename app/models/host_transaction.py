"""
托管商交易记录模型
记录托管商域名被购买时的收益分成
"""
from datetime import datetime
from decimal import Decimal
from app import db
from app.utils.timezone import now as beijing_now


class HostTransaction(db.Model):
    """托管商交易记录"""
    __tablename__ = 'host_transactions'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='托管商用户ID')
    purchase_record_id = db.Column(db.Integer, db.ForeignKey('purchase_records.id', ondelete='CASCADE'), nullable=False, comment='购买记录ID')
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id', ondelete='SET NULL'), nullable=True, comment='域名ID')
    total_amount = db.Column(db.Numeric(10, 2), nullable=False, comment='订单总额')
    platform_fee = db.Column(db.Numeric(10, 2), nullable=False, comment='平台抽成')
    host_earnings = db.Column(db.Numeric(10, 2), nullable=False, comment='托管商收益')
    commission_rate = db.Column(db.Numeric(5, 2), nullable=False, comment='当时的抽成比例(%)')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False, comment='创建时间')
    
    # 关系
    host = db.relationship('User', backref=db.backref('host_transactions', lazy='dynamic', cascade='all, delete-orphan'))
    purchase_record = db.relationship('PurchaseRecord', backref=db.backref('host_transaction', uselist=False, cascade='all, delete-orphan'))
    domain = db.relationship('Domain', backref=db.backref('host_transactions', lazy='dynamic'))
    
    def to_dict(self, include_details=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'host_id': self.host_id,
            'purchase_record_id': self.purchase_record_id,
            'domain_id': self.domain_id,
            'total_amount': float(self.total_amount),
            'platform_fee': float(self.platform_fee),
            'host_earnings': float(self.host_earnings),
            'commission_rate': float(self.commission_rate),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_details:
            if self.domain:
                data['domain_name'] = self.domain.name
            if self.purchase_record:
                data['subdomain'] = self.purchase_record.subdomain_name if hasattr(self.purchase_record, 'subdomain_name') else None
                data['buyer_id'] = self.purchase_record.user_id
        return data
    
    @staticmethod
    def calculate_earnings(total_amount, commission_rate):
        """
        计算收益分成
        Args:
            total_amount: 订单总额
            commission_rate: 平台抽成比例(%)
        Returns:
            (platform_fee, host_earnings) 元组
        """
        total = Decimal(str(total_amount))
        rate = Decimal(str(commission_rate))
        platform_fee = (total * rate / Decimal('100')).quantize(Decimal('0.01'))
        host_earnings = total - platform_fee
        return float(platform_fee), float(host_earnings)
    
    @classmethod
    def create_transaction(cls, host_id, purchase_record_id, domain_id, total_amount, commission_rate):
        """
        创建交易记录
        Args:
            host_id: 托管商用户ID
            purchase_record_id: 购买记录ID
            domain_id: 域名ID
            total_amount: 订单总额
            commission_rate: 平台抽成比例(%)
        Returns:
            HostTransaction 实例
        """
        platform_fee, host_earnings = cls.calculate_earnings(total_amount, commission_rate)
        transaction = cls(
            host_id=host_id,
            purchase_record_id=purchase_record_id,
            domain_id=domain_id,
            total_amount=total_amount,
            platform_fee=platform_fee,
            host_earnings=host_earnings,
            commission_rate=commission_rate
        )
        return transaction
