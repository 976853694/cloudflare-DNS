"""
积分变动记录模型
"""
from datetime import datetime
from app.utils.timezone import now as beijing_now
from app import db


class PointRecord(db.Model):
    """积分变动记录"""
    __tablename__ = 'point_records'
    
    # 积分类型常量
    TYPE_SIGNIN = 'signin'          # 签到
    TYPE_SIGNIN_BONUS = 'signin_bonus'  # 连续签到奖励
    TYPE_INVITE = 'invite'          # 邀请注册奖励
    TYPE_INVITE_RECHARGE = 'invite_recharge'  # 邀请首充奖励
    TYPE_INVITED = 'invited'        # 被邀请人奖励
    TYPE_EXCHANGE = 'exchange'      # 兑换消耗
    TYPE_ADMIN = 'admin'            # 管理员调整
    TYPE_RENEW = 'renew'            # 积分续费
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    type = db.Column(db.String(20), nullable=False, comment='类型')
    points = db.Column(db.Integer, nullable=False, comment='变动积分')
    balance = db.Column(db.Integer, nullable=False, comment='变动后余额')
    description = db.Column(db.String(200), nullable=True, comment='描述')
    related_id = db.Column(db.Integer, nullable=True, comment='关联ID')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    # 关联
    user = db.relationship('User', backref=db.backref('point_records', lazy='dynamic', cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'type_text': self.type_text,
            'points': self.points,
            'balance': self.balance,
            'description': self.description,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
    
    @property
    def type_text(self):
        """类型文本"""
        type_map = {
            self.TYPE_SIGNIN: '每日签到',
            self.TYPE_SIGNIN_BONUS: '连续签到奖励',
            self.TYPE_INVITE: '邀请注册奖励',
            self.TYPE_INVITE_RECHARGE: '邀请首充奖励',
            self.TYPE_INVITED: '受邀注册奖励',
            self.TYPE_EXCHANGE: '积分兑换',
            self.TYPE_ADMIN: '管理员调整',
            self.TYPE_RENEW: '积分续费'
        }
        return type_map.get(self.type, self.type)
