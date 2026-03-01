"""
Cloudflare API 服务 - 向后兼容层

此模块保留旧的 CloudflareService 接口以确保向后兼容。
新代码应使用 app.services.dns 模块中的 DnsServiceFactory。

已废弃警告：此模块将在未来版本中移除，请迁移到新的 DNS 服务抽象层。
"""
import warnings
import requests
from flask import current_app


class CloudflareService:
    """
    Cloudflare API服务（向后兼容层）
    
    已废弃：请使用 app.services.dns.DnsServiceFactory 创建 DNS 服务实例。
    
    支持两种认证方式:
    1. API Token (Bearer token) - 推荐
    2. API Key + Email (Global API Key) - 传统方式
    """
    
    def __init__(self, api_key=None, email=None, api_token=None):
        # 发出废弃警告
        warnings.warn(
            "CloudflareService 已废弃，请使用 DnsServiceFactory.create('cloudflare', credentials) 替代",
            DeprecationWarning,
            stacklevel=2
        )
        
        self.base_url = current_app.config.get('CF_API_BASE_URL', 'https://api.cloudflare.com/client/v4')
        
        # 优先使用API Key + Email方式
        if api_key and email:
            self.auth_type = 'api_key'
            self.headers = {
                'X-Auth-Key': api_key,
                'X-Auth-Email': email,
                'Content-Type': 'application/json'
            }
        # 其次使用API Token方式
        elif api_token:
            self.auth_type = 'api_token'
            self.headers = {
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json'
            }
        # 使用配置文件中的默认值
        else:
            default_key = current_app.config.get('CF_API_KEY', '')
            default_email = current_app.config.get('CF_EMAIL', '')
            default_token = current_app.config.get('CF_API_TOKEN', '')
            
            if default_key and default_email:
                self.auth_type = 'api_key'
                self.headers = {
                    'X-Auth-Key': default_key,
                    'X-Auth-Email': default_email,
                    'Content-Type': 'application/json'
                }
            else:
                self.auth_type = 'api_token'
                self.headers = {
                    'Authorization': f'Bearer {default_token}',
                    'Content-Type': 'application/json'
                }
    
    @classmethod
    def from_account(cls, cf_account):
        """
        从 CloudflareAccount 模型创建服务实例
        
        已废弃：请使用 domain.get_dns_service() 或 DnsServiceFactory 替代
        """
        if cf_account:
            if cf_account.api_key and cf_account.email:
                return cls(api_key=cf_account.api_key, email=cf_account.email)
            elif cf_account.api_token:
                return cls(api_token=cf_account.api_token)
        return cls()
    
    def _request(self, method, endpoint, data=None):
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                timeout=30
            )
            result = response.json()
            
            if not result.get('success', False):
                errors = result.get('errors', [])
                error_msg = errors[0].get('message', 'Unknown error') if errors else 'Unknown error'
                raise Exception(error_msg)
            
            return result.get('result')
        
        except requests.exceptions.RequestException as e:
            raise Exception(f'网络请求失败: {str(e)}')
    
    def get_zones(self):
        return self._request('GET', '/zones')
    
    def get_zone(self, zone_id):
        return self._request('GET', f'/zones/{zone_id}')
    
    def get_records(self, zone_id, name=None, record_type=None):
        params = []
        if name:
            params.append(f'name={name}')
        if record_type:
            params.append(f'type={record_type}')
        
        query = '&'.join(params)
        endpoint = f'/zones/{zone_id}/dns_records'
        if query:
            endpoint += f'?{query}'
        
        return self._request('GET', endpoint)
    
    def create_record(self, zone_id, record_type, name, content, ttl=300, proxied=False, priority=None):
        data = {
            'type': record_type,
            'name': name,
            'content': content,
            'ttl': ttl,
            'proxied': proxied
        }
        
        if record_type == 'MX' and priority is not None:
            data['priority'] = priority
        
        return self._request('POST', f'/zones/{zone_id}/dns_records', data)
    
    def update_record(self, zone_id, record_id, record_type, name, content, ttl=300, proxied=False, priority=None):
        data = {
            'type': record_type,
            'name': name,
            'content': content,
            'ttl': ttl,
            'proxied': proxied
        }
        
        if record_type == 'MX' and priority is not None:
            data['priority'] = priority
        
        return self._request('PUT', f'/zones/{zone_id}/dns_records/{record_id}', data)
    
    def delete_record(self, zone_id, record_id):
        return self._request('DELETE', f'/zones/{zone_id}/dns_records/{record_id}')
    
    def verify_token(self):
        """验证认证信息是否有效"""
        try:
            if self.auth_type == 'api_key':
                # API Key使用/user端点验证
                result = self._request('GET', '/user')
                return result.get('id') is not None
            else:
                # API Token使用/user/tokens/verify端点验证
                result = self._request('GET', '/user/tokens/verify')
                return result.get('status') == 'active'
        except Exception as e:
            current_app.logger.warning(f"Cloudflare 凭据验证失败: {e}")
            return False


def get_dns_service_for_domain(domain):
    """
    获取域名的 DNS 服务实例（推荐使用）
    
    优先使用新的 dns_channel，如果没有则回退到旧的 cf_account
    
    Args:
        domain: Domain 模型实例
        
    Returns:
        DNS 服务实例或 None
    """
    # 优先使用新的 DNS 渠道
    if hasattr(domain, 'get_dns_service'):
        service = domain.get_dns_service()
        if service:
            return service
    
    # 回退到旧的 Cloudflare 账户
    if hasattr(domain, 'cf_account') and domain.cf_account:
        return CloudflareService.from_account(domain.cf_account)
    
    return None
