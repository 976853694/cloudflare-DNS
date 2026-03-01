"""
自动续费服务
当用户余额充足且域名即将到期时自动续费
"""
from datetime import timedelta
from decimal import Decimal
from app import db
from app.models import Subdomain, User, Plan, PurchaseRecord, Setting, OperationLog
from app.utils.timezone import now as beijing_now
from app.utils.logger import get_logger

logger = get_logger('dns.auto_renew')


class AutoRenewService:
    """自动续费服务"""
    
    @staticmethod
    def is_enabled():
        """检查自动续费功能是否启用"""
        return Setting.get('auto_renew_enabled', '0') == '1'
    
    @staticmethod
    def get_renew_days_before():
        """获取提前续费天数"""
        return int(Setting.get('auto_renew_days_before', '3'))
    
    @staticmethod
    def process_auto_renew():
        """
        处理自动续费
        
        Returns:
            dict: {success: int, failed: int, skipped: int}
        """
        if not AutoRenewService.is_enabled():
            logger.info('自动续费功能未启用')
            return {'success': 0, 'failed': 0, 'skipped': 0, 'disabled': True}
        
        result = {'success': 0, 'failed': 0, 'skipped': 0}
        days_before = AutoRenewService.get_renew_days_before()
        
        # 查找即将到期的域名（N天内到期）
        target_date = beijing_now() + timedelta(days=days_before)
        
        expiring_subdomains = Subdomain.query.filter(
            Subdomain.expires_at != None,
            Subdomain.expires_at <= target_date,
            Subdomain.expires_at > beijing_now(),
            Subdomain.status == 1,
            Subdomain.auto_renew == 1  # 需要用户开启自动续费
        ).all()
        
        for subdomain in expiring_subdomains:
            try:
                renewed = AutoRenewService.renew_single(subdomain)
                if renewed:
                    result['success'] += 1
                else:
                    result['skipped'] += 1
            except Exception as e:
                logger.error(f'自动续费失败 [{subdomain.full_name}]: {e}')
                result['failed'] += 1
        
        logger.info(f'自动续费完成: 成功{result["success"]}, 失败{result["failed"]}, 跳过{result["skipped"]}')
        return result
    
    @staticmethod
    def renew_single(subdomain):
        """
        续费单个域名
        
        Args:
            subdomain: Subdomain对象
            
        Returns:
            bool: 是否成功续费
        """
        user = subdomain.user
        if not user or not user.is_active:
            logger.warning(f'用户不可用，跳过续费 [{subdomain.full_name}]')
            return False
        
        # 获取续费套餐（使用当前套餐或默认最便宜的套餐）
        plan = subdomain.plan
        if not plan or not plan.is_active or plan.duration_days == -1:
            # 查找关联该域名的最便宜的非永久套餐
            plan = Plan.query.filter(
                Plan.domains.any(id=subdomain.domain_id),
                Plan.status == 1,
                Plan.duration_days > 0
            ).order_by(Plan.price).first()
        
        if not plan:
            logger.warning(f'没有可用的续费套餐 [{subdomain.full_name}]')
            # 发送失败通知
            AutoRenewService._send_failed_email(user, subdomain, '没有可用的续费套餐')
            return False
        
        # 检查余额
        if not user.can_afford(plan.price):
            logger.info(f'余额不足，跳过续费 [{subdomain.full_name}], 需要¥{plan.price}, 余额: {user.balance}')
            # 发送失败通知
            AutoRenewService._send_failed_email(user, subdomain, f'余额不足（需要¥{plan.price}，当前余额¥{user.balance}）')
            return False
        
        # 扣除余额
        user.deduct_balance(plan.price)
        
        # 延长到期时间
        base_time = subdomain.expires_at if subdomain.expires_at > beijing_now() else beijing_now()
        subdomain.expires_at = base_time + timedelta(days=plan.duration_days)
        subdomain.plan_id = plan.id
        
        # 创建购买记录
        purchase_record = PurchaseRecord(
            user_id=user.id,
            subdomain_id=subdomain.id,
            plan_id=plan.id,
            plan_name=f'{plan.name}(自动续费)',
            domain_name=subdomain.domain.name,
            subdomain_name=subdomain.full_name,
            price=plan.price,
            duration_days=plan.duration_days,
            payment_method='balance'
        )
        db.session.add(purchase_record)
        db.session.flush()  # 获取 purchase_record.id
        
        # ========== 托管商收益分成（自动续费） ==========
        domain = subdomain.domain
        if domain.is_host_owned and domain.owner_id:
            from app.models.host_transaction import HostTransaction
            from app.models import User as UserModel
            
            host = UserModel.query.get(domain.owner_id)
            if host and host.is_host:
                # 获取抽成比例
                default_commission = Setting.get('host_default_commission', 10)
                commission_rate = host.get_effective_commission_rate(default_commission)
                
                # 创建交易记录并计算收益
                transaction = HostTransaction.create_transaction(
                    host_id=host.id,
                    purchase_record_id=purchase_record.id,
                    domain_id=domain.id,
                    total_amount=float(plan.price),
                    commission_rate=commission_rate
                )
                db.session.add(transaction)
                
                # 增加托管商余额
                host.add_host_balance(transaction.host_earnings)
        
        # 记录操作日志
        OperationLog.log(
            user_id=user.id,
            username=user.username,
            action=OperationLog.ACTION_UPDATE,
            target_type='subdomain',
            target_id=subdomain.id,
            target_name=subdomain.full_name,
            detail=f'自动续费: {subdomain.full_name}, 套餐: {plan.name}, 金额: ¥{plan.price}'
        )
        
        db.session.commit()
        
        logger.info(f'自动续费成功 [{subdomain.full_name}], 延长{plan.duration_days}天, 扣款¥{plan.price}')
        
        # 发送成功通知邮件
        AutoRenewService._send_success_email(user, subdomain, plan)
        
        return True
    
    @staticmethod
    def _send_success_email(user, subdomain, plan):
        """发送自动续费成功邮件"""
        try:
            from app.services.email_service import EmailService
            from app.services.email_template_service import EmailTemplateService
            
            variables = {
                'username': user.username,
                'domain_name': subdomain.full_name,
                'plan_name': plan.name,
                'price': str(plan.price),
                'duration_days': plan.duration_days,
                'expires_at': subdomain.expires_at.strftime('%Y-%m-%d %H:%M:%S'),
                'balance': str(user.balance)
            }
            
            subject, html_content = EmailTemplateService.render_email('auto_renew_success', variables)
            EmailService.send(user.email, subject, html_content)
            logger.info(f'自动续费成功邮件已发送: {user.email}')
        except Exception as e:
            logger.error(f'发送自动续费成功邮件失败: {e}')
    
    @staticmethod
    def _send_failed_email(user, subdomain, reason):
        """发送自动续费失败邮件"""
        try:
            from app.services.email_service import EmailService
            from app.services.email_template_service import EmailTemplateService
            
            variables = {
                'username': user.username,
                'domain_name': subdomain.full_name,
                'reason': reason,
                'expires_at': subdomain.expires_at.strftime('%Y-%m-%d %H:%M:%S') if subdomain.expires_at else '未知',
                'balance': str(user.balance)
            }
            
            subject, html_content = EmailTemplateService.render_email('auto_renew_failed', variables)
            EmailService.send(user.email, subject, html_content)
            logger.info(f'自动续费失败邮件已发送: {user.email}')
        except Exception as e:
            logger.error(f'发送自动续费失败邮件失败: {e}')


def init_auto_renew_settings():
    """初始化自动续费相关设置"""
    defaults = {
        'auto_renew_enabled': '0',  # 是否启用自动续费
        'auto_renew_days_before': '3',  # 提前几天自动续费
    }
    
    for key, value in defaults.items():
        if Setting.get(key) is None:
            Setting.set(key, value)
