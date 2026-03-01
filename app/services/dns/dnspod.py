"""
腾讯云 DNSPod 服务实现
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


class DnspodService(DnsServiceBase):
    """腾讯云 DNSPod 服务"""
    
    provider_type = 'dnspod'
    provider_name = '腾讯云 DNSPod'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'secret_id', 'label': 'SecretId', 'type': 'text', 'required': True},
        {'name': 'secret_key', 'label': 'SecretKey', 'type': 'password', 'required': True}
    ]
    
    # 线路代码映射
    LINE_MAP = {
        '0': '默认',
        '10=0': '电信',
        '10=1': '联通',
        '10=3': '移动',
        '10=2': '教育网',
        '3=0': '境外',
        '10=22': '广电网',
        '80=0': '搜索引擎',
        '7=0': '内网'
    }
    
    def __init__(self, secret_id: str = None, secret_key: str = None, **kwargs):
        """初始化 DNSPod 服务"""
        if not secret_id or not secret_key:
            raise DnsAuthenticationError('DNSPod', '缺少 SecretId/SecretKey 凭据')
        
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.endpoint = 'dnspod.tencentcloudapi.com'
        self.service = 'dnspod'
        self.api_version = '2021-03-23'
    
    def _sign(self, timestamp: int, payload: str) -> str:
        """生成腾讯云 API 3.0 签名"""
        date = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d')
        
        # 1. 拼接规范请求串
        canonical_request = (
            f"POST\n/\n\n"
            f"content-type:application/json\n"
            f"host:{self.endpoint}\n"
            f"x-tc-action:describeuserdetail\n\n"
            f"content-type;host;x-tc-action\n"
            f"{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"
        )
        
        # 2. 拼接待签名字符串
        credential_scope = f"{date}/{self.service}/tc3_request"
        string_to_sign = (
            f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )
        
        # 3. 计算签名
        def hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        secret_date = hmac_sha256(f"TC3{self.secret_key}".encode('utf-8'), date)
        secret_service = hmac_sha256(secret_date, self.service)
        secret_signing = hmac_sha256(secret_service, 'tc3_request')
        signature = hmac.new(secret_signing, string_to_sign.encode('utf-8'), 
                           hashlib.sha256).hexdigest()
        
        return signature

    def _request(self, action: str, params: Dict[str, Any] = None) -> Dict:
        """发送 API 请求"""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        payload = json.dumps(params or {})
        date = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d')
        
        # 构建规范请求
        canonical_headers = (
            f"content-type:application/json\n"
            f"host:{self.endpoint}\n"
            f"x-tc-action:{action.lower()}\n"
        )
        signed_headers = "content-type;host;x-tc-action"
        hashed_payload = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        
        # 构建待签名字符串
        credential_scope = f"{date}/{self.service}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()
        string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashed_canonical}"
        
        # 计算签名
        def hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        secret_date = hmac_sha256(f"TC3{self.secret_key}".encode('utf-8'), date)
        secret_service = hmac_sha256(secret_date, self.service)
        secret_signing = hmac_sha256(secret_service, 'tc3_request')
        signature = hmac.new(secret_signing, string_to_sign.encode('utf-8'), 
                           hashlib.sha256).hexdigest()
        
        # 构建 Authorization
        authorization = (
            f"TC3-HMAC-SHA256 Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        
        headers = {
            'Content-Type': 'application/json',
            'Host': self.endpoint,
            'X-TC-Action': action,
            'X-TC-Version': self.api_version,
            'X-TC-Timestamp': str(timestamp),
            'Authorization': authorization
        }
        
        try:
            response = requests.post(
                f"https://{self.endpoint}",
                headers=headers,
                data=payload,
                timeout=30
            )
            result = response.json()
            
            if 'Response' in result:
                if 'Error' in result['Response']:
                    error = result['Response']['Error']
                    raise DnsApiError('DNSPod', action, error.get('Message', '未知错误'))
                return result['Response']
            
            raise DnsApiError('DNSPod', action, '响应格式错误')
        except requests.exceptions.RequestException as e:
            raise DnsApiError('DNSPod', action, f'网络请求失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('DescribeUserDetail')
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        params = {
            'Offset': (page - 1) * page_size,
            'Limit': page_size
        }
        if keyword:
            params['Keyword'] = keyword
        
        result = self._request('DescribeDomainList', params)
        zones = []
        for item in result.get('DomainList', []):
            # DNSPod API 使用域名作为标识，所以 zone_id 存储域名
            zones.append(DnsZone(
                zone_id=item['Name'],  # 使用域名作为 zone_id
                name=item['Name'],
                record_count=item.get('RecordCount', 0),
                status='active' if item.get('Status') == 'ENABLE' else 'paused'
            ))
        
        return {
            'total': result.get('DomainCountInfo', {}).get('AllTotal', len(zones)),
            'list': zones
        }

    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        params = {
            'Domain': zone_id,
            'Offset': (filters.get('page', 1) - 1) * filters.get('page_size', 100),
            'Limit': filters.get('page_size', 100)
        }
        
        if filters.get('keyword'):
            params['Keyword'] = filters['keyword']
        if filters.get('subdomain'):
            params['Subdomain'] = filters['subdomain']
        if filters.get('type'):
            params['RecordType'] = filters['type']
        if filters.get('line'):
            params['RecordLine'] = filters['line']
        
        # 使用 DescribeRecordFilterList 如果有状态或值筛选
        action = 'DescribeRecordList'
        if filters.get('status') is not None or filters.get('value'):
            action = 'DescribeRecordFilterList'
            if filters.get('status') is not None:
                params['RecordStatus'] = ['ENABLE'] if filters['status'] else ['DISABLE']
            if filters.get('value'):
                params['RecordValue'] = filters['value']
        
        result = self._request(action, params)
        records = []
        for item in result.get('RecordList', []):
            records.append(self._parse_record(item, zone_id))
        
        return {
            'total': result.get('RecordCountInfo', {}).get('TotalCount', len(records)),
            'list': records
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        try:
            result = self._request('DescribeRecord', {
                'Domain': zone_id,
                'RecordId': int(record_id)
            })
            return self._parse_record(result.get('RecordInfo', {}), zone_id)
        except DnsApiError:
            return None
    
    def _parse_record(self, item: Dict, domain: str) -> DnsRecord:
        """解析 DNSPod 记录为统一格式"""
        name = item.get('Name', item.get('SubDomain', ''))
        full_name = f"{name}.{domain}" if name != '@' else domain
        line = item.get('Line', item.get('RecordLine', '0'))
        
        return DnsRecord(
            record_id=str(item.get('RecordId', item.get('Id', ''))),
            name=name,
            full_name=full_name,
            type=item.get('Type', item.get('RecordType', '')),
            value=item.get('Value', ''),
            ttl=item.get('TTL', 600),
            priority=item.get('MX'),
            line=line,
            line_name=self.LINE_MAP.get(line, line),
            weight=item.get('Weight'),
            status='active' if item.get('Status', item.get('Enabled')) in ['ENABLE', 1] else 'paused',
            remark=item.get('Remark'),
            update_time=item.get('UpdatedOn')
        )
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        # DNSPod 要求 RecordLine 不能为空，默认使用 '默认' 线路
        line = kwargs.get('line')
        if not line:
            line = '默认'
        
        # DNSPod 免费版最小 TTL 为 600 秒
        if ttl < 600:
            ttl = 600
        
        params = {
            'Domain': zone_id,
            'SubDomain': name,
            'RecordType': record_type,
            'Value': value,
            'TTL': ttl,
            'RecordLine': line
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            params['MX'] = kwargs['priority']
        if kwargs.get('weight') is not None:
            params['Weight'] = kwargs['weight']
        
        result = self._request('CreateRecord', params)
        return str(result.get('RecordId', ''))
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录"""
        # DNSPod 要求 RecordLine 不能为空，默认使用 '默认' 线路
        line = kwargs.get('line')
        if not line:
            line = '默认'
        
        # DNSPod 免费版最小 TTL 为 600 秒
        if ttl < 600:
            ttl = 600
        
        params = {
            'Domain': zone_id,
            'RecordId': int(record_id),
            'SubDomain': name,
            'RecordType': record_type,
            'Value': value,
            'TTL': ttl,
            'RecordLine': line
        }
        
        if record_type == 'MX' and kwargs.get('priority') is not None:
            params['MX'] = kwargs['priority']
        if kwargs.get('weight') is not None:
            params['Weight'] = kwargs['weight']
        
        self._request('ModifyRecord', params)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        self._request('DeleteRecord', {
            'Domain': zone_id,
            'RecordId': int(record_id)
        })
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取 DNSPod 能力"""
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
        self._request('ModifyRecordStatus', {
            'Domain': zone_id,
            'RecordId': int(record_id),
            'Status': 'ENABLE' if enabled else 'DISABLE'
        })
        return True
