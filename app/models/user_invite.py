"""
用户邀请记录模型
"""
from datetime import datetime
from app.utils.timezone import now as beijing_now
from app import db


class UserInvite(db.Model):
    """用户邀请记录"""
    __tablename__ = 'user_invites'
    
    # 状态常量
    STATUS_REGISTERED = 0   # 已注册
    STATUS_RECHARGED = 1    # 已首充
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='邀请人')
    invitee_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='被邀请人')
    invite_code = db.Column(db.String(20), nullable=False, comment='使用的邀请码')
    register_reward = db.Column(db.Integer, nullable=False, default=0, comment='注册奖励积分(邀请人)')
    recharge_reward = db.Column(db.Integer, nullable=False, default=0, comment='首充奖励积分(邀请人)')
    invitee_reward = db.Column(db.Integer, nullable=False, default=0, comment='被邀请人奖励积分')
    status = db.Column(db.SmallInteger, nullable=False, default=0, comment='状态')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    # 唯一约束：每个被邀请人只能有一个邀请记录
    __table_args__ = (
        db.UniqueConstraint('invitee_id', name='uk_invitee'),
    )
    
    # 关联
    inviter = db.relationship('User', foreign_keys=[inviter_id], backref=db.backref('invites_sent', lazy='dynamic', cascade='all, delete-orphan'))
    invitee = db.relationship('User', foreign_keys=[invitee_id], backref=db.backref('invite_received', uselist=False, cascade='all, delete-orphan'))
    
    def to_dict(self, include_invitee=True):
        data = {
            'id': self.id,
            'invite_code': self.invite_code,
            'register_reward': self.register_reward,
            'recharge_reward': self.recharge_reward,
            'invitee_reward': self.invitee_reward,
            'total_reward': self.register_reward + self.recharge_reward,
            'status': self.status,
            'status_text': self.status_text,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
        if include_invitee and self.invitee:
            data['invitee'] = {
                'id': self.invitee.id,
                'username': self.invitee.username
            }
        return data
    
    @property
    def status_text(self):
        """状态文本"""
        if self.status == self.STATUS_RECHARGED:
            return '已首充'
        return '已注册'
