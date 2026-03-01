from datetime import datetime
from app.utils.timezone import now as beijing_now
from decimal import Decimal
import bcrypt
from app import db


class User(db.Model):
    __tablename__ = 'users'
    
    # 角色常量
    ROLE_USER = 'user'
    ROLE_ADMIN = 'admin'
    ROLE_DEMO = 'demo'
    
    # 用户状态常量
    STATUS_BANNED = 0       # 已封禁
    STATUS_ACTIVE = 1       # 正常
    STATUS_SLEEPING = 2     # 沉睡（需验证邮箱）
    
    # 托管商状态常量
    HOST_STATUS_NONE = 'none'           # 未申请
    HOST_STATUS_PENDING = 'pending'     # 待审核
    HOST_STATUS_APPROVED = 'approved'   # 已通过
    HOST_STATUS_REJECTED = 'rejected'   # 已拒绝
    HOST_STATUS_SUSPENDED = 'suspended' # 已暂停
    HOST_STATUS_REVOKED = 'revoked'     # 已撤销
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)  # 手机号
    password_hash = db.Column(db.String(255), nullable=True)  # OAuth用户可能没有密码
    github_id = db.Column(db.String(50), unique=True, nullable=True)  # GitHub OAuth ID
    google_id = db.Column(db.String(50), unique=True, nullable=True)  # Google OAuth ID
    nodeloc_id = db.Column(db.String(50), unique=True, nullable=True)  # NodeLoc OAuth ID
    role = db.Column(db.Enum('user', 'admin', 'demo'), default='user', nullable=False)
    status = db.Column(db.SmallInteger, default=1, nullable=False)
    balance = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    max_domains = db.Column(db.Integer, default=5, nullable=False)
    totp_secret = db.Column(db.String(64), nullable=True)
    totp_enabled = db.Column(db.SmallInteger, default=0, nullable=False)
    backup_codes = db.Column(db.Text, nullable=True)
    allowed_ips = db.Column(db.Text, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    # API相关字段
    api_key = db.Column(db.String(64), unique=True, nullable=True)
    api_secret = db.Column(db.String(64), nullable=True)
    api_enabled = db.Column(db.SmallInteger, default=0, nullable=False)
    api_ip_whitelist = db.Column(db.Text, nullable=True)
    # 实名认证相关字段
    real_name = db.Column(db.String(50), nullable=True, comment='真实姓名')
    id_card = db.Column(db.String(18), nullable=True, comment='身份证号')
    verified = db.Column(db.SmallInteger, default=0, nullable=False, comment='实名认证状态 0=未认证 1=已认证')
    verified_at = db.Column(db.DateTime, nullable=True, comment='实名认证时间')
    # 托管商相关字段
    host_status = db.Column(db.String(20), default='none', nullable=False, comment='托管商状态')
    host_balance = db.Column(db.Numeric(10, 2), default=0, nullable=False, comment='托管收益余额')
    host_commission_rate = db.Column(db.Numeric(5, 2), nullable=True, comment='个人抽成比例，NULL则使用系统默认')
    host_approved_at = db.Column(db.DateTime, nullable=True, comment='托管商审核通过时间')
    host_suspended_at = db.Column(db.DateTime, nullable=True, comment='托管商暂停时间')
    host_suspended_reason = db.Column(db.String(255), nullable=True, comment='托管商暂停原因')
    # TG 通知设置字段
    tg_notify_domain_expire = db.Column(db.SmallInteger, default=1, nullable=False, comment='TG域名到期通知')
    tg_notify_purchase = db.Column(db.SmallInteger, default=1, nullable=False, comment='TG购买成功通知')
    tg_notify_balance = db.Column(db.SmallInteger, default=1, nullable=False, comment='TG余额变动通知')
    tg_notify_announcement = db.Column(db.SmallInteger, default=1, nullable=False, comment='TG系统公告通知')
    tg_notify_order = db.Column(db.SmallInteger, default=1, nullable=False, comment='TG托管商订单通知')
    tg_notify_daily = db.Column(db.SmallInteger, default=1, nullable=False, comment='TG管理员每日报表')
    tg_language = db.Column(db.String(10), default='zh', nullable=True, comment='TG语言设置')
    # 用户活跃度相关字段
    login_count = db.Column(db.Integer, default=0, nullable=False, comment='登录次数')
    last_activity_at = db.Column(db.DateTime, nullable=True, comment='最后活动时间')
    activity_score = db.Column(db.Integer, default=0, nullable=False, comment='活跃度分数')
    # 积分相关字段
    points = db.Column(db.Integer, default=0, nullable=False, comment='当前积分')
    total_points = db.Column(db.Integer, default=0, nullable=False, comment='累计获得积分')
    invite_code = db.Column(db.String(20), unique=True, nullable=True, comment='邀请码')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    subdomains = db.relationship('Subdomain', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def to_dict(self, include_stats=False, include_security=False, include_host=False, mask_private=False):
        MASKED = '******'
        # 手机号脱敏处理
        phone_masked = None
        if self.phone:
            if len(self.phone) >= 7:
                phone_masked = self.phone[:3] + '****' + self.phone[-4:]
            else:
                phone_masked = self.phone
        
        # 获取系统是否要求强制绑定手机号
        from app.models import Setting
        require_phone_binding = Setting.get('require_phone_binding', '0') == '1'
        
        data = {
            'id': self.id,
            'username': self.username,
            'email': MASKED if mask_private else self.email,
            'role': self.role,
            'status': self.status,
            'balance': float(self.balance) if self.balance is not None else 0,
            'balance_text': '无限' if self.balance == -1 else f'¥{self.balance}',
            'max_domains': self.max_domains,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'oauth_bindings': {
                'github': bool(self.github_id),
                'google': bool(self.google_id),
                'nodeloc': bool(self.nodeloc_id)
            },
            'phone': MASKED if mask_private else phone_masked,
            'phone_bound': bool(self.phone),
            'require_phone_binding': require_phone_binding,
            'verified': self.verified == 1,
            'real_name_masked': self.real_name_masked if self.verified == 1 else None
        }
        if include_stats:
            data['used_domains'] = self.subdomains.count()
            data['totp_enabled'] = self.totp_enabled == 1
            data['login_count'] = self.login_count or 0
            data['last_activity_at'] = self.last_activity_at.isoformat() if self.last_activity_at else None
            data['activity_score'] = self.activity_score or 0
        if include_security:
            data['totp_enabled'] = self.totp_enabled == 1
            data['has_allowed_ips'] = bool(self.allowed_ips)
            data['last_login_at'] = self.last_login_at.isoformat() if self.last_login_at else None
            data['last_login_ip'] = MASKED if mask_private else self.last_login_ip
            data['allowed_ips'] = MASKED if mask_private else self.get_allowed_ips()
        if include_host:
            data['host_status'] = self.host_status
            data['host_balance'] = float(self.host_balance) if self.host_balance else 0
            data['host_balance_text'] = self.host_balance_text
            data['host_commission_rate'] = float(self.host_commission_rate) if self.host_commission_rate else None
            data['host_approved_at'] = self.host_approved_at.isoformat() if self.host_approved_at else None
            data['is_host'] = self.is_host
            data['can_apply_host'] = self.can_apply_host
        return data
    
    @property
    def is_totp_enabled(self):
        return self.totp_enabled == 1
    
    def get_backup_codes(self):
        if not self.backup_codes:
            return []
        import json
        try:
            return json.loads(self.backup_codes)
        except:
            return []
    
    def set_backup_codes(self, codes):
        import json
        self.backup_codes = json.dumps(codes)
    
    def use_backup_code(self, code):
        codes = self.get_backup_codes()
        if code in codes:
            codes.remove(code)
            self.set_backup_codes(codes)
            return True
        return False
    
    def get_allowed_ips(self):
        if not self.allowed_ips:
            return []
        import json
        try:
            return json.loads(self.allowed_ips)
        except:
            return []
    
    def set_allowed_ips(self, ips):
        import json
        self.allowed_ips = json.dumps(ips) if ips else None
    
    def is_ip_allowed(self, ip):
        allowed = self.get_allowed_ips()
        if not allowed:
            return True
        return ip in allowed
    
    # ========== API 相关方法 ==========
    def generate_api_keys(self):
        """生成API密钥对"""
        import secrets
        self.api_key = secrets.token_hex(16)  # 32字符
        self.api_secret = secrets.token_hex(32)  # 64字符
        return self.api_key, self.api_secret
    
    def get_api_ip_whitelist(self):
        """获取API IP白名单"""
        if not self.api_ip_whitelist:
            return []
        import json
        try:
            return json.loads(self.api_ip_whitelist)
        except:
            return []
    
    def set_api_ip_whitelist(self, ips):
        """设置API IP白名单"""
        import json
        self.api_ip_whitelist = json.dumps(ips) if ips else None
    
    def is_api_ip_allowed(self, ip):
        """检查IP是否在API白名单中"""
        whitelist = self.get_api_ip_whitelist()
        if not whitelist:
            return True  # 未设置白名单则允许所有IP
        return ip in whitelist
    
    def verify_api_signature(self, timestamp, method, path, body, signature):
        """验证API签名"""
        import hmac
        import hashlib
        import time
        
        # 检查时间戳（5分钟有效期）
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > 300:
                return False, '签名已过期'
        except:
            return False, '时间戳无效'
        
        # 计算签名
        message = f"{timestamp}{method.upper()}{path}{body}"
        expected = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected):
            return False, '签名验证失败'
        
        return True, None
    
    @property
    def has_unlimited_balance(self):
        return self.balance == -1
    
    @property
    def balance_text(self):
        if self.balance == -1:
            return '无限'
        return f'¥{self.balance}'
    
    def can_afford(self, price):
        if self.has_unlimited_balance:
            return True
        return self.balance >= price
    
    def deduct_balance(self, amount):
        if not self.has_unlimited_balance:
            self.balance = self.balance - Decimal(str(amount))
    
    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE
    
    @property
    def is_sleeping(self):
        """是否处于沉睡状态"""
        return self.status == self.STATUS_SLEEPING
    
    @property
    def is_banned(self):
        """是否已被封禁"""
        return self.status == self.STATUS_BANNED
    
    @property
    def status_text(self):
        """状态文本"""
        status_map = {
            self.STATUS_BANNED: '已封禁',
            self.STATUS_ACTIVE: '正常',
            self.STATUS_SLEEPING: '沉睡'
        }
        return status_map.get(self.status, '未知')
    
    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN
    
    @property
    def is_demo(self):
        return self.role == self.ROLE_DEMO
    
    @property
    def is_verified(self):
        """是否已实名认证"""
        return self.verified == 1
    
    @property
    def real_name_masked(self):
        """脱敏后的真实姓名"""
        if not self.real_name:
            return None
        if len(self.real_name) <= 1:
            return self.real_name
        return self.real_name[0] + '*' * (len(self.real_name) - 1)
    
    @property
    def id_card_masked(self):
        """脱敏后的身份证号"""
        if not self.id_card:
            return None
        if len(self.id_card) < 8:
            return self.id_card
        return self.id_card[:4] + '**********' + self.id_card[-4:]
    
    # ========== 托管商相关方法 ==========
    @property
    def is_host(self):
        """是否为已通过的托管商"""
        return self.host_status == self.HOST_STATUS_APPROVED
    
    @property
    def is_host_active(self):
        """托管商是否处于活跃状态（已通过且未被暂停/撤销）"""
        return self.host_status == self.HOST_STATUS_APPROVED
    
    @property
    def can_apply_host(self):
        """是否可以申请成为托管商"""
        return self.host_status in [self.HOST_STATUS_NONE, self.HOST_STATUS_REJECTED, self.HOST_STATUS_REVOKED]
    
    @property
    def host_balance_text(self):
        """托管收益余额文本"""
        if self.host_balance is None:
            return '¥0.00'
        return f'¥{self.host_balance}'
    
    def add_host_balance(self, amount):
        """增加托管收益余额"""
        if self.host_balance is None:
            self.host_balance = Decimal('0')
        self.host_balance = self.host_balance + Decimal(str(amount))
    
    def get_effective_commission_rate(self, default_rate=10):
        """获取有效的抽成比例（个人设置优先，否则使用默认值）"""
        if self.host_commission_rate is not None:
            return float(self.host_commission_rate)
        return default_rate
    
    def to_host_dict(self):
        """托管商信息字典"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'host_status': self.host_status,
            'host_balance': float(self.host_balance) if self.host_balance else 0,
            'host_balance_text': self.host_balance_text,
            'host_commission_rate': float(self.host_commission_rate) if self.host_commission_rate else None,
            'host_approved_at': self.host_approved_at.isoformat() if self.host_approved_at else None,
            'is_host': self.is_host,
            'can_apply_host': self.can_apply_host
        }
