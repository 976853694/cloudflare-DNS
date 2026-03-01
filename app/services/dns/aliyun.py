"""
阿里云 DNS 服务实现
使用官方 SDK alibabacloud-alidns20150109
"""
from typing import Dict, Any, Optional, List

from alibabacloud_alidns20150109.client import Client as AlidnsClient
from alibabacloud_alidns20150109 import models as alidns_models
from alibabacloud_tea_openapi import models as open_api_models
from Tea.exceptions import TeaException

from app.services.dns.base import (
    DnsServiceBase,
    DnsRecord,
    DnsZone,
    DnsLine,
    ProviderCapabilities,
    DnsAuthenticationError,
    DnsApiError,
    DnsUnsupportedError
)


class AliyunService(DnsServiceBase):
    """阿里云 DNS 服务"""
    
    provider_type = 'aliyun'
    provider_name = '阿里云 DNS'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'access_key_id', 'label': 'AccessKey ID', 'type': 'text', 'required': True},
        {'name': 'access_key_secret', 'label': 'AccessKey Secret', 'type': 'password', 'required': True}
    ]
    
    # 线路代码映射
    LINE_MAP = {
        'default': '默认',
        'telecom': '电信',
        'unicom': '联通',
        'mobile': '移动',
        'edu': '教育网',
        'oversea': '境外',
        'btvn': '广电网',
        'search': '搜索引擎'
    }
    
    def __init__(self, access_key_id: str = None, access_key_secret: str = None, **kwargs):
        """初始化阿里云 DNS 服务"""
        if not access_key_id or not access_key_secret:
            raise DnsAuthenticationError('阿里云', '缺少 AccessKey 凭据')
        
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        
        # 创建 SDK 客户端
        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint='alidns.cn-hangzhou.aliyuncs.com'
        )
        self.client = AlidnsClient(config)
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            request = alidns_models.DescribeDomainsRequest(
                page_number=1,
                page_size=1
            )
            self.client.describe_domains(request)
            return True
        except TeaException as e:
            if 'InvalidAccessKeyId' in str(e.code) or 'SignatureDoesNotMatch' in str(e.code):
                return False
            # 其他错误也返回 False
            return False
        except Exception:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        try:
            request = alidns_models.DescribeDomainsRequest(
                page_number=page,
                page_size=page_size,
                key_word=keyword
            )
            response = self.client.describe_domains(request)
            
            zones = []
            if response.body.domains and response.body.domains.domain:
                for item in response.body.domains.domain:
                    zones.append(DnsZone(
                        zone_id=item.domain_name,  # 使用域名作为 zone_id
                        name=item.domain_name,
                        record_count=item.record_count or 0,
                        status='active'
                    ))
            
            return {
                'total': response.body.total_count or len(zones),
                'list': zones
            }
        except TeaException as e:
            raise DnsApiError('阿里云', 'DescribeDomains', str(e.message))

    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        try:
            request = alidns_models.DescribeDomainRecordsRequest(
                domain_name=zone_id,
                page_number=filters.get('page', 1),
                page_size=filters.get('page_size', 100)
            )
            
            if filters.get('keyword'):
                request.key_word = filters['keyword']
            if filters.get('subdomain'):
                # 阿里云使用 RRKeyWord 参数过滤主机记录
                request.rrkey_word = filters['subdomain']
            if filters.get('type'):
                request.type_key_word = filters['type']
            if filters.get('status') is not None:
                request.status = 'Enable' if filters['status'] else 'Disable'
            
            response = self.client.describe_domain_records(request)
            
            records = []
            if response.body.domain_records and response.body.domain_records.record:
                for item in response.body.domain_records.record:
                    records.append(self._parse_record(item, zone_id))
            
            return {
                'total': response.body.total_count or len(records),
                'list': records
            }
        except TeaException as e:
            raise DnsApiError('阿里云', 'DescribeDomainRecords', str(e.message))
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        try:
            request = alidns_models.DescribeDomainRecordInfoRequest(
                record_id=record_id
            )
            response = self.client.describe_domain_record_info(request)
            return self._parse_record_info(response.body, zone_id)
        except TeaException:
            return None
    
    def _parse_record(self, item, domain: str) -> DnsRecord:
        """解析阿里云记录为统一格式（从列表返回）"""
        name = item.rr or ''
        full_name = f"{name}.{domain}" if name != '@' else domain
        
        return DnsRecord(
            record_id=item.record_id,
            name=name,
            full_name=full_name,
            type=item.type,
            value=item.value,
            ttl=item.ttl or 600,
            priority=item.priority,
            line=item.line or 'default',
            line_name=self.LINE_MAP.get(item.line or 'default', item.line or '默认'),
            weight=item.weight,
            status='active' if item.status == 'ENABLE' else 'paused',
            remark=item.remark,
            update_time=None
        )
    
    def _parse_record_info(self, item, domain: str) -> DnsRecord:
        """解析阿里云记录为统一格式（从详情返回）"""
        name = item.rr or ''
        full_name = f"{name}.{domain}" if name != '@' else domain
        
        return DnsRecord(
            record_id=item.record_id,
            name=name,
            full_name=full_name,
            type=item.type,
            value=item.value,
            ttl=item.ttl or 600,
            priority=item.priority,
            line=item.line or 'default',
            line_name=self.LINE_MAP.get(item.line or 'default', item.line or '默认'),
            weight=None,
            status='active' if item.status == 'ENABLE' else 'paused',
            remark=None,
            update_time=None
        )

    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        try:
            request = alidns_models.AddDomainRecordRequest(
                domain_name=zone_id,
                rr=name,
                type=record_type,
                value=value,
                ttl=ttl
            )
            
            # 只有明确指定了有效线路才设置
            line = kwargs.get('line')
            if line and line != 'default' and line in self.LINE_MAP:
                request.line = self.LINE_MAP.get(line, line)
            
            if record_type == 'MX' and kwargs.get('priority') is not None:
                request.priority = kwargs['priority']
            if kwargs.get('weight') is not None:
                request.weight = kwargs['weight']
            
            response = self.client.add_domain_record(request)
            return response.body.record_id or ''
        except TeaException as e:
            raise DnsApiError('阿里云', 'AddDomainRecord', str(e.message))
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录"""
        if not record_id:
            raise DnsApiError('阿里云', 'UpdateDomainRecord', '记录ID不能为空')
        
        try:
            request = alidns_models.UpdateDomainRecordRequest(
                record_id=record_id,
                rr=name,
                type=record_type,
                value=value,
                ttl=ttl
            )
            
            # 只有明确指定了有效线路才设置
            line = kwargs.get('line')
            if line and line != 'default' and line in self.LINE_MAP:
                request.line = self.LINE_MAP.get(line, line)
            
            if record_type == 'MX' and kwargs.get('priority') is not None:
                request.priority = kwargs['priority']
            if kwargs.get('weight') is not None:
                request.weight = kwargs['weight']
            
            self.client.update_domain_record(request)
            return True
        except TeaException as e:
            raise DnsApiError('阿里云', 'UpdateDomainRecord', str(e.message))
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        try:
            request = alidns_models.DeleteDomainRecordRequest(
                record_id=record_id
            )
            self.client.delete_domain_record(request)
            return True
        except TeaException as e:
            raise DnsApiError('阿里云', 'DeleteDomainRecord', str(e.message))
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取阿里云能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=True,
            supports_weight=True,
            supports_status=True,
            supports_remark=True,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA', 
                           'REDIRECT_URL', 'FORWARD_URL']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """获取线路列表"""
        lines = []
        for line_id, name in self.LINE_MAP.items():
            lines.append(DnsLine(line_id=line_id, name=name))
        return lines
    
    def set_record_status(self, zone_id: str, record_id: str, 
                          enabled: bool) -> bool:
        """设置记录状态"""
        try:
            request = alidns_models.SetDomainRecordStatusRequest(
                record_id=record_id,
                status='Enable' if enabled else 'Disable'
            )
            self.client.set_domain_record_status(request)
            return True
        except TeaException as e:
            raise DnsApiError('阿里云', 'SetDomainRecordStatus', str(e.message))
