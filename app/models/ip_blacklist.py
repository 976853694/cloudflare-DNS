"""
IP黑名单模型
"""
from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class IPBlacklist(db.Model):
    """IP黑名单"""
    __tablename__ = 'ip_blacklist'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_address = db.Column(db.String(45), nullable=False, unique=True)  # 支持IPv6
    reason = db.Column(db.String(255), nullable=True)
    blocked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)  # NULL表示永久封禁
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'reason': self.reason,
            'blocked_by': self.blocked_by,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_permanent': self.expires_at is None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def is_active(self):
        """检查封禁是否有效"""
        if self.expires_at is None:
            return True
        return beijing_now() < self.expires_at
    
    @classmethod
    def is_blocked(cls, ip_address):
        """检查IP是否被封禁"""
        record = cls.query.filter_by(ip_address=ip_address).first()
        if not record:
            return False
        return record.is_active
    
    @classmethod
    def block(cls, ip_address, reason=None, blocked_by=None, expires_at=None):
        """
        封禁IP
        
        Args:
            ip_address: IP地址
            reason: 封禁原因
            blocked_by: 操作者ID
            expires_at: 过期时间，None表示永久
        """
        existing = cls.query.filter_by(ip_address=ip_address).first()
        if existing:
            existing.reason = reason
            existing.blocked_by = blocked_by
            existing.expires_at = expires_at
            existing.created_at = beijing_now()
        else:
            record = cls(
                ip_address=ip_address,
                reason=reason,
                blocked_by=blocked_by,
                expires_at=expires_at
            )
            db.session.add(record)
        db.session.commit()
    
    @classmethod
    def unblock(cls, ip_address):
        """解除封禁"""
        record = cls.query.filter_by(ip_address=ip_address).first()
        if record:
            db.session.delete(record)
            db.session.commit()
            return True
        return False
    
    @classmethod
    def cleanup_expired(cls):
        """清理过期的封禁记录"""
        now = beijing_now()
        deleted = cls.query.filter(
            cls.expires_at != None,
            cls.expires_at < now
        ).delete()
        db.session.commit()
        return deleted
