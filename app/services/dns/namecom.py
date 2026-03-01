"""
Name.com DNS 服务实现
"""
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


class NamecomService(DnsServiceBase):
    """Name.com DNS 服务"""
    
    provider_type = 'namecom'
    provider_name = 'Name.com'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'username', 'label': '用户名', 'type': 'text', 'required': True},
        {'name': 'api_token', 'label': 'API Token', 'type': 'password', 'required': True}
    ]
    
    def __init__(self, username: str = None, api_token: str = None, **kwargs):
        """初始化 Name.com 服务"""
        if not username or not api_token:
            raise DnsAuthenticationError('Name.com', '缺少用户名或 API Token')
        
        self.username = username
        self.api_token = api_token
        self.endpoint = 'https://api.name.com/v4'
    
    def _request(self, method: str, uri: str, data: Dict = None) -> Dict:
        """发送 API 请求"""
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.request(
                method=method,
                url=f"{self.endpoint}{uri}",
                headers=headers,
                auth=(self.username, self.api_token),
                json=data if data else None,
                timeout=30
            )
            
            if response.status_code >= 400:
                try:
                    error = response.json()
                    msg = error.get('message', str(error))
                except:
                    msg = response.text or f'HTTP {response.status_code}'
                raise DnsApiError('Name.com', method, msg)
            
            if response.text:
                return response.json()
            return {}
        except requests.exceptions.RequestException as e:
            raise DnsApiError('Name.com', method, f'网络请求失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('GET', '/domains')
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        result = self._request('GET', '/domains')
        
        zones = []
        for item in result.get('domains', []):
            domain = item.get('domainName', '')
            if keyword and keyword.lower() not in domain.lower():
                continue
            
            zones.append(DnsZone(
                zone_id=domain,
                name=domain,
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
        result = self._request('GET', f'/domains/{zone_id}/records')
        
        records = []
        for item in result.get('records', []):
            record = self._parse_record(item, zone_id)
            
            # 过滤
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
        try:
            result = self._request('GET', f'/domains/{zone_id}/records/{record_id}')
            return self._parse_record(result, zone_id)
        except DnsApiError:
            return None
    
    def _parse_record(self, item: Dict, domain: str) -> DnsRecord:
        """解析记录"""
        fqdn = item.get('fqdn', '')
        host = item.get('host', '@')
        
        # 如果 host 为空，设为 @
        if not host:
            host = '@'
        
        full_name = fqdn.rstrip('.') if fqdn else (f"{host}.{domain}" if host != '@' else domain)
        
        return DnsRecord(
            record_id=str(item['id']),
            name=host,
            full_name=full_name,
            type=item['type'],
            value=item['answer'],
            ttl=item.get('ttl', 300),
            priority=item.get('priority'),
            status='active'
        )
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 300, **kwargs) -> str:
        """创建记录"""
        data = {
            'host': name if name and name != '@' else '',
            'type': record_type,
            'answer': value,
            'ttl': ttl
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            data['priority'] = kwargs['priority']
        if record_type == 'SRV':
            data['priority'] = kwargs.get('priority', 0)
            data['weight'] = kwargs.get('weight', 0)
            data['port'] = kwargs.get('port', 0)
        
        result = self._request('POST', f'/domains/{zone_id}/records', data)
        return str(result.get('id', ''))
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 300, 
                      **kwargs) -> bool:
        """更新记录"""
        data = {
            'host': name if name and name != '@' else '',
            'type': record_type,
            'answer': value,
            'ttl': ttl
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            data['priority'] = kwargs['priority']
        
        self._request('PUT', f'/domains/{zone_id}/records/{record_id}', data)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        self._request('DELETE', f'/domains/{zone_id}/records/{record_id}')
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=False,
            supports_weight=False,
            supports_status=False,
            supports_remark=False,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """Name.com 不支持线路"""
        return []
