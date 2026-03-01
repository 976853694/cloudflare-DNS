"""
免费套餐自动开通服务
处理免费套餐申请审批通过后的自动开通逻辑
"""
from datetime import timedelta
from app import db
from app.models import FreePlanApplication, Subdomain, PurchaseRecord, User, Plan, Domain
from app.utils.validators import validate_subdomain_name
from app.utils.timezone import now as beijing_now
from app.services.dns import DnsApiError
import logging

logger = logging.getLogger(__name__)


class FreePlanProvisionService:
    """免费套餐自动开通服务"""
    
    @staticmethod
    def auto_provision(application_id, auto_create=True):
        """
        自动开通免费套餐
        
        Args:
            application_id: 申请ID
            auto_create: 是否自动创建（管理员可控制）
            
        Returns:
            tuple: (success: bool, message: str, data: dict)
        """
        application = FreePlanApplication.query.get(application_id)
        
        if not application:
            return False, '申请不存在', {}
        
        if application.status != FreePlanApplication.STATUS_APPROVED:
            return False, '申请状态不是已通过', {}
        
        # 如果管理员选择不自动开通
        if not auto_create:
            return True, '已通过申请，未自动开通', {'auto_created': False}
        
        # 如果没有域名前缀，返回错误（现在域名前缀是必填的）
        if not application.subdomain_name or not application.subdomain_name.strip():
            return False, '域名前缀不能为空', {'auto_created': False, 'error': '域名前缀不能为空'}
        
        # 如果已经尝试过自动开通
        if application.provision_attempted:
            return False, '已经尝试过自动开通', {'provision_error': application.provision_error}
        
        # 标记为已尝试
        application.provision_attempted = 1
        
        try:
            # 验证并创建子域名
            success, message, subdomain = FreePlanProvisionService._create_subdomain_for_application(application)
            
            if not success:
                # 创建失败，记录错误原因
                application.provision_error = message
                db.session.commit()
                return False, message, {'auto_created': False, 'error': message}
            
            # 创建成功，更新申请状态
            application.status = FreePlanApplication.STATUS_USED
            application.subdomain_id = subdomain.id
            application.provision_error = None
            db.session.commit()
            
            return True, '自动开通成功', {
                'auto_created': True,
                'subdomain': subdomain.to_dict()
            }
            
        except Exception as e:
            # 发生异常，回滚并记录错误
            db.session.rollback()
            error_msg = f'自动开通异常: {str(e)}'
            logger.error(f'[FreePlanProvision] Application {application_id} failed: {error_msg}')
            
            # 重新获取申请对象（因为回滚了）
            application = FreePlanApplication.query.get(application_id)
            application.provision_attempted = 1
            application.provision_error = error_msg
            db.session.commit()
            
            return False, error_msg, {'auto_created': False, 'error': error_msg}
    
    @staticmethod
    def _validate_subdomain_prefix(application, plan, domain):
        """
        验证域名前缀
        
        Returns:
            tuple: (valid: bool, error_message: str)
        """
        subdomain_name = application.subdomain_name.strip().lower()
        
        # 验证长度
        name_len = len(subdomain_name)
        if name_len < plan.min_length or name_len > plan.max_length:
            return False, f'域名前缀长度需在 {plan.min_length}-{plan.max_length} 个字符之间'
        
        # 验证格式
        if not validate_subdomain_name(subdomain_name, min_len=plan.min_length, max_len=plan.max_length):
            return False, '域名前缀格式不正确，只能包含字母、数字和连字符，且不能以连字符开头或结尾'
        
        # 检查是否已被占用
        existing = Subdomain.query.filter_by(domain_id=domain.id, name=subdomain_name).first()
        if existing:
            return False, '该域名前缀已被占用'
        
        # 检查敏感词
        from app.services.sensitive_filter import SensitiveFilter
        if SensitiveFilter.contains_sensitive(subdomain_name):
            return False, '该域名前缀包含敏感词'
        
        return True, ''
    
    @staticmethod
    def _create_subdomain_for_application(application):
        """
        为申请创建子域名
        
        Returns:
            tuple: (success: bool, message: str, subdomain: Subdomain or None)
        """
        # 获取用户、套餐、域名
        user = application.user
        plan = application.plan
        domain = application.domain
        
        if not user or not user.is_active:
            return False, '用户不可用', None
        
        if not plan or not plan.is_active:
            return False, '套餐不可用', None
        
        # 如果申请时没有指定域名，使用套餐关联的第一个域名
        if not domain:
            if not plan.domains:
                return False, '套餐未关联任何域名', None
            domain = plan.domains[0]
        else:
            # 验证域名是否在套餐关联的域名列表中
            if domain not in plan.domains:
                return False, '该域名不在套餐支持的域名列表中', None
        
        if not domain.is_active:
            return False, '域名不可用', None
        
        # 检查用户域名数量限制
        current_count = user.subdomains.count()
        if user.max_domains != -1 and current_count >= user.max_domains:
            return False, f'已达到域名数量上限（当前 {current_count}/{user.max_domains} 个）', None
        
        # 验证域名前缀
        valid, error_msg = FreePlanProvisionService._validate_subdomain_prefix(application, plan, domain)
        if not valid:
            return False, error_msg, None
        
        subdomain_name = application.subdomain_name.strip().lower()
        full_name = f"{subdomain_name}.{domain.name}"
        
        # 计算过期时间
        expires_at = None if plan.duration_days == -1 else beijing_now() + timedelta(days=plan.duration_days)
        
        # 处理上游DNS服务（如果有）
        upstream_subdomain_id = None
        if plan.upstream_plan_id and domain.upstream_domain_id and domain.dns_channel:
            if domain.dns_channel.provider_type == 'liuqu':
                try:
                    service = domain.dns_channel.get_service()
                    
                    # 先检查上游是否可用
                    check_result = service.check_subdomain_available(domain.upstream_domain_id, subdomain_name)
                    if not check_result.get('available', False):
                        return False, f'上游域名不可用: {check_result.get("message", "已被占用")}', None
                    
                    # 调用上游购买
                    upstream_result = service.purchase_subdomain(
                        domain_id=domain.upstream_domain_id,
                        prefix=subdomain_name,
                        plan_id=plan.upstream_plan_id
                    )
                    upstream_subdomain_id = upstream_result.get('subdomain', {}).get('id')
                    
                    # 使用上游返回的过期时间
                    upstream_expires = upstream_result.get('subdomain', {}).get('expires_at')
                    if upstream_expires:
                        from datetime import datetime as dt
                        try:
                            expires_at = dt.fromisoformat(upstream_expires.replace('Z', '+00:00'))
                        except:
                            pass
                            
                except DnsApiError as e:
                    return False, f'上游购买失败: {str(e)}', None
                except Exception as e:
                    return False, f'上游购买异常: {str(e)}', None
        
        # 创建子域名（免费套餐不扣除余额）
        subdomain = Subdomain(
            user_id=user.id,
            domain_id=domain.id,
            plan_id=plan.id,
            name=subdomain_name,
            full_name=full_name,
            expires_at=expires_at,
            upstream_subdomain_id=upstream_subdomain_id
        )
        db.session.add(subdomain)
        db.session.flush()  # 获取subdomain.id
        
        # 创建购买记录（价格为0，标记为免费套餐）
        purchase_record = FreePlanProvisionService._create_purchase_record(
            user.id, subdomain, plan, domain
        )
        db.session.add(purchase_record)
        
        # 记录操作日志
        from app.models import OperationLog
        from app.utils.ip_utils import get_real_ip
        detail_text = f'免费套餐自动开通: {full_name}, 套餐: {plan.name}'
        if upstream_subdomain_id:
            detail_text += f' (上游ID: {upstream_subdomain_id})'
        
        OperationLog.log(
            user_id=user.id,
            username=user.username,
            action=OperationLog.ACTION_CREATE,
            target_type='subdomain',
            target_id=subdomain.id,
            target_name=full_name,
            detail=detail_text,
            ip_address=get_real_ip()
        )
        
        # 记录域名创建活动
        from app.services.activity_tracker import ActivityTracker
        ActivityTracker.log(user.id, 'domain_create', {
            'subdomain_id': subdomain.id,
            'full_name': full_name,
            'plan_name': plan.name,
            'price': 0,
            'source': 'free_plan'
        })
        
        return True, '创建成功', subdomain
    
    @staticmethod
    def _create_purchase_record(user_id, subdomain, plan, domain):
        """
        创建购买记录
        
        Args:
            user_id: 用户ID
            subdomain: 子域名对象
            plan: 套餐对象
            domain: 域名对象
            
        Returns:
            PurchaseRecord: 购买记录对象
        """
        purchase_record = PurchaseRecord(
            user_id=user_id,
            subdomain_id=subdomain.id,
            plan_id=plan.id,
            plan_name=f'{plan.name}(免费套餐)',
            domain_name=domain.name,
            subdomain_name=subdomain.full_name,
            price=0.0,  # 免费套餐价格为0
            duration_days=plan.duration_days,
            payment_method='free_plan'  # 标记为免费套餐
        )
        return purchase_record
