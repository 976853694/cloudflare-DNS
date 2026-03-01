"""
托管商提现模型
记录托管商的提现申请和处理状态
"""
from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class HostWithdrawal(db.Model):
    """托管商提现申请"""
    __tablename__ = 'host_withdrawals'
    
    # 状态常量
    STATUS_PENDING = 'pending'      # 待审核
    STATUS_APPROVED = 'approved'    # 已通过
    STATUS_REJECTED = 'rejected'    # 已拒绝
    STATUS_COMPLETED = 'completed'  # 已完成
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    host_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='托管商用户ID')
    amount = db.Column(db.Numeric(10, 2), nullable=False, comment='提现金额')
    status = db.Column(db.String(20), default='pending', nullable=False, comment='提现状态')
    
    # 收款信息
    payment_method = db.Column(db.String(50), nullable=True, comment='收款方式: alipay/wechat/bank')
    payment_account = db.Column(db.String(100), nullable=True, comment='收款账号')
    payment_name = db.Column(db.String(50), nullable=True, comment='收款人姓名')
    
    # 审核信息
    admin_remark = db.Column(db.String(255), nullable=True, comment='管理员备注')
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='审核管理员ID')
    reviewed_at = db.Column(db.DateTime, nullable=True, comment='审核时间')
    completed_at = db.Column(db.DateTime, nullable=True, comment='完成时间')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False, comment='申请时间')
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 关系
    host = db.relationship('User', foreign_keys=[host_id], backref=db.backref('withdrawals', lazy='dynamic', cascade='all, delete-orphan'))
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    def to_dict(self, include_host=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'host_id': self.host_id,
            'amount': float(self.amount) if self.amount else 0,
            'status': self.status,
            'status_text': self.status_text,
            'payment_method': self.payment_method,
            'payment_account': self.payment_account,
            'payment_name': self.payment_name,
            'admin_remark': self.admin_remark,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_host and self.host:
            data['host'] = {
                'id': self.host.id,
                'username': self.host.username,
                'email': self.host.email
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
            'rejected': '已拒绝',
            'completed': '已完成'
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
    
    @property
    def is_completed(self):
        return self.status == self.STATUS_COMPLETED
    
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
    
    def complete(self):
        """标记为已完成"""
        self.status = self.STATUS_COMPLETED
        self.completed_at = beijing_now()
