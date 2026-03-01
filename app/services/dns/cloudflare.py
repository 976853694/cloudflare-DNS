"""
Cloudflare DNS 服务实现
"""
import requests
from typing import Dict, Any, Optional, List
from flask import current_app

from app.services.dns.base import (
    DnsServiceBase,
    DnsRecord,
    DnsZone,
    DnsLine,
    ProviderCapabilities,
    DnsAuthenticationError,
    DnsApiError
)


class CloudflareService(DnsServiceBase):
    """Cloudflare DNS 服务"""
    
    provider_type = 'cloudflare'
    provider_name = 'Cloudflare'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'api_key', 'label': 'API Key', 'type': 'password', 'required': True,
         'help': 'Global API Key'},
        {'name': 'email', 'label': 'Email', 'type': 'text', 'required': True,
         'help': 'Cloudflare 账户邮箱'}
    ]
    
    def __init__(self, api_key: str = None, email: str = None, **kwargs):
        """
        初始化 Cloudflare 服务
        
        使用 API Key + Email 认证方式
        """
        self.base_url = 'https://api.cloudflare.com/client/v4'
        
        if api_key and email:
            self.headers = {
                'X-Auth-Key': api_key,
                'X-Auth-Email': email,
                'Content-Type': 'application/json'
            }
        else:
            raise DnsAuthenticationError('Cloudflare', '缺少 API Key 或 Email')
    
    def _request(self, method: str, endpoint: str, data: Dict = None, 
                 params: Dict = None) -> Any:
        """发送 API 请求"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )
            result = response.json()
            
            if not result.get('success', False):
                errors = result.get('errors', [])
                error_msg = errors[0].get('message', '未知错误') if errors else '未知错误'
                raise DnsApiError('Cloudflare', method, error_msg)
            
            return result
        except requests.exceptions.RequestException as e:
            raise DnsApiError('Cloudflare', method, f'网络请求失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            # 使用 API Key + Email 认证方式
            result = self._request('GET', '/user')
            return result.get('result', {}).get('id') is not None
        except DnsApiError:
            return False

    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        params = {
            'page': page,
            'per_page': page_size
        }
        if keyword:
            params['name'] = keyword
        
        result = self._request('GET', '/zones', params=params)
        zones = []
        for item in result.get('result', []):
            zones.append(DnsZone(
                zone_id=item['id'],
                name=item['name'],
                record_count=item.get('meta', {}).get('dns_records_count', 0),
                status=item.get('status', 'active')
            ))
        
        result_info = result.get('result_info', {})
        return {
            'total': result_info.get('total_count', len(zones)),
            'list': zones
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        params = {
            'page': filters.get('page', 1),
            'per_page': filters.get('page_size', 100)
        }
        
        if filters.get('subdomain'):
            params['name'] = filters['subdomain']
        if filters.get('type'):
            params['type'] = filters['type']
        
        result = self._request('GET', f'/zones/{zone_id}/dns_records', params=params)
        records = []
        for item in result.get('result', []):
            records.append(self._parse_record(item))
        
        result_info = result.get('result_info', {})
        return {
            'total': result_info.get('total_count', len(records)),
            'list': records
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        try:
            result = self._request('GET', f'/zones/{zone_id}/dns_records/{record_id}')
            return self._parse_record(result.get('result', {}))
        except DnsApiError:
            return None
    
    def _parse_record(self, item: Dict) -> DnsRecord:
        """解析 Cloudflare 记录为统一格式"""
        name = item.get('name', '')
        zone_name = item.get('zone_name', '')
        
        # 提取主机记录
        if zone_name and name.endswith(f'.{zone_name}'):
            host = name[:-len(zone_name)-1]
        elif name == zone_name:
            host = '@'
        else:
            host = name
        
        return DnsRecord(
            record_id=item['id'],
            name=host,
            full_name=name,
            type=item['type'],
            value=item['content'],
            ttl=item.get('ttl', 1),
            proxied=item.get('proxied', False),
            priority=item.get('priority'),
            status='active' if not item.get('locked') else 'locked',
            update_time=item.get('modified_on')
        )
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        # 确保 proxied 参数为布尔值，默认为 False
        proxied = kwargs.get('proxied')
        if proxied is None:
            proxied = False
        proxied = bool(proxied)
        
        data = {
            'type': record_type,
            'name': name,
            'content': value,
            'ttl': ttl if ttl > 0 else 1,  # Cloudflare 1=auto
            'proxied': proxied
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            data['priority'] = kwargs['priority']
        
        result = self._request('POST', f'/zones/{zone_id}/dns_records', data=data)
        return result.get('result', {}).get('id', '')
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录"""
        # 确保 proxied 参数为布尔值，默认为 False
        proxied = kwargs.get('proxied')
        if proxied is None:
            proxied = False
        proxied = bool(proxied)
        
        data = {
            'type': record_type,
            'name': name,
            'content': value,
            'ttl': ttl if ttl > 0 else 1,
            'proxied': proxied
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            data['priority'] = kwargs['priority']
        
        self._request('PUT', f'/zones/{zone_id}/dns_records/{record_id}', data=data)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        self._request('DELETE', f'/zones/{zone_id}/dns_records/{record_id}')
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取 Cloudflare 能力"""
        return ProviderCapabilities(
            supports_proxy=True,
            supports_line=False,
            supports_weight=False,
            supports_status=False,
            supports_remark=False,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """Cloudflare 不支持线路"""
        return []
