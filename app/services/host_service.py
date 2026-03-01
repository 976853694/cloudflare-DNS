"""
托管商业务逻辑服务
处理托管商相关的所有业务逻辑
"""
from decimal import Decimal
from app import db
from app.models import User, Domain, Plan, Setting, DnsChannel
from app.models.host_application import HostApplication
from app.models.host_transaction import HostTransaction
from app.models.host_withdrawal import HostWithdrawal
from app.utils.timezone import now as beijing_now
from app.utils.logger import get_logger

logger = get_logger(__name__)


class HostService:
    """托管商服务类"""
    
    # ==================== 申请管理 ====================
    
    @staticmethod
    def create_application(user_id: int, reason: str) -> tuple:
        """
        创建托管商申请
        返回: (success, message, application)
        """
        user = User.query.get(user_id)
        if not user:
            return False, '用户不存在', None
        
        if not user.can_apply_host:
            return False, f'您已有待审核或已通过的申请（当前状态: {user.host_status}）', None
        
        # 检查托管功能是否启用
        if not Setting.get('host_enabled', True):
            return False, '托管功能未启用', None
        
        # 验证申请理由
        min_length = Setting.get('host_min_apply_reason', 10)
        if not reason or len(reason.strip()) < min_length:
            return False, f'申请理由至少需要{min_length}个字符', None
        
        try:
            application = HostApplication(
                user_id=user.id,
                reason=reason.strip(),
                status=HostApplication.STATUS_PENDING
            )
            user.host_status = User.HOST_STATUS_PENDING
            
            db.session.add(application)
            db.session.commit()
            
            logger.info(f"用户 {user.id} 成功提交托管商申请 (申请ID: {application.id})")
            return True, '申请已提交，请等待管理员审核', application
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建托管商申请失败: {str(e)}", exc_info=True)
            return False, '系统错误，请稍后重试', None
    
    @staticmethod
    def approve_application(application_id: int, admin_id: int, remark: str = None) -> tuple:
        """
        审核通过申请
        返回: (success, message)
        """
        application = HostApplication.query.get(application_id)
        if not application:
            return False, '申请不存在'
        
        if not application.is_pending:
            return False, '该申请已被处理'
        
        try:
            application.approve(admin_id, remark)
            
            # 更新用户状态
            user = application.user
            user.host_status = User.HOST_STATUS_APPROVED
            user.host_approved_at = beijing_now()
            
            db.session.commit()
            
            logger.info(f"管理员 {admin_id} 审核通过托管商申请 {application_id}")
            return True, '审核通过'
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"审核通过申请失败: {str(e)}", exc_info=True)
            return False, '系统错误'
    
    @staticmethod
    def reject_application(application_id: int, admin_id: int, remark: str) -> tuple:
        """
        拒绝申请
        返回: (success, message)
        """
        if not remark:
            return False, '请填写拒绝原因'
        
        application = HostApplication.query.get(application_id)
        if not application:
            return False, '申请不存在'
        
        if not application.is_pending:
            return False, '该申请已被处理'
        
        try:
            application.reject(admin_id, remark)
            
            # 更新用户状态
            user = application.user
            user.host_status = User.HOST_STATUS_REJECTED
            
            db.session.commit()
            
            logger.info(f"管理员 {admin_id} 拒绝托管商申请 {application_id}")
            return True, '已拒绝'
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"拒绝申请失败: {str(e)}", exc_info=True)
            return False, '系统错误'
    
    # ==================== 托管商管理 ====================
    
    @staticmethod
    def suspend_host(host_id: int, admin_id: int, reason: str) -> tuple:
        """
        暂停托管商
        返回: (success, message)
        """
        if not reason:
            return False, '请填写暂停原因'
        
        user = User.query.get(host_id)
        if not user:
            return False, '用户不存在'
        
        if user.host_status != User.HOST_STATUS_APPROVED:
            return False, '该用户不是活跃的托管商'
        
        try:
            user.host_status = User.HOST_STATUS_SUSPENDED
            user.host_suspended_at = beijing_now()
            user.host_suspended_reason = reason
            
            db.session.commit()
            
            logger.info(f"管理员 {admin_id} 暂停托管商 {host_id}")
            return True, '已暂停'
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"暂停托管商失败: {str(e)}", exc_info=True)
            return False, '系统错误'
    
    @staticmethod
    def resume_host(host_id: int, admin_id: int) -> tuple:
        """
        恢复托管商
        返回: (success, message)
        """
        user = User.query.get(host_id)
        if not user:
            return False, '用户不存在'
        
        if user.host_status != User.HOST_STATUS_SUSPENDED:
            return False, '该用户不是被暂停的托管商'
        
        try:
            user.host_status = User.HOST_STATUS_APPROVED
            user.host_suspended_at = None
            user.host_suspended_reason = None
            
            db.session.commit()
            
            logger.info(f"管理员 {admin_id} 恢复托管商 {host_id}")
            return True, '已恢复'
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"恢复托管商失败: {str(e)}", exc_info=True)
            return False, '系统错误'
    
    @staticmethod
    def revoke_host(host_id: int, admin_id: int, reason: str) -> tuple:
        """
        撤销托管商资格
        返回: (success, message)
        """
        if not reason:
            return False, '请填写撤销原因'
        
        user = User.query.get(host_id)
        if not user:
            return False, '用户不存在'
        
        if user.host_status not in [User.HOST_STATUS_APPROVED, User.HOST_STATUS_SUSPENDED]:
            return False, '该用户不是托管商'
        
        try:
            user.host_status = User.HOST_STATUS_REVOKED
            user.host_suspended_at = beijing_now()
            user.host_suspended_reason = reason
            
            db.session.commit()
            
            logger.info(f"管理员 {admin_id} 撤销托管商 {host_id}")
            return True, '已撤销'
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"撤销托管商失败: {str(e)}", exc_info=True)
            return False, '系统错误'
    
    # ==================== 收益管理 ====================
    
    @staticmethod
    def calculate_earnings(total_amount: Decimal, host_id: int) -> tuple:
        """
        计算托管商收益
        返回: (host_earnings, platform_fee, commission_rate)
        """
        user = User.query.get(host_id)
        if not user:
            return Decimal('0'), total_amount, Decimal('0')
        
        # 获取抽成比例
        default_rate = Setting.get('host_default_commission', 10)
        commission_rate = user.get_effective_commission_rate(default_rate)
        
        # 计算平台抽成和托管商收益
        platform_fee = total_amount * Decimal(str(commission_rate)) / Decimal('100')
        host_earnings = total_amount - platform_fee
        
        return host_earnings, platform_fee, Decimal(str(commission_rate))
    
    @staticmethod
    def create_transaction(host_id: int, purchase_record_id: int, domain_id: int, 
                          total_amount: Decimal) -> tuple:
        """
        创建交易记录
        返回: (success, message, transaction)
        """
        try:
            host_earnings, platform_fee, commission_rate = HostService.calculate_earnings(
                total_amount, host_id
            )
            
            transaction = HostTransaction(
                host_id=host_id,
                purchase_record_id=purchase_record_id,
                domain_id=domain_id,
                total_amount=total_amount,
                platform_fee=platform_fee,
                host_earnings=host_earnings,
                commission_rate=commission_rate
            )
            
            # 更新托管商余额
            user = User.query.get(host_id)
            if user:
                user.add_host_balance(host_earnings)
            
            db.session.add(transaction)
            db.session.commit()
            
            logger.info(f"创建托管商交易记录: host={host_id}, amount={total_amount}, earnings={host_earnings}")
            return True, '交易记录已创建', transaction
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建交易记录失败: {str(e)}", exc_info=True)
            return False, '系统错误', None
    
    # ==================== 提现管理 ====================
    
    @staticmethod
    def create_withdrawal(host_id: int, amount: Decimal, payment_method: str,
                         payment_account: str, payment_name: str) -> tuple:
        """
        创建提现申请
        返回: (success, message, withdrawal)
        """
        user = User.query.get(host_id)
        if not user:
            return False, '用户不存在', None
        
        if not user.is_host:
            return False, '您不是托管商', None
        
        # 检查余额
        if user.host_balance < amount:
            return False, f'余额不足，当前余额: ¥{user.host_balance}', None
        
        # 检查最小提现金额
        min_amount = Setting.get('host_min_withdrawal', 10)
        if amount < min_amount:
            return False, f'最小提现金额为 ¥{min_amount}', None
        
        # 检查是否有待处理的提现
        pending = HostWithdrawal.query.filter_by(
            host_id=host_id, 
            status=HostWithdrawal.STATUS_PENDING
        ).first()
        if pending:
            return False, '您有待处理的提现申请，请等待处理完成', None
        
        try:
            withdrawal = HostWithdrawal(
                host_id=host_id,
                amount=amount,
                payment_method=payment_method,
                payment_account=payment_account,
                payment_name=payment_name,
                status=HostWithdrawal.STATUS_PENDING
            )
            
            # 冻结余额
            user.host_balance -= amount
            
            db.session.add(withdrawal)
            db.session.commit()
            
            logger.info(f"托管商 {host_id} 创建提现申请: ¥{amount}")
            return True, '提现申请已提交', withdrawal
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建提现申请失败: {str(e)}", exc_info=True)
            return False, '系统错误', None
    
    @staticmethod
    def approve_withdrawal(withdrawal_id: int, admin_id: int, remark: str = None) -> tuple:
        """
        审核通过提现
        返回: (success, message)
        """
        withdrawal = HostWithdrawal.query.get(withdrawal_id)
        if not withdrawal:
            return False, '提现申请不存在'
        
        if not withdrawal.is_pending:
            return False, '该申请已被处理'
        
        try:
            withdrawal.approve(admin_id, remark)
            db.session.commit()
            
            logger.info(f"管理员 {admin_id} 审核通过提现申请 {withdrawal_id}")
            return True, '审核通过'
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"审核通过提现失败: {str(e)}", exc_info=True)
            return False, '系统错误'
    
    @staticmethod
    def reject_withdrawal(withdrawal_id: int, admin_id: int, remark: str) -> tuple:
        """
        拒绝提现
        返回: (success, message)
        """
        if not remark:
            return False, '请填写拒绝原因'
        
        withdrawal = HostWithdrawal.query.get(withdrawal_id)
        if not withdrawal:
            return False, '提现申请不存在'
        
        if not withdrawal.is_pending:
            return False, '该申请已被处理'
        
        try:
            withdrawal.reject(admin_id, remark)
            
            # 返还余额
            user = withdrawal.host
            if user:
                user.host_balance += withdrawal.amount
            
            db.session.commit()
            
            logger.info(f"管理员 {admin_id} 拒绝提现申请 {withdrawal_id}")
            return True, '已拒绝，金额已返还'
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"拒绝提现失败: {str(e)}", exc_info=True)
            return False, '系统错误'
    
    @staticmethod
    def complete_withdrawal(withdrawal_id: int, admin_id: int) -> tuple:
        """
        完成提现
        返回: (success, message)
        """
        withdrawal = HostWithdrawal.query.get(withdrawal_id)
        if not withdrawal:
            return False, '提现申请不存在'
        
        if not withdrawal.is_approved:
            return False, '该申请未通过审核'
        
        try:
            withdrawal.complete()
            db.session.commit()
            
            logger.info(f"管理员 {admin_id} 完成提现申请 {withdrawal_id}")
            return True, '已完成'
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"完成提现失败: {str(e)}", exc_info=True)
            return False, '系统错误'
    
    # ==================== 统计数据 ====================
    
    @staticmethod
    def get_host_statistics(host_id: int) -> dict:
        """获取托管商统计数据"""
        user = User.query.get(host_id)
        if not user:
            return {}
        
        # 渠道数量
        channels_count = DnsChannel.query.filter_by(owner_id=host_id).count()
        
        # 域名数量
        domains_count = Domain.query.filter_by(owner_id=host_id).count()
        
        # 套餐数量
        plans_count = Plan.query.filter_by(owner_id=host_id).count()
        
        # 总收益
        total_earnings = db.session.query(db.func.sum(HostTransaction.host_earnings))\
            .filter_by(host_id=host_id).scalar() or Decimal('0')
        
        # 待结算余额
        pending_balance = user.host_balance
        
        # 已提现金额
        withdrawn = db.session.query(db.func.sum(HostWithdrawal.amount))\
            .filter_by(host_id=host_id, status=HostWithdrawal.STATUS_COMPLETED).scalar() or Decimal('0')
        
        # 待处理提现
        pending_withdrawal = db.session.query(db.func.sum(HostWithdrawal.amount))\
            .filter(
                HostWithdrawal.host_id == host_id,
                HostWithdrawal.status.in_([HostWithdrawal.STATUS_PENDING, HostWithdrawal.STATUS_APPROVED])
            ).scalar() or Decimal('0')
        
        return {
            'channels_count': channels_count,
            'domains_count': domains_count,
            'plans_count': plans_count,
            'total_earnings': float(total_earnings),
            'pending_balance': float(pending_balance),
            'withdrawn': float(withdrawn),
            'pending_withdrawal': float(pending_withdrawal)
        }
    
    @staticmethod
    def get_admin_statistics() -> dict:
        """获取管理员统计数据"""
        # 托管商数量
        total_hosts = User.query.filter(
            User.host_status.in_([User.HOST_STATUS_APPROVED, User.HOST_STATUS_SUSPENDED])
        ).count()
        
        active_hosts = User.query.filter_by(host_status=User.HOST_STATUS_APPROVED).count()
        
        # 待审核申请
        pending_applications = HostApplication.query.filter_by(
            status=HostApplication.STATUS_PENDING
        ).count()
        
        # 待处理提现
        pending_withdrawals = HostWithdrawal.query.filter_by(
            status=HostWithdrawal.STATUS_PENDING
        ).count()
        
        # 总交易额
        total_transactions = db.session.query(db.func.sum(HostTransaction.total_amount)).scalar() or Decimal('0')
        
        # 平台总收益
        platform_earnings = db.session.query(db.func.sum(HostTransaction.platform_fee)).scalar() or Decimal('0')
        
        # 托管商总收益
        host_earnings = db.session.query(db.func.sum(HostTransaction.host_earnings)).scalar() or Decimal('0')
        
        return {
            'total_hosts': total_hosts,
            'active_hosts': active_hosts,
            'pending_applications': pending_applications,
            'pending_withdrawals': pending_withdrawals,
            'total_transactions': float(total_transactions),
            'platform_earnings': float(platform_earnings),
            'host_earnings': float(host_earnings)
        }
