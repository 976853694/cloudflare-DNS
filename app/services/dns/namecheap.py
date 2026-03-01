"""
Namecheap DNS 服务实现
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


class NamecheapService(DnsServiceBase):
    """Namecheap DNS 服务"""
    
    provider_type = 'namecheap'
    provider_name = 'Namecheap'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'api_user', 'label': 'API User', 'type': 'text', 'required': True},
        {'name': 'api_key', 'label': 'API Key', 'type': 'password', 'required': True},
        {'name': 'client_ip', 'label': '白名单IP', 'type': 'text', 'required': True,
         'help': '需要在Namecheap后台添加到白名单的服务器IP'}
    ]
    
    def __init__(self, api_user: str = None, api_key: str = None, 
                 client_ip: str = None, **kwargs):
        """初始化 Namecheap 服务"""
        if not api_user or not api_key:
            raise DnsAuthenticationError('Namecheap', '缺少 API 用户名或 Key')
        
        self.api_user = api_user
        self.api_key = api_key
        self.client_ip = client_ip or '127.0.0.1'
        self.endpoint = 'https://api.namecheap.com/xml.response'
    
    def _request(self, command: str, params: Dict = None) -> ET.Element:
        """发送 API 请求"""
        base_params = {
            'ApiUser': self.api_user,
            'ApiKey': self.api_key,
            'UserName': self.api_user,
            'ClientIp': self.client_ip,
            'Command': command
        }
        
        if params:
            base_params.update(params)
        
        try:
            response = requests.get(self.endpoint, params=base_params, timeout=30)
            root = ET.fromstring(response.text)
            
            # 检查错误
            status = root.get('Status')
            if status != 'OK':
                errors = root.find('.//Errors')
                if errors is not None:
                    error = errors.find('Error')
                    if error is not None:
                        raise DnsApiError('Namecheap', command, error.text)
                raise DnsApiError('Namecheap', command, '未知错误')
            
            return root
        except requests.exceptions.RequestException as e:
            raise DnsApiError('Namecheap', command, f'网络请求失败: {str(e)}')
        except ET.ParseError as e:
            raise DnsApiError('Namecheap', command, f'XML解析失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('namecheap.domains.getList', {'PageSize': 1})
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        params = {
            'Page': page,
            'PageSize': page_size
        }
        if keyword:
            params['SearchTerm'] = keyword
        
        root = self._request('namecheap.domains.getList', params)
        
        zones = []
        for domain in root.findall('.//Domain'):
            name = domain.get('Name', '')
            zones.append(DnsZone(
                zone_id=name,
                name=name,
                record_count=0,
                status='active' if domain.get('IsExpired') == 'false' else 'expired'
            ))
        
        # 获取总数
        paging = root.find('.//Paging')
        total = int(paging.find('TotalItems').text) if paging is not None else len(zones)
        
        return {
            'total': total,
            'list': zones
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        # 分离 SLD 和 TLD
        parts = zone_id.rsplit('.', 1)
        if len(parts) != 2:
            raise DnsApiError('Namecheap', 'getHosts', '无效的域名格式')
        
        sld, tld = parts
        
        root = self._request('namecheap.domains.dns.getHosts', {
            'SLD': sld,
            'TLD': tld
        })
        
        records = []
        for idx, host in enumerate(root.findall('.//host')):
            record = self._parse_record(host, zone_id, idx)
            
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
        result = self.get_records(zone_id)
        for record in result['list']:
            if record.record_id == record_id:
                return record
        return None
    
    def _parse_record(self, host: ET.Element, domain: str, idx: int) -> DnsRecord:
        """解析记录"""
        name = host.get('Name', '@')
        record_type = host.get('Type', 'A')
        full_name = f"{name}.{domain}" if name != '@' else domain
        
        return DnsRecord(
            record_id=f"{idx}_{record_type}_{name}",
            name=name,
            full_name=full_name,
            type=record_type,
            value=host.get('Address', ''),
            ttl=int(host.get('TTL', 1800)),
            priority=int(host.get('MXPref', 0)) if record_type == 'MX' else None,
            status='active'
        )
    
    def _get_all_records(self, zone_id: str) -> List[Dict]:
        """获取所有记录（用于更新）"""
        result = self.get_records(zone_id)
        records = []
        for r in result['list']:
            rec = {
                'HostName': r.name,
                'RecordType': r.type,
                'Address': r.value,
                'TTL': r.ttl
            }
            if r.type == 'MX' and r.priority:
                rec['MXPref'] = r.priority
            records.append(rec)
        return records
    
    def _set_hosts(self, zone_id: str, records: List[Dict]) -> None:
        """设置所有记录"""
        parts = zone_id.rsplit('.', 1)
        if len(parts) != 2:
            raise DnsApiError('Namecheap', 'setHosts', '无效的域名格式')
        
        sld, tld = parts
        
        params = {
            'SLD': sld,
            'TLD': tld
        }
        
        for idx, rec in enumerate(records, 1):
            params[f'HostName{idx}'] = rec['HostName']
            params[f'RecordType{idx}'] = rec['RecordType']
            params[f'Address{idx}'] = rec['Address']
            params[f'TTL{idx}'] = rec.get('TTL', 1800)
            if rec.get('MXPref'):
                params[f'MXPref{idx}'] = rec['MXPref']
        
        self._request('namecheap.domains.dns.setHosts', params)
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 1800, **kwargs) -> str:
        """创建记录"""
        records = self._get_all_records(zone_id)
        
        new_record = {
            'HostName': name if name else '@',
            'RecordType': record_type,
            'Address': value,
            'TTL': ttl
        }
        if record_type == 'MX' and kwargs.get('priority') is not None:
            new_record['MXPref'] = kwargs['priority']
        
        records.append(new_record)
        self._set_hosts(zone_id, records)
        
        return f"{len(records)-1}_{record_type}_{name}"
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 1800, 
                      **kwargs) -> bool:
        """更新记录"""
        records = self._get_all_records(zone_id)
        
        # 解析 record_id
        parts = record_id.split('_', 2)
        if len(parts) >= 1:
            idx = int(parts[0])
            if 0 <= idx < len(records):
                records[idx] = {
                    'HostName': name if name else '@',
                    'RecordType': record_type,
                    'Address': value,
                    'TTL': ttl
                }
                if record_type == 'MX' and kwargs.get('priority') is not None:
                    records[idx]['MXPref'] = kwargs['priority']
        
        self._set_hosts(zone_id, records)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        records = self._get_all_records(zone_id)
        
        # 解析 record_id
        parts = record_id.split('_', 2)
        if len(parts) >= 1:
            idx = int(parts[0])
            if 0 <= idx < len(records):
                records.pop(idx)
        
        self._set_hosts(zone_id, records)
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=False,
            supports_weight=False,
            supports_status=False,
            supports_remark=False,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'URL', 'URL301', 'FRAME']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """Namecheap 不支持线路"""
        return []
