"""
西部数码 DNS 服务实现
"""
import hashlib
import time
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


class WestcnService(DnsServiceBase):
    """西部数码 DNS 服务"""
    
    provider_type = 'westcn'
    provider_name = '西部数码'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'username', 'label': '用户名', 'type': 'text', 'required': True,
         'help': '西部数码账户用户名'},
        {'name': 'api_password', 'label': 'API密码', 'type': 'password', 'required': True,
         'help': '在控制台设置的API密码'}
    ]
    
    LINE_MAP = {
        'default': '默认',
        'telecom': '电信',
        'unicom': '联通',
        'mobile': '移动',
        'edu': '教育网'
    }
    
    def __init__(self, username: str = None, api_password: str = None, **kwargs):
        """初始化西部数码 DNS 服务"""
        if not username or not api_password:
            raise DnsAuthenticationError('西部数码', '缺少用户名或API密码')
        
        self.username = username
        self.api_password = api_password
        self.endpoint = 'https://api.west.cn/api/v2'
    
    def _sign(self, params: Dict) -> str:
        """生成签名"""
        params['username'] = self.username
        params['time'] = str(int(time.time()))
        
        # 按key排序拼接
        sorted_params = sorted(params.items())
        sign_str = '&'.join(f"{k}={v}" for k, v in sorted_params)
        sign_str += self.api_password
        
        return hashlib.md5(sign_str.encode('utf-8')).hexdigest()
    
    def _request(self, action: str, params: Dict = None) -> Dict:
        """发送 API 请求"""
        if params is None:
            params = {}
        
        params['act'] = action
        params['username'] = self.username
        params['time'] = str(int(time.time()))
        params['token'] = self._sign(params.copy())
        
        try:
            response = requests.post(self.endpoint, data=params, timeout=30)
            result = response.json()
            
            if result.get('result') != 200:
                raise DnsApiError('西部数码', action, result.get('msg', '未知错误'))
            
            return result.get('data', {})
        except requests.exceptions.RequestException as e:
            raise DnsApiError('西部数码', action, f'网络请求失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('getdomains', {'limit': 1})
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        params = {'page': page, 'limit': page_size}
        if keyword:
            params['domain'] = keyword
        
        result = self._request('getdomains', params)
        zones = []
        for item in result.get('items', []):
            zones.append(DnsZone(
                zone_id=item['domain'],
                name=item['domain'],
                record_count=item.get('record_count', 0),
                status='active'
            ))
        
        return {
            'total': result.get('total', len(zones)),
            'list': zones
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        params = {
            'domain': zone_id,
            'page': filters.get('page', 1),
            'limit': filters.get('page_size', 100)
        }
        
        if filters.get('subdomain'):
            params['host'] = filters['subdomain']
        if filters.get('type'):
            params['type'] = filters['type']
        
        result = self._request('getdnsrecord', params)
        records = []
        for item in result.get('items', []):
            records.append(self._parse_record(item, zone_id))
        
        return {
            'total': result.get('total', len(records)),
            'list': records
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        try:
            result = self._request('getdnsrecord', {
                'domain': zone_id,
                'id': record_id
            })
            items = result.get('items', [])
            if items:
                return self._parse_record(items[0], zone_id)
            return None
        except DnsApiError:
            return None
    
    def _parse_record(self, item: Dict, domain: str) -> DnsRecord:
        """解析记录为统一格式"""
        name = item.get('host', '@')
        full_name = f"{name}.{domain}" if name != '@' else domain
        
        return DnsRecord(
            record_id=str(item['id']),
            name=name,
            full_name=full_name,
            type=item['type'],
            value=item['value'],
            ttl=item.get('ttl', 600),
            priority=item.get('mx_priority'),
            line=item.get('line', 'default'),
            line_name=self.LINE_MAP.get(item.get('line', 'default'), '默认'),
            status='active' if item.get('pause') == 0 else 'paused'
        )
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        params = {
            'domain': zone_id,
            'host': name if name else '@',
            'type': record_type,
            'value': value,
            'ttl': ttl
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            params['level'] = kwargs['priority']
        if kwargs.get('line'):
            params['line'] = kwargs['line']
        
        result = self._request('adddnsrecord', params)
        return str(result.get('id', ''))
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录"""
        params = {
            'domain': zone_id,
            'id': record_id,
            'host': name if name else '@',
            'type': record_type,
            'value': value,
            'ttl': ttl
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            params['level'] = kwargs['priority']
        if kwargs.get('line'):
            params['line'] = kwargs['line']
        
        self._request('moddnsrecord', params)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        self._request('deldnsrecord', {'domain': zone_id, 'id': record_id})
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=True,
            supports_weight=False,
            supports_status=True,
            supports_remark=False,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """获取线路列表"""
        return [DnsLine(line_id=k, name=v) for k, v in self.LINE_MAP.items()]
