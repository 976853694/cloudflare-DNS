from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class Setting(db.Model):
    """系统设置模型"""
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 默认设置
    DEFAULT_SETTINGS = {
        'site_name': {'value': '六趣DNS', 'description': '站点名称'},
        'site_description': {'value': '六趣DNS二级域名解析系统', 'description': '站点描述'},
        'site_logo': {'value': '', 'description': '站点Logo URL'},
        'site_favicon': {'value': '', 'description': '站点Favicon URL'},
        'admin_email': {'value': '', 'description': '管理员邮箱'},
        'support_email': {'value': '', 'description': '客服邮箱'},
        'icp_number': {'value': '', 'description': 'ICP备案号'},
        'footer_text': {'value': '', 'description': '页脚文字'},
        'allow_register': {'value': '1', 'description': '是否开放注册 (1开放/0关闭)'},
        'allow_email_register': {'value': '1', 'description': '是否允许邮箱注册 (1允许/0仅快捷登录)'},
        'default_max_domains': {'value': '5', 'description': '用户默认可申请域名数'},
        'announcement': {'value': '', 'description': '系统公告'},
        'terms_of_service': {'value': '', 'description': '服务条款'},
        'privacy_policy': {'value': '', 'description': '隐私政策'},
        # 邮箱后缀限制
        'email_suffix_enabled': {'value': '0', 'description': '是否启用邮箱后缀限制 (1启用/0禁用)'},
        'email_suffix_mode': {'value': 'whitelist', 'description': '邮箱后缀模式 (whitelist白名单/blacklist黑名单)'},
        'email_suffix_list': {'value': '', 'description': '邮箱后缀列表，每行一个'},
        # 验证码场景开关
        'captcha_login': {'value': '1', 'description': '登录是否需要验证码 (1需要/0不需要)'},
        'captcha_register': {'value': '1', 'description': '注册是否需要验证码 (1需要/0不需要)'},
        'captcha_forgot_password': {'value': '1', 'description': '找回密码是否需要验证码 (1需要/0不需要)'},
        'captcha_change_password': {'value': '1', 'description': '修改密码是否需要验证码 (1需要/0不需要)'},
        'captcha_change_email': {'value': '1', 'description': '修改邮箱是否需要验证码 (1需要/0不需要)'},
        'captcha_signin': {'value': '1', 'description': '签到是否需要验证码 (1需要/0不需要)'},
        # Cloudflare Turnstile 验证码
        'turnstile_enabled': {'value': '0', 'description': '是否启用 Turnstile 验证码 (1启用/0禁用)'},
        'turnstile_site_key': {'value': '', 'description': 'Turnstile Site Key'},
        'turnstile_secret_key': {'value': '', 'description': 'Turnstile Secret Key'},
        # 网站统计代码
        'analytics_code': {'value': '', 'description': '网站统计代码（如百度统计、Google Analytics等）'},
        # GitHub OAuth
        'github_oauth_enabled': {'value': '0', 'description': '是否启用 GitHub 快捷登录 (1启用/0禁用)'},
        'github_client_id': {'value': '', 'description': 'GitHub OAuth Client ID'},
        'github_client_secret': {'value': '', 'description': 'GitHub OAuth Client Secret'},
        # Google OAuth
        'google_oauth_enabled': {'value': '0', 'description': '是否启用 Google 快捷登录 (1启用/0禁用)'},
        'google_client_id': {'value': '', 'description': 'Google OAuth Client ID'},
        'google_client_secret': {'value': '', 'description': 'Google OAuth Client Secret'},
        # NodeLoc OAuth
        'nodeloc_oauth_enabled': {'value': '0', 'description': '是否启用 NodeLoc 快捷登录 (1启用/0禁用)'},
        'nodeloc_client_id': {'value': '', 'description': 'NodeLoc OAuth Client ID'},
        'nodeloc_client_secret': {'value': '', 'description': 'NodeLoc OAuth Client Secret'},
        # 阿里云短信配置
        'sms_enabled': {'value': '0', 'description': '是否启用短信服务 (1启用/0禁用)'},
        'aliyun_sms_access_key_id': {'value': '', 'description': '阿里云短信 AccessKey ID'},
        'aliyun_sms_access_key_secret': {'value': '', 'description': '阿里云短信 AccessKey Secret'},
        # 手机号绑定验证
        'require_phone_binding': {'value': '0', 'description': '是否强制绑定手机号才能购买 (1启用/0禁用)'},
        # 全局广告按钮
        'ad_buttons': {'value': '免费流量卡,https://172.lot-ml.com/ProductEn/Index/f2732ecf744f09d6', 'description': '全局广告按钮，每行一个，格式：文字,链接'},
        # 域名空置检测配置
        'idle_domain_check_enabled': {'value': '1', 'description': '是否启用空置域名检测 (1启用/0禁用)'},
        'idle_domain_reminder_days': {'value': '7', 'description': '空置域名提醒天数'},
        'idle_domain_delete_days': {'value': '10', 'description': '空置域名删除天数'},
        # 域名到期提醒配置
        'domain_expiry_reminder_enabled': {'value': '1', 'description': '是否启用域名到期提醒 (1启用/0禁用)'},
        'domain_expiry_reminder_days': {'value': '7,3,2,1', 'description': '域名到期提醒天数，多个用逗号分隔'},
        'domain_expiry_disable_days': {'value': '0', 'description': '域名过期后多少天停用 (0表示立即停用)'},
        'domain_expiry_delete_days': {'value': '30', 'description': '域名过期后多少天删除'},
        # 邮箱链接登录（Magic Link）
        'magic_link_enabled': {'value': '1', 'description': '是否启用邮箱链接登录 (1启用/0禁用)'},
        'magic_link_expire_minutes': {'value': '15', 'description': '登录链接有效期（分钟）'},
        'magic_link_cooldown_seconds': {'value': '60', 'description': '发送冷却时间（秒）'},
        'captcha_magic_link': {'value': '1', 'description': '邮箱链接登录是否需要验证码 (1需要/0不需要)'},
        # 免费套餐设置
        'free_plan_enabled': {'value': '1', 'description': '是否启用免费套餐功能 (1启用/0禁用)'},
        'free_plan_review_mode': {'value': 'manual', 'description': '审核模式 (manual手动审核/auto自动通过)'},
        'free_plan_max_applications': {'value': '3', 'description': '单用户最大申请次数'},
        'free_plan_min_reason_length': {'value': '50', 'description': '申请理由最小字符数'},
        'free_plan_reject_cooldown_days': {'value': '7', 'description': '被拒绝后多少天可重新申请'},
    }
    
    @classmethod
    def get(cls, key, default=None):
        """获取设置值"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            return setting.value
        # 返回默认值
        if key in cls.DEFAULT_SETTINGS:
            return cls.DEFAULT_SETTINGS[key]['value']
        return default
    
    @classmethod
    def set(cls, key, value):
        """设置值"""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            description = cls.DEFAULT_SETTINGS.get(key, {}).get('description', '')
            setting = cls(key=key, value=value, description=description)
            db.session.add(setting)
        db.session.commit()
        return setting
    
    @classmethod
    def get_all(cls):
        """获取所有设置"""
        settings = {}
        # 先加载默认值
        for key, info in cls.DEFAULT_SETTINGS.items():
            settings[key] = info['value']
        # 覆盖数据库中的值
        for setting in cls.query.all():
            settings[setting.key] = setting.value
        return settings
    
    @classmethod
    def init_defaults(cls):
        """初始化默认设置"""
        for key, info in cls.DEFAULT_SETTINGS.items():
            if not cls.query.filter_by(key=key).first():
                setting = cls(key=key, value=info['value'], description=info['description'])
                db.session.add(setting)
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'description': self.description
        }
