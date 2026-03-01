from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class Announcement(db.Model):
    """公告模型"""
    __tablename__ = 'announcements'
    
    TYPE_INFO = 'info'
    TYPE_WARNING = 'warning'
    TYPE_SUCCESS = 'success'
    TYPE_ERROR = 'error'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default=TYPE_INFO, nullable=False)  # info, warning, success, error
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)  # 是否置顶
    is_popup = db.Column(db.Boolean, default=False, nullable=False)  # 是否弹窗显示（重要公告）
    status = db.Column(db.SmallInteger, default=1, nullable=False)  # 0=草稿, 1=发布
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    def to_dict(self, user_id=None):
        data = {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'type': self.type,
            'type_text': self.type_text,
            'is_pinned': self.is_pinned,
            'is_popup': self.is_popup,
            'status': self.status,
            'status_text': '已发布' if self.status == 1 else '草稿',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if user_id:
            data['is_read'] = self.reads.filter_by(user_id=user_id).first() is not None
        return data
    
    @property
    def type_text(self):
        types = {
            'info': '通知',
            'warning': '警告',
            'success': '成功',
            'error': '紧急'
        }
        return types.get(self.type, '通知')
    
    @property
    def is_published(self):
        return self.status == 1
