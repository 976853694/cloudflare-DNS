"""
邮件发送日志模型
"""
from app import db
from app.utils.timezone import now as beijing_now


class EmailLog(db.Model):
    """邮件发送日志"""
    __tablename__ = 'email_logs'
    
    # 状态常量
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('email_campaigns.id', ondelete='CASCADE'), comment='关联的群发任务ID')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), comment='收件人用户ID')
    to_email = db.Column(db.String(100), nullable=False, comment='收件人邮箱')
    subject = db.Column(db.String(200), nullable=False, comment='邮件主题')
    content = db.Column(db.Text, comment='邮件内容')
    status = db.Column(db.String(20), default=STATUS_PENDING, comment='状态')
    error_message = db.Column(db.Text, comment='失败原因')
    sent_at = db.Column(db.DateTime, comment='发送时间')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'user_id': self.user_id,
            'to_email': self.to_email,
            'subject': self.subject,
            'status': self.status,
            'error_message': self.error_message,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @property
    def is_pending(self):
        """是否待发送"""
        return self.status == self.STATUS_PENDING
    
    @property
    def is_sent(self):
        """是否已发送"""
        return self.status == self.STATUS_SENT
    
    @property
    def is_failed(self):
        """是否失败"""
        return self.status == self.STATUS_FAILED
