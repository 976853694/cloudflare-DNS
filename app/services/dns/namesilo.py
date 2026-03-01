"""
NameSilo DNS 服务实现
"""
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List
import requests

from app.services.dns.base import (
    DnsServiceBase,
    DnsRecord,
    DnsZone,
    DnsLine,
    ProviderCapabilities,
    DnsAuthenticationError,
    DnsApiError
)


class NamesiloService(DnsServiceBase):
    """NameSilo DNS 服务"""
    
    provider_type = 'namesilo'
    provider_name = 'NameSilo'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'username', 'label': '账户名', 'type': 'text', 'required': False,
         'help': 'NameSilo 账户用户名（可选）'},
        {'name': 'api_key', 'label': 'API Key', 'type': 'password', 'required': True,
         'help': '在 NameSilo 账户 API Manager 中生成'}
    ]
    
    def __init__(self, api_key: str = None, username: str = None, **kwargs):
        """初始化 NameSilo 服务"""
        if not api_key:
            raise DnsAuthenticationError('NameSilo', '缺少 API Key')
        
        self.api_key = api_key
        self.username = username  # 可选，用于记录
        self.endpoint = 'https://www.namesilo.com/api'
    
    def _request(self, operation: str, params: Dict = None) -> ET.Element:
        """发送 API 请求"""
        if params is None:
            params = {}
        
        params['version'] = '1'
        params['type'] = 'xml'
        params['key'] = self.api_key
        
        try:
            response = requests.get(
                f"{self.endpoint}/{operation}",
                params=params,
                timeout=30
            )
            
            root = ET.fromstring(response.text)
            
            # 检查响应状态
            reply = root.find('reply')
            if reply is not None:
                code = reply.find('code')
                detail = reply.find('detail')
                
                if code is not None and code.text not in ['300', '301', '302']:
                    error_msg = detail.text if detail is not None else f'错误代码: {code.text}'
                    raise DnsApiError('NameSilo', operation, error_msg)
            
            return root
        except requests.exceptions.RequestException as e:
            raise DnsApiError('NameSilo', operation, f'网络请求失败: {str(e)}')
        except ET.ParseError as e:
            raise DnsApiError('NameSilo', operation, f'XML解析失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('listDomains')
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        root = self._request('listDomains')
        
        zones = []
        domains = root.find('.//domains')
        if domains is not None:
            for domain in domains.findall('domain'):
                domain_name = domain.text
                if keyword and keyword.lower() not in domain_name.lower():
                    continue
                
                zones.append(DnsZone(
                    zone_id=domain_name,
                    name=domain_name,
                    record_count=0,
                    status='active'
                ))
        
        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        
        return {
            'total': len(zones),
            'list': zones[start:end]
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        root = self._request('dnsListRecords', {'domain': zone_id})
        
        records = []
        resource_record = root.find('.//resource_record')
        if resource_record is not None:
            for rr in resource_record.findall('.//resource_record') or [resource_record]:
                # 处理单条和多条记录的情况
                if rr.find('record_id') is None:
                    continue
                    
                record = self._parse_record(rr, zone_id)
                
                # 过滤
                if filters.get('type') and record.type != filters['type']:
                    continue
                if filters.get('subdomain') and filters['subdomain'] not in record.name:
                    continue
                
                records.append(record)
        
        # 尝试另一种 XML 结构
        if not records:
            for rr in root.findall('.//resource_record'):
                record = self._parse_record(rr, zone_id)
                
                if filters.get('type') and record.type != filters['type']:
                    continue
                if filters.get('subdomain') and filters['subdomain'] not in record.name:
                    continue
                
                records.append(record)
        
        return {
            'total': len(records),
            'list': records
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        result = self.get_records(zone_id)
        for record in result['list']:
            if record.record_id == record_id:
                return record
        return None
    
    def _parse_record(self, rr: ET.Element, domain: str) -> DnsRecord:
        """解析记录"""
        record_id = rr.find('record_id').text if rr.find('record_id') is not None else ''
        host = rr.find('host').text if rr.find('host') is not None else ''
        record_type = rr.find('type').text if rr.find('type') is not None else 'A'
        value = rr.find('value').text if rr.find('value') is not None else ''
        ttl = int(rr.find('ttl').text) if rr.find('ttl') is not None else 7200
        distance = rr.find('distance')
        priority = int(distance.text) if distance is not None and distance.text else None
        
        # 提取主机记录名
        if host == domain:
            name = '@'
        elif host.endswith('.' + domain):
            name = host[:-len('.' + domain)]
        else:
            name = host
        
        return DnsRecord(
            record_id=record_id,
            name=name,
            full_name=host,
            type=record_type,
            value=value,
            ttl=ttl,
            priority=priority,
            status='active'
        )
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 7200, **kwargs) -> str:
        """创建记录"""
        params = {
            'domain': zone_id,
            'rrtype': record_type,
            'rrhost': name if name and name != '@' else '',
            'rrvalue': value,
            'rrttl': ttl
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            params['rrdistance'] = kwargs['priority']
        
        root = self._request('dnsAddRecord', params)
        
        # 获取新记录 ID
        record_id = root.find('.//record_id')
        return record_id.text if record_id is not None else ''
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 7200, 
                      **kwargs) -> bool:
        """更新记录"""
        params = {
            'domain': zone_id,
            'rrid': record_id,
            'rrhost': name if name and name != '@' else '',
            'rrvalue': value,
            'rrttl': ttl
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            params['rrdistance'] = kwargs['priority']
        
        self._request('dnsUpdateRecord', params)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        self._request('dnsDeleteRecord', {
            'domain': zone_id,
            'rrid': record_id
        })
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=False,
            supports_weight=False,
            supports_status=False,
            supports_remark=False,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """NameSilo 不支持线路"""
        return []
