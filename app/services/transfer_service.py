"""
域名转移服务
提供域名转移的核心业务逻辑
"""
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional

from app import db
from app.models import User, Subdomain, Setting
from app.models.domain_transfer import DomainTransfer
from app.models.point_record import PointRecord
from app.utils.timezone import now as beijing_now

logger = logging.getLogger(__name__)


class TransferService:
    """域名转移服务"""
    
    # 状态常量
    STATUS_PENDING = DomainTransfer.STATUS_PENDING
    STATUS_COMPLETED = DomainTransfer.STATUS_COMPLETED
    STATUS_CANCELLED = DomainTransfer.STATUS_CANCELLED
    STATUS_EXPIRED = DomainTransfer.STATUS_EXPIRED
    
    # 默认配置
    DEFAULT_ENABLED = '1'
    DEFAULT_FEE = '0'
    DEFAULT_COOLDOWN = '24'
    DEFAULT_DAILY_LIMIT = '5'
    DEFAULT_VERIFY_EXPIRE = '10'
    DEFAULT_NOTIFY_EMAIL = '1'
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """
        获取转移配置
        
        Returns:
            Dict: 配置字典
        """
        return {
            'enabled': Setting.get('domain_transfer_enabled', cls.DEFAULT_ENABLED) == '1',
            'fee': int(Setting.get('domain_transfer_fee', cls.DEFAULT_FEE)),
            'cooldown': int(Setting.get('domain_transfer_cooldown', cls.DEFAULT_COOLDOWN)),
            'daily_limit': int(Setting.get('domain_transfer_daily_limit', cls.DEFAULT_DAILY_LIMIT)),
            'verify_expire': int(Setting.get('domain_transfer_verify_expire', cls.DEFAULT_VERIFY_EXPIRE)),
            'notify_email': Setting.get('domain_transfer_notify_email', cls.DEFAULT_NOTIFY_EMAIL) == '1'
        }
    
    @classmethod
    def _generate_verify_code(cls) -> str:
        """
        生成6位数字验证码
        
        Returns:
            str: 6位数字验证码
        """
        return str(random.randint(0, 999999)).zfill(6)
    
    @classmethod
    def _check_cooldown(cls, subdomain_id: int) -> Tuple[bool, int]:
        """
        检查冷却期
        
        Args:
            subdomain_id: 子域名ID
            
        Returns:
            Tuple[bool, int]: (是否在冷却期, 剩余秒数)
        """
        config = cls.get_config()
        cooldown_hours = config['cooldown']
        
        if cooldown_hours <= 0:
            return False, 0
        
        # 查找该子域名最近一次完成的转移
        last_transfer = DomainTransfer.query.filter_by(
            subdomain_id=subdomain_id,
            status=cls.STATUS_COMPLETED
        ).order_by(DomainTransfer.completed_at.desc()).first()
        
        if not last_transfer or not last_transfer.completed_at:
            return False, 0
        
        cooldown_end = last_transfer.completed_at + timedelta(hours=cooldown_hours)
        now = beijing_now()
        
        if now >= cooldown_end:
            return False, 0
        
        remaining = (cooldown_end - now).total_seconds()
        return True, int(remaining)
    
    @classmethod
    def _check_daily_limit(cls, user_id: int) -> Tuple[bool, int]:
        """
        检查每日限制
        
        Args:
            user_id: 用户ID
            
        Returns:
            Tuple[bool, int]: (是否超限, 今日已转移数)
        """
        config = cls.get_config()
        daily_limit = config['daily_limit']
        
        if daily_limit <= 0:
            return False, 0
        
        # 统计今日发起的转移数（不含已取消和已过期）
        today = beijing_now().date()
        today_count = DomainTransfer.query.filter(
            DomainTransfer.from_user_id == user_id,
            db.func.date(DomainTransfer.created_at) == today,
            DomainTransfer.status.in_([cls.STATUS_PENDING, cls.STATUS_COMPLETED])
        ).count()
        
        return today_count >= daily_limit, today_count
    
    @classmethod
    def initiate_transfer(
        cls, 
        user_id: int, 
        subdomain_id: int, 
        to_username: str, 
        remark: str = None
    ) -> Dict[str, Any]:
        """
        发起转移请求
        
        Args:
            user_id: 发起用户ID
            subdomain_id: 子域名ID
            to_username: 目标用户名
            remark: 备注
            
        Returns:
            Dict: 包含 transfer_id, fee_points, expires_in
            
        Raises:
            ValueError: 验证失败时抛出
        """
        config = cls.get_config()
        
        # 1. 验证转移功能是否开启
        if not config['enabled']:
            raise ValueError('TRANSFER_DISABLED|转移功能已关闭')
        
        # 2. 验证用户是否拥有该子域名
        subdomain = Subdomain.query.get(subdomain_id)
        if not subdomain:
            raise ValueError('NOT_FOUND|子域名不存在')
        
        if subdomain.user_id != user_id:
            raise ValueError('NOT_OWNER|您不是该域名的所有者')
        
        # 3. 验证目标用户是否存在且不是自己
        to_user = User.query.filter_by(username=to_username).first()
        if not to_user:
            raise ValueError('USER_NOT_FOUND|目标用户不存在')
        
        if to_user.id == user_id:
            raise ValueError('SELF_TRANSFER|不能转移给自己')
        
        # 4. 验证子域名是否在冷却期
        in_cooldown, remaining = cls._check_cooldown(subdomain_id)
        if in_cooldown:
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            raise ValueError(f'COOLDOWN_PERIOD|域名在冷却期内，剩余 {hours}小时{minutes}分钟')
        
        # 5. 验证是否超过每日限制
        exceeded, today_count = cls._check_daily_limit(user_id)
        if exceeded:
            raise ValueError(f'DAILY_LIMIT_EXCEEDED|今日转移次数已达上限（{config["daily_limit"]}次）')
        
        # 6. 验证积分是否足够
        from_user = User.query.get(user_id)
        fee = config['fee']
        if fee > 0 and from_user.points < fee:
            raise ValueError(f'INSUFFICIENT_POINTS|积分不足，需要 {fee} 积分')
        
        # 7. 验证是否有待处理的转移
        pending = DomainTransfer.query.filter_by(
            subdomain_id=subdomain_id,
            status=cls.STATUS_PENDING
        ).first()
        if pending:
            raise ValueError('PENDING_TRANSFER|该域名有待处理的转移请求')
        
        # 8. 生成验证码
        verify_code = cls._generate_verify_code()
        verify_expire_minutes = config['verify_expire']
        verify_expires = beijing_now() + timedelta(minutes=verify_expire_minutes)
        
        try:
            # 9. 创建转移记录
            transfer = DomainTransfer(
                subdomain_id=subdomain_id,
                subdomain_name=subdomain.full_name,
                from_user_id=user_id,
                from_username=from_user.username,
                to_user_id=None,  # 确认后再填充
                to_username=to_username,
                fee_points=fee,
                verify_code=verify_code,
                verify_expires=verify_expires,
                code_sent_at=beijing_now(),
                status=cls.STATUS_PENDING,
                remark=remark
            )
            db.session.add(transfer)
            db.session.commit()
            
            # 10. 发送验证码邮件（失败不影响转移记录创建）
            if config['notify_email']:
                try:
                    cls._send_verify_code_email(
                        from_user.email,
                        subdomain.full_name,
                        to_username,
                        verify_code,
                        verify_expire_minutes,
                        fee
                    )
                except Exception as e:
                    logger.error(f"Send verify code email failed: {e}")
                    # 邮件发送失败不影响转移记录创建
            
            logger.info(f"Transfer initiated: {subdomain.full_name} from {from_user.username} to {to_username}")
            
            return {
                'transfer_id': transfer.id,
                'fee_points': fee,
                'expires_in': verify_expire_minutes * 60
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Initiate transfer failed: {e}")
            raise ValueError(f'SYSTEM_ERROR|系统错误：{str(e)}')
    
    @classmethod
    def verify_transfer(
        cls, 
        user_id: int, 
        transfer_id: int, 
        verify_code: str
    ) -> Dict[str, Any]:
        """
        验证并确认转移
        
        Args:
            user_id: 用户ID
            transfer_id: 转移记录ID
            verify_code: 验证码
            
        Returns:
            Dict: 包含 subdomain_name, to_username, fee_points
            
        Raises:
            ValueError: 验证失败时抛出
        """
        # 1. 查找转移记录
        transfer = DomainTransfer.query.get(transfer_id)
        if not transfer:
            raise ValueError('TRANSFER_NOT_FOUND|转移记录不存在')
        
        # 2. 验证是否是发起者
        if transfer.from_user_id != user_id:
            raise ValueError('NOT_OWNER|您不是该转移的发起者')
        
        # 3. 验证状态
        if not transfer.is_pending:
            raise ValueError('CANNOT_VERIFY|该转移已处理，无法验证')
        
        # 4. 验证验证码是否过期
        if transfer.is_code_expired:
            raise ValueError('CODE_EXPIRED|验证码已过期，请重新发送')
        
        # 5. 验证验证码是否正确
        if transfer.verify_code != verify_code:
            raise ValueError('INVALID_CODE|验证码错误')
        
        # 6. 再次验证积分是否足够（防止发起后积分被消耗）
        from_user = User.query.get(user_id)
        if transfer.fee_points > 0 and from_user.points < transfer.fee_points:
            raise ValueError(f'INSUFFICIENT_POINTS|积分不足，需要 {transfer.fee_points} 积分')
        
        # 7. 查找目标用户
        to_user = User.query.filter_by(username=transfer.to_username).first()
        if not to_user:
            raise ValueError('USER_NOT_FOUND|目标用户不存在')
        
        # 8. 查找子域名
        subdomain = Subdomain.query.get(transfer.subdomain_id)
        if not subdomain:
            raise ValueError('NOT_FOUND|子域名不存在')
        
        config = cls.get_config()
        
        try:
            # 9. 在事务中执行转移
            # 9.1 扣除积分
            if transfer.fee_points > 0:
                from_user.points -= transfer.fee_points
                
                # 记录积分变动
                point_record = PointRecord(
                    user_id=user_id,
                    type='transfer',
                    points=-transfer.fee_points,
                    balance=from_user.points,
                    description=f'域名转移手续费 ({transfer.subdomain_name})',
                    related_id=transfer.id
                )
                db.session.add(point_record)
            
            # 9.2 更新子域名所有者
            subdomain.user_id = to_user.id
            
            # 9.3 更新转移记录状态
            transfer.status = cls.STATUS_COMPLETED
            transfer.to_user_id = to_user.id
            transfer.completed_at = beijing_now()
            
            db.session.commit()
            
            # 10. 发送通知邮件（失败不影响转移完成）
            if config['notify_email']:
                try:
                    # 发送给接收方
                    cls._send_received_email(
                        to_user.email,
                        transfer.subdomain_name,
                        from_user.username
                    )
                except Exception as e:
                    logger.error(f"Send received email failed: {e}")
                
                try:
                    # 发送给发起方
                    cls._send_completed_email(
                        from_user.email,
                        transfer.subdomain_name,
                        to_user.username,
                        transfer.fee_points
                    )
                except Exception as e:
                    logger.error(f"Send completed email failed: {e}")
            
            logger.info(f"Transfer completed: {transfer.subdomain_name} from {from_user.username} to {to_user.username}")
            
            return {
                'subdomain_name': transfer.subdomain_name,
                'to_username': to_user.username,
                'fee_points': transfer.fee_points
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Verify transfer failed: {e}")
            raise ValueError(f'SYSTEM_ERROR|系统错误：{str(e)}')
    
    @classmethod
    def cancel_transfer(cls, user_id: int, transfer_id: int) -> bool:
        """
        取消转移请求
        
        Args:
            user_id: 用户ID
            transfer_id: 转移记录ID
            
        Returns:
            bool: 是否成功
            
        Raises:
            ValueError: 验证失败时抛出
        """
        transfer = DomainTransfer.query.get(transfer_id)
        if not transfer:
            raise ValueError('TRANSFER_NOT_FOUND|转移记录不存在')
        
        if transfer.from_user_id != user_id:
            raise ValueError('NOT_OWNER|您不是该转移的发起者')
        
        if not transfer.is_pending:
            raise ValueError('CANNOT_CANCEL|该转移已处理，无法取消')
        
        try:
            transfer.status = cls.STATUS_CANCELLED
            db.session.commit()
            
            logger.info(f"Transfer cancelled: {transfer.subdomain_name}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Cancel transfer failed: {e}")
            raise ValueError(f'SYSTEM_ERROR|系统错误：{str(e)}')
    
    @classmethod
    def resend_code(cls, user_id: int, transfer_id: int) -> Dict[str, Any]:
        """
        重发验证码
        
        Args:
            user_id: 用户ID
            transfer_id: 转移记录ID
            
        Returns:
            Dict: 包含 expires_in
            
        Raises:
            ValueError: 验证失败时抛出
        """
        transfer = DomainTransfer.query.get(transfer_id)
        if not transfer:
            raise ValueError('TRANSFER_NOT_FOUND|转移记录不存在')
        
        if transfer.from_user_id != user_id:
            raise ValueError('NOT_OWNER|您不是该转移的发起者')
        
        if not transfer.is_pending:
            raise ValueError('CANNOT_RESEND|该转移已处理，无法重发验证码')
        
        # 检查重发间隔
        can_resend, wait_seconds = transfer.can_resend_code
        if not can_resend:
            raise ValueError(f'RESEND_TOO_FAST|请等待 {wait_seconds} 秒后再重发')
        
        config = cls.get_config()
        
        try:
            # 生成新验证码
            verify_code = cls._generate_verify_code()
            verify_expire_minutes = config['verify_expire']
            
            transfer.verify_code = verify_code
            transfer.verify_expires = beijing_now() + timedelta(minutes=verify_expire_minutes)
            transfer.code_sent_at = beijing_now()
            
            db.session.commit()
            
            # 发送验证码邮件（失败不影响重发操作）
            if config['notify_email']:
                try:
                    from_user = User.query.get(user_id)
                    cls._send_verify_code_email(
                        from_user.email,
                        transfer.subdomain_name,
                        transfer.to_username,
                        verify_code,
                        verify_expire_minutes,
                        transfer.fee_points
                    )
                except Exception as e:
                    logger.error(f"Resend verify code email failed: {e}")
                    # 邮件发送失败不影响验证码更新
            
            logger.info(f"Verification code resent for transfer: {transfer.subdomain_name}")
            
            return {
                'expires_in': verify_expire_minutes * 60
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Resend code failed: {e}")
            raise ValueError(f'SYSTEM_ERROR|系统错误：{str(e)}')

    
    @classmethod
    def get_user_transfers(
        cls, 
        user_id: int, 
        direction: str = 'all',
        status: int = None,
        page: int = 1, 
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        获取用户转移记录
        
        Args:
            user_id: 用户ID
            direction: 方向过滤 (all/in/out)
            status: 状态过滤
            page: 页码
            per_page: 每页数量
            
        Returns:
            Dict: 分页的转移记录
        """
        query = DomainTransfer.query
        
        # 方向过滤
        if direction == 'in':
            query = query.filter(DomainTransfer.to_user_id == user_id)
        elif direction == 'out':
            query = query.filter(DomainTransfer.from_user_id == user_id)
        else:
            query = query.filter(
                db.or_(
                    DomainTransfer.from_user_id == user_id,
                    DomainTransfer.to_user_id == user_id
                )
            )
        
        # 状态过滤
        if status is not None:
            query = query.filter(DomainTransfer.status == status)
        
        # 排序
        query = query.order_by(DomainTransfer.created_at.desc())
        
        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': [t.to_dict(for_user_id=user_id) for t in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page,
            'per_page': per_page
        }
    
    @classmethod
    def get_admin_transfers(
        cls,
        keyword: str = None,
        status: int = None,
        date_from: str = None,
        date_to: str = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        获取所有转移记录（管理员）
        
        Args:
            keyword: 搜索关键词（域名/用户名）
            status: 状态过滤
            date_from: 开始日期
            date_to: 结束日期
            page: 页码
            per_page: 每页数量
            
        Returns:
            Dict: 分页的转移记录
        """
        query = DomainTransfer.query
        
        # 关键词搜索
        if keyword:
            keyword_filter = f'%{keyword}%'
            query = query.filter(
                db.or_(
                    DomainTransfer.subdomain_name.like(keyword_filter),
                    DomainTransfer.from_username.like(keyword_filter),
                    DomainTransfer.to_username.like(keyword_filter)
                )
            )
        
        # 状态过滤
        if status is not None:
            query = query.filter(DomainTransfer.status == status)
        
        # 日期范围过滤
        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                query = query.filter(DomainTransfer.created_at >= from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                query = query.filter(DomainTransfer.created_at < to_date)
            except ValueError:
                pass
        
        # 排序
        query = query.order_by(DomainTransfer.created_at.desc())
        
        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'items': [t.to_admin_dict() for t in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page,
            'per_page': per_page
        }
    
    @classmethod
    def get_transfer_stats(cls) -> Dict[str, Any]:
        """
        获取转移统计数据
        
        Returns:
            Dict: 统计数据
        """
        # 总数统计
        total = DomainTransfer.query.count()
        completed = DomainTransfer.query.filter_by(status=cls.STATUS_COMPLETED).count()
        pending = DomainTransfer.query.filter_by(status=cls.STATUS_PENDING).count()
        cancelled = DomainTransfer.query.filter_by(status=cls.STATUS_CANCELLED).count()
        expired = DomainTransfer.query.filter_by(status=cls.STATUS_EXPIRED).count()
        
        # 手续费总额
        total_fee = db.session.query(
            db.func.sum(DomainTransfer.fee_points)
        ).filter(
            DomainTransfer.status == cls.STATUS_COMPLETED
        ).scalar() or 0
        
        # 今日转移数
        today = beijing_now().date()
        today_count = DomainTransfer.query.filter(
            db.func.date(DomainTransfer.created_at) == today
        ).count()
        
        # 本月转移数
        first_day_of_month = today.replace(day=1)
        month_count = DomainTransfer.query.filter(
            DomainTransfer.created_at >= first_day_of_month
        ).count()
        
        return {
            'total_transfers': total,
            'completed_transfers': completed,
            'pending_transfers': pending,
            'cancelled_transfers': cancelled,
            'expired_transfers': expired,
            'total_fee_collected': total_fee,
            'today_transfers': today_count,
            'this_month_transfers': month_count
        }
    
    @classmethod
    def add_admin_remark(cls, transfer_id: int, remark: str) -> bool:
        """
        添加管理员备注
        
        Args:
            transfer_id: 转移记录ID
            remark: 备注内容
            
        Returns:
            bool: 是否成功
        """
        transfer = DomainTransfer.query.get(transfer_id)
        if not transfer:
            raise ValueError('TRANSFER_NOT_FOUND|转移记录不存在')
        
        try:
            transfer.admin_remark = remark
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Add admin remark failed: {e}")
            raise ValueError(f'SYSTEM_ERROR|系统错误：{str(e)}')
    
    @classmethod
    def expire_pending_transfers(cls) -> int:
        """
        过期处理待验证的转移（定时任务调用）
        
        Returns:
            int: 处理数量
        """
        now = beijing_now()
        
        # 查找所有过期的待验证转移
        expired_transfers = DomainTransfer.query.filter(
            DomainTransfer.status == cls.STATUS_PENDING,
            DomainTransfer.verify_expires < now
        ).all()
        
        count = 0
        for transfer in expired_transfers:
            try:
                transfer.status = cls.STATUS_EXPIRED
                count += 1
            except Exception as e:
                logger.error(f"Expire transfer {transfer.id} failed: {e}")
        
        if count > 0:
            try:
                db.session.commit()
                logger.info(f"Expired {count} pending transfers")
            except Exception as e:
                db.session.rollback()
                logger.error(f"Commit expired transfers failed: {e}")
                return 0
        
        return count
    
    # ========== 邮件发送方法 ==========
    
    @classmethod
    def _send_verify_code_email(
        cls,
        to_email: str,
        subdomain_name: str,
        to_username: str,
        verify_code: str,
        expire_minutes: int,
        fee_points: int
    ):
        """发送转移验证码邮件"""
        try:
            from app.services.email import EmailService
            
            subject = f'域名转移验证码 - {subdomain_name}'
            html_content = f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #4F46E5;">域名转移验证</h2>
                <p>您正在将域名 <strong>{subdomain_name}</strong> 转移给用户 <strong>{to_username}</strong></p>
                <div style="background: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                    <p style="margin: 0; color: #6B7280;">验证码</p>
                    <p style="font-size: 32px; font-weight: bold; color: #4F46E5; margin: 10px 0; letter-spacing: 4px;">{verify_code}</p>
                    <p style="margin: 0; color: #6B7280;">有效期 {expire_minutes} 分钟</p>
                </div>
                <p>手续费：<strong>{fee_points}</strong> 积分</p>
                <p style="color: #EF4444;">如果这不是您的操作，请忽略此邮件。</p>
                <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 20px 0;">
                <p style="color: #6B7280; font-size: 14px;">此邮件由系统自动发送，请勿回复。</p>
            </div>
            '''
            
            EmailService.send(to_email, subject, html_content)
        except Exception as e:
            logger.error(f"Send verify code email failed: {e}")
    
    @classmethod
    def _send_received_email(
        cls,
        to_email: str,
        subdomain_name: str,
        from_username: str
    ):
        """发送收到域名通知邮件"""
        try:
            from app.services.email import EmailService
            
            subject = f'您收到了一个域名 - {subdomain_name}'
            html_content = f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #10B981;">您收到了一个域名</h2>
                <p>用户 <strong>{from_username}</strong> 已将域名 <strong>{subdomain_name}</strong> 转移给您。</p>
                <p>您现在可以在域名管理中查看和管理该域名。</p>
                <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 20px 0;">
                <p style="color: #6B7280; font-size: 14px;">此邮件由系统自动发送，请勿回复。</p>
            </div>
            '''
            
            EmailService.send(to_email, subject, html_content)
        except Exception as e:
            logger.error(f"Send received email failed: {e}")
    
    @classmethod
    def _send_completed_email(
        cls,
        to_email: str,
        subdomain_name: str,
        to_username: str,
        fee_points: int
    ):
        """发送转移完成确认邮件"""
        try:
            from app.services.email import EmailService
            
            subject = f'域名转移完成 - {subdomain_name}'
            html_content = f'''
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #10B981;">域名转移完成</h2>
                <p>您的域名 <strong>{subdomain_name}</strong> 已成功转移给用户 <strong>{to_username}</strong>。</p>
                <p>手续费：<strong>{fee_points}</strong> 积分</p>
                <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 20px 0;">
                <p style="color: #6B7280; font-size: 14px;">此邮件由系统自动发送，请勿回复。</p>
            </div>
            '''
            
            EmailService.send(to_email, subject, html_content)
        except Exception as e:
            logger.error(f"Send completed email failed: {e}")
