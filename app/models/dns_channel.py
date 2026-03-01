"""
DNS 渠道模型
支持多 DNS 服务商的统一渠道管理
"""
import json
from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now
from cryptography.fernet import Fernet
from flask import current_app


class DnsChannel(db.Model):
    """DNS 渠道（服务商账户）"""
    __tablename__ = 'dns_channels'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, comment='所属用户ID，NULL=平台，有值=托管商')
    name = db.Column(db.String(100), nullable=False, comment='渠道名称')
    provider_type = db.Column(db.String(20), nullable=False, comment='服务商类型')
    credentials = db.Column(db.Text, nullable=False, comment='加密凭据JSON')
    status = db.Column(db.SmallInteger, default=1, nullable=False, comment='状态 1=启用 0=禁用')
    config = db.Column(db.Text, nullable=True, comment='渠道配置JSON')
    remark = db.Column(db.String(255), nullable=True, comment='备注')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 关联域名
    domains = db.relationship('Domain', backref='dns_channel', lazy='dynamic',
                             foreign_keys='Domain.dns_channel_id')
    
    # 关联所有者（托管商）
    owner = db.relationship('User', backref=db.backref('owned_channels', lazy='dynamic'))
    
    # 服务商类型映射
    PROVIDER_NAMES = {
        'cloudflare': 'Cloudflare',
        'aliyun': '阿里云 DNS',
        'dnspod': '腾讯云 DNSPod',
        'huawei': '华为云 DNS'
    }
    
    @staticmethod
    def _get_cipher():
        """获取加密器"""
        key = current_app.config.get('SECRET_KEY', 'default-secret-key')
        # 确保 key 是 32 字节的 base64 编码
        import hashlib
        import base64
        key_hash = hashlib.sha256(key.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(key_hash))
    
    def set_credentials(self, creds: dict):
        """加密存储凭据"""
        cipher = self._get_cipher()
        json_str = json.dumps(creds)
        self.credentials = cipher.encrypt(json_str.encode()).decode()
    
    def get_credentials(self) -> dict:
        """解密获取凭据"""
        if not self.credentials:
            return {}
        cipher = self._get_cipher()
        try:
            decrypted = cipher.decrypt(self.credentials.encode())
            return json.loads(decrypted.decode())
        except Exception:
            return {}

    def get_config(self) -> dict:
        """获取渠道配置"""
        if not self.config:
            return {}
        try:
            return json.loads(self.config)
        except Exception:
            return {}
    
    def set_config(self, config: dict):
        """设置渠道配置"""
        self.config = json.dumps(config)
    
    def get_service(self):
        """获取 DNS 服务实例"""
        from app.services.dns import DnsServiceFactory
        credentials = self.get_credentials()
        return DnsServiceFactory.create(self.provider_type, credentials)
    
    def verify_credentials(self) -> bool:
        """验证凭据是否有效"""
        try:
            service = self.get_service()
            return service.verify_credentials()
        except Exception:
            return False
    
    @property
    def provider_name(self) -> str:
        """获取服务商显示名称"""
        return self.PROVIDER_NAMES.get(self.provider_type, self.provider_type)
    
    @property
    def is_active(self) -> bool:
        return self.status == 1
    
    def to_dict(self, include_credentials=False, mask_private=False) -> dict:
        """
        转换为字典
        Args:
            include_credentials: 是否包含凭据信息
            mask_private: 是否隐藏敏感信息
        """
        MASKED = '******'
        data = {
            'id': self.id,
            'owner_id': self.owner_id,
            'is_platform': self.owner_id is None,
            'name': self.name,
            'provider_type': self.provider_type,
            'provider_name': self.provider_name,
            'status': self.status,
            'remark': self.remark,
            'domains_count': self.domains.count(),
            'config': self.get_config(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # 添加所有者信息
        if self.owner:
            data['owner'] = {
                'id': self.owner.id,
                'username': self.owner.username
            }
        
        if include_credentials:
            if mask_private:
                data['credentials'] = {k: MASKED for k in self.get_credentials().keys()}
            else:
                # 部分显示凭据
                creds = self.get_credentials()
                masked_creds = {}
                for k, v in creds.items():
                    if v and len(str(v)) > 10:
                        masked_creds[k] = str(v)[:10] + '...'
                    elif v:
                        masked_creds[k] = '***'
                    else:
                        masked_creds[k] = None
                data['credentials'] = masked_creds
        
        return data
    
    @classmethod
    def get_provider_types(cls) -> list:
        """获取支持的服务商类型列表"""
        return [
            {'type': k, 'name': v}
            for k, v in cls.PROVIDER_NAMES.items()
        ]
    
    @property
    def is_platform_owned(self) -> bool:
        """是否为平台所有"""
        return self.owner_id is None
    
    @property
    def is_host_owned(self) -> bool:
        """是否为托管商所有"""
        return self.owner_id is not None
