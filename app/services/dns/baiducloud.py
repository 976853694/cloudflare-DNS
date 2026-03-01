"""
百度云 DNS 服务实现
"""
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import requests
from urllib.parse import quote

from app.services.dns.base import (
    DnsServiceBase,
    DnsRecord,
    DnsZone,
    DnsLine,
    ProviderCapabilities,
    DnsAuthenticationError,
    DnsApiError
)


class BaiducloudService(DnsServiceBase):
    """百度云 DNS 服务"""
    
    provider_type = 'baiducloud'
    provider_name = '百度智能云 DNS'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'access_key', 'label': 'Access Key', 'type': 'text', 'required': True},
        {'name': 'secret_key', 'label': 'Secret Key', 'type': 'password', 'required': True}
    ]
    
    LINE_MAP = {
        'default': '默认',
        'ct': '电信',
        'cnc': '联通',
        'cmnet': '移动',
        'edu': '教育网',
        'oversea': '海外'
    }
    
    def __init__(self, access_key: str = None, secret_key: str = None, **kwargs):
        """初始化百度云 DNS 服务"""
        if not access_key or not secret_key:
            raise DnsAuthenticationError('百度云', '缺少 AccessKey 凭据')
        
        self.access_key = access_key
        self.secret_key = secret_key
        self.endpoint = 'dns.baidubce.com'
        self.region = 'bj'
    
    def _sign(self, method: str, uri: str, params: Dict, headers: Dict) -> str:
        """生成百度云签名"""
        # 时间戳
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # 规范化 URI
        canonical_uri = quote(uri, safe='/')
        
        # 规范化查询字符串
        canonical_qs = '&'.join(f"{quote(k, safe='')}={quote(str(v), safe='')}" 
                                for k, v in sorted(params.items()))
        
        # 规范化请求头
        signed_headers = ['host']
        canonical_headers = f"host:{self.endpoint}"
        
        # 规范化请求
        canonical_request = f"{method}\n{canonical_uri}\n{canonical_qs}\n{canonical_headers}"
        
        # 签名密钥
        auth_string_prefix = f"bce-auth-v1/{self.access_key}/{timestamp}/1800"
        signing_key = hmac.new(
            self.secret_key.encode('utf-8'),
            auth_string_prefix.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # 签名
        signature = hmac.new(
            signing_key.encode('utf-8'),
            canonical_request.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"{auth_string_prefix}/{';'.join(signed_headers)}/{signature}"
    
    def _request(self, method: str, uri: str, params: Dict = None, 
                 data: Dict = None) -> Dict:
        """发送 API 请求"""
        if params is None:
            params = {}
        
        headers = {
            'Host': self.endpoint,
            'Content-Type': 'application/json'
        }
        
        headers['Authorization'] = self._sign(method, uri, params, headers)
        
        url = f"https://{self.endpoint}{uri}"
        if params:
            url += '?' + '&'.join(f"{k}={v}" for k, v in params.items())
        
        try:
            response = requests.request(
                method=method,
                url=url,
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
                raise DnsApiError('百度云', method, msg)
            
            if response.text:
                return response.json()
            return {}
        except requests.exceptions.RequestException as e:
            raise DnsApiError('百度云', method, f'网络请求失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('GET', '/v1/dns/zone', {'pageNo': 1, 'pageSize': 1})
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        params = {
            'pageNo': page,
            'pageSize': page_size
        }
        if keyword:
            params['name'] = keyword
        
        result = self._request('GET', '/v1/dns/zone', params)
        
        zones = []
        for item in result.get('zones', []):
            zones.append(DnsZone(
                zone_id=item['id'],
                name=item['name'].rstrip('.'),
                record_count=item.get('recordCount', 0),
                status='active' if item.get('status') == 'running' else 'paused'
            ))
        
        return {
            'total': result.get('totalCount', len(zones)),
            'list': zones
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        params = {
            'pageNo': filters.get('page', 1),
            'pageSize': filters.get('page_size', 100)
        }
        
        if filters.get('subdomain'):
            params['rr'] = filters['subdomain']
        if filters.get('type'):
            params['type'] = filters['type']
        
        result = self._request('GET', f'/v1/dns/zone/{zone_id}/record', params)
        
        records = []
        for item in result.get('records', []):
            records.append(self._parse_record(item, zone_id))
        
        return {
            'total': result.get('totalCount', len(records)),
            'list': records
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        try:
            result = self._request('GET', f'/v1/dns/zone/{zone_id}/record/{record_id}')
            return self._parse_record(result, zone_id)
        except DnsApiError:
            return None
    
    def _parse_record(self, item: Dict, zone_id: str) -> DnsRecord:
        """解析记录"""
        rr = item.get('rr', '@')
        domain = item.get('zoneName', '').rstrip('.')
        full_name = f"{rr}.{domain}" if rr != '@' else domain
        
        line = item.get('line', 'default')
        
        return DnsRecord(
            record_id=item['id'],
            name=rr,
            full_name=full_name,
            type=item['type'],
            value=item['value'],
            ttl=item.get('ttl', 600),
            priority=item.get('priority'),
            line=line,
            line_name=self.LINE_MAP.get(line, line),
            status='active' if item.get('status') == 'running' else 'paused',
            remark=item.get('description')
        )
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        data = {
            'rr': name if name else '@',
            'type': record_type,
            'value': value,
            'ttl': ttl
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            data['priority'] = kwargs['priority']
        if kwargs.get('line'):
            data['line'] = kwargs['line']
        if kwargs.get('remark'):
            data['description'] = kwargs['remark']
        
        result = self._request('POST', f'/v1/dns/zone/{zone_id}/record', data=data)
        return result.get('id', '')
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录"""
        data = {
            'rr': name if name else '@',
            'type': record_type,
            'value': value,
            'ttl': ttl
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            data['priority'] = kwargs['priority']
        if kwargs.get('line'):
            data['line'] = kwargs['line']
        if kwargs.get('remark'):
            data['description'] = kwargs['remark']
        
        self._request('PUT', f'/v1/dns/zone/{zone_id}/record/{record_id}', data=data)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        self._request('DELETE', f'/v1/dns/zone/{zone_id}/record/{record_id}')
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=True,
            supports_weight=False,
            supports_status=True,
            supports_remark=True,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """获取线路列表"""
        return [DnsLine(line_id=k, name=v) for k, v in self.LINE_MAP.items()]
    
    def set_record_status(self, zone_id: str, record_id: str, 
                          enabled: bool) -> bool:
        """设置记录状态"""
        self._request('PUT', f'/v1/dns/zone/{zone_id}/record/{record_id}/enable' 
                      if enabled else f'/v1/dns/zone/{zone_id}/record/{record_id}/disable')
        return True
