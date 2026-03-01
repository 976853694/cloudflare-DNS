from datetime import datetime, timedelta
import secrets
from app import db
from app.utils.timezone import now as beijing_now


class EmailVerification(db.Model):
    """邮箱验证记录模型"""
    __tablename__ = 'email_verifications'
    
    TYPE_REGISTER = 'register'
    TYPE_RESET_PASSWORD = 'reset_password'
    TYPE_CHANGE_EMAIL = 'change_email'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    email = db.Column(db.String(100), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    invite_code = db.Column(db.String(20), nullable=True)  # 关联的邀请码
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    user = db.relationship('User', backref=db.backref('email_verifications', lazy='dynamic', cascade='all, delete-orphan'))
    
    @classmethod
    def create(cls, email, verification_type, user_id=None, expires_minutes=30, invite_code=None):
        """创建验证记录"""
        token = secrets.token_urlsafe(32)
        verification = cls(
            user_id=user_id,
            email=email,
            token=token,
            type=verification_type,
            invite_code=invite_code,
            expires_at=beijing_now() + timedelta(minutes=expires_minutes)
        )
        db.session.add(verification)
        db.session.commit()
        return verification
    
    @classmethod
    def get_by_token(cls, token):
        """根据token获取验证记录"""
        return cls.query.filter_by(token=token).first()
    
    @classmethod
    def can_send(cls, email, verification_type, interval_seconds=60):
        """检查是否可以发送（频率限制）"""
        recent = cls.query.filter_by(email=email, type=verification_type).order_by(
            cls.created_at.desc()
        ).first()
        if recent:
            elapsed = (beijing_now() - recent.created_at).total_seconds()
            if elapsed < interval_seconds:
                return False, int(interval_seconds - elapsed)
        return True, 0
    
    @property
    def is_valid(self):
        """验证是否有效（未过期且未使用）"""
        return self.used_at is None and beijing_now() < self.expires_at
    
    def mark_used(self):
        """标记为已使用"""
        self.used_at = beijing_now()
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'type': self.type,
            'invite_code': self.invite_code,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
