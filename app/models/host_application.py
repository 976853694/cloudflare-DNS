"""
托管商申请模型
记录用户申请成为托管商的申请记录
"""
from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class HostApplication(db.Model):
    """托管商申请记录"""
    __tablename__ = 'host_applications'
    
    # 状态常量
    STATUS_PENDING = 'pending'    # 待审核
    STATUS_APPROVED = 'approved'  # 已通过
    STATUS_REJECTED = 'rejected'  # 已拒绝
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='申请用户ID')
    reason = db.Column(db.Text, nullable=False, comment='申请理由')
    status = db.Column(db.String(20), default='pending', nullable=False, comment='申请状态')
    admin_remark = db.Column(db.String(255), nullable=True, comment='管理员备注/拒绝原因')
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='审核管理员ID')
    reviewed_at = db.Column(db.DateTime, nullable=True, comment='审核时间')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False, comment='申请时间')
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 关系
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('host_applications', lazy='dynamic', cascade='all, delete-orphan'))
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    def to_dict(self, include_user=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'reason': self.reason,
            'status': self.status,
            'status_text': self.status_text,
            'admin_remark': self.admin_remark,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_user and self.user:
            data['user'] = {
                'id': self.user.id,
                'username': self.user.username,
                'email': self.user.email
            }
        if self.reviewer:
            data['reviewer'] = {
                'id': self.reviewer.id,
                'username': self.reviewer.username
            }
        return data
    
    @property
    def status_text(self):
        """状态文本"""
        status_map = {
            'pending': '待审核',
            'approved': '已通过',
            'rejected': '已拒绝'
        }
        return status_map.get(self.status, self.status)
    
    @property
    def is_pending(self):
        return self.status == self.STATUS_PENDING
    
    @property
    def is_approved(self):
        return self.status == self.STATUS_APPROVED
    
    @property
    def is_rejected(self):
        return self.status == self.STATUS_REJECTED
    
    def approve(self, admin_id, remark=None):
        """审核通过"""
        self.status = self.STATUS_APPROVED
        self.reviewed_by = admin_id
        self.reviewed_at = beijing_now()
        if remark:
            self.admin_remark = remark
    
    def reject(self, admin_id, remark):
        """审核拒绝"""
        self.status = self.STATUS_REJECTED
        self.reviewed_by = admin_id
        self.reviewed_at = beijing_now()
        self.admin_remark = remark
