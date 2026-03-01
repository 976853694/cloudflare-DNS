from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class AnnouncementRead(db.Model):
    """用户公告已读记录"""
    __tablename__ = 'announcement_reads'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcements.id', ondelete='CASCADE'), nullable=False)
    read_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'announcement_id', name='uk_user_announcement'),
    )
    
    user = db.relationship('User', backref=db.backref('announcement_reads', lazy='dynamic', cascade='all, delete-orphan'))
    announcement = db.relationship('Announcement', backref=db.backref('reads', lazy='dynamic', cascade='all, delete-orphan'))
