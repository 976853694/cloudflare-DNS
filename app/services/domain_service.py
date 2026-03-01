"""
域名业务服务层
封装域名相关的业务逻辑
支持多 DNS 服务商
"""
from datetime import timedelta
from app import db
from app.models import Domain, Subdomain, DnsRecord, Plan, PurchaseRecord
from app.services.dns import DnsApiError
from app.utils.validators import validate_subdomain_name
from app.utils.timezone import now as beijing_now


class DomainService:
    """域名服务"""
    
    @staticmethod
    def get_available_domains():
        """获取可注册的域名列表"""
        return Domain.query.filter_by(status=1, allow_register=1).all()
    
    @staticmethod
    def get_domain_plans(domain_id):
        """获取域名的可用套餐"""
        return Plan.query.filter(
            Plan.domains.any(id=domain_id),
            Plan.status == 1
        ).order_by(Plan.sort_order, Plan.id).all()
    
    @staticmethod
    def check_subdomain_available(domain_id, name):
        """检查子域名是否可用"""
        return Subdomain.query.filter_by(domain_id=domain_id, name=name.lower()).first() is None
    
    @staticmethod
    def create_subdomain(user, plan, subdomain_name, domain=None):
        """
        创建子域名
        
        Args:
            user: 用户对象
            plan: 套餐对象
            subdomain_name: 子域名前缀
            domain: 域名对象（可选，如果套餐关联多个域名则必须指定）
            
        Returns:
            Subdomain: 创建的子域名对象
        """
        # 如果没有指定域名，使用套餐关联的第一个域名
        if domain is None:
            if not plan.domains:
                raise ValueError('套餐未关联任何域名')
            domain = plan.domains[0]
        else:
            # 验证域名是否在套餐关联的域名中
            if domain.id not in [d.id for d in plan.domains]:
                raise ValueError('套餐与域名不匹配')
        
        subdomain_name = subdomain_name.lower().strip()
        
        # 验证域名前缀长度
        name_len = len(subdomain_name)
        if name_len < plan.min_length or name_len > plan.max_length:
            raise ValueError(f'域名前缀长度需在 {plan.min_length}-{plan.max_length} 个字符之间')
        
        # 验证域名前缀格式
        if not validate_subdomain_name(subdomain_name, min_len=plan.min_length, max_len=plan.max_length):
            raise ValueError('域名前缀格式不正确')
        
        # 检查是否已存在
        if not DomainService.check_subdomain_available(domain.id, subdomain_name):
            raise ValueError('该域名前缀已被占用')
        
        # 检查余额
        if not user.can_afford(plan.price):
            raise ValueError(f'余额不足，需要 ¥{plan.price}')
        
        full_name = f"{subdomain_name}.{domain.name}"
        expires_at = None if plan.duration_days == -1 else beijing_now() + timedelta(days=plan.duration_days)
        
        # 扣除余额
        user.deduct_balance(plan.price)
        
        # 创建子域名
        subdomain = Subdomain(
            user_id=user.id,
            domain_id=domain.id,
            plan_id=plan.id,
            name=subdomain_name,
            full_name=full_name,
            expires_at=expires_at
        )
        db.session.add(subdomain)
        db.session.flush()
        
        # 创建购买记录
        purchase_record = PurchaseRecord(
            user_id=user.id,
            subdomain_id=subdomain.id,
            plan_id=plan.id,
            plan_name=plan.name,
            domain_name=domain.name,
            subdomain_name=full_name,
            price=plan.price,
            duration_days=plan.duration_days,
            payment_method='balance'
        )
        db.session.add(purchase_record)
        db.session.commit()
        
        return subdomain
    
    @staticmethod
    def renew_subdomain(subdomain, plan, user):
        """
        续费子域名
        
        Args:
            subdomain: 子域名对象
            plan: 续费套餐对象
            user: 用户对象
        """
        if subdomain.expires_at is None:
            raise ValueError('该域名为永久有效，无需续费')
        
        # 检查套餐是否关联了该域名
        if subdomain.domain_id not in [d.id for d in plan.domains]:
            raise ValueError('套餐与域名不匹配')
        
        if plan.duration_days == -1:
            raise ValueError('永久套餐不支持续费')
        
        if not user.can_afford(plan.price):
            raise ValueError(f'余额不足，需要 ¥{plan.price}')
        
        # 扣除余额
        user.deduct_balance(plan.price)
        
        # 计算新的到期时间
        base_time = subdomain.expires_at if subdomain.expires_at > beijing_now() else beijing_now()
        subdomain.expires_at = base_time + timedelta(days=plan.duration_days)
        subdomain.plan_id = plan.id
        
        # 如果域名已停用，恢复启用状态
        if subdomain.status == 0:
            subdomain.status = 1
        
        # 创建续费购买记录
        purchase_record = PurchaseRecord(
            user_id=user.id,
            subdomain_id=subdomain.id,
            plan_id=plan.id,
            plan_name=f'{plan.name}(续费)',
            domain_name=subdomain.domain.name,
            subdomain_name=subdomain.full_name,
            price=plan.price,
            duration_days=plan.duration_days,
            payment_method='balance'
        )
        db.session.add(purchase_record)
        db.session.commit()
    
    @staticmethod
    def delete_subdomain(subdomain):
        """删除子域名及其DNS记录"""
        domain = subdomain.domain
        subdomain_id = subdomain.id
        
        # 获取 DNS 服务
        dns_service = domain.get_dns_service() if domain else None
        zone_id = domain.get_zone_id() if domain else None
        
        # 删除 DNS 服务商上的记录
        if dns_service and zone_id:
            for record in subdomain.records.all():
                try:
                    dns_service.delete_record(zone_id, record.cf_record_id)
                except:
                    pass
        
        # 删除关联的转移记录（避免外键约束错误）
        from app.models.domain_transfer import DomainTransfer
        DomainTransfer.query.filter_by(subdomain_id=subdomain_id).delete()
        
        db.session.delete(subdomain)
        db.session.commit()
    
    @staticmethod
    def create_dns_record(subdomain, record_type, name_prefix, content, ttl=300, proxied=False, priority=None, line=None, weight=None):
        """
        创建DNS记录
        
        Args:
            subdomain: 子域名对象
            record_type: 记录类型
            name_prefix: 名称前缀（@ 表示根域名）
            content: 记录值
            ttl: TTL
            proxied: 是否开启代理
            priority: 优先级（MX记录）
            line: 线路（国内服务商）
            weight: 权重
        """
        # 确保 proxied 参数为布尔值，默认为 False
        if proxied is None:
            proxied = False
        proxied = bool(proxied)
        
        if subdomain.is_expired:
            raise ValueError('套餐已到期，无法添加DNS记录')
        
        # 获取 DNS 服务
        dns_service = subdomain.domain.get_dns_service()
        if not dns_service:
            raise ValueError('域名未配置DNS服务')
        
        # 验证记录类型
        if not dns_service.validate_record_type(record_type):
            caps = dns_service.get_capabilities()
            raise ValueError(f'不支持的记录类型: {record_type}，支持: {", ".join(caps.supported_types)}')
        
        if name_prefix and name_prefix != '@':
            record_name = f"{name_prefix}.{subdomain.full_name}"
        else:
            record_name = subdomain.full_name
        
        try:
            zone_id = subdomain.domain.get_zone_id()
            record_id = dns_service.create_record(
                zone_id=zone_id,
                name=record_name,
                record_type=record_type,
                value=content,
                ttl=ttl,
                proxied=proxied,
                priority=priority,
                line=line,
                weight=weight
            )
        except DnsApiError as e:
            raise ValueError(f'DNS API错误: {e.message}')
        
        record = DnsRecord(
            subdomain_id=subdomain.id,
            type=record_type,
            name=record_name,
            content=content,
            ttl=ttl,
            proxied=1 if proxied else 0,
            priority=priority,
            cf_record_id=record_id
        )
        
        db.session.add(record)
        db.session.commit()
        
        return record
    
    @staticmethod
    def update_dns_record(record, content=None, ttl=None, proxied=None, line=None, weight=None):
        """更新DNS记录"""
        if record.subdomain.is_expired:
            raise ValueError('套餐已到期，无法修改DNS记录')
        
        # 获取 DNS 服务
        dns_service = record.subdomain.domain.get_dns_service()
        if not dns_service:
            raise ValueError('域名未配置DNS服务')
        
        new_content = content if content is not None else record.content
        new_ttl = ttl if ttl is not None else record.ttl
        # 确保 proxied 参数为布尔值
        if proxied is not None:
            new_proxied = bool(proxied)
        else:
            new_proxied = (record.proxied == 1)
        
        try:
            zone_id = record.subdomain.domain.get_zone_id()
            dns_service.update_record(
                zone_id=zone_id,
                record_id=record.cf_record_id,
                name=record.name,
                record_type=record.type,
                value=new_content,
                ttl=new_ttl,
                proxied=new_proxied,
                line=line,
                weight=weight
            )
        except DnsApiError as e:
            raise ValueError(f'DNS API错误: {e.message}')
        
        record.content = new_content
        record.ttl = new_ttl
        record.proxied = 1 if new_proxied else 0
        
        db.session.commit()
    
    @staticmethod
    def delete_dns_record(record):
        """删除DNS记录"""
        # 获取 DNS 服务
        dns_service = record.subdomain.domain.get_dns_service()
        if not dns_service:
            raise ValueError('域名未配置DNS服务')
        
        try:
            zone_id = record.subdomain.domain.get_zone_id()
            dns_service.delete_record(zone_id, record.cf_record_id)
        except DnsApiError as e:
            raise ValueError(f'DNS API错误: {e.message}')
        
        db.session.delete(record)
        db.session.commit()
