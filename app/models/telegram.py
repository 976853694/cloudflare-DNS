"""
Telegram 机器人相关模型
"""
from datetime import datetime, timedelta
from app import db
from app.utils.timezone import now as beijing_now
import random
import string


class TelegramBot(db.Model):
    """Telegram 机器人配置"""
    __tablename__ = 'telegram_bots'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, comment='机器人名称')
    token = db.Column(db.String(100), nullable=False, comment='Bot Token')
    username = db.Column(db.String(100), nullable=True, comment='机器人用户名')
    is_enabled = db.Column(db.Boolean, default=True, nullable=False, comment='是否启用')
    api_urls = db.Column(db.Text, nullable=True, comment='API地址列表(JSON)')
    ad_button = db.Column(db.Text, nullable=True, comment='全局广告按钮(每行一个,格式:文字,链接)')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    def to_dict(self):
        import json
        api_urls = []
        if self.api_urls:
            try:
                api_urls = json.loads(self.api_urls)
            except:
                pass
        return {
            'id': self.id,
            'name': self.name,
            'token': self.token[:10] + '...' if self.token else '',  # 隐藏部分token
            'username': self.username,
            'is_enabled': self.is_enabled,
            'api_urls': api_urls,
            'ad_button': self.ad_button or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }
    
    def get_api_urls(self):
        """获取API地址列表"""
        import json
        if self.api_urls:
            try:
                return json.loads(self.api_urls)
            except:
                pass
        return []
    
    def set_api_urls(self, urls):
        """设置API地址列表"""
        import json
        self.api_urls = json.dumps(urls) if urls else None
    
    def get_ad_buttons(self):
        """获取广告按钮列表，返回 [(text, url), ...] 或空列表"""
        if not self.ad_button:
            return []
        buttons = []
        for line in self.ad_button.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.split(',', 1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                buttons.append((parts[0].strip(), parts[1].strip()))
        return buttons
    
    @classmethod
    def get_enabled_bot(cls):
        """获取已启用的机器人配置"""
        return cls.query.filter_by(is_enabled=True).first()


class TelegramUser(db.Model):
    """Telegram 用户绑定"""
    __tablename__ = 'telegram_users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False, comment='TG用户ID')
    telegram_username = db.Column(db.String(100), nullable=True, comment='TG用户名')
    telegram_first_name = db.Column(db.String(100), nullable=True, comment='TG名字')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, comment='关联系统用户ID')
    is_active = db.Column(db.Boolean, default=True, nullable=False, comment='是否启用')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 关联用户
    user = db.relationship('User', backref=db.backref('telegram_bindings', lazy='dynamic', cascade='all, delete-orphan'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'telegram_username': self.telegram_username,
            'telegram_first_name': self.telegram_first_name,
            'user_id': self.user_id,
            'user': self.user.username if self.user else None,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
    
    @classmethod
    def get_by_telegram_id(cls, telegram_id):
        """根据TG用户ID获取绑定"""
        return cls.query.filter_by(telegram_id=telegram_id).first()
    
    @classmethod
    def get_by_user_id(cls, user_id):
        """根据系统用户ID获取绑定"""
        return cls.query.filter_by(user_id=user_id).first()


class TelegramBindCode(db.Model):
    """Telegram 绑定码"""
    __tablename__ = 'telegram_bind_codes'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, comment='用户ID')
    code = db.Column(db.String(10), unique=True, nullable=False, comment='绑定码')
    expires_at = db.Column(db.DateTime, nullable=False, comment='过期时间')
    used = db.Column(db.Boolean, default=False, nullable=False, comment='是否已使用')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    
    # 关联用户
    user = db.relationship('User', backref=db.backref('telegram_bind_codes', lazy='dynamic', cascade='all, delete-orphan'))
    
    @classmethod
    def generate_code(cls, user_id, expires_minutes=5):
        """生成绑定码"""
        # 删除该用户之前的未使用绑定码
        cls.query.filter_by(user_id=user_id, used=False).delete()
        
        # 生成6位随机码（数字+大写字母）
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # 确保唯一性
        while cls.query.filter_by(code=code).first():
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        bind_code = cls(
            user_id=user_id,
            code=code,
            expires_at=beijing_now() + timedelta(minutes=expires_minutes)
        )
        db.session.add(bind_code)
        db.session.commit()
        
        return bind_code
    
    @classmethod
    def verify_code(cls, code):
        """验证绑定码，返回用户ID或None"""
        bind_code = cls.query.filter_by(code=code.upper(), used=False).first()
        if not bind_code:
            return None
        
        # 检查是否过期
        if bind_code.expires_at < beijing_now():
            return None
        
        return bind_code
    
    @classmethod
    def use_code(cls, code):
        """使用绑定码"""
        bind_code = cls.query.filter_by(code=code.upper(), used=False).first()
        if bind_code:
            bind_code.used = True
            db.session.commit()
            return True
        return False
