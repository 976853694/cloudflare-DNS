from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class CloudflareAccount(db.Model):
    __tablename__ = 'cf_accounts'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    api_key = db.Column(db.String(255), nullable=True)
    api_token = db.Column(db.String(255), nullable=True)
    auth_type = db.Column(db.String(20), default='api_key', nullable=False)
    account_id = db.Column(db.String(50), nullable=True)
    status = db.Column(db.SmallInteger, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    domains = db.relationship('Domain', backref='cf_account', lazy='dynamic')
    
    def to_dict(self, include_secret=False, mask_private=False):
        """
        转换为字典
        Args:
            include_secret: 是否包含密钥信息
            mask_private: 是否隐藏敏感信息（演示用户使用）
        """
        MASKED = '******'
        data = {
            'id': self.id,
            'name': self.name,
            'email': MASKED if mask_private else self.email,
            'auth_type': self.auth_type,
            'account_id': MASKED if mask_private else self.account_id,
            'status': self.status,
            'domains_count': self.domains.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_secret:
            if mask_private:
                data['api_key'] = MASKED if self.api_key else None
                data['api_token'] = MASKED if self.api_token else None
            else:
                if self.api_key:
                    data['api_key'] = self.api_key[:10] + '...' if len(self.api_key) > 10 else '***'
                if self.api_token:
                    data['api_token'] = self.api_token[:10] + '...' if len(self.api_token) > 10 else '***'
        return data
    
    @property
    def is_active(self):
        return self.status == 1
