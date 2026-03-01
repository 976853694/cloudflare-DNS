"""
配置验证模块
在应用启动时验证必要的配置项
"""
import os
from app.utils.logger import get_logger

logger = get_logger('dns.config')


class ConfigValidator:
    """配置验证器"""
    
    # 必需的配置项
    REQUIRED_CONFIGS = [
        ('SECRET_KEY', '应用密钥'),
        ('JWT_SECRET_KEY', 'JWT密钥'),
        ('DB_HOST', '数据库主机'),
        ('DB_NAME', '数据库名'),
        ('DB_USER', '数据库用户'),
    ]
    
    # 可选但建议配置的项
    RECOMMENDED_CONFIGS = [
        ('DB_PASSWORD', '数据库密码'),
    ]
    
    # 生产环境必需的配置项
    PRODUCTION_REQUIRED = [
        ('SECRET_KEY', '应用密钥（不能使用默认值）'),
        ('JWT_SECRET_KEY', 'JWT密钥（不能使用默认值）'),
    ]
    
    @classmethod
    def validate(cls, app_config, is_production=False):
        """
        验证配置
        
        Args:
            app_config: Flask应用配置对象
            is_production: 是否为生产环境
            
        Returns:
            tuple: (是否通过, 错误列表, 警告列表)
        """
        errors = []
        warnings = []
        
        # 检查必需配置
        for key, desc in cls.REQUIRED_CONFIGS:
            value = app_config.get(key, os.getenv(key))
            if not value:
                errors.append(f'缺少必需配置: {key} ({desc})')
        
        # 检查建议配置
        for key, desc in cls.RECOMMENDED_CONFIGS:
            value = app_config.get(key, os.getenv(key))
            if not value:
                warnings.append(f'建议配置: {key} ({desc})')
        
        # 生产环境额外检查
        if is_production:
            if app_config.get('SECRET_KEY') == 'dev-secret-key':
                errors.append('生产环境不能使用默认的 SECRET_KEY')
            if app_config.get('JWT_SECRET_KEY') == 'jwt-secret-key':
                errors.append('生产环境不能使用默认的 JWT_SECRET_KEY')
            if app_config.get('DEBUG', False):
                warnings.append('生产环境建议关闭 DEBUG 模式')
        
        return len(errors) == 0, errors, warnings
    
    @classmethod
    def validate_and_log(cls, app_config, is_production=False):
        """
        验证配置并记录日志
        
        Args:
            app_config: Flask应用配置对象
            is_production: 是否为生产环境
            
        Returns:
            bool: 是否通过验证
        """
        passed, errors, warnings = cls.validate(app_config, is_production)
        
        for warning in warnings:
            logger.warning(f'[Config] {warning}')
        
        for error in errors:
            logger.error(f'[Config] {error}')
        
        if passed:
            logger.info('[Config] 配置验证通过')
        else:
            logger.error('[Config] 配置验证失败')
        
        return passed


def validate_smtp_config():
    """
    验证SMTP配置
    
    Returns:
        tuple: (是否配置, 配置详情)
    """
    from app.models import Setting
    
    config = {
        'host': Setting.get('smtp_host', ''),
        'port': Setting.get('smtp_port', ''),
        'user': Setting.get('smtp_user', ''),
        'password': Setting.get('smtp_password', ''),
    }
    
    is_configured = bool(config['host'] and config['user'] and config['password'])
    
    return is_configured, config


def validate_cloudflare_config(app_config):
    """
    验证Cloudflare配置
    
    Args:
        app_config: Flask应用配置对象
        
    Returns:
        tuple: (是否配置, 配置类型)
    """
    api_key = app_config.get('CF_API_KEY', '')
    email = app_config.get('CF_EMAIL', '')
    api_token = app_config.get('CF_API_TOKEN', '')
    
    if api_key and email:
        return True, 'api_key'
    elif api_token:
        return True, 'api_token'
    else:
        return False, None
