from datetime import datetime
from decimal import Decimal
import secrets
import string
from app import db
from app.utils.timezone import now as beijing_now


class RedeemCode(db.Model):
    """卡密/兑换码模型 - 用于充值余额"""
    __tablename__ = 'redeem_codes'
    
    STATUS_UNUSED = 0
    STATUS_USED = 1
    STATUS_DISABLED = 2
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)  # 充值金额，-1表示无限余额
    status = db.Column(db.SmallInteger, default=STATUS_UNUSED, nullable=False)
    used_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    batch_no = db.Column(db.String(32), nullable=True, index=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    user = db.relationship('User', backref=db.backref('used_codes', lazy='dynamic'), foreign_keys=[used_by])
    
    def to_dict(self, include_user=False, mask_private=False):
        """
        转换为字典
        Args:
            include_user: 是否包含使用者信息
            mask_private: 是否隐藏敏感信息（演示用户使用）
        """
        MASKED = '******'
        data = {
            'id': self.id,
            'code': MASKED if mask_private else self.code,
            'amount': float(self.amount) if self.amount else 0,
            'amount_text': '无限' if self.amount == -1 else f'¥{self.amount}',
            'status': self.status,
            'status_text': self.status_text,
            'batch_no': self.batch_no,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_user and self.user:
            data['used_by'] = {
                'id': self.user.id,
                'username': self.user.username
            }
        elif include_user:
            data['used_by'] = None
        return data
    
    @property
    def status_text(self):
        if self.status == self.STATUS_UNUSED:
            return '未使用'
        elif self.status == self.STATUS_USED:
            return '已使用'
        elif self.status == self.STATUS_DISABLED:
            return '已禁用'
        return '未知'
    
    @property
    def is_valid(self):
        """检查卡密是否可用"""
        if self.status != self.STATUS_UNUSED:
            return False
        if self.expires_at and beijing_now() > self.expires_at:
            return False
        return True
    
    @property
    def amount_text(self):
        """返回金额文本"""
        if self.amount == -1:
            return '无限'
        return f'¥{self.amount}'
    
    @staticmethod
    def generate_code(length=16):
        """生成随机卡密"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    @classmethod
    def create_batch(cls, amount, count, expires_at=None, batch_no=None):
        """批量生成卡密
        
        Args:
            amount: 充值金额，-1表示无限余额
            count: 生成数量
            expires_at: 过期时间
            batch_no: 批次号
        """
        if batch_no is None:
            batch_no = beijing_now().strftime('%Y%m%d%H%M%S') + secrets.token_hex(4).upper()
        
        codes = []
        for _ in range(count):
            code = cls(
                code=cls.generate_code(),
                amount=amount,
                batch_no=batch_no,
                expires_at=expires_at
            )
            codes.append(code)
        
        return codes, batch_no
