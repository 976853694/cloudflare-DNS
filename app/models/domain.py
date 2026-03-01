from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class Domain(db.Model):
    __tablename__ = 'domains'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='所属用户ID，NULL=平台，有值=托管商')
    cf_account_id = db.Column(db.Integer, db.ForeignKey('cf_accounts.id', ondelete='SET NULL'), nullable=True)
    dns_channel_id = db.Column(db.Integer, db.ForeignKey('dns_channels.id', ondelete='SET NULL'), nullable=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    cf_zone_id = db.Column(db.String(50), nullable=True)  # 改为可空，兼容新渠道
    zone_id = db.Column(db.String(100), nullable=True, comment='DNS Zone ID（通用）')
    upstream_domain_id = db.Column(db.Integer, nullable=True, comment='上游域名ID（六趣DNS分销）')
    status = db.Column(db.SmallInteger, default=1, nullable=False)
    allow_register = db.Column(db.SmallInteger, default=1, nullable=False)
    allow_ns_transfer = db.Column(db.SmallInteger, default=1, nullable=False, comment='是否允许NS转移 (1允许/0禁止)')
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    subdomains = db.relationship('Subdomain', backref='domain', lazy='dynamic', cascade='all, delete-orphan')
    
    # 关联所有者（托管商）
    owner = db.relationship('User', backref=db.backref('owned_domains', lazy='dynamic'))
    
    def to_dict(self, include_stats=False, mask_private=False):
        """
        转换为字典
        Args:
            include_stats: 是否包含统计信息
            mask_private: 是否隐藏敏感信息（演示用户使用）
        """
        MASKED = '******'
        data = {
            'id': self.id,
            'owner_id': self.owner_id,
            'is_platform': self.owner_id is None,
            'name': MASKED if mask_private else self.name,
            'status': self.status,
            'allow_register': self.allow_register == 1,
            'allow_ns_transfer': self.allow_ns_transfer == 1,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_stats:
            data['subdomain_count'] = self.subdomains.count()
        # 添加所有者信息
        if self.owner:
            data['owner'] = {
                'id': self.owner.id,
                'username': self.owner.username
            }
        return data
    
    def to_admin_dict(self, mask_private=False):
        """管理员视图字典，支持隐藏敏感信息"""
        MASKED = '******'
        data = self.to_dict(include_stats=True, mask_private=mask_private)
        data['cf_zone_id'] = MASKED if mask_private else self.cf_zone_id
        data['zone_id'] = MASKED if mask_private else (self.zone_id or self.cf_zone_id)
        data['cf_account_id'] = self.cf_account_id
        data['dns_channel_id'] = self.dns_channel_id
        data['upstream_domain_id'] = self.upstream_domain_id
        data['is_upstream'] = self.upstream_domain_id is not None
        data['is_host_owned'] = self.owner_id is not None
        data['cf_account'] = {
            'id': self.cf_account.id,
            'name': self.cf_account.name
        } if self.cf_account else None
        data['dns_channel'] = {
            'id': self.dns_channel.id,
            'name': self.dns_channel.name,
            'provider_type': self.dns_channel.provider_type,
            'provider_name': self.dns_channel.provider_name
        } if self.dns_channel else None
        # 便捷字段：直接获取服务商名称
        data['provider_name'] = (
            self.dns_channel.provider_name if self.dns_channel 
            else ('Cloudflare' if self.cf_account else None)
        )
        data['provider_type'] = (
            self.dns_channel.provider_type if self.dns_channel 
            else ('cloudflare' if self.cf_account else None)
        )
        return data
    
    @property
    def is_active(self):
        return self.status == 1
    
    @property
    def can_register(self):
        return self.allow_register == 1 and self.is_active
    
    def get_dns_service(self):
        """获取域名对应的 DNS 服务实例"""
        # 优先使用新的 dns_channel
        if self.dns_channel:
            return self.dns_channel.get_service()
        # 兼容旧的 cf_account
        if self.cf_account:
            from app.services.dns import DnsServiceFactory
            creds = {}
            if self.cf_account.api_key and self.cf_account.email:
                creds = {'api_key': self.cf_account.api_key, 'email': self.cf_account.email}
            elif self.cf_account.api_token:
                creds = {'api_token': self.cf_account.api_token}
            try:
                return DnsServiceFactory.create('cloudflare', creds)
            except Exception:
                return None
        return None
    
    def get_zone_id(self) -> str:
        """
        获取 Zone ID（兼容新旧字段和不同服务商）
        
        - Cloudflare: 使用实际的 zone_id（32位十六进制字符串）
        - 阿里云/DNSPod: 使用域名作为标识符
        - 华为云: 使用实际的 zone_id
        """
        zone_id = self.zone_id or self.cf_zone_id or ''
        
        # 如果有 dns_channel，根据服务商类型决定返回值
        if self.dns_channel:
            provider_type = self.dns_channel.provider_type
            # 阿里云和 DNSPod 使用域名作为 API 标识符
            if provider_type in ('aliyun', 'dnspod'):
                # 如果 zone_id 是纯数字（旧格式），返回域名
                if zone_id.isdigit():
                    return self.name
                # 否则返回 zone_id（可能已经是域名）
                return zone_id or self.name
        
        return zone_id

    @property
    def is_platform_owned(self):
        """是否为平台所有"""
        return self.owner_id is None
    
    @property
    def is_host_owned(self):
        """是否为托管商所有"""
        return self.owner_id is not None
