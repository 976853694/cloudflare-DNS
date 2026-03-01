"""
Magic Link Token 模型
用于邮箱链接登录功能
"""
import secrets
from datetime import datetime, timedelta
from app import db
from app.utils.timezone import now as beijing_now


class MagicLinkToken(db.Model):
    """邮箱链接登录令牌模型"""
    __tablename__ = 'magic_link_tokens'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_ip = db.Column(db.String(45), nullable=True)
    used_ip = db.Column(db.String(45), nullable=True)
    
    # 关联用户
    user = db.relationship('User', backref=db.backref('magic_link_tokens', lazy='dynamic', cascade='all, delete-orphan'))
    
    @classmethod
    def create(cls, user_id: int, ip_address: str = None) -> 'MagicLinkToken':
        """
        创建新的登录令牌
        :param user_id: 用户ID
        :param ip_address: 创建时的IP地址
        :return: MagicLinkToken 实例
        """
        from app.models import Setting
        
        # 获取配置的过期时间（分钟）
        expire_minutes = int(Setting.get('magic_link_expire_minutes', '15'))
        
        # 生成安全令牌（32字节 = 64字符hex）
        token = secrets.token_hex(32)
        
        # 计算过期时间
        now = beijing_now()
        expires_at = now + timedelta(minutes=expire_minutes)
        
        # 创建记录
        magic_link = cls(
            user_id=user_id,
            token=token,
            created_at=now,
            expires_at=expires_at,
            created_ip=ip_address
        )
        
        db.session.add(magic_link)
        db.session.commit()
        
        return magic_link
    
    @classmethod
    def get_by_token(cls, token: str) -> 'MagicLinkToken':
        """
        根据令牌获取记录
        :param token: 登录令牌
        :return: MagicLinkToken 实例或 None
        """
        return cls.query.filter_by(token=token).first()
    
    @property
    def is_valid(self) -> bool:
        """
        检查令牌是否有效
        - 未使用
        - 未过期
        """
        if self.used_at is not None:
            return False
        if beijing_now() > self.expires_at:
            return False
        return True
    
    @property
    def is_expired(self) -> bool:
        """检查令牌是否已过期"""
        return beijing_now() > self.expires_at
    
    @property
    def is_used(self) -> bool:
        """检查令牌是否已使用"""
        return self.used_at is not None
    
    def mark_used(self, ip_address: str = None):
        """
        标记令牌已使用
        :param ip_address: 使用时的IP地址
        """
        self.used_at = beijing_now()
        self.used_ip = ip_address
        db.session.commit()
    
    @classmethod
    def can_send(cls, user_id: int) -> tuple:
        """
        检查是否可以发送新链接（频率限制）
        :param user_id: 用户ID
        :return: (是否可以发送, 剩余等待秒数)
        """
        from app.models import Setting
        
        # 获取配置的冷却时间（秒）
        cooldown_seconds = int(Setting.get('magic_link_cooldown_seconds', '60'))
        
        # 查找该用户最近的令牌
        latest = cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).first()
        
        if not latest:
            return True, 0
        
        # 计算距离上次发送的时间
        elapsed = (beijing_now() - latest.created_at).total_seconds()
        
        if elapsed < cooldown_seconds:
            wait_seconds = int(cooldown_seconds - elapsed)
            return False, wait_seconds
        
        return True, 0
    
    @classmethod
    def cleanup_expired(cls) -> int:
        """
        清理过期令牌
        :return: 删除的记录数
        """
        # 删除已过期超过24小时的令牌
        cutoff = beijing_now() - timedelta(hours=24)
        result = cls.query.filter(cls.expires_at < cutoff).delete()
        db.session.commit()
        return result
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token': self.token[:8] + '...',  # 只显示部分令牌
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'expires_at': self.expires_at.strftime('%Y-%m-%d %H:%M:%S') if self.expires_at else None,
            'used_at': self.used_at.strftime('%Y-%m-%d %H:%M:%S') if self.used_at else None,
            'is_valid': self.is_valid
        }
