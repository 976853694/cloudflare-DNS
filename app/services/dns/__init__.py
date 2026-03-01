# DNS 服务抽象层
# 支持多 DNS 服务商的统一接口
# 插件模式：自动扫描加载所有渠道

import os
import importlib
import logging

from app.services.dns.base import (
    DnsServiceBase,
    DnsRecord,
    DnsZone,
    DnsLine,
    ProviderCapabilities,
    DnsAuthenticationError,
    DnsApiError,
    DnsUnsupportedError,
    DnsRecordNotFoundError,
    is_record_not_found_error
)
from app.services.dns.factory import DnsServiceFactory

logger = logging.getLogger(__name__)

# 排除的文件（非渠道模块）
EXCLUDED_FILES = {'__init__.py', 'base.py', 'factory.py'}


def _load_providers():
    """
    动态加载所有 DNS 渠道插件
    扫描当前目录下的所有 .py 文件，自动导入并注册
    """
    current_dir = os.path.dirname(__file__)
    
    for filename in os.listdir(current_dir):
        # 跳过非 Python 文件和排除的文件
        if not filename.endswith('.py') or filename in EXCLUDED_FILES:
            continue
        
        module_name = filename[:-3]  # 去掉 .py
        
        try:
            # 动态导入模块
            module = importlib.import_module(f'app.services.dns.{module_name}')
            
            # 查找继承自 DnsServiceBase 的类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, DnsServiceBase) and 
                    attr is not DnsServiceBase):
                    
                    # 获取 provider_type
                    provider_type = getattr(attr, 'provider_type', None)
                    if provider_type:
                        # 注册到工厂
                        DnsServiceFactory.register(provider_type, attr)
                        logger.debug(f'已加载 DNS 渠道: {provider_type} ({attr.provider_name})')
                    break
                    
        except ImportError as e:
            # 缺少依赖，跳过该渠道
            logger.warning(f'跳过 DNS 渠道 {module_name}: 缺少依赖 - {e}')
        except Exception as e:
            logger.warning(f'加载 DNS 渠道 {module_name} 失败: {e}')


# 启动时自动加载所有渠道
_load_providers()


__all__ = [
    'DnsServiceBase',
    'DnsRecord',
    'DnsZone', 
    'DnsLine',
    'ProviderCapabilities',
    'DnsServiceFactory',
    'DnsAuthenticationError',
    'DnsApiError',
    'DnsUnsupportedError',
    'DnsRecordNotFoundError',
    'is_record_not_found_error'
]
