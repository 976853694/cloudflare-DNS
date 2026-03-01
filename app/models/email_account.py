"""
邮箱账户模型 - 支持多账户轮询发送
"""
import json
from datetime import datetime, date
from app import db


class EmailAccount(db.Model):
    """邮箱账户模型"""
    __tablename__ = 'email_accounts'
    
    # 账户类型常量
    TYPE_SMTP = 'smtp'
    TYPE_ALIYUN = 'aliyun'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='账户名称')
    type = db.Column(db.String(20), nullable=False, comment='账户类型: smtp/aliyun')
    config = db.Column(db.Text, nullable=False, comment='配置JSON')
    daily_limit = db.Column(db.Integer, nullable=False, default=500, comment='日发送限额(0/-1无限)')
    daily_sent = db.Column(db.Integer, nullable=False, default=0, comment='今日已发送')
    last_reset_at = db.Column(db.DateTime, nullable=True, comment='上次重置时间')
    last_sent_at = db.Column(db.DateTime, nullable=True, comment='上次发送时间')
    priority = db.Column(db.Integer, nullable=False, default=10, comment='优先级(越小越优先)')
    enabled = db.Column(db.Boolean, nullable=False, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    
    def get_config(self) -> dict:
        """获取配置字典"""
        if not self.config:
            return {}
        try:
            return json.loads(self.config)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_config(self, config: dict):
        """设置配置"""
        self.config = json.dumps(config, ensure_ascii=False)
    
    def is_quota_available(self) -> bool:
        """检查配额是否可用"""
        # 先检查是否需要重置
        self._check_and_reset_quota()
        
        # 0 或 -1 表示无限配额
        if self.daily_limit <= 0:
            return True
        
        return self.daily_sent < self.daily_limit
    
    def _check_and_reset_quota(self):
        """检查并重置过期配额"""
        today = date.today()
        
        # 如果从未重置过，或者上次重置不是今天，则重置
        if self.last_reset_at is None or self.last_reset_at.date() < today:
            self.reset_daily_quota()
    
    def reset_daily_quota(self):
        """重置日配额"""
        self.daily_sent = 0
        self.last_reset_at = datetime.utcnow()
        db.session.commit()
    
    def increment_sent(self):
        """增加发送计数"""
        self.daily_sent += 1
        self.last_sent_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self, include_config=False) -> dict:
        """转换为字典"""
        result = {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'daily_limit': self.daily_limit,
            'daily_sent': self.daily_sent,
            'last_reset_at': self.last_reset_at.isoformat() if self.last_reset_at else None,
            'last_sent_at': self.last_sent_at.isoformat() if self.last_sent_at else None,
            'priority': self.priority,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'quota_available': self.is_quota_available()
        }
        
        if include_config:
            config = self.get_config()
            # 隐藏敏感信息
            if 'password' in config:
                config['password'] = '******' if config['password'] else ''
            if 'access_key_secret' in config:
                config['access_key_secret'] = '******' if config['access_key_secret'] else ''
            result['config'] = config
        
        return result
    
    @staticmethod
    def validate_config(account_type: str, config: dict) -> tuple:
        """
        验证配置格式
        返回: (is_valid, error_message)
        """
        if account_type == EmailAccount.TYPE_SMTP:
            required_fields = ['host', 'port', 'user', 'password']
            for field in required_fields:
                if not config.get(field):
                    return False, f'SMTP配置缺少必填字段: {field}'
            
            # 验证端口
            try:
                port = int(config['port'])
                if port < 1 or port > 65535:
                    return False, 'SMTP端口必须在1-65535之间'
            except (ValueError, TypeError):
                return False, 'SMTP端口必须是数字'
            
            return True, None
        
        elif account_type == EmailAccount.TYPE_ALIYUN:
            required_fields = ['access_key_id', 'access_key_secret', 'account_name']
            for field in required_fields:
                if not config.get(field):
                    return False, f'阿里云配置缺少必填字段: {field}'
            
            return True, None
        
        else:
            return False, f'不支持的账户类型: {account_type}'
    
    @classmethod
    def get_available_accounts(cls):
        """获取所有可用账户（启用且配额未耗尽），按优先级排序"""
        accounts = cls.query.filter_by(enabled=True).order_by(cls.priority.asc()).all()
        
        # 过滤配额可用的账户
        available = []
        for account in accounts:
            if account.is_quota_available():
                available.append(account)
        
        return available
    
    @classmethod
    def get_next_account_for_send(cls):
        """
        获取下一个用于发送的账户（轮询机制）
        按照 daily_sent 最少的账户优先，实现均匀分配
        """
        accounts = cls.query.filter_by(enabled=True).all()
        
        # 过滤配额可用的账户
        available = []
        for account in accounts:
            if account.is_quota_available():
                available.append(account)
        
        if not available:
            return None
        
        # 按 daily_sent 升序排序，发送最少的优先
        # 如果 daily_sent 相同，按 priority 排序
        available.sort(key=lambda a: (a.daily_sent, a.priority))
        
        return available[0]
    
    @classmethod
    def get_all_accounts(cls):
        """获取所有账户，按优先级排序"""
        return cls.query.order_by(cls.priority.asc()).all()
