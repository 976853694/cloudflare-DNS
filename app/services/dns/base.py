"""
DNS 服务抽象基类
定义统一的 DNS 操作接口和数据结构
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


# ==================== 异常类 ====================

class DnsAuthenticationError(Exception):
    """认证失败"""
    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] 认证失败: {message}")


class DnsApiError(Exception):
    """API 调用错误"""
    def __init__(self, provider: str, operation: str, message: str):
        self.provider = provider
        self.operation = operation
        self.message = message
        super().__init__(f"[{provider}] {operation} 失败: {message}")


class DnsUnsupportedError(Exception):
    """功能不支持"""
    def __init__(self, provider: str, feature: str):
        self.provider = provider
        self.feature = feature
        super().__init__(f"[{provider}] 不支持 {feature} 功能")


class DnsRecordNotFoundError(DnsApiError):
    """DNS 记录不存在错误"""
    def __init__(self, provider: str, record_id: str):
        self.record_id = record_id
        super().__init__(provider, 'RecordNotFound', f'记录 {record_id} 不存在')


# ==================== 辅助函数 ====================

def is_record_not_found_error(error: DnsApiError) -> bool:
    """
    判断是否为"记录不存在"错误
    
    各服务商的错误消息关键词：
    - Cloudflare: "does not exist", "not found"
    - 阿里云: "DomainRecordNotBelongToUser", "InvalidRecordId.NotFound"
    - DNSPod: "记录不存在", "record not exist"
    - 华为云: "DNS.0312" (记录不存在)
    - GoDaddy: "not found"
    - NameSilo: "not found"
    - Name.com: "not found"
    - Namecheap: "not found"
    - Route53: "not found"
    - PowerDNS: "not found"
    
    Args:
        error: DnsApiError 异常实例
        
    Returns:
        bool: 如果是"记录不存在"错误返回 True
    """
    # 如果已经是 DnsRecordNotFoundError 类型，直接返回 True
    if isinstance(error, DnsRecordNotFoundError):
        return True
    
    # 各服务商"记录不存在"错误的关键词模式
    not_found_patterns = [
        # 通用模式
        'does not exist',
        'not found',
        'not exist',
        '不存在',
        '记录不存在',
        # Cloudflare
        'invalid dns record identifier',
        # 阿里云
        'invalidrecordid',
        'domainrecordnotbelongtouser',
        'domainrecordnotfound',
        # DNSPod / 腾讯云
        'recordnotexist',
        'record not exist',
        'the record does not exist',
        # 华为云
        'dns.0312',
        # GoDaddy
        'record_not_found',
        # NameSilo
        'record does not exist',
        # Route53
        'nosuchrecord',
        'rrset not found',
        # 百度云
        'recordnotfound',
    ]
    
    message_lower = error.message.lower()
    return any(pattern.lower() in message_lower for pattern in not_found_patterns)


# ==================== 数据结构 ====================

@dataclass
class DnsRecord:
    """统一的 DNS 记录数据结构"""
    record_id: str              # 记录ID
    name: str                   # 主机记录 (如 www, @)
    full_name: str              # 完整域名 (如 www.example.com)
    type: str                   # 记录类型 (A, AAAA, CNAME, etc.)
    value: str                  # 记录值
    ttl: int = 600              # TTL
    proxied: bool = False       # 是否代理 (Cloudflare 特有)
    priority: Optional[int] = None   # MX 优先级
    line: Optional[str] = None       # 线路ID (国内服务商)
    line_name: Optional[str] = None  # 线路名称
    weight: Optional[int] = None     # 权重
    status: str = 'active'      # 状态 (active/paused)
    remark: Optional[str] = None     # 备注
    update_time: Optional[str] = None  # 更新时间
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'record_id': self.record_id,
            'name': self.name,
            'full_name': self.full_name,
            'type': self.type,
            'value': self.value,
            'ttl': self.ttl,
            'proxied': self.proxied,
            'priority': self.priority,
            'line': self.line,
            'line_name': self.line_name,
            'weight': self.weight,
            'status': self.status,
            'remark': self.remark,
            'update_time': self.update_time
        }


@dataclass
class DnsZone:
    """统一的域名区域数据结构"""
    zone_id: str            # Zone ID
    name: str               # 域名
    record_count: int = 0   # 记录数量
    status: str = 'active'  # 状态
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'zone_id': self.zone_id,
            'name': self.name,
            'record_count': self.record_count,
            'status': self.status
        }


@dataclass
class DnsLine:
    """统一的线路数据结构"""
    line_id: str                    # 线路ID（服务商原始值）
    name: str                       # 线路名称（显示用）
    parent_id: Optional[str] = None # 父级线路ID（用于层级结构）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'line_id': self.line_id,
            'name': self.name,
            'parent_id': self.parent_id
        }


@dataclass
class ProviderCapabilities:
    """服务商能力描述"""
    supports_proxy: bool = False      # CDN 代理 (Cloudflare)
    supports_line: bool = False       # 线路分流 (国内服务商)
    supports_weight: bool = False     # 权重负载
    supports_status: bool = True      # 记录状态开关
    supports_remark: bool = False     # 备注功能
    supported_types: List[str] = field(default_factory=lambda: [
        'A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS'
    ])
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'supports_proxy': self.supports_proxy,
            'supports_line': self.supports_line,
            'supports_weight': self.supports_weight,
            'supports_status': self.supports_status,
            'supports_remark': self.supports_remark,
            'supported_types': self.supported_types
        }


# ==================== 抽象基类 ====================

class DnsServiceBase(ABC):
    """DNS 服务抽象基类"""
    
    # 子类必须定义
    provider_type: str = ""
    provider_name: str = ""
    
    @abstractmethod
    def verify_credentials(self) -> bool:
        """
        验证凭据是否有效
        
        Returns:
            bool: 凭据有效返回 True
            
        Raises:
            DnsAuthenticationError: 认证失败
        """
        pass
    
    @abstractmethod
    def get_zones(self, keyword: str = None, page: int = 1, 
                  page_size: int = 20) -> Dict[str, Any]:
        """
        获取域名列表
        
        Args:
            keyword: 搜索关键字
            page: 页码
            page_size: 每页数量
            
        Returns:
            {
                'total': int,
                'list': List[DnsZone]
            }
        """
        pass
    
    @abstractmethod
    def get_records(self, zone_id: str, **filters) -> Dict[str, Any]:
        """
        获取解析记录列表
        
        Args:
            zone_id: 域名区域ID
            **filters: 筛选条件
                - page: 页码
                - page_size: 每页数量
                - keyword: 搜索关键字
                - subdomain: 子域名筛选
                - type: 记录类型筛选
                - line: 线路筛选
                - status: 状态筛选
                
        Returns:
            {
                'total': int,
                'list': List[DnsRecord]
            }
        """
        pass
    
    @abstractmethod
    def get_record(self, zone_id: str, record_id: str) -> Optional[DnsRecord]:
        """
        获取单条记录详情
        
        Args:
            zone_id: 域名区域ID
            record_id: 记录ID
            
        Returns:
            DnsRecord 或 None
        """
        pass
    
    @abstractmethod
    def create_record(self, zone_id: str, name: str, record_type: str,
                      value: str, ttl: int = 600, **kwargs) -> str:
        """
        创建记录
        
        Args:
            zone_id: 域名区域ID
            name: 主机记录
            record_type: 记录类型
            value: 记录值
            ttl: TTL
            **kwargs: 其他参数
                - proxied: 是否代理 (Cloudflare)
                - priority: MX优先级
                - line: 线路ID
                - weight: 权重
                - remark: 备注
                
        Returns:
            str: 记录ID
            
        Raises:
            DnsApiError: 创建失败
        """
        pass
    
    @abstractmethod
    def update_record(self, zone_id: str, record_id: str, name: str,
                      record_type: str, value: str, ttl: int = 600, 
                      **kwargs) -> bool:
        """
        更新记录
        
        Args:
            zone_id: 域名区域ID
            record_id: 记录ID
            name: 主机记录
            record_type: 记录类型
            value: 记录值
            ttl: TTL
            **kwargs: 其他参数
                
        Returns:
            bool: 成功返回 True
            
        Raises:
            DnsApiError: 更新失败
        """
        pass
    
    @abstractmethod
    def delete_record(self, zone_id: str, record_id: str) -> bool:
        """
        删除记录
        
        Args:
            zone_id: 域名区域ID
            record_id: 记录ID
            
        Returns:
            bool: 成功返回 True
            
        Raises:
            DnsApiError: 删除失败
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """
        获取服务商能力
        
        Returns:
            ProviderCapabilities
        """
        pass
    
    def get_lines(self) -> List[DnsLine]:
        """
        获取线路列表（可选实现）
        
        Returns:
            List[DnsLine]: 线路列表，不支持则返回空列表
        """
        return []
    
    def set_record_status(self, zone_id: str, record_id: str, 
                          enabled: bool) -> bool:
        """
        设置记录状态（可选实现）
        
        Args:
            zone_id: 域名区域ID
            record_id: 记录ID
            enabled: True=启用, False=暂停
            
        Returns:
            bool: 成功返回 True
            
        Raises:
            DnsUnsupportedError: 不支持此功能
        """
        raise DnsUnsupportedError(self.provider_name, '记录状态切换')
    
    def validate_record_type(self, record_type: str) -> bool:
        """
        验证记录类型是否支持
        
        Args:
            record_type: 记录类型
            
        Returns:
            bool: 支持返回 True
        """
        caps = self.get_capabilities()
        return record_type.upper() in caps.supported_types
