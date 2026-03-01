"""
GoDaddy DNS 服务实现
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


class GodaddyService(DnsServiceBase):
    """GoDaddy DNS 服务"""
    
    provider_type = 'godaddy'
    provider_name = 'GoDaddy'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'api_key', 'label': 'API Key', 'type': 'text', 'required': True},
        {'name': 'api_secret', 'label': 'API Secret', 'type': 'password', 'required': True}
    ]
    
    def __init__(self, api_key: str = None, api_secret: str = None, **kwargs):
        """初始化 GoDaddy 服务"""
        if not api_key or not api_secret:
            raise DnsAuthenticationError('GoDaddy', '缺少 API Key 或 Secret')
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.endpoint = 'https://api.godaddy.com/v1'
    
    def _request(self, method: str, uri: str, data: Any = None) -> Any:
        """发送 API 请求"""
        headers = {
            'Authorization': f'sso-key {self.api_key}:{self.api_secret}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            response = requests.request(
                method=method,
                url=f"{self.endpoint}{uri}",
                headers=headers,
                json=data if data else None,
                timeout=30
            )
            
            if response.status_code >= 400:
                try:
                    error = response.json()
                    msg = error.get('message', str(error))
                except:
                    msg = response.text or f'HTTP {response.status_code}'
                raise DnsApiError('GoDaddy', method, msg)
            
            if response.text:
                return response.json()
            return {}
        except requests.exceptions.RequestException as e:
            raise DnsApiError('GoDaddy', method, f'网络请求失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('GET', '/domains?limit=1')
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        result = self._request('GET', '/domains')
        
        zones = []
        for item in result:
            domain = item.get('domain', '')
            if keyword and keyword.lower() not in domain.lower():
                continue
            
            zones.append(DnsZone(
                zone_id=domain,
                name=domain,
                record_count=0,
                status='active' if item.get('status') == 'ACTIVE' else 'paused'
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
        uri = f'/domains/{zone_id}/records'
        if filters.get('type'):
            uri += f"/{filters['type']}"
            if filters.get('subdomain'):
                uri += f"/{filters['subdomain']}"
        
        result = self._request('GET', uri)
        
        records = []
        for idx, item in enumerate(result):
            record = self._parse_record(item, zone_id, idx)
            if filters.get('subdomain') and not filters.get('type'):
                if filters['subdomain'] not in record.name:
                    continue
            records.append(record)
        
        return {
            'total': len(records),
            'list': records
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        # GoDaddy 没有单独获取记录的 API
        result = self.get_records(zone_id)
        for record in result['list']:
            if record.record_id == record_id:
                return record
        return None
    
    def _parse_record(self, item: Dict, domain: str, idx: int) -> DnsRecord:
        """解析记录"""
        name = item.get('name', '@')
        full_name = f"{name}.{domain}" if name != '@' else domain
        
        # GoDaddy 没有记录 ID，使用索引和内容生成
        record_id = f"{item['type']}_{name}_{idx}"
        
        return DnsRecord(
            record_id=record_id,
            name=name,
            full_name=full_name,
            type=item['type'],
            value=item['data'],
            ttl=item.get('ttl', 600),
            priority=item.get('priority'),
            status='active'
        )
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        record_data = [{
            'type': record_type,
            'name': name if name else '@',
            'data': value,
            'ttl': ttl
        }]
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            record_data[0]['priority'] = kwargs['priority']
        if record_type == 'SRV':
            record_data[0]['priority'] = kwargs.get('priority', 0)
            record_data[0]['weight'] = kwargs.get('weight', 0)
            record_data[0]['port'] = kwargs.get('port', 0)
        
        self._request('PATCH', f'/domains/{zone_id}/records', record_data)
        return f"{record_type}_{name}_new"
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录"""
        record_data = [{
            'data': value,
            'ttl': ttl
        }]
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            record_data[0]['priority'] = kwargs['priority']
        
        self._request('PUT', f'/domains/{zone_id}/records/{record_type}/{name}', record_data)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        # 解析 record_id 获取类型和名称
        parts = record_id.split('_')
        if len(parts) >= 2:
            record_type = parts[0]
            name = parts[1]
            self._request('DELETE', f'/domains/{zone_id}/records/{record_type}/{name}')
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
        """GoDaddy 不支持线路"""
        return []
