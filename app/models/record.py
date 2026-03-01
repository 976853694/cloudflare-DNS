from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class DnsRecord(db.Model):
    __tablename__ = 'dns_records'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subdomain_id = db.Column(db.Integer, db.ForeignKey('subdomains.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    content = db.Column(db.String(255), nullable=False)
    ttl = db.Column(db.Integer, default=300, nullable=False)
    proxied = db.Column(db.SmallInteger, default=0, nullable=False)
    priority = db.Column(db.Integer, nullable=True)
    cf_record_id = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    ALLOWED_TYPES = ['A', 'AAAA', 'CNAME', 'TXT', 'MX']
    
    def to_dict(self, mask_private=False):
        """
        转换为字典
        Args:
            mask_private: 是否隐藏敏感信息（演示用户使用）
        """
        MASKED = '******'
        return {
            'id': self.id,
            'cf_record_id': MASKED if mask_private else self.cf_record_id,
            'type': self.type,
            'name': MASKED if mask_private else self.name,
            'content': MASKED if mask_private else self.content,
            'ttl': self.ttl,
            'proxied': self.proxied == 1,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def validate_type(cls, record_type):
        return record_type.upper() in cls.ALLOWED_TYPES
