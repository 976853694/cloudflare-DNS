"""
用户活动记录模型
"""
from app import db
from app.utils.timezone import now as beijing_now


class UserActivity(db.Model):
    """用户活动记录"""
    __tablename__ = 'user_activities'
    
    # 活动类型常量
    TYPE_LOGIN = 'login'
    TYPE_DOMAIN_CREATE = 'domain_create'
    TYPE_RECORD_UPDATE = 'record_update'
    TYPE_BALANCE_RECHARGE = 'balance_recharge'
    TYPE_PURCHASE = 'purchase'
    TYPE_PASSWORD_CHANGE = 'password_change'
    TYPE_EMAIL_CHANGE = 'email_change'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False, comment='活动类型')
    activity_data = db.Column(db.Text, comment='活动详情(JSON)')
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    def to_dict(self):
        """转换为字典"""
        import json
        data = None
        if self.activity_data:
            try:
                data = json.loads(self.activity_data)
            except:
                data = self.activity_data
        
        return {
            'id': self.id,
            'user_id': self.user_id,
            'activity_type': self.activity_type,
            'activity_data': data,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
