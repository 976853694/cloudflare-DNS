"""
统一日志管理模块
替代散落在代码中的 print 语句
"""
import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logger(app):
    """
    配置应用日志
    
    Args:
        app: Flask应用实例
    """
    # 创建日志目录
    log_dir = os.path.join(app.root_path, '..', 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # 日志格式
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    # 文件处理器 - 应用日志
    app_log_file = os.path.join(log_dir, 'app.log')
    file_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # 文件处理器 - 错误日志
    error_log_file = os.path.join(log_dir, 'error.log')
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # 配置应用日志
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # 配置 werkzeug 日志（HTTP请求日志）
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addHandler(file_handler)
    
    return app.logger


def get_logger(name=None):
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称，默认为 'dns'
        
    Returns:
        Logger: 日志记录器
    """
    logger_name = name or 'dns'
    logger = logging.getLogger(logger_name)
    
    if not logger.handlers:
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s]: %(message)s'
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        logger.setLevel(logging.INFO)
    
    return logger


# 预定义的日志记录器
app_logger = get_logger('dns.app')
scheduler_logger = get_logger('dns.scheduler')
cloudflare_logger = get_logger('dns.cloudflare')
email_logger = get_logger('dns.email')
auth_logger = get_logger('dns.auth')
