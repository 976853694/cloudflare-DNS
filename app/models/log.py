from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class OperationLog(db.Model):
    """操作日志模型"""
    __tablename__ = 'operation_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    username = db.Column(db.String(50), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    target_name = db.Column(db.String(100), nullable=True)
    detail = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    user = db.relationship('User', backref=db.backref('logs', lazy='dynamic'))
    
    # 操作类型常量
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_REGISTER = 'register'
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_PASSWORD_CHANGE = 'password_change'
    ACTION_OTHER = 'other'
    
    @classmethod
    def log(cls, user_id=None, username=None, action=None, target_type=None, 
            target_id=None, target_name=None, detail=None, ip_address=None, user_agent=None):
        """记录操作日志"""
        log = cls(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(log)
        db.session.commit()
        return log
    
    def to_dict(self, mask_private=False):
        """
        转换为字典
        Args:
            mask_private: 是否隐藏敏感信息（演示用户使用）
        """
        MASKED = '******'
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': MASKED if mask_private else self.username,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': MASKED if mask_private else self.target_id,
            'target_name': MASKED if mask_private else self.target_name,
            'detail': MASKED if mask_private else self.detail,
            'ip_address': MASKED if mask_private else self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
