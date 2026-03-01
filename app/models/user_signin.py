"""
用户签到记录模型
"""
from datetime import datetime
from app.utils.timezone import now as beijing_now
from app import db


class UserSignin(db.Model):
    """用户签到记录"""
    __tablename__ = 'user_signins'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    signin_date = db.Column(db.Date, nullable=False, comment='签到日期')
    continuous_days = db.Column(db.Integer, nullable=False, default=1, comment='当前连续天数')
    points_earned = db.Column(db.Integer, nullable=False, comment='本次获得积分')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    # 唯一约束
    __table_args__ = (
        db.UniqueConstraint('user_id', 'signin_date', name='uk_user_date'),
    )
    
    # 关联
    user = db.relationship('User', backref=db.backref('signins', lazy='dynamic', cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'signin_date': self.signin_date.strftime('%Y-%m-%d') if self.signin_date else None,
            'continuous_days': self.continuous_days,
            'points_earned': self.points_earned,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
