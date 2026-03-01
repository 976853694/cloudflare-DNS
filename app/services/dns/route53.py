"""
AWS Route53 DNS 服务实现
"""
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import requests
import xml.etree.ElementTree as ET

from app.services.dns.base import (
    DnsServiceBase,
    DnsRecord,
    DnsZone,
    DnsLine,
    ProviderCapabilities,
    DnsAuthenticationError,
    DnsApiError
)


class Route53Service(DnsServiceBase):
    """AWS Route53 DNS 服务"""
    
    provider_type = 'route53'
    provider_name = 'AWS Route53'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'access_key_id', 'label': 'Access Key ID', 'type': 'text', 'required': True},
        {'name': 'secret_access_key', 'label': 'Secret Access Key', 'type': 'password', 'required': True},
        {'name': 'region', 'label': 'Region', 'type': 'text', 'required': False,
         'help': '默认 us-east-1'}
    ]
    
    def __init__(self, access_key_id: str = None, secret_access_key: str = None, 
                 region: str = 'us-east-1', **kwargs):
        """初始化 Route53 服务"""
        if not access_key_id or not secret_access_key:
            raise DnsAuthenticationError('Route53', '缺少 AWS 凭据')
        
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.region = region
        self.service = 'route53'
        self.host = 'route53.amazonaws.com'
        self.endpoint = f'https://{self.host}'
    
    def _sign(self, method: str, uri: str, headers: Dict, payload: str = '') -> Dict:
        """AWS Signature Version 4"""
        t = datetime.now(timezone.utc)
        amz_date = t.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = t.strftime('%Y%m%d')
        
        # 规范请求
        canonical_headers = '\n'.join(f"{k.lower()}:{v}" for k, v in sorted(headers.items())) + '\n'
        signed_headers = ';'.join(k.lower() for k in sorted(headers.keys()))
        payload_hash = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        canonical_request = f"{method}\n{uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        
        # 待签名字符串
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        
        # 计算签名
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()
        
        k_date = sign(('AWS4' + self.secret_access_key).encode('utf-8'), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, self.service)
        k_signing = sign(k_service, 'aws4_request')
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()
        
        auth_header = f"{algorithm} Credential={self.access_key_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        
        return {
            'x-amz-date': amz_date,
            'Authorization': auth_header
        }
    
    def _request(self, method: str, uri: str, payload: str = '') -> str:
        """发送 API 请求"""
        headers = {
            'Host': self.host,
            'Content-Type': 'application/xml'
        }
        
        auth_headers = self._sign(method, uri, headers, payload)
        headers.update(auth_headers)
        
        try:
            response = requests.request(
                method=method,
                url=f"{self.endpoint}{uri}",
                headers=headers,
                data=payload if payload else None,
                timeout=30
            )
            
            if response.status_code >= 400:
                raise DnsApiError('Route53', method, f'HTTP {response.status_code}: {response.text[:200]}')
            
            return response.text
        except requests.exceptions.RequestException as e:
            raise DnsApiError('Route53', method, f'网络请求失败: {str(e)}')
    
    def _parse_xml(self, xml_str: str) -> ET.Element:
        """解析 XML 响应"""
        # 移除命名空间
        xml_str = xml_str.replace('xmlns="https://route53.amazonaws.com/doc/2013-04-01/"', '')
        return ET.fromstring(xml_str)
    
    def verify_credentials(self) -> bool:
        """验证凭据"""
        try:
            self._request('GET', '/2013-04-01/hostedzone?maxitems=1')
            return True
        except DnsApiError:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """获取域名列表"""
        result = self._request('GET', '/2013-04-01/hostedzone')
        root = self._parse_xml(result)
        
        zones = []
        for hz in root.findall('.//HostedZone'):
            zone_id = hz.find('Id').text.replace('/hostedzone/', '')
            name = hz.find('Name').text.rstrip('.')
            
            if keyword and keyword.lower() not in name.lower():
                continue
            
            zones.append(DnsZone(
                zone_id=zone_id,
                name=name,
                record_count=int(hz.find('ResourceRecordSetCount').text),
                status='active'
            ))
        
        # 简单分页
        start = (page - 1) * page_size
        end = start + page_size
        
        return {
            'total': len(zones),
            'list': zones[start:end]
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        result = self._request('GET', f'/2013-04-01/hostedzone/{zone_id}/rrset')
        root = self._parse_xml(result)
        
        records = []
        for rrs in root.findall('.//ResourceRecordSet'):
            record = self._parse_record(rrs, zone_id)
            if record:
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
        # Route53 没有单独获取记录的 API，需要从列表中查找
        result = self.get_records(zone_id)
        for record in result['list']:
            if record.record_id == record_id:
                return record
        return None
    
    def _parse_record(self, rrs: ET.Element, zone_id: str) -> Optional[DnsRecord]:
        """解析记录"""
        name = rrs.find('Name').text.rstrip('.')
        record_type = rrs.find('Type').text
        
        # 跳过 SOA 和 NS 根记录
        if record_type in ['SOA']:
            return None
        
        ttl_elem = rrs.find('TTL')
        ttl = int(ttl_elem.text) if ttl_elem is not None else 300
        
        # 获取记录值
        values = []
        for rr in rrs.findall('.//ResourceRecord/Value'):
            values.append(rr.text)
        
        if not values:
            return None
        
        value = values[0]
        priority = None
        if record_type == 'MX':
            parts = value.split(' ', 1)
            if len(parts) == 2:
                priority = int(parts[0])
                value = parts[1]
        
        # 生成唯一 ID
        record_id = hashlib.md5(f"{name}:{record_type}:{value}".encode()).hexdigest()[:16]
        
        # 提取主机记录
        parts = name.split('.')
        host = parts[0] if len(parts) > 2 else '@'
        
        return DnsRecord(
            record_id=record_id,
            name=host,
            full_name=name,
            type=record_type,
            value=value,
            ttl=ttl,
            priority=priority,
            status='active'
        )
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        # 获取域名
        zones = self.get_zones()
        domain = None
        for z in zones['list']:
            if z.zone_id == zone_id:
                domain = z.name
                break
        
        if not domain:
            raise DnsApiError('Route53', 'CreateRecord', '找不到域名')
        
        full_name = f"{name}.{domain}" if name and name != '@' else domain
        
        # 处理 MX 记录
        record_value = value
        if record_type == 'MX' and kwargs.get('priority') is not None:
            record_value = f"{kwargs['priority']} {value}"
        
        xml_payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<ChangeResourceRecordSetsRequest xmlns="https://route53.amazonaws.com/doc/2013-04-01/">
    <ChangeBatch>
        <Changes>
            <Change>
                <Action>CREATE</Action>
                <ResourceRecordSet>
                    <Name>{full_name}.</Name>
                    <Type>{record_type}</Type>
                    <TTL>{ttl}</TTL>
                    <ResourceRecords>
                        <ResourceRecord>
                            <Value>{record_value}</Value>
                        </ResourceRecord>
                    </ResourceRecords>
                </ResourceRecordSet>
            </Change>
        </Changes>
    </ChangeBatch>
</ChangeResourceRecordSetsRequest>'''
        
        self._request('POST', f'/2013-04-01/hostedzone/{zone_id}/rrset', xml_payload)
        return hashlib.md5(f"{full_name}:{record_type}:{value}".encode()).hexdigest()[:16]
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录 - Route53 需要先删除再创建"""
        # 先获取旧记录
        old_record = self.get_record(zone_id, record_id)
        if old_record:
            try:
                self.delete_record(zone_id, record_id)
            except:
                pass
        
        self.create_record(zone_id, name, record_type, value, ttl, **kwargs)
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        record = self.get_record(zone_id, record_id)
        if not record:
            return True
        
        record_value = record.value
        if record.type == 'MX' and record.priority:
            record_value = f"{record.priority} {record.value}"
        
        xml_payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<ChangeResourceRecordSetsRequest xmlns="https://route53.amazonaws.com/doc/2013-04-01/">
    <ChangeBatch>
        <Changes>
            <Change>
                <Action>DELETE</Action>
                <ResourceRecordSet>
                    <Name>{record.full_name}.</Name>
                    <Type>{record.type}</Type>
                    <TTL>{record.ttl}</TTL>
                    <ResourceRecords>
                        <ResourceRecord>
                            <Value>{record_value}</Value>
                        </ResourceRecord>
                    </ResourceRecords>
                </ResourceRecordSet>
            </Change>
        </Changes>
    </ChangeBatch>
</ChangeResourceRecordSetsRequest>'''
        
        self._request('POST', f'/2013-04-01/hostedzone/{zone_id}/rrset', xml_payload)
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取能力"""
        return ProviderCapabilities(
            supports_proxy=False,
            supports_line=False,
            supports_weight=True,
            supports_status=False,
            supports_remark=False,
            supported_types=['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA', 'PTR']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """Route53 不支持线路"""
        return []
