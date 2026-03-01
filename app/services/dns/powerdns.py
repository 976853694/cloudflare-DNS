"""
PowerDNS DNS 服务实现
支持 PowerDNS Authoritative Server 的 HTTP API
"""
import requests
from typing import Dict, Any, Optional, List

from app.services.dns.base import (
    DnsServiceBase,
    DnsRecord,
    DnsZone,
    DnsLine,
    ProviderCapabilities,
    DnsAuthenticationError,
    DnsApiError
)


class PowerDnsService(DnsServiceBase):
    """PowerDNS DNS 服务"""
    
    provider_type = 'powerdns'
    provider_name = 'PowerDNS'
    
    # 凭据字段定义
    CREDENTIAL_FIELDS = [
        {'name': 'api_url', 'label': 'API 地址', 'type': 'text', 'required': True,
         'help': 'PowerDNS API 地址，如 http://127.0.0.1:8081'},
        {'name': 'api_key', 'label': 'API Key', 'type': 'password', 'required': True,
         'help': 'PowerDNS API Key (在 pdns.conf 中配置的 api-key)'},
        {'name': 'server_id', 'label': '服务器ID', 'type': 'text', 'required': False,
         'help': '服务器ID，默认为 localhost'}
    ]
    
    def __init__(self, api_url: str = None, api_key: str = None, 
                 server_id: str = 'localhost', **kwargs):
        """
        初始化 PowerDNS 服务
        
        Args:
            api_url: PowerDNS API 地址
            api_key: API Key
            server_id: 服务器ID，默认 localhost
        """
        if not api_url or not api_key:
            raise DnsAuthenticationError('PowerDNS', '缺少 API 地址或 API Key')
        
        self.base_url = api_url.rstrip('/')
        self.server_id = server_id or 'localhost'
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def _request(self, method: str, endpoint: str, data: Dict = None,
                 params: Dict = None) -> Any:
        """发送 API 请求"""
        url = f"{self.base_url}/api/v1/servers/{self.server_id}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )
            
            # 204 No Content 表示成功（DELETE 操作）
            if response.status_code == 204:
                return {}
            
            # 检查错误
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', response.text)
                except:
                    error_msg = response.text or f'HTTP {response.status_code}'
                raise DnsApiError('PowerDNS', method, error_msg)
            
            # 空响应
            if not response.text:
                return {}
            
            return response.json()
        except requests.exceptions.RequestException as e:
            raise DnsApiError('PowerDNS', method, f'网络请求失败: {str(e)}')
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            # 获取服务器信息来验证凭据
            url = f"{self.base_url}/api/v1/servers/{self.server_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1,
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        result = self._request('GET', '/zones')
        
        zones = []
        for item in result if isinstance(result, list) else []:
            zone_name = item.get('name', '').rstrip('.')
            
            # 关键字过滤
            if keyword and keyword.lower() not in zone_name.lower():
                continue
            
            zones.append(DnsZone(
                zone_id=item.get('id', zone_name),
                name=zone_name,
                record_count=item.get('rrset_count', 0),
                status='active' if item.get('kind') else 'unknown'
            ))
        
        # 分页
        total = len(zones)
        start = (page - 1) * page_size
        end = start + page_size
        
        return {
            'total': total,
            'list': zones[start:end]
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        # 确保 zone_id 以点结尾（PowerDNS 格式）
        zone_name = zone_id if zone_id.endswith('.') else f"{zone_id}."
        
        result = self._request('GET', f'/zones/{zone_name}')
        
        records = []
        rrsets = result.get('rrsets', [])
        
        for rrset in rrsets:
            record_type = rrset.get('type', '')
            name = rrset.get('name', '').rstrip('.')
            ttl = rrset.get('ttl', 300)
            
            # 类型过滤
            if filters.get('type') and record_type != filters['type']:
                continue
            
            # 提取主机记录
            zone_base = zone_id.rstrip('.')
            if name == zone_base:
                host = '@'
            elif name.endswith(f'.{zone_base}'):
                host = name[:-len(zone_base)-1]
            else:
                host = name
            
            # 子域名过滤
            if filters.get('subdomain'):
                subdomain_filter = filters['subdomain'].lower()
                if subdomain_filter not in host.lower() and subdomain_filter not in name.lower():
                    continue
            
            # 每条 record 是一个值
            for idx, record in enumerate(rrset.get('records', [])):
                content = record.get('content', '')
                disabled = record.get('disabled', False)
                
                # 生成唯一记录ID
                record_id = f"{name}|{record_type}|{idx}"
                
                # 解析 MX 优先级
                priority = None
                if record_type == 'MX' and ' ' in content:
                    parts = content.split(' ', 1)
                    try:
                        priority = int(parts[0])
                        content = parts[1] if len(parts) > 1 else content
                    except ValueError:
                        pass
                
                records.append(DnsRecord(
                    record_id=record_id,
                    name=host,
                    full_name=name,
                    type=record_type,
                    value=content.rstrip('.'),
                    ttl=ttl,
                    priority=priority,
                    status='paused' if disabled else 'active'
                ))
        
        # 关键字过滤
        if filters.get('keyword'):
            keyword = filters['keyword'].lower()
            records = [r for r in records if keyword in r.name.lower() or keyword in r.value.lower()]
        
        # 分页
        page = filters.get('page', 1)
        page_size = filters.get('page_size', 100)
        total = len(records)
        start = (page - 1) * page_size
        end = start + page_size
        
        return {
            'total': total,
            'list': records[start:end]
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录"""
        try:
            result = self.get_records(zone_id)
            for record in result.get('list', []):
                if record.record_id == record_id:
                    return record
            return None
        except:
            return None
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 300, **kwargs) -> str:
        """创建记录"""
        zone_name = zone_id if zone_id.endswith('.') else f"{zone_id}."
        zone_base = zone_id.rstrip('.')
        
        # 构建完整域名
        if name == '@' or name == '':
            full_name = zone_name
        else:
            full_name = f"{name}.{zone_base}."
        
        # 处理 MX 记录优先级
        content = value
        if record_type == 'MX':
            priority = kwargs.get('priority', 10)
            # MX 值需要以点结尾
            if not value.endswith('.'):
                value = f"{value}."
            content = f"{priority} {value}"
        elif record_type in ['CNAME', 'NS']:
            # CNAME/NS 值需要以点结尾
            if not value.endswith('.'):
                content = f"{value}."
        
        # PowerDNS 使用 PATCH 来添加/修改记录
        data = {
            'rrsets': [{
                'name': full_name,
                'type': record_type,
                'ttl': ttl,
                'changetype': 'REPLACE',
                'records': [{
                    'content': content,
                    'disabled': False
                }]
            }]
        }
        
        # 检查是否已存在同类型记录，如果存在则合并
        try:
            existing = self._get_rrset(zone_name, full_name, record_type)
            if existing:
                # 添加到现有记录
                records = existing.get('records', [])
                records.append({'content': content, 'disabled': False})
                data['rrsets'][0]['records'] = records
        except:
            pass
        
        self._request('PATCH', f'/zones/{zone_name}', data=data)
        
        # 返回记录ID
        return f"{full_name.rstrip('.')}|{record_type}|0"
    
    def _get_rrset(self, zone_name: str, name: str, record_type: str) -> Optional[Dict]:
        """获取指定的 RRSet"""
        result = self._request('GET', f'/zones/{zone_name}')
        for rrset in result.get('rrsets', []):
            if rrset.get('name') == name and rrset.get('type') == record_type:
                return rrset
        return None
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 300,
                      **kwargs) -> bool:
        """更新记录"""
        zone_name = zone_id if zone_id.endswith('.') else f"{zone_id}."
        zone_base = zone_id.rstrip('.')
        
        # 解析原记录ID
        parts = record_id.split('|')
        if len(parts) >= 2:
            old_name = parts[0] if parts[0].endswith('.') else f"{parts[0]}."
            old_type = parts[1]
        else:
            old_name = None
            old_type = None
        
        # 构建新的完整域名
        if name == '@' or name == '':
            full_name = zone_name
        else:
            full_name = f"{name}.{zone_base}."
        
        # 处理记录值
        content = value
        if record_type == 'MX':
            priority = kwargs.get('priority', 10)
            if not value.endswith('.'):
                value = f"{value}."
            content = f"{priority} {value}"
        elif record_type in ['CNAME', 'NS']:
            if not value.endswith('.'):
                content = f"{value}."
        
        # 如果名称或类型改变，需要删除旧记录
        if old_name and old_type and (old_name != full_name or old_type != record_type):
            try:
                delete_data = {
                    'rrsets': [{
                        'name': old_name,
                        'type': old_type,
                        'changetype': 'DELETE'
                    }]
                }
                self._request('PATCH', f'/zones/{zone_name}', data=delete_data)
            except:
                pass
        
        # 创建/更新记录
        data = {
            'rrsets': [{
                'name': full_name,
                'type': record_type,
                'ttl': ttl,
                'changetype': 'REPLACE',
                'records': [{
                    'content': content,
                    'disabled': False
                }]
            }]
        }
        
        self._request('PATCH', f'/zones/{zone_name}', data=data)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        zone_name = zone_id if zone_id.endswith('.') else f"{zone_id}."
        
        # 解析记录ID
        parts = record_id.split('|')
        if len(parts) < 2:
            raise DnsApiError('PowerDNS', 'DELETE', '无效的记录ID')
        
        name = parts[0] if parts[0].endswith('.') else f"{parts[0]}."
        record_type = parts[1]
        record_idx = int(parts[2]) if len(parts) > 2 else 0
        
        # 获取当前 RRSet
        rrset = self._get_rrset(zone_name, name, record_type)
        
        if not rrset:
            return True  # 记录不存在，视为删除成功
        
        records = rrset.get('records', [])
        
        if len(records) <= 1:
            # 只有一条记录，删除整个 RRSet
            data = {
                'rrsets': [{
                    'name': name,
                    'type': record_type,
                    'changetype': 'DELETE'
                }]
            }
        else:
            # 多条记录，删除指定的一条
            if 0 <= record_idx < len(records):
                records.pop(record_idx)
            data = {
                'rrsets': [{
                    'name': name,
                    'type': record_type,
                    'ttl': rrset.get('ttl', 300),
                    'changetype': 'REPLACE',
                    'records': records
                }]
            }
        
        self._request('PATCH', f'/zones/{zone_name}', data=data)
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取 PowerDNS 能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=False,
            supports_weight=False,
            supports_status=True,
            supports_remark=False,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA', 'PTR', 'SOA']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """PowerDNS 不支持线路"""
        return []
    
    def set_record_status(self, zone_id: str, record_id: str,
                          enabled: bool) -> bool:
        """设置记录状态"""
        zone_name = zone_id if zone_id.endswith('.') else f"{zone_id}."
        
        # 解析记录ID
        parts = record_id.split('|')
        if len(parts) < 2:
            raise DnsApiError('PowerDNS', 'STATUS', '无效的记录ID')
        
        name = parts[0] if parts[0].endswith('.') else f"{parts[0]}."
        record_type = parts[1]
        record_idx = int(parts[2]) if len(parts) > 2 else 0
        
        # 获取当前 RRSet
        rrset = self._get_rrset(zone_name, name, record_type)
        if not rrset:
            raise DnsApiError('PowerDNS', 'STATUS', '记录不存在')
        
        records = rrset.get('records', [])
        if 0 <= record_idx < len(records):
            records[record_idx]['disabled'] = not enabled
        
        data = {
            'rrsets': [{
                'name': name,
                'type': record_type,
                'ttl': rrset.get('ttl', 300),
                'changetype': 'REPLACE',
                'records': records
            }]
        }
        
        self._request('PATCH', f'/zones/{zone_name}', data=data)
        return True
