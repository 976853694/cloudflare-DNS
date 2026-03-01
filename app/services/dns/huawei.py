"""
华为云 DNS 服务实现
"""
import hmac
import hashlib
import json
from datetime import datetime, timezone
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


class HuaweiService(DnsServiceBase):
    """华为云 DNS 服务"""
    
    provider_type = 'huawei'
    provider_name = '华为云 DNS'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'ak', 'label': 'Access Key (AK)', 'type': 'text', 'required': True},
        {'name': 'sk', 'label': 'Secret Key (SK)', 'type': 'password', 'required': True}
    ]
    
    # 基础线路映射
    LINE_MAP = {
        'default': '默认',
        'Dianxin': '电信',
        'Liantong': '联通',
        'Yidong': '移动',
        'CN': '中国',
        'Abroad': '境外'
    }
    
    def __init__(self, ak: str = None, sk: str = None, **kwargs):
        """初始化华为云 DNS 服务"""
        if not ak or not sk:
            raise DnsAuthenticationError('华为云', '缺少 AK/SK 凭据')
        
        self.ak = ak
        self.sk = sk
        self.endpoint = 'dns.myhuaweicloud.com'
        self.region = 'cn-north-1'
    
    def _sign(self, method: str, uri: str, query: str, headers: Dict, 
              payload: str) -> str:
        """生成华为云 API 签名"""
        # 规范化请求
        canonical_headers = '\n'.join(
            f"{k.lower()}:{v}" for k, v in sorted(headers.items())
        ) + '\n'
        signed_headers = ';'.join(k.lower() for k in sorted(headers.keys()))
        
        hashed_payload = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        canonical_request = f"{method}\n{uri}\n{query}\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        
        # 待签名字符串
        algorithm = 'SDK-HMAC-SHA256'
        timestamp = headers.get('X-Sdk-Date', '')
        hashed_canonical = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        string_to_sign = f"{algorithm}\n{timestamp}\n{hashed_canonical}"
        
        # 计算签名
        signature = hmac.new(
            self.sk.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f"{algorithm} Access={self.ak}, SignedHeaders={signed_headers}, Signature={signature}"

    def _request(self, method: str, uri: str, params: Dict = None, 
                 data: Dict = None) -> Dict:
        """发送 API 请求"""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        
        # 构建查询字符串
        query = ''
        if params:
            query = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
        
        payload = json.dumps(data) if data else ''
        
        headers = {
            'Host': self.endpoint,
            'X-Sdk-Date': timestamp,
            'Content-Type': 'application/json'
        }
        
        # 生成签名
        headers['Authorization'] = self._sign(method, uri, query, headers, payload)
        
        url = f"https://{self.endpoint}{uri}"
        if query:
            url += f"?{query}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=payload if payload else None,
                timeout=30
            )
            
            if response.status_code >= 400:
                try:
                    error = response.json()
                    msg = error.get('message', error.get('error_msg', '未知错误'))
                except:
                    msg = response.text or f'HTTP {response.status_code}'
                raise DnsApiError('华为云', method, msg)
            
            if response.text:
                return response.json()
            return {}
        except requests.exceptions.RequestException as e:
            raise DnsApiError('华为云', method, f'网络请求失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('GET', '/v2/zones', {'limit': 1})
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        params = {
            'type': 'public',
            'limit': page_size,
            'offset': (page - 1) * page_size
        }
        if keyword:
            params['name'] = keyword
        
        result = self._request('GET', '/v2/zones', params)
        zones = []
        for item in result.get('zones', []):
            name = item['name'].rstrip('.')
            zones.append(DnsZone(
                zone_id=item['id'],
                name=name,
                record_count=item.get('record_num', 0),
                status='active' if item.get('status') == 'ACTIVE' else 'paused'
            ))
        
        return {
            'total': result.get('metadata', {}).get('total_count', len(zones)),
            'list': zones
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        params = {
            'limit': filters.get('page_size', 100),
            'offset': (filters.get('page', 1) - 1) * filters.get('page_size', 100)
        }
        
        if filters.get('subdomain'):
            params['name'] = filters['subdomain']
        if filters.get('type'):
            params['type'] = filters['type']
        if filters.get('line'):
            params['line'] = filters['line']
        if filters.get('status') is not None:
            params['status'] = 'ACTIVE' if filters['status'] else 'DISABLE'
        
        result = self._request('GET', f'/v2.1/zones/{zone_id}/recordsets', params)
        records = []
        for item in result.get('recordsets', []):
            records.append(self._parse_record(item))
        
        return {
            'total': result.get('metadata', {}).get('total_count', len(records)),
            'list': records
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        try:
            result = self._request('GET', f'/v2.1/zones/{zone_id}/recordsets/{record_id}')
            return self._parse_record(result)
        except DnsApiError:
            return None

    def _parse_record(self, item: Dict) -> DnsRecord:
        """解析华为云记录为统一格式"""
        full_name = item.get('name', '').rstrip('.')
        # 提取主机记录
        parts = full_name.split('.')
        if len(parts) > 2:
            name = parts[0]
        else:
            name = '@'
        
        # 处理记录值（华为云返回数组）
        records = item.get('records', [])
        value = records[0] if records else ''
        # 去除 TXT 记录的引号
        if item.get('type') == 'TXT' and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        
        line = item.get('line', 'default')
        
        return DnsRecord(
            record_id=item['id'],
            name=name,
            full_name=full_name,
            type=item['type'],
            value=value,
            ttl=item.get('ttl', 600),
            priority=item.get('priority'),
            line=line,
            line_name=self.LINE_MAP.get(line, line),
            weight=item.get('weight'),
            status='active' if item.get('status') == 'ACTIVE' else 'paused',
            remark=item.get('description'),
            update_time=item.get('updated_at')
        )
    
    def _build_name(self, name: str, zone_id: str) -> str:
        """构建完整域名（华为云要求以.结尾）"""
        # 需要先获取域名
        zone = self._request('GET', f'/v2/zones/{zone_id}')
        domain = zone.get('name', '').rstrip('.')
        
        if name == '@' or not name:
            return f"{domain}."
        return f"{name}.{domain}."
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        full_name = self._build_name(name, zone_id)
        
        # 处理记录值
        records = [value]
        if record_type == 'TXT':
            records = [f'"{value}"']
        elif record_type == 'MX' and kwargs.get('priority') is not None:
            records = [f"{kwargs['priority']} {value}"]
        
        data = {
            'name': full_name,
            'type': record_type,
            'records': records,
            'ttl': ttl
        }
        
        if kwargs.get('line'):
            data['line'] = kwargs['line']
        if kwargs.get('weight') is not None:
            data['weight'] = kwargs['weight']
        if kwargs.get('remark'):
            data['description'] = kwargs['remark']
        
        result = self._request('POST', f'/v2.1/zones/{zone_id}/recordsets', data=data)
        return result.get('id', '')
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录"""
        full_name = self._build_name(name, zone_id)
        
        # 处理记录值
        records = [value]
        if record_type == 'TXT':
            records = [f'"{value}"']
        elif record_type == 'MX' and kwargs.get('priority') is not None:
            records = [f"{kwargs['priority']} {value}"]
        
        data = {
            'name': full_name,
            'type': record_type,
            'records': records,
            'ttl': ttl
        }
        
        if kwargs.get('line'):
            data['line'] = kwargs['line']
        if kwargs.get('weight') is not None:
            data['weight'] = kwargs['weight']
        if kwargs.get('remark'):
            data['description'] = kwargs['remark']
        
        self._request('PUT', f'/v2.1/zones/{zone_id}/recordsets/{record_id}', data=data)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        self._request('DELETE', f'/v2.1/zones/{zone_id}/recordsets/{record_id}')
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取华为云能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=True,
            supports_weight=True,
            supports_status=True,
            supports_remark=True,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA']
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
        self._request('PUT', f'/v2.1/recordsets/{record_id}/statuses/set', data={
            'status': 'ENABLE' if enabled else 'DISABLE'
        })
        return True
