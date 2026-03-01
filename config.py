import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # Database
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'dns_system')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'pool_size': 5,           # 减少连接池大小（默认5，显式设置）
        'max_overflow': 10,       # 最大溢出连接数
        'pool_timeout': 30,       # 连接超时时间
    }
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400)))
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    
    # Cloudflare
    CF_API_KEY = os.getenv('CF_API_KEY', '')
    CF_EMAIL = os.getenv('CF_EMAIL', '')
    CF_API_TOKEN = os.getenv('CF_API_TOKEN', '')
    CF_API_BASE_URL = 'https://api.cloudflare.com/client/v4'
    
    # App
    APP_NAME = os.getenv('APP_NAME', '六趣DNS')
    APP_VERSION = os.getenv('APP_VERSION', '9999)  # 当前版本号
    VERSION_CHECK_URL = os.getenv('VERSION_CHECK_URL', 'https://gx.6qu.cc/api/check-update')  # 版本检查地址
    DEFAULT_MAX_DOMAINS = int(os.getenv('DEFAULT_MAX_DOMAINS', 5))
    
    # 阿里云短信配置（固定值）
    ALIYUN_SMS_SIGN_NAME = '速通互联验证码'  # 短信签名（固定）
    ALIYUN_SMS_CODE_EXPIRE = 5  # 验证码有效期（分钟）
    
    # 短信模板CODE（固定值）
    ALIYUN_SMS_TPL_LOGIN = '100001'        # 登录/注册
    ALIYUN_SMS_TPL_CHANGE_PHONE = '100002' # 修改手机号
    ALIYUN_SMS_TPL_RESET_PWD = '100003'    # 重置密码
    ALIYUN_SMS_TPL_BIND_PHONE = '100004'   # 绑定新手机
    ALIYUN_SMS_TPL_VERIFY_PHONE = '100005' # 验证绑定手机
    
    # 后台任务配置
    BACKGROUND_TASK_WORKERS = int(os.getenv('BACKGROUND_TASK_WORKERS', 2))
    BACKGROUND_TASK_MAX_QUEUE = int(os.getenv('BACKGROUND_TASK_MAX_QUEUE', 100))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}  # SQLite 不需要连接池配置


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
