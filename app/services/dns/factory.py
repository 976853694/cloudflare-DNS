"""
DNS 服务工厂
负责注册和创建 DNS 服务实例
插件模式：凭据字段由各渠道类自己定义
"""
from typing import Dict, Type, Any, List
from app.services.dns.base import DnsServiceBase


class DnsServiceFactory:
    """DNS 服务工厂类"""
    
    # 已注册的服务商
    _providers: Dict[str, Type[DnsServiceBase]] = {}
    
    @classmethod
    def register(cls, provider_type: str, service_class: Type[DnsServiceBase]) -> None:
        """
        注册 DNS 服务商
        
        Args:
            provider_type: 服务商类型标识 (如 'cloudflare', 'aliyun')
            service_class: 服务类
        """
        cls._providers[provider_type] = service_class
    
    @classmethod
    def create(cls, provider_type: str, credentials: Dict[str, Any]) -> DnsServiceBase:
        """
        创建 DNS 服务实例
        
        Args:
            provider_type: 服务商类型
            credentials: 凭据字典
            
        Returns:
            DnsServiceBase 实例
            
        Raises:
            ValueError: 未知的服务商类型
        """
        if provider_type not in cls._providers:
            available = ', '.join(cls._providers.keys()) or '无'
            raise ValueError(f"未知的 DNS 服务商: {provider_type}，可用: {available}")
        
        service_class = cls._providers[provider_type]
        return service_class(**credentials)
    
    @classmethod
    def get_providers(cls) -> List[Dict[str, str]]:
        """
        获取所有已注册的服务商
        
        Returns:
            [{'type': 'cloudflare', 'name': 'Cloudflare'}, ...]
        """
        result = []
        for provider_type, service_class in cls._providers.items():
            result.append({
                'type': provider_type,
                'name': getattr(service_class, 'provider_name', provider_type)
            })
        return result
    
    @classmethod
    def is_registered(cls, provider_type: str) -> bool:
        """检查服务商是否已注册"""
        return provider_type in cls._providers
    
    @classmethod
    def get_credential_fields(cls, provider_type: str) -> List[Dict[str, Any]]:
        """
        获取服务商所需的凭据字段
        从渠道类的 CREDENTIAL_FIELDS 属性获取
        
        Args:
            provider_type: 服务商类型
            
        Returns:
            凭据字段定义列表
        """
        if provider_type not in cls._providers:
            return []
        
        service_class = cls._providers[provider_type]
        return getattr(service_class, 'CREDENTIAL_FIELDS', [])
