"""
WHOIS 查询服务
从本地数据库查询域名注册信息
"""
import re
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from app.services.cache import CacheService

logger = logging.getLogger(__name__)


class WhoisService:
    """WHOIS 查询服务 - 本地数据库查询"""
    
    CACHE_PREFIX = 'whois:'
    RATE_PREFIX = 'whois_rate:'
    CACHE_TTL = 300  # 5 分钟缓存（本地查询快，缓存时间短）
    RATE_LIMIT = 30  # 每分钟最多查询次数（本地查询可以放宽）
    RATE_WINDOW = 60  # 频率限制窗口（秒）
    
    # 域名格式正则表达式
    DOMAIN_PATTERN = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    )
    
    @classmethod
    def validate_domain(cls, domain: str) -> bool:
        """验证域名格式"""
        if not domain or not isinstance(domain, str):
            return False
        
        domain = domain.strip().lower()
        
        if len(domain) < 4 or len(domain) > 253:
            return False
        
        return bool(cls.DOMAIN_PATTERN.match(domain))
    
    @classmethod
    def mask_email(cls, email: str) -> str:
        """邮箱隐私保护"""
        if not email or '@' not in email:
            return email or ''
        
        try:
            local, domain = email.split('@', 1)
            if len(local) <= 2:
                masked = local[0] + '***' if local else '***'
            else:
                masked = local[:2] + '***'
            return f"{masked}@{domain}"
        except Exception:
            return '***@***'
    
    @classmethod
    def mask_username(cls, username: str) -> str:
        """用户名隐私保护"""
        if not username:
            return '***'
        
        if len(username) <= 2:
            return username[0] + '***' if username else '***'
        else:
            return username[:2] + '***'
    
    @classmethod
    def check_rate_limit(cls, identifier: str) -> Tuple[bool, int]:
        """检查频率限制"""
        cache_key = f"{cls.RATE_PREFIX}{identifier}"
        
        count = CacheService.get(cache_key)
        
        if count is None:
            CacheService.set(cache_key, 1, cls.RATE_WINDOW)
            return True, 0
        
        count = int(count)
        
        if count >= cls.RATE_LIMIT:
            return False, cls.RATE_WINDOW
        
        CacheService.set(cache_key, count + 1, cls.RATE_WINDOW)
        return True, 0
    
    @classmethod
    def query(cls, domain: str, identifier: str = None) -> Dict[str, Any]:
        """
        查询域名 WHOIS 信息（本地数据库）
        
        Args:
            domain: 域名（支持子域名如 xxx.example.com）
            identifier: 用户标识（用于频率限制）
            
        Returns:
            Dict: 查询结果
        """
        # 标准化域名
        domain = domain.strip().lower()
        
        # 验证域名格式
        if not cls.validate_domain(domain):
            raise ValueError("无效的域名格式")
        
        # 检查频率限制
        if identifier:
            allowed, wait_time = cls.check_rate_limit(identifier)
            if not allowed:
                raise PermissionError(f"查询过于频繁，请 {wait_time} 秒后再试")
        
        # 检查缓存
        cache_key = f"{cls.CACHE_PREFIX}{domain}"
        cached_data = CacheService.get(cache_key)
        
        if cached_data:
            logger.info(f"WHOIS cache hit: {domain}")
            result = cached_data.copy() if isinstance(cached_data, dict) else cached_data
            if isinstance(result, dict):
                result['cached'] = True
            return result
        
        # 从本地数据库查询
        logger.info(f"WHOIS query: {domain}")
        result = cls._query_local(domain)
        
        if result:
            # 缓存结果
            CacheService.set(cache_key, result, cls.CACHE_TTL)
            result['cached'] = False
            return result
        
        raise LookupError("域名未在本平台注册")
    
    @classmethod
    def _query_local(cls, domain: str) -> Optional[Dict[str, Any]]:
        """从本地数据库查询域名信息"""
        from app.models import Subdomain, Domain
        
        # 首先尝试作为子域名查询（完整匹配）
        subdomain = Subdomain.query.filter_by(full_name=domain).first()
        
        if subdomain:
            return cls._format_subdomain_result(subdomain)
        
        # 尝试作为主域名查询
        main_domain = Domain.query.filter_by(name=domain).first()
        
        if main_domain:
            return cls._format_domain_result(main_domain)
        
        # 尝试模糊匹配（查询是否是某个主域名的子域名）
        parts = domain.split('.')
        for i in range(1, len(parts)):
            parent_domain = '.'.join(parts[i:])
            main_domain = Domain.query.filter_by(name=parent_domain).first()
            if main_domain:
                # 找到了主域名，但子域名不存在
                return None
        
        return None
    
    @classmethod
    def _format_subdomain_result(cls, subdomain) -> Dict[str, Any]:
        """格式化子域名查询结果"""
        user = subdomain.user
        domain = subdomain.domain
        
        return {
            'domain': subdomain.full_name,
            'type': 'subdomain',
            'registrant': user.username if user else 'Unknown',
            'email': cls.mask_email(user.email) if user else None,
            'creation_date': subdomain.created_at.strftime('%Y-%m-%d') if subdomain.created_at else None,
            'expiry_date': subdomain.expires_at.strftime('%Y-%m-%d') if subdomain.expires_at else None,
            'status': cls._get_subdomain_status_cn(subdomain),
            'parent_domain': domain.name if domain else None,
            'owner_id': user.id if user else None,  # 用于发起工单
            'queried_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        }
    
    @classmethod
    def _format_domain_result(cls, domain) -> Dict[str, Any]:
        """格式化主域名查询结果"""
        # 主域名的所有者
        owner_name = '平台'
        owner_email = None
        if domain.owner:
            owner_name = domain.owner.username
            owner_email = cls.mask_email(domain.owner.email)
        
        return {
            'domain': domain.name,
            'type': 'domain',
            'registrant': owner_name,
            'email': owner_email,
            'creation_date': domain.created_at.strftime('%Y-%m-%d') if domain.created_at else None,
            'expiry_date': None,  # 主域名没有到期时间
            'status': ['正常'] if domain.status == 1 else ['已停用'],
            'subdomain_count': domain.subdomains.count(),
            'allow_register': domain.allow_register == 1,
            'queried_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        }
    
    @classmethod
    def _get_subdomain_status_cn(cls, subdomain) -> list:
        """获取子域名状态列表（中文）"""
        status = []
        
        if subdomain.status == 1:
            status.append('正常')
        else:
            status.append('已停用')
        
        if subdomain.is_expired:
            status.append('已过期')
        
        if subdomain.ns_mode == 1:
            status.append('已转移NS')
        
        if subdomain.auto_renew == 1:
            status.append('自动续费')
        
        return status
