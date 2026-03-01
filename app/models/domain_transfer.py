"""
域名转移记录模型
"""
from datetime import datetime
from typing import Dict, Tuple, Optional
from app import db
from app.utils.timezone import now as beijing_now


class DomainTransfer(db.Model):
    """域名转移记录"""
    __tablename__ = 'domain_transfers'
    
    # 状态常量
    STATUS_PENDING = 0      # 待验证
    STATUS_COMPLETED = 1    # 已完成
    STATUS_CANCELLED = 2    # 已取消
    STATUS_EXPIRED = 3      # 已过期
    
    # 状态文本映射
    STATUS_TEXT_MAP = {
        STATUS_PENDING: '待验证',
        STATUS_COMPLETED: '已完成',
        STATUS_CANCELLED: '已取消',
        STATUS_EXPIRED: '已过期'
    }
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subdomain_id = db.Column(db.Integer, db.ForeignKey('subdomains.id', ondelete='CASCADE'), nullable=False, comment='子域名ID')
    subdomain_name = db.Column(db.String(255), nullable=False, comment='子域名全名')
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='原所有者ID')
    from_username = db.Column(db.String(100), nullable=False, comment='原所有者用户名')
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='新所有者ID')
    to_username = db.Column(db.String(100), nullable=False, comment='目标用户名')
    fee_points = db.Column(db.Integer, default=0, nullable=False, comment='手续费（积分）')
    verify_code = db.Column(db.String(10), nullable=True, comment='验证码')
    verify_expires = db.Column(db.DateTime, nullable=True, comment='验证码过期时间')
    code_sent_at = db.Column(db.DateTime, nullable=True, comment='验证码发送时间')
    status = db.Column(db.SmallInteger, default=0, nullable=False, comment='状态：0=待验证，1=已完成，2=已取消，3=已过期')
    remark = db.Column(db.String(500), nullable=True, comment='备注')
    admin_remark = db.Column(db.String(500), nullable=True, comment='管理员备注')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True, comment='完成时间')
    
    # 关联关系
    subdomain = db.relationship('Subdomain', backref=db.backref('transfers', lazy='dynamic'))
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref=db.backref('transfers_out', lazy='dynamic', cascade='all, delete-orphan'))
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref=db.backref('transfers_in', lazy='dynamic'))
    
    def to_dict(self, for_user_id: int = None) -> Dict:
        """
        转换为字典
        
        Args:
            for_user_id: 如果提供，会计算 direction 字段
        """
        data = {
            'id': self.id,
            'subdomain_id': self.subdomain_id,
            'subdomain_name': self.subdomain_name,
            'from_user_id': self.from_user_id,
            'from_username': self.from_username,
            'to_user_id': self.to_user_id,
            'to_username': self.to_username,
            'fee_points': self.fee_points,
            'status': self.status,
            'status_text': self.status_text,
            'remark': self.remark,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'completed_at': self.completed_at.strftime('%Y-%m-%d %H:%M:%S') if self.completed_at else None
        }
        
        # 计算转移方向
        if for_user_id is not None:
            if self.from_user_id == for_user_id:
                data['direction'] = 'out'
                data['counterparty'] = self.to_username
            elif self.to_user_id == for_user_id:
                data['direction'] = 'in'
                data['counterparty'] = self.from_username
            else:
                data['direction'] = 'unknown'
                data['counterparty'] = None
        
        return data
    
    def to_admin_dict(self) -> Dict:
        """管理员视图字典"""
        data = self.to_dict()
        data['verify_code'] = self.verify_code
        data['verify_expires'] = self.verify_expires.strftime('%Y-%m-%d %H:%M:%S') if self.verify_expires else None
        data['code_sent_at'] = self.code_sent_at.strftime('%Y-%m-%d %H:%M:%S') if self.code_sent_at else None
        data['admin_remark'] = self.admin_remark
        return data
    
    @property
    def status_text(self) -> str:
        """状态文本"""
        return self.STATUS_TEXT_MAP.get(self.status, '未知')
    
    @property
    def is_pending(self) -> bool:
        """是否待验证"""
        return self.status == self.STATUS_PENDING
    
    @property
    def is_completed(self) -> bool:
        """是否已完成"""
        return self.status == self.STATUS_COMPLETED
    
    @property
    def is_cancelled(self) -> bool:
        """是否已取消"""
        return self.status == self.STATUS_CANCELLED
    
    @property
    def is_code_expired(self) -> bool:
        """验证码是否已过期"""
        if not self.verify_expires:
            return True
        return beijing_now() > self.verify_expires
    
    @property
    def can_resend_code(self) -> Tuple[bool, int]:
        """
        是否可以重发验证码
        
        Returns:
            Tuple[bool, int]: (可否重发, 剩余等待秒数)
        """
        if not self.is_pending:
            return False, 0
        
        if not self.code_sent_at:
            return True, 0
        
        # 60秒间隔限制
        elapsed = (beijing_now() - self.code_sent_at).total_seconds()
        if elapsed >= 60:
            return True, 0
        
        return False, int(60 - elapsed)
    
    @property
    def expires_in_seconds(self) -> int:
        """验证码剩余有效秒数"""
        if not self.verify_expires:
            return 0
        remaining = (self.verify_expires - beijing_now()).total_seconds()
        return max(0, int(remaining))
    
    def __repr__(self):
        return f'<DomainTransfer {self.id}: {self.subdomain_name} {self.from_username} -> {self.to_username}>'
