"""
邮件群发任务模型
"""
from app import db
from app.utils.timezone import now as beijing_now


class EmailCampaign(db.Model):
    """邮件群发任务"""
    __tablename__ = 'email_campaigns'
    
    # 状态常量
    STATUS_DRAFT = 'draft'
    STATUS_SENDING = 'sending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='任务名称')
    subject = db.Column(db.String(200), nullable=False, comment='邮件主题')
    content = db.Column(db.Text, nullable=False, comment='邮件内容(HTML)')
    recipient_filter = db.Column(db.Text, comment='收件人筛选条件(JSON)')
    recipient_count = db.Column(db.Integer, default=0, comment='收件人数量')
    sent_count = db.Column(db.Integer, default=0, comment='已发送数量')
    success_count = db.Column(db.Integer, default=0, comment='成功数量')
    failed_count = db.Column(db.Integer, default=0, comment='失败数量')
    status = db.Column(db.String(20), default=STATUS_DRAFT, comment='状态')
    task_id = db.Column(db.String(64), nullable=True, comment='后台任务ID')
    scheduled_at = db.Column(db.DateTime, comment='定时发送时间')
    started_at = db.Column(db.DateTime, comment='开始发送时间')
    completed_at = db.Column(db.DateTime, comment='完成时间')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='创建人ID')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 关联
    logs = db.relationship('EmailLog', backref='campaign', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, include_logs=False):
        """转换为字典"""
        import json
        
        recipient_filter_data = None
        if self.recipient_filter:
            try:
                recipient_filter_data = json.loads(self.recipient_filter)
            except:
                recipient_filter_data = self.recipient_filter
        
        data = {
            'id': self.id,
            'name': self.name,
            'subject': self.subject,
            'content': self.content,
            'recipient_filter': recipient_filter_data,
            'recipient_count': self.recipient_count,
            'sent_count': self.sent_count,
            'success_count': self.success_count,
            'failed_count': self.failed_count,
            'status': self.status,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'progress_percent': self.progress_percent
        }
        
        if include_logs:
            data['logs'] = [log.to_dict() for log in self.logs.all()]
        
        return data
    
    @property
    def progress_percent(self):
        """发送进度百分比"""
        if self.recipient_count == 0:
            return 0
        return int((self.sent_count / self.recipient_count) * 100)
    
    @property
    def is_draft(self):
        """是否为草稿"""
        return self.status == self.STATUS_DRAFT
    
    @property
    def is_sending(self):
        """是否正在发送"""
        return self.status == self.STATUS_SENDING
    
    @property
    def is_completed(self):
        """是否已完成"""
        return self.status == self.STATUS_COMPLETED
    
    @property
    def is_failed(self):
        """是否失败"""
        return self.status == self.STATUS_FAILED
