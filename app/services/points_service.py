"""
积分服务
提供签到、积分变动、兑换、邀请等功能
"""
import secrets
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple

from app import db
from app.models import User, Setting
from app.models.point_record import PointRecord
from app.models.user_signin import UserSignin
from app.models.user_invite import UserInvite

logger = logging.getLogger(__name__)


class PointsService:
    """积分服务"""
    
    # 默认积分规则常量（可通过后台设置覆盖）
    DEFAULT_SIGNIN_BASE_POINTS = 10          # 每日签到基础积分
    DEFAULT_SIGNIN_BONUS_3_DAYS = 5          # 连续3天额外奖励
    DEFAULT_SIGNIN_BONUS_7_DAYS = 20         # 连续7天额外奖励
    DEFAULT_SIGNIN_BONUS_30_DAYS = 100       # 连续30天额外奖励
    DEFAULT_INVITE_REGISTER_POINTS = 50     # 邀请注册奖励(邀请人)
    DEFAULT_INVITE_RECHARGE_POINTS = 100    # 邀请首充奖励(邀请人)
    DEFAULT_INVITEE_REWARD_POINTS = 30      # 被邀请人奖励
    DEFAULT_EXCHANGE_RATE = 100              # 兑换比例：100积分 = 1元
    DEFAULT_MIN_EXCHANGE = 100               # 最低兑换积分
    DEFAULT_MAX_DAILY_EXCHANGE = 10000       # 每日最大兑换积分
    
    @classmethod
    def get_config(cls) -> Dict[str, int]:
        """获取积分配置（从设置中读取，如果没有则使用默认值）"""
        return {
            'signin_base': int(Setting.get('points_signin_base', str(cls.DEFAULT_SIGNIN_BASE_POINTS))),
            'signin_bonus_3': int(Setting.get('points_signin_bonus_3', str(cls.DEFAULT_SIGNIN_BONUS_3_DAYS))),
            'signin_bonus_7': int(Setting.get('points_signin_bonus_7', str(cls.DEFAULT_SIGNIN_BONUS_7_DAYS))),
            'signin_bonus_30': int(Setting.get('points_signin_bonus_30', str(cls.DEFAULT_SIGNIN_BONUS_30_DAYS))),
            'invite_register': int(Setting.get('points_invite_register', str(cls.DEFAULT_INVITE_REGISTER_POINTS))),
            'invite_recharge': int(Setting.get('points_invite_recharge', str(cls.DEFAULT_INVITE_RECHARGE_POINTS))),
            'invitee_reward': int(Setting.get('points_invitee_reward', str(cls.DEFAULT_INVITEE_REWARD_POINTS))),
            'exchange_rate': int(Setting.get('points_exchange_rate', str(cls.DEFAULT_EXCHANGE_RATE))),
            'min_exchange': int(Setting.get('points_min_exchange', str(cls.DEFAULT_MIN_EXCHANGE))),
            'max_daily_exchange': int(Setting.get('points_max_daily_exchange', str(cls.DEFAULT_MAX_DAILY_EXCHANGE))),
        }
    
    # 兼容旧代码的属性
    @classmethod
    @property
    def SIGNIN_BASE_POINTS(cls):
        return cls.get_config()['signin_base']
    
    @classmethod
    @property
    def EXCHANGE_RATE(cls):
        return cls.get_config()['exchange_rate']
    
    @classmethod
    @property
    def MIN_EXCHANGE(cls):
        return cls.get_config()['min_exchange']
    
    @classmethod
    @property
    def MAX_DAILY_EXCHANGE(cls):
        return cls.get_config()['max_daily_exchange']
    
    @classmethod
    def signin(cls, user_id: int) -> Dict[str, Any]:
        """
        用户签到
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 签到结果
            
        Raises:
            ValueError: 今日已签到
        """
        from app.utils.timezone import now as beijing_now
        
        user = User.query.get(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        # 使用北京时间获取今天的日期
        today = beijing_now().date()
        
        # 检查今天是否已签到
        today_signin = UserSignin.query.filter_by(
            user_id=user_id,
            signin_date=today
        ).first()
        
        if today_signin:
            raise ValueError("今日已签到")
        
        # 计算连续签到天数
        yesterday = today - timedelta(days=1)
        yesterday_signin = UserSignin.query.filter_by(
            user_id=user_id,
            signin_date=yesterday
        ).first()
        
        if yesterday_signin:
            continuous_days = yesterday_signin.continuous_days + 1
        else:
            continuous_days = 1
        
        # 获取配置
        config = cls.get_config()
        
        # 计算积分
        base_points = config['signin_base']
        bonus_points = 0
        bonus_desc = None
        
        # 连续签到奖励（在达到天数时发放）
        if continuous_days == 3:
            bonus_points = config['signin_bonus_3']
            bonus_desc = "连续签到3天奖励"
        elif continuous_days == 7:
            bonus_points = config['signin_bonus_7']
            bonus_desc = "连续签到7天奖励"
        elif continuous_days == 30:
            bonus_points = config['signin_bonus_30']
            bonus_desc = "连续签到30天奖励"
        elif continuous_days > 30 and continuous_days % 30 == 0:
            bonus_points = config['signin_bonus_30']
            bonus_desc = f"连续签到{continuous_days}天奖励"
        
        total_points = base_points + bonus_points
        
        try:
            # 创建签到记录
            signin = UserSignin(
                user_id=user_id,
                signin_date=today,
                continuous_days=continuous_days,
                points_earned=total_points
            )
            db.session.add(signin)
            
            # 添加基础签到积分
            cls._add_points_internal(
                user, base_points, 
                PointRecord.TYPE_SIGNIN, 
                f"每日签到 (连续{continuous_days}天)"
            )
            
            # 添加连续签到奖励积分
            if bonus_points > 0:
                cls._add_points_internal(
                    user, bonus_points,
                    PointRecord.TYPE_SIGNIN_BONUS,
                    bonus_desc
                )
            
            db.session.commit()
            
            return {
                'success': True,
                'base_points': base_points,
                'bonus_points': bonus_points,
                'total_points': total_points,
                'continuous_days': continuous_days,
                'current_points': user.points
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Signin failed for user {user_id}: {e}")
            raise
    
    @classmethod
    def get_signin_status(cls, user_id: int) -> Dict[str, Any]:
        """
        获取签到状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 签到状态信息
        """
        from app.utils.timezone import now as beijing_now
        
        # 使用北京时间获取今天的日期
        today = beijing_now().date()
        config = cls.get_config()
        
        # 今日是否已签到
        today_signin = UserSignin.query.filter_by(
            user_id=user_id,
            signin_date=today
        ).first()
        
        signed_today = today_signin is not None
        
        # 获取连续签到天数
        if signed_today:
            continuous_days = today_signin.continuous_days
        else:
            # 检查昨天是否签到
            yesterday = today - timedelta(days=1)
            yesterday_signin = UserSignin.query.filter_by(
                user_id=user_id,
                signin_date=yesterday
            ).first()
            continuous_days = yesterday_signin.continuous_days if yesterday_signin else 0
        
        # 计算下一个奖励节点
        next_bonus = None
        next_bonus_points = 0
        
        if continuous_days < 3:
            next_bonus = 3
            next_bonus_points = config['signin_bonus_3']
        elif continuous_days < 7:
            next_bonus = 7
            next_bonus_points = config['signin_bonus_7']
        elif continuous_days < 30:
            next_bonus = 30
            next_bonus_points = config['signin_bonus_30']
        else:
            # 下一个30天周期
            next_bonus = ((continuous_days // 30) + 1) * 30
            next_bonus_points = config['signin_bonus_30']
        
        return {
            'signed_today': signed_today,
            'continuous_days': continuous_days,
            'next_bonus_days': next_bonus,
            'next_bonus_points': next_bonus_points,
            'days_to_next_bonus': next_bonus - continuous_days if next_bonus else 0
        }
    
    @classmethod
    def _add_points_internal(cls, user: User, points: int, type: str, 
                             description: str, related_id: int = None) -> PointRecord:
        """
        内部方法：添加积分（不提交事务）
        """
        user.points += points
        if points > 0:
            user.total_points += points
        
        record = PointRecord(
            user_id=user.id,
            type=type,
            points=points,
            balance=user.points,
            description=description,
            related_id=related_id
        )
        db.session.add(record)
        return record
    
    @classmethod
    def add_points(cls, user_id: int, points: int, type: str,
                   description: str, related_id: int = None) -> PointRecord:
        """
        添加积分
        
        Args:
            user_id: 用户ID
            points: 积分数量（正数增加，负数减少）
            type: 积分类型
            description: 描述
            related_id: 关联ID
            
        Returns:
            PointRecord: 积分记录
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        try:
            record = cls._add_points_internal(user, points, type, description, related_id)
            db.session.commit()
            return record
        except Exception as e:
            db.session.rollback()
            logger.error(f"Add points failed for user {user_id}: {e}")
            raise
    
    @classmethod
    def exchange(cls, user_id: int, points: int) -> Dict[str, Any]:
        """
        积分兑换余额
        
        Args:
            user_id: 用户ID
            points: 兑换积分数量
            
        Returns:
            Dict: 兑换结果
        """
        from app.utils.timezone import now as beijing_now
        
        user = User.query.get(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        config = cls.get_config()
        
        # 验证兑换数量
        if points < config['min_exchange']:
            raise ValueError(f"最低兑换 {config['min_exchange']} 积分")
        
        if points > user.points:
            raise ValueError("积分不足")
        
        # 检查每日兑换限制
        max_daily = config['max_daily_exchange']
        if max_daily > 0:
            # 使用北京时间获取今天的日期
            today = beijing_now().date()
            today_exchanged = db.session.query(
                db.func.abs(db.func.sum(PointRecord.points))
            ).filter(
                PointRecord.user_id == user_id,
                PointRecord.type == PointRecord.TYPE_EXCHANGE,
                db.func.date(PointRecord.created_at) == today
            ).scalar() or 0
            
            if today_exchanged + points > max_daily:
                remaining = max_daily - today_exchanged
                raise ValueError(f"今日兑换已达上限，剩余可兑换 {remaining} 积分")
        
        # 计算兑换金额
        exchange_rate = config['exchange_rate']
        amount = Decimal(str(points)) / Decimal(str(exchange_rate))
        
        try:
            # 扣除积分
            user.points -= points
            
            # 增加余额
            user.balance += amount
            
            # 记录积分变动
            record = PointRecord(
                user_id=user_id,
                type=PointRecord.TYPE_EXCHANGE,
                points=-points,
                balance=user.points,
                description=f"兑换余额 ¥{amount}"
            )
            db.session.add(record)
            db.session.commit()
            
            return {
                'success': True,
                'points_used': points,
                'amount': float(amount),
                'current_points': user.points,
                'current_balance': float(user.balance)
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Exchange failed for user {user_id}: {e}")
            raise
    
    @classmethod
    def get_records(cls, user_id: int, type: str = None, 
                    page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        获取积分记录
        
        Args:
            user_id: 用户ID
            type: 积分类型筛选
            page: 页码
            per_page: 每页数量
            
        Returns:
            Dict: 分页的积分记录
        """
        query = PointRecord.query.filter_by(user_id=user_id)
        
        if type:
            query = query.filter_by(type=type)
        
        query = query.order_by(PointRecord.created_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'records': [r.to_dict() for r in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page,
            'per_page': per_page
        }
    
    @classmethod
    def generate_invite_code(cls, user_id: int) -> str:
        """
        生成邀请码
        
        Args:
            user_id: 用户ID
            
        Returns:
            str: 邀请码
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        if user.invite_code:
            return user.invite_code
        
        # 生成唯一邀请码
        while True:
            code = secrets.token_hex(4).upper()  # 8位十六进制
            existing = User.query.filter_by(invite_code=code).first()
            if not existing:
                break
        
        user.invite_code = code
        db.session.commit()
        
        return code
    
    @classmethod
    def get_invite_info(cls, user_id: int) -> Dict[str, Any]:
        """
        获取邀请信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 邀请信息
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        # 确保有邀请码
        if not user.invite_code:
            cls.generate_invite_code(user_id)
            db.session.refresh(user)
        
        # 统计邀请数据
        total_invited = UserInvite.query.filter_by(inviter_id=user_id).count()
        
        total_earned = db.session.query(
            db.func.sum(UserInvite.register_reward + UserInvite.recharge_reward)
        ).filter(UserInvite.inviter_id == user_id).scalar() or 0
        
        recharged_count = UserInvite.query.filter_by(
            inviter_id=user_id,
            status=UserInvite.STATUS_RECHARGED
        ).count()
        
        config = cls.get_config()
        
        return {
            'invite_code': user.invite_code,
            'total_invited': total_invited,
            'recharged_count': recharged_count,
            'total_earned': total_earned,
            'register_reward': config['invite_register'],
            'recharge_reward': config['invite_recharge'],
            'invitee_reward': config['invitee_reward']
        }
    
    @classmethod
    def get_invite_list(cls, user_id: int, page: int = 1, 
                        per_page: int = 20) -> Dict[str, Any]:
        """
        获取邀请记录列表
        
        Args:
            user_id: 用户ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            Dict: 分页的邀请记录
        """
        query = UserInvite.query.filter_by(inviter_id=user_id)
        query = query.order_by(UserInvite.created_at.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return {
            'records': [r.to_dict() for r in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page,
            'per_page': per_page
        }
    
    @classmethod
    def process_invite_register(cls, inviter_id: int, invitee_id: int, 
                                invite_code: str) -> Optional[UserInvite]:
        """
        处理邀请注册奖励
        
        Args:
            inviter_id: 邀请人ID
            invitee_id: 被邀请人ID
            invite_code: 邀请码
            
        Returns:
            UserInvite: 邀请记录
        """
        # 检查是否已有邀请记录
        existing = UserInvite.query.filter_by(invitee_id=invitee_id).first()
        if existing:
            return None
        
        inviter = User.query.get(inviter_id)
        invitee = User.query.get(invitee_id)
        if not inviter or not invitee:
            return None
        
        config = cls.get_config()
        register_points = config['invite_register']
        invitee_reward_points = config['invitee_reward']
        
        try:
            # 创建邀请记录
            invite = UserInvite(
                inviter_id=inviter_id,
                invitee_id=invitee_id,
                invite_code=invite_code,
                register_reward=register_points,
                invitee_reward=invitee_reward_points,
                status=UserInvite.STATUS_REGISTERED
            )
            db.session.add(invite)
            
            # 给邀请人添加积分
            if register_points > 0:
                cls._add_points_internal(
                    inviter, 
                    register_points,
                    PointRecord.TYPE_INVITE,
                    "邀请新用户注册奖励",
                    invitee_id
                )
            
            # 给被邀请人添加积分
            if invitee_reward_points > 0:
                cls._add_points_internal(
                    invitee,
                    invitee_reward_points,
                    PointRecord.TYPE_INVITED,
                    "受邀注册奖励",
                    inviter_id
                )
            
            db.session.commit()
            logger.info(f"Invite register reward: inviter={inviter_id}, invitee={invitee_id}, inviter_reward={register_points}, invitee_reward={invitee_reward_points}")
            return invite
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Process invite register failed: {e}")
            return None
    
    @classmethod
    def process_invite_recharge(cls, invitee_id: int) -> bool:
        """
        处理邀请首充奖励
        
        Args:
            invitee_id: 被邀请人ID
            
        Returns:
            bool: 是否成功发放奖励
        """
        # 查找邀请记录
        invite = UserInvite.query.filter_by(invitee_id=invitee_id).first()
        if not invite:
            return False
        
        # 检查是否已发放首充奖励
        if invite.status == UserInvite.STATUS_RECHARGED:
            return False
        
        inviter = User.query.get(invite.inviter_id)
        if not inviter:
            return False
        
        config = cls.get_config()
        recharge_points = config['invite_recharge']
        
        try:
            # 更新邀请记录状态
            invite.status = UserInvite.STATUS_RECHARGED
            invite.recharge_reward = recharge_points
            
            # 给邀请人添加积分
            cls._add_points_internal(
                inviter,
                recharge_points,
                PointRecord.TYPE_INVITE_RECHARGE,
                "被邀请用户首充奖励",
                invitee_id
            )
            
            db.session.commit()
            logger.info(f"Invite recharge reward: inviter={invite.inviter_id}, invitee={invitee_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Process invite recharge failed: {e}")
            return False
    
    @classmethod
    def get_user_points(cls, user_id: int) -> Dict[str, Any]:
        """
        获取用户积分信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 积分信息
        """
        user = User.query.get(user_id)
        if not user:
            raise ValueError("用户不存在")
        
        signin_status = cls.get_signin_status(user_id)
        config = cls.get_config()
        
        return {
            'points': user.points,
            'total_points': user.total_points,
            'exchange_rate': config['exchange_rate'],
            'min_exchange': config['min_exchange'],
            'max_daily_exchange': config['max_daily_exchange'],
            'signin_base': config['signin_base'],
            'signin_bonus_3': config['signin_bonus_3'],
            'signin_bonus_7': config['signin_bonus_7'],
            'signin_bonus_30': config['signin_bonus_30'],
            'signin_status': signin_status
        }
