"""
免费套餐申请模型
"""
from app import db
from app.utils.timezone import now as beijing_now


class FreePlanApplication(db.Model):
    """免费套餐申请表"""
    __tablename__ = 'free_plan_applications'
    
    # 申请状态常量
    STATUS_PENDING = 'pending'      # 待审核
    STATUS_APPROVED = 'approved'    # 已通过
    STATUS_REJECTED = 'rejected'    # 已拒绝
    STATUS_CANCELLED = 'cancelled'  # 已取消
    STATUS_USED = 'used'            # 已使用
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='申请用户ID')
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id', ondelete='CASCADE'), nullable=False, comment='申请的套餐ID')
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id', ondelete='SET NULL'), nullable=True, comment='选择的域名ID')
    subdomain_name = db.Column(db.String(63), nullable=False, comment='域名前缀（必填）')
    
    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False, comment='申请状态')
    apply_reason = db.Column(db.Text, nullable=False, comment='申请理由')
    admin_note = db.Column(db.Text, nullable=True, comment='管理员备注')
    rejection_reason = db.Column(db.Text, nullable=True, comment='拒绝原因')
    
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='审核人ID')
    reviewed_at = db.Column(db.DateTime, nullable=True, comment='审核时间')
    
    # 托管商审核相关字段
    host_review_status = db.Column(db.String(20), nullable=True, comment='托管商审核状态')
    host_reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='托管商审核人ID')
    host_reviewed_at = db.Column(db.DateTime, nullable=True, comment='托管商审核时间')
    host_rejection_reason = db.Column(db.Text, nullable=True, comment='托管商拒绝原因')
    host_admin_note = db.Column(db.Text, nullable=True, comment='托管商备注')
    
    ip_address = db.Column(db.String(45), nullable=True, comment='申请时的IP地址')
    user_info_snapshot = db.Column(db.Text, nullable=True, comment='用户信息快照(JSON)')
    
    # 自动开通相关字段
    provision_attempted = db.Column(db.SmallInteger, default=0, nullable=False, comment='是否尝试过自动开通 0=否 1=是')
    provision_error = db.Column(db.Text, nullable=True, comment='自动开通失败原因')
    subdomain_id = db.Column(db.Integer, db.ForeignKey('subdomains.id', ondelete='SET NULL'), nullable=True, comment='自动创建的子域名ID')
    
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False, comment='申请时间')
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False, comment='更新时间')
    
    # 关系
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('free_plan_applications', lazy='dynamic', cascade='all, delete-orphan'))
    plan = db.relationship('Plan', backref=db.backref('applications', lazy='dynamic', cascade='all, delete-orphan'))
    domain = db.relationship('Domain', backref=db.backref('plan_applications', lazy='dynamic'))
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    host_reviewer = db.relationship('User', foreign_keys=[host_reviewed_by])
    subdomain = db.relationship('Subdomain', foreign_keys=[subdomain_id], backref=db.backref('free_plan_application', uselist=False))
    
    def to_dict(self, include_user=False, include_plan=False):
        """转换为字典"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'plan_id': self.plan_id,
            'domain_id': self.domain_id,
            'subdomain_name': self.subdomain_name,
            'status': self.status,
            'status_text': self.get_status_text(),
            'apply_reason': self.apply_reason,
            'admin_note': self.admin_note,
            'rejection_reason': self.rejection_reason,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            # 托管商审核信息
            'host_review_status': self.host_review_status,
            'host_review_status_text': self.get_host_review_status_text(),
            'host_reviewed_by': self.host_reviewed_by,
            'host_reviewed_at': self.host_reviewed_at.isoformat() if self.host_reviewed_at else None,
            'host_rejection_reason': self.host_rejection_reason,
            'host_admin_note': self.host_admin_note,
            # 其他信息
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'provision_attempted': self.provision_attempted,
            'provision_error': self.provision_error,
            'subdomain_id': self.subdomain_id,
        }
        
        # 包含用户信息
        if include_user and self.user:
            data['user'] = {
                'id': self.user.id,
                'username': self.user.username,
                'email': self.user.email,
                'phone': self.user.phone,
                'created_at': self.user.created_at.isoformat() if self.user.created_at else None
            }
        
        # 包含套餐信息
        if include_plan and self.plan:
            data['plan'] = {
                'id': self.plan.id,
                'name': self.plan.name,
                'duration_days': self.plan.duration_days,
                'max_records': self.plan.max_records,
                'owner_id': self.plan.owner_id,
                'is_host_owned': self.plan.is_host_owned
            }
            # 包含套餐所有者信息
            if self.plan.owner:
                data['plan']['owner'] = {
                    'id': self.plan.owner.id,
                    'username': self.plan.owner.username
                }
        
        # 包含域名信息
        if self.domain:
            data['domain'] = {
                'id': self.domain.id,
                'name': self.domain.name
            }
        
        # 包含管理员审核人信息
        if self.reviewer:
            data['reviewer'] = {
                'id': self.reviewer.id,
                'username': self.reviewer.username
            }
        
        # 包含托管商审核人信息
        if self.host_reviewer:
            data['host_reviewer'] = {
                'id': self.host_reviewer.id,
                'username': self.host_reviewer.username
            }
        
        # 包含子域名信息
        if self.subdomain:
            data['subdomain'] = {
                'id': self.subdomain.id,
                'name': self.subdomain.name,
                'full_name': self.subdomain.full_name
            }
        
        return data
    
    def get_status_text(self):
        """获取状态文本"""
        status_map = {
            self.STATUS_PENDING: '待审核',
            self.STATUS_APPROVED: '已通过',
            self.STATUS_REJECTED: '已拒绝',
            self.STATUS_CANCELLED: '已取消',
            self.STATUS_USED: '已使用'
        }
        return status_map.get(self.status, '未知')
    
    def get_host_review_status_text(self):
        """获取托管商审核状态文本"""
        if self.host_review_status is None:
            return '待审核'
        elif self.host_review_status == 'approved':
            return '已通过'
        elif self.host_review_status == 'rejected':
            return '已拒绝'
        return '未知'
    
    @property
    def is_pending(self):
        """是否待审核"""
        return self.status == self.STATUS_PENDING
    
    @property
    def is_approved(self):
        """是否已通过"""
        return self.status == self.STATUS_APPROVED
    
    @property
    def is_rejected(self):
        """是否已拒绝"""
        return self.status == self.STATUS_REJECTED
    
    @property
    def is_used(self):
        """是否已使用"""
        return self.status == self.STATUS_USED
    
    @property
    def can_cancel(self):
        """是否可以取消"""
        return self.status == self.STATUS_PENDING
    
    @property
    def can_use(self):
        """是否可以使用"""
        return self.status == self.STATUS_APPROVED
    
    @property
    def is_host_reviewed(self):
        """托管商是否已审核"""
        return self.host_review_status is not None
    
    @property
    def is_host_approved(self):
        """托管商是否已通过"""
        return self.host_review_status == 'approved'
    
    @property
    def is_host_rejected(self):
        """托管商是否已拒绝"""
        return self.host_review_status == 'rejected'
    
    @property
    def is_admin_reviewed(self):
        """管理员是否已审核"""
        return self.reviewed_by is not None
    
    @property
    def needs_host_review(self):
        """是否需要托管商审核"""
        # 只有托管商套餐需要托管商审核
        return self.plan and self.plan.is_host_owned and not self.is_host_reviewed
