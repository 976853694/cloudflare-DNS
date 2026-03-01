from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from app.models import User, UserActivity
from flask import request
from app.utils.ip_utils import get_real_ip


class ActivityTracker:
    """用户活跃度追踪服务"""
    
    @staticmethod
    def log(user_id, activity_type, activity_data=None):
        """
        记录用户活动
        
        Args:
            user_id: 用户ID
            activity_type: 活动类型 (login, domain_create, record_update, balance_recharge等)
            activity_data: 活动数据(JSON格式)
        """
        try:
            # 获取IP地址
            ip_address = get_real_ip() if request else None
            
            # 创建活动记录
            activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                activity_data=activity_data,
                ip_address=ip_address
            )
            db.session.add(activity)
            
            # 更新用户最后活动时间
            user = User.query.get(user_id)
            if user:
                user.last_activity_at = datetime.now()
                
                # 如果是登录活动,增加登录次数
                if activity_type == UserActivity.TYPE_LOGIN:
                    user.login_count = (user.login_count or 0) + 1
                
                # 重新计算活跃度分数
                user.activity_score = ActivityTracker.calculate_activity_score(user_id)
            
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] ActivityTracker.log failed: {e}")
            return False
    
    @staticmethod
    def calculate_activity_score(user_id):
        """
        计算用户活跃度分数
        
        计算规则:
        - 最近7天的活动: 每次活动 +10分
        - 最近30天的活动: 每次活动 +5分
        - 最近90天的活动: 每次活动 +2分
        - 登录活动额外加分: +5分
        - 域名创建活动额外加分: +10分
        - 余额充值活动额外加分: +15分
        """
        now = datetime.now()
        score = 0
        
        # 最近7天的活动
        activities_7d = UserActivity.query.filter(
            UserActivity.user_id == user_id,
            UserActivity.created_at >= now - timedelta(days=7)
        ).all()
        
        for activity in activities_7d:
            score += 10
            # 额外加分
            if activity.activity_type == UserActivity.TYPE_LOGIN:
                score += 5
            elif activity.activity_type == UserActivity.TYPE_DOMAIN_CREATE:
                score += 10
            elif activity.activity_type == UserActivity.TYPE_BALANCE_RECHARGE:
                score += 15
        
        # 最近8-30天的活动
        activities_30d = UserActivity.query.filter(
            UserActivity.user_id == user_id,
            UserActivity.created_at >= now - timedelta(days=30),
            UserActivity.created_at < now - timedelta(days=7)
        ).all()
        
        for activity in activities_30d:
            score += 5
            # 额外加分
            if activity.activity_type == UserActivity.TYPE_LOGIN:
                score += 2
            elif activity.activity_type == UserActivity.TYPE_DOMAIN_CREATE:
                score += 5
            elif activity.activity_type == UserActivity.TYPE_BALANCE_RECHARGE:
                score += 8
        
        # 最近31-90天的活动
        activities_90d = UserActivity.query.filter(
            UserActivity.user_id == user_id,
            UserActivity.created_at >= now - timedelta(days=90),
            UserActivity.created_at < now - timedelta(days=30)
        ).all()
        
        for activity in activities_90d:
            score += 2
        
        return score
    
    @staticmethod
    def get_activity_level(user):
        """
        获取用户活跃度等级
        
        综合评分规则 (满分100分):
        1. 最后登录时间 (40分):
           - 7天内: 40分
           - 7-30天: 30分
           - 30-90天: 20分
           - 90-180天: 10分
           - 180天以上: 0分
        
        2. 是否有域名 (30分):
           - 有域名: 30分
           - 无域名: 0分
        
        3. 登录频率 (30分):
           - 频率 = 登录次数 / 注册天数
           - 频率 >= 0.5 (每2天登录1次): 30分
           - 频率 >= 0.2 (每5天登录1次): 20分
           - 频率 >= 0.1 (每10天登录1次): 10分
           - 频率 < 0.1: 0分
        
        等级划分:
        - high: 总分 >= 70
        - medium: 总分 >= 50
        - low: 总分 >= 30
        - dormant: 总分 >= 10
        - lost: 总分 < 10
        """
        score = 0
        now = datetime.now()
        
        # 1. 最后登录时间评分 (40分)
        last_login = user.last_login_at or user.last_activity_at
        if last_login:
            days_since_login = (now - last_login).days
            if days_since_login < 7:
                score += 40
            elif days_since_login < 30:
                score += 30
            elif days_since_login < 90:
                score += 20
            elif days_since_login < 180:
                score += 10
            # 180天以上: 0分
        
        # 2. 是否有域名评分 (30分)
        domain_count = user.subdomains.count() if user.subdomains else 0
        if domain_count > 0:
            score += 30
        
        # 3. 登录频率评分 (30分)
        login_count = user.login_count or 0
        if user.created_at:
            days_since_register = max((now - user.created_at).days, 1)  # 至少1天，避免除零
            login_frequency = login_count / days_since_register
            
            if login_frequency >= 0.5:
                score += 30
            elif login_frequency >= 0.2:
                score += 20
            elif login_frequency >= 0.1:
                score += 10
            # 频率 < 0.1: 0分
        
        # 根据总分判断等级
        if score >= 70:
            return 'high'
        elif score >= 50:
            return 'medium'
        elif score >= 30:
            return 'low'
        elif score >= 10:
            return 'dormant'
        else:
            return 'lost'
    
    @staticmethod
    def get_activity_details(user):
        """
        获取用户活跃度详细信息
        
        Returns:
            dict: 包含各项评分指标的详细信息
        """
        now = datetime.now()
        
        # 最后登录时间
        last_login = user.last_login_at or user.last_activity_at
        days_since_login = (now - last_login).days if last_login else None
        
        # 域名数量
        domain_count = user.subdomains.count() if user.subdomains else 0
        
        # 登录频率
        login_count = user.login_count or 0
        days_since_register = max((now - user.created_at).days, 1) if user.created_at else 1
        login_frequency = round(login_count / days_since_register, 3)
        
        # 计算各项得分
        login_score = 0
        if last_login:
            if days_since_login < 7:
                login_score = 40
            elif days_since_login < 30:
                login_score = 30
            elif days_since_login < 90:
                login_score = 20
            elif days_since_login < 180:
                login_score = 10
        
        domain_score = 30 if domain_count > 0 else 0
        
        frequency_score = 0
        if login_frequency >= 0.5:
            frequency_score = 30
        elif login_frequency >= 0.2:
            frequency_score = 20
        elif login_frequency >= 0.1:
            frequency_score = 10
        
        total_score = login_score + domain_score + frequency_score
        
        return {
            'last_login_days': days_since_login,
            'last_login_score': login_score,
            'domain_count': domain_count,
            'domain_score': domain_score,
            'login_count': login_count,
            'days_since_register': days_since_register,
            'login_frequency': login_frequency,
            'frequency_score': frequency_score,
            'total_score': total_score,
            'activity_level': ActivityTracker.get_activity_level(user)
        }
    
    @staticmethod
    def get_activity_stats():
        """
        获取活跃度统计数据
        
        使用新的综合评分规则统计各等级用户数
        
        Returns:
            dict: 包含各活跃度等级的用户数量
        """
        # 统计各等级用户数
        total_users = User.query.count()
        
        # 需要遍历所有用户计算活跃度等级
        high_count = 0
        medium_count = 0
        low_count = 0
        dormant_count = 0
        lost_count = 0
        
        users = User.query.all()
        for user in users:
            level = ActivityTracker.get_activity_level(user)
            if level == 'high':
                high_count += 1
            elif level == 'medium':
                medium_count += 1
            elif level == 'low':
                low_count += 1
            elif level == 'dormant':
                dormant_count += 1
            else:
                lost_count += 1
        
        return {
            'total': total_users,
            'high': high_count,
            'medium': medium_count,
            'low': low_count,
            'dormant': dormant_count,
            'lost': lost_count
        }
