from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


# 套餐-域名多对多关联表
plan_domains = db.Table('plan_domains',
    db.Column('plan_id', db.Integer, db.ForeignKey('plans.id', ondelete='CASCADE'), primary_key=True),
    db.Column('domain_id', db.Integer, db.ForeignKey('domains.id', ondelete='CASCADE'), primary_key=True)
)


class Plan(db.Model):
    """套餐模型"""
    __tablename__ = 'plans'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='所属用户ID，NULL=平台，有值=托管商')
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    duration_days = db.Column(db.Integer, default=30, nullable=False)
    min_length = db.Column(db.Integer, default=1, nullable=False)
    max_length = db.Column(db.Integer, default=63, nullable=False)
    max_records = db.Column(db.Integer, default=10, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    status = db.Column(db.SmallInteger, default=1, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    # 免费套餐相关
    is_free = db.Column(db.Boolean, default=False, nullable=False, comment='是否免费套餐')
    max_purchase_count = db.Column(db.Integer, default=0, nullable=False, comment='最大购买次数(0=不限)')
    renew_before_days = db.Column(db.Integer, default=0, nullable=False, comment='到期前多少天可续费(0=不限)')
    points_per_day = db.Column(db.Integer, default=0, nullable=False, comment='每天所需积分(0=不支持积分续费)')
    
    # 上游分销相关
    dns_channel_id = db.Column(db.Integer, db.ForeignKey('dns_channels.id', ondelete='SET NULL'), nullable=True, comment='关联渠道ID')
    upstream_plan_id = db.Column(db.Integer, nullable=True, comment='上游套餐ID')
    upstream_price = db.Column(db.Numeric(10, 2), nullable=True, comment='上游成本价')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 多对多关系：一个套餐可以关联多个域名
    domains = db.relationship('Domain', secondary=plan_domains, lazy='subquery',
                              backref=db.backref('plans', lazy='dynamic'))
    
    dns_channel = db.relationship('DnsChannel', backref=db.backref('plans', lazy='dynamic'))
    
    # 关联所有者（托管商）
    owner = db.relationship('User', backref=db.backref('owned_plans', lazy='dynamic'))
    
    def to_dict(self):
        data = {
            'id': self.id,
            'owner_id': self.owner_id,
            'is_platform': self.owner_id is None,
            'domain_ids': [d.id for d in self.domains],
            'domain_names': [d.name for d in self.domains],
            # 兼容旧版：返回第一个域名ID（如果有）
            'domain_id': self.domains[0].id if self.domains else None,
            'domain_name': ', '.join([d.name for d in self.domains]) if self.domains else None,
            'name': self.name,
            'price': float(self.price),
            'duration_days': self.duration_days,
            'duration_text': '永久' if self.duration_days == -1 else f'{self.duration_days}天',
            'min_length': self.min_length,
            'max_length': self.max_length,
            'max_records': self.max_records,
            'max_records_text': '无限' if self.max_records == -1 else f'{self.max_records}条',
            'description': self.description,
            'status': self.status,
            'sort_order': self.sort_order,
            # 免费套餐相关
            'is_free': self.is_free,
            'max_purchase_count': self.max_purchase_count,
            'renew_before_days': self.renew_before_days,
            'points_per_day': self.points_per_day,
            # 上游分销相关
            'dns_channel_id': self.dns_channel_id,
            'upstream_plan_id': self.upstream_plan_id,
            'upstream_price': float(self.upstream_price) if self.upstream_price else None,
            'is_upstream': self.upstream_plan_id is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        # 添加所有者信息
        if self.owner:
            data['owner'] = {
                'id': self.owner.id,
                'username': self.owner.username
            }
        return data
    
    @property
    def is_active(self):
        return self.status == 1
    
    @property
    def is_permanent(self):
        """是否永久有效"""
        return self.duration_days == -1
    
    @property
    def is_platform_owned(self):
        """是否为平台所有"""
        return self.owner_id is None
    
    @property
    def is_host_owned(self):
        """是否为托管商所有"""
        return self.owner_id is not None
