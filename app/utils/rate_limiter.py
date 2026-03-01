"""
API 限流模块
简单的内存限流实现，生产环境建议使用 Redis
"""
import time
from functools import wraps
from flask import request, jsonify
from collections import defaultdict
import threading
from app.utils.ip_utils import get_real_ip


class RateLimiter:
    """
    简单的滑动窗口限流器
    注意：内存存储，多进程环境下不共享，生产环境建议使用 Redis
    """
    
    def __init__(self):
        self._requests = defaultdict(list)
        self._lock = threading.Lock()
    
    def _get_key(self, identifier, endpoint=None):
        """生成限流键"""
        if endpoint:
            return f"{identifier}:{endpoint}"
        return identifier
    
    def _cleanup(self, key, window_seconds):
        """清理过期的请求记录"""
        now = time.time()
        cutoff = now - window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
    
    def is_allowed(self, identifier, max_requests, window_seconds, endpoint=None):
        """
        检查是否允许请求
        
        Args:
            identifier: 标识符（如IP地址）
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
            endpoint: 端点名称（可选，用于按端点限流）
            
        Returns:
            tuple: (是否允许, 剩余请求数, 重置时间)
        """
        key = self._get_key(identifier, endpoint)
        now = time.time()
        
        with self._lock:
            self._cleanup(key, window_seconds)
            
            request_count = len(self._requests[key])
            
            if request_count >= max_requests:
                # 计算重置时间
                oldest = self._requests[key][0] if self._requests[key] else now
                reset_time = int(oldest + window_seconds - now)
                return False, 0, reset_time
            
            # 记录请求
            self._requests[key].append(now)
            remaining = max_requests - len(self._requests[key])
            return True, remaining, window_seconds
    
    def clear(self, identifier=None, endpoint=None):
        """清除限流记录"""
        with self._lock:
            if identifier is None:
                self._requests.clear()
            else:
                key = self._get_key(identifier, endpoint)
                self._requests.pop(key, None)


# 全局限流器实例
rate_limiter = RateLimiter()


def rate_limit(max_requests=60, window_seconds=60, key_func=None, endpoint_specific=False):
    """
    限流装饰器
    
    Args:
        max_requests: 时间窗口内最大请求数
        window_seconds: 时间窗口（秒）
        key_func: 自定义获取标识符的函数，默认使用IP
        endpoint_specific: 是否按端点分别限流
        
    Usage:
        @app.route('/api/example')
        @rate_limit(max_requests=10, window_seconds=60)
        def example():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 获取标识符
            if key_func:
                identifier = key_func()
            else:
                # 默认使用IP地址
                identifier = get_real_ip()
                if ',' in identifier:
                    identifier = identifier.split(',')[0].strip()
            
            # 端点名称
            endpoint = request.endpoint if endpoint_specific else None
            
            # 检查限流
            allowed, remaining, reset_time = rate_limiter.is_allowed(
                identifier, max_requests, window_seconds, endpoint
            )
            
            if not allowed:
                response = jsonify({
                    'code': 429,
                    'message': f'请求过于频繁，请在 {reset_time} 秒后重试'
                })
                response.status_code = 429
                response.headers['X-RateLimit-Limit'] = str(max_requests)
                response.headers['X-RateLimit-Remaining'] = '0'
                response.headers['X-RateLimit-Reset'] = str(reset_time)
                response.headers['Retry-After'] = str(reset_time)
                return response
            
            # 执行原函数
            response = f(*args, **kwargs)
            
            # 添加限流头
            if hasattr(response, 'headers'):
                response.headers['X-RateLimit-Limit'] = str(max_requests)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
            
            return response
        return wrapper
    return decorator


# 预定义的限流配置
def login_rate_limit():
    """登录接口限流：每分钟10次"""
    return rate_limit(max_requests=10, window_seconds=60, endpoint_specific=True)


def register_rate_limit():
    """注册接口限流：每分钟5次"""
    return rate_limit(max_requests=5, window_seconds=60, endpoint_specific=True)


def api_rate_limit():
    """普通API限流：每分钟60次"""
    return rate_limit(max_requests=60, window_seconds=60)


def strict_rate_limit():
    """严格限流：每分钟20次"""
    return rate_limit(max_requests=20, window_seconds=60)
