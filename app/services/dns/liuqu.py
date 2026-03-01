"""
六趣DNS服务商 - 对接其他六趣DNS实例的开放API
"""
import hmac
import hashlib
import time
import json
import requests
from typing import Dict, Any, List, Optional

from app.services.dns.base import (
    DnsServiceBase, DnsRecord, DnsZone, DnsLine,
    ProviderCapabilities, DnsAuthenticationError, DnsApiError
)


class LiuquDNSService(DnsServiceBase):
    """六趣DNS服务 - 对接其他六趣DNS实例"""
    
    provider_type = 'liuqu'
    provider_name = '六趣DNS'
    
    # 凭据字段定义（插件模式）
    CREDENTIAL_FIELDS = [
        {'name': 'api_url', 'label': 'API地址', 'type': 'text', 'required': True,
         'help': '上游六趣DNS站点地址，如 https://dns.example.com'},
        {'name': 'api_key', 'label': 'API Key', 'type': 'text', 'required': True,
         'help': '上游站点的用户API Key'},
        {'name': 'api_secret', 'label': 'API Secret', 'type': 'password', 'required': True,
         'help': '上游站点的用户API Secret'}
    ]
    
    def __init__(self, api_url: str, api_key: str, api_secret: str):
        """
        初始化六趣DNS服务
        
        Args:
            api_url: 上游站点URL，如 https://dns.example.com
            api_key: 上游站点的用户API Key
            api_secret: 上游站点的用户API Secret
        """
        self.base_url = api_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = 30
    
    def _sign_request(self, method: str, path: str, body: str = '') -> tuple:
        """
        生成API签名
        
        Returns:
            (timestamp, signature)
        """
        timestamp = str(int(time.time()))
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return timestamp, signature
    
    def _request(self, method: str, path: str, data: Dict = None) -> Dict:
        """
        发送API请求
        
        Args:
            method: HTTP方法
            path: API路径（可包含查询参数）
            data: 请求数据
            
        Returns:
            响应JSON
            
        Raises:
            DnsAuthenticationError: 认证失败
            DnsApiError: API调用失败
        """
        body = '' if data is None else json.dumps(data, ensure_ascii=False)
        
        # 签名时只使用路径部分，不包含查询参数
        # 服务端使用 request.path 验证，不包含查询参数
        sign_path = path.split('?')[0]
        timestamp, signature = self._sign_request(method, sign_path, body)
        
        headers = {
            'X-Api-Key': self.api_key,
            'X-Timestamp': timestamp,
            'X-Signature': signature,
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{path}"
        
        try:
            response = requests.request(
                method, url, 
                headers=headers, 
                data=body.encode('utf-8') if body else None,
                timeout=self.timeout
            )
            result = response.json()
            
            # 处理错误响应
            code = result.get('code', 500)
            if code == 401:
                raise DnsAuthenticationError(self.provider_name, result.get('message', '认证失败'))
            elif code == 403:
                raise DnsApiError(self.provider_name, '权限验证', result.get('message', '权限不足'))
            elif code >= 400:
                raise DnsApiError(self.provider_name, '请求', result.get('message', '请求失败'))
            
            return result
            
        except requests.exceptions.Timeout:
            raise DnsApiError(self.provider_name, '请求', '请求超时')
        except requests.exceptions.ConnectionError:
            raise DnsApiError(self.provider_name, '请求', '连接失败，请检查API地址')
        except json.JSONDecodeError:
            raise DnsApiError(self.provider_name, '请求', '响应格式错误')
    
    def verify_credentials(self) -> bool:
        """验证凭据是否有效"""
        try:
            result = self._request('GET', '/api/open/user/info')
            return result.get('code') == 200
        except Exception:
            return False
    
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """
        获取域名列表（子域名列表）
        
        注意：六趣DNS的zone对应的是子域名
        """
        path = f'/api/open/subdomains?page={page}&per_page={page_size}'
        result = self._request('GET', path)
        
        if result.get('code') != 200:
            return {'total': 0, 'list': []}
        
        data = result.get('data', {})
        subdomains = data.get('subdomains', [])
        pagination = data.get('pagination', {})
        
        zones = []
        for sub in subdomains:
            # 关键字过滤
            if keyword and keyword.lower() not in sub.get('full_name', '').lower():
                continue
            zones.append(DnsZone(
                zone_id=str(sub.get('id')),
                name=sub.get('full_name', ''),
                status='active' if sub.get('status') == 1 else 'paused'
            ))
        
        return {
            'total': pagination.get('total', len(zones)),
            'list': zones
        }
    
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """获取解析记录列表"""
        path = f'/api/open/subdomains/{zone_id}/records'
        result = self._request('GET', path)
        
        if result.get('code') != 200:
            return {'total': 0, 'list': []}
        
        records_data = result.get('data', {}).get('records', [])
        
        # 应用过滤
        record_type = filters.get('type')
        keyword = filters.get('keyword')
        
        records = []
        for r in records_data:
            # 类型过滤
            if record_type and r.get('type', '').upper() != record_type.upper():
                continue
            # 关键字过滤
            if keyword and keyword.lower() not in r.get('name', '').lower():
                continue
            
            records.append(DnsRecord(
                record_id=str(r.get('id', '')),
                name=r.get('name', '@'),
                full_name=r.get('name', '@'),
                type=r.get('type', 'A'),
                value=r.get('content', ''),
                ttl=r.get('ttl', 600),
                proxied=r.get('proxied', False),
                status='active',
                update_time=r.get('created_at')
            ))
        
        return {
            'total': len(records),
            'list': records
        }
    
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """获取单条记录详情"""
        result = self.get_records(zone_id)
        for record in result.get('list', []):
            if record.record_id == record_id:
                return record
        return None
    
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """创建记录"""
        data = {
            'type': record_type.upper(),
            'name': name,
            'content': value,
            'ttl': ttl
        }
        
        # 可选参数
        if kwargs.get('proxied') is not None:
            data['proxied'] = kwargs['proxied']
        if kwargs.get('priority') is not None:
            data['priority'] = kwargs['priority']
        
        path = f'/api/open/subdomains/{zone_id}/records'
        result = self._request('POST', path, data)
        
        if result.get('code') not in [200, 201]:
            raise DnsApiError(self.provider_name, '创建记录', result.get('message', '创建失败'))
        
        record = result.get('data', {}).get('record', {})
        return str(record.get('id', ''))
    
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """更新记录"""
        data = {
            'type': record_type.upper(),
            'name': name,
            'content': value,
            'ttl': ttl
        }
        
        if kwargs.get('proxied') is not None:
            data['proxied'] = kwargs['proxied']
        
        path = f'/api/open/dns-records/{record_id}'
        result = self._request('PUT', path, data)
        
        if result.get('code') != 200:
            raise DnsApiError(self.provider_name, '更新记录', result.get('message', '更新失败'))
        
        return True
    
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """删除记录"""
        path = f'/api/open/dns-records/{record_id}'
        result = self._request('DELETE', path)
        
        if result.get('code') != 200:
            raise DnsApiError(self.provider_name, '删除记录', result.get('message', '删除失败'))
        
        return True
    
    def get_capabilities(self) -> ProviderCapabilities:
        """获取服务商能力"""
        return ProviderCapabilities(
            supports_proxy=False,  # 六趣DNS不支持CDN代理
            supports_line=False,   # 不支持线路
            supports_weight=False, # 不支持权重
            supports_status=False, # 不支持状态切换
            supports_remark=False, # 不支持备注
            supported_types=['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'NS']
        )
    
    def get_lines(self) -> List[DnsLine]:
        """获取线路列表 - 六趣DNS不支持线路"""
        return []
    
    # ========== 扩展方法 ==========
    
    def get_user_info(self) -> Dict[str, Any]:
        """获取上游用户信息"""
        result = self._request('GET', '/api/open/user/info')
        if result.get('code') == 200:
            return result.get('data', {})
        return {}
    
    def get_available_domains(self) -> List[Dict]:
        """
        获取上游可购买的域名列表（包含套餐信息）
        支持分页获取全部域名
        
        Returns:
            [
                {
                    'id': 1,
                    'name': 'example.com',
                    'description': '示例域名',
                    'plans': [
                        {
                            'id': 1,
                            'name': '月付套餐',
                            'price': 10.00,
                            'duration_days': 30,
                            'min_length': 3,
                            'max_length': 20,
                            'max_records': 10
                        }
                    ]
                }
            ]
        """
        all_domains = []
        page = 1
        per_page = 100  # 每页获取100条
        
        while True:
            result = self._request('GET', f'/api/open/domains?page={page}&per_page={per_page}')
            if result.get('code') == 200:
                data = result.get('data', {})
                domains = data.get('domains', [])
                
                if not domains:
                    break
                
                all_domains.extend(domains)
                
                # 检查是否还有更多页
                total = data.get('total', len(domains))
                if len(all_domains) >= total:
                    break
                
                page += 1
            else:
                break
        
        # 为每个域名获取套餐
        for domain in all_domains:
            domain_id = domain.get('id')
            plans_result = self._request('GET', f'/api/open/domains/{domain_id}/plans')
            if plans_result.get('code') == 200:
                domain['plans'] = plans_result.get('data', {}).get('plans', [])
            else:
                domain['plans'] = []
        
        return all_domains
    
    def get_domain_plans(self, domain_id: int) -> List[Dict]:
        """获取指定域名的套餐列表"""
        result = self._request('GET', f'/api/open/domains/{domain_id}/plans')
        if result.get('code') == 200:
            return result.get('data', {}).get('plans', [])
        return []
    
    def check_subdomain_available(self, domain_id: int, prefix: str) -> Dict:
        """
        检查子域名前缀是否可用
        
        Returns:
            {
                'available': True/False,
                'name': 'test',
                'full_name': 'test.example.com',
                'message': '可以注册' / '已被占用'
            }
        """
        path = f'/api/open/domains/{domain_id}/check?name={prefix}'
        result = self._request('GET', path)
        if result.get('code') == 200:
            return result.get('data', {})
        return {'available': False, 'message': result.get('message', '检查失败')}
    
    def purchase_subdomain(self, domain_id: int, prefix: str, plan_id: int, 
                          coupon_code: str = None) -> Dict:
        """
        购买子域名
        
        Args:
            domain_id: 上游域名ID
            prefix: 子域名前缀
            plan_id: 上游套餐ID
            coupon_code: 优惠码（可选）
            
        Returns:
            {
                'subdomain': {
                    'id': 123,
                    'full_name': 'test.example.com',
                    'expires_at': '2026-01-01T00:00:00'
                },
                'cost': 9.00,
                'balance': 91.00
            }
        """
        data = {
            'domain_id': domain_id,
            'name': prefix,
            'plan_id': plan_id
        }
        if coupon_code:
            data['coupon_code'] = coupon_code
        
        result = self._request('POST', '/api/open/purchase', data)
        if result.get('code') in [200, 201]:
            return result.get('data', {})
        raise DnsApiError(self.provider_name, '购买子域名', result.get('message', '购买失败'))
    
    def renew_subdomain(self, subdomain_id: int, plan_id: int) -> Dict:
        """
        续费子域名
        
        Args:
            subdomain_id: 上游子域名ID
            plan_id: 上游套餐ID
            
        Returns:
            {
                'subdomain': {...},
                'expires_at': '2026-02-01T00:00:00',
                'balance': 81.00
            }
        """
        data = {'plan_id': plan_id}
        
        path = f'/api/open/subdomains/{subdomain_id}/renew'
        result = self._request('POST', path, data)
        if result.get('code') == 200:
            return result.get('data', {})
        raise DnsApiError(self.provider_name, '续费子域名', result.get('message', '续费失败'))
    
    def delete_subdomain(self, subdomain_id: int) -> bool:
        """删除上游子域名"""
        path = f'/api/open/subdomains/{subdomain_id}'
        result = self._request('DELETE', path)
        if result.get('code') == 200:
            return True
        raise DnsApiError(self.provider_name, '删除子域名', result.get('message', '删除失败'))
