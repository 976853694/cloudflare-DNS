from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class Subdomain(db.Model):
    __tablename__ = 'subdomains'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id', ondelete='CASCADE'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id', ondelete='SET NULL'), nullable=True)
    name = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(150), unique=True, nullable=False)
    cf_record_id = db.Column(db.String(50), nullable=True)
    status = db.Column(db.SmallInteger, default=1, nullable=False)
    auto_renew = db.Column(db.SmallInteger, default=0, nullable=False)  # 0=关闭, 1=开启自动续费
    ns_mode = db.Column(db.SmallInteger, default=0, nullable=False)  # 0=使用Cloudflare NS, 1=已转移NS
    ns_servers = db.Column(db.String(500), nullable=True)  # 用户设置的NS服务器(JSON格式)
    ns_changed_at = db.Column(db.DateTime, nullable=True)  # NS修改时间
    upstream_subdomain_id = db.Column(db.Integer, nullable=True, comment='上游子域名ID（六趣DNS分销）')
    first_record_at = db.Column(db.DateTime, nullable=True, comment='首次添加DNS记录时间')
    last_record_activity_at = db.Column(db.DateTime, nullable=True, comment='最后DNS记录活动时间')
    idle_reminder_sent_at = db.Column(db.DateTime, nullable=True, comment='空置提醒邮件发送时间')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    plan = db.relationship('Plan', backref=db.backref('subdomains', lazy='dynamic'))
    
    __table_args__ = (
        db.UniqueConstraint('domain_id', 'name', name='uk_domain_name'),
    )
    
    records = db.relationship('DnsRecord', backref='subdomain', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, include_records=False, mask_private=False):
        """
        转换为字典
        Args:
            include_records: 是否包含DNS记录
            mask_private: 是否隐藏敏感信息（演示用户使用）
        """
        MASKED = '******'
        data = {
            'id': self.id,
            'name': MASKED if mask_private else self.name,
            'full_name': MASKED if mask_private else self.full_name,
            'domain': {
                'id': self.domain.id,
                'name': MASKED if mask_private else self.domain.name
            } if self.domain else None,
            'plan': {
                'id': self.plan.id,
                'name': self.plan.name
            } if self.plan else None,
            'status': self.status,
            'auto_renew': self.auto_renew,
            'records_count': self.records.count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired,
            'days_remaining': self.days_remaining,
            'ns_mode': self.ns_mode,
            'ns_servers': [MASKED] if mask_private and self.ns_servers_list else self.ns_servers_list,
            'ns_changed_at': self.ns_changed_at.isoformat() if self.ns_changed_at else None,
            'upstream_subdomain_id': self.upstream_subdomain_id,
            'is_upstream': self.upstream_subdomain_id is not None,
            'first_record_at': self.first_record_at.isoformat() if self.first_record_at else None,
            'last_record_activity_at': self.last_record_activity_at.isoformat() if self.last_record_activity_at else None,
            'idle_reminder_sent_at': self.idle_reminder_sent_at.isoformat() if self.idle_reminder_sent_at else None
        }
        if include_records:
            data['records'] = [r.to_dict(mask_private=mask_private) for r in self.records.all()]
        return data
    
    @property
    def is_active(self):
        return self.status == 1
    
    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return beijing_now() > self.expires_at
    
    @property
    def days_remaining(self):
        """剩余天数"""
        if self.expires_at is None:
            return None
        delta = self.expires_at - beijing_now()
        days = delta.days
        return max(0, days)
    
    @property
    def ns_servers_list(self):
        """获取NS服务器列表"""
        if not self.ns_servers:
            return []
        import json
        try:
            return json.loads(self.ns_servers)
        except:
            return []
    
    @property
    def is_ns_transferred(self):
        """是否已转移NS"""
        return self.ns_mode == 1
    
    @property
    def full_domain(self):
        """完整域名（full_name 的别名）"""
        return self.full_name
    
    @property
    def is_idle(self):
        """是否空置（无DNS记录）"""
        return self.records.count() == 0
    
    @property
    def idle_days(self):
        """空置天数（从注册到现在）"""
        if not self.is_idle:
            return 0
        from app.utils.timezone import now as beijing_now
        delta = beijing_now() - self.created_at
        return delta.days
