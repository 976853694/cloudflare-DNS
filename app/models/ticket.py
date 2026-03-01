"""
工单模型
"""
from datetime import datetime
from app.utils.timezone import now as beijing_now
from app import db


class Ticket(db.Model):
    """工单表"""
    __tablename__ = 'tickets'
    
    # 工单类型
    TYPE_USER_TO_USER = 1      # 用户对用户
    TYPE_USER_TO_ADMIN = 2     # 用户对管理员
    
    # 工单状态
    STATUS_PENDING = 0         # 待处理
    STATUS_PROCESSING = 1      # 处理中
    STATUS_CLOSED = 2          # 已关闭
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_no = db.Column(db.String(20), nullable=False, unique=True, comment='工单编号')
    type = db.Column(db.SmallInteger, nullable=False, default=TYPE_USER_TO_ADMIN, comment='类型')
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='发起人')
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='接收人')
    subject = db.Column(db.String(200), nullable=False, comment='工单标题')
    content = db.Column(db.Text, nullable=False, comment='工单内容')
    status = db.Column(db.SmallInteger, nullable=False, default=STATUS_PENDING, comment='状态')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 关联
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref=db.backref('sent_tickets', lazy='dynamic', cascade='all, delete-orphan'))
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref=db.backref('received_tickets', lazy='dynamic'))
    replies = db.relationship('TicketReply', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    
    @staticmethod
    def generate_ticket_no():
        """生成工单编号"""
        now = datetime.now()
        prefix = now.strftime('TK%Y%m%d')
        # 查询今天的最大编号
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_ticket = Ticket.query.filter(
            Ticket.created_at >= today_start,
            Ticket.ticket_no.like(f'{prefix}%')
        ).order_by(Ticket.id.desc()).first()
        
        if last_ticket:
            last_num = int(last_ticket.ticket_no[-4:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f'{prefix}{new_num:04d}'
    
    def to_dict(self, include_replies=False):
        data = {
            'id': self.id,
            'ticket_no': self.ticket_no,
            'type': self.type,
            'type_text': self.type_text,
            'from_user_id': self.from_user_id,
            'from_username': self.from_user.username if self.from_user else None,
            'to_user_id': self.to_user_id,
            'to_username': self.to_user.username if self.to_user else None,
            'subject': self.subject,
            'content': self.content,
            'status': self.status,
            'status_text': self.status_text,
            'reply_count': self.replies.count(),
            'unread_count': self.get_unread_count(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }
        if include_replies:
            data['replies'] = [r.to_dict() for r in self.replies.order_by(TicketReply.created_at.asc()).all()]
        return data
    
    def get_unread_count(self, user_id=None):
        """获取未读回复数"""
        if user_id:
            return self.replies.filter(TicketReply.is_read == 0, TicketReply.user_id != user_id).count()
        return self.replies.filter(TicketReply.is_read == 0).count()
    
    @property
    def type_text(self):
        type_map = {
            self.TYPE_USER_TO_USER: '用户工单',
            self.TYPE_USER_TO_ADMIN: '管理员工单'
        }
        return type_map.get(self.type, '未知')
    
    @property
    def status_text(self):
        status_map = {
            self.STATUS_PENDING: '待处理',
            self.STATUS_PROCESSING: '处理中',
            self.STATUS_CLOSED: '已关闭'
        }
        return status_map.get(self.status, '未知')


class TicketReply(db.Model):
    """工单回复表"""
    __tablename__ = 'ticket_replies'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id', ondelete='CASCADE'), nullable=False, comment='工单ID')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='回复人')
    content = db.Column(db.Text, nullable=False, comment='回复内容')
    is_read = db.Column(db.SmallInteger, nullable=False, default=0, comment='是否已读')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    # 关联
    user = db.relationship('User', backref=db.backref('ticket_replies', lazy='dynamic', cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'content': self.content,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
