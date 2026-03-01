"""
缓存服务
支持Redis和内存缓存，自动降级
"""
import json
import time
from functools import wraps


class MemoryCache:
    """内存缓存（Redis不可用时的降级方案）"""
    
    # 最大缓存条目数，防止内存无限增长
    MAX_ENTRIES = 500
    
    # 清理间隔（秒），避免频繁清理
    CLEANUP_INTERVAL = 60
    
    def __init__(self):
        self._store = {}
        self._expires = {}
        self._last_cleanup = 0
    
    def get(self, key):
        self._maybe_cleanup()
        # 检查是否过期
        if key in self._expires and self._expires[key] < time.time():
            self._store.pop(key, None)
            self._expires.pop(key, None)
            return None
        return self._store.get(key)
    
    def set(self, key, value, ex=None):
        self._maybe_cleanup()
        # 如果超过最大条目数，强制清理
        if len(self._store) >= self.MAX_ENTRIES:
            self._force_cleanup()
        self._store[key] = value
        if ex:
            self._expires[key] = time.time() + ex
    
    def delete(self, key):
        self._store.pop(key, None)
        self._expires.pop(key, None)
    
    def clear(self):
        """清除所有缓存"""
        self._store.clear()
        self._expires.clear()
    
    def exists(self, key):
        self._maybe_cleanup()
        if key in self._expires and self._expires[key] < time.time():
            self._store.pop(key, None)
            self._expires.pop(key, None)
            return False
        return key in self._store
    
    def incr(self, key):
        val = int(self._store.get(key, 0)) + 1
        self._store[key] = val
        return val
    
    def expire(self, key, seconds):
        if key in self._store:
            self._expires[key] = time.time() + seconds
    
    def ttl(self, key):
        if key not in self._expires:
            return -1
        remaining = self._expires[key] - time.time()
        return max(0, int(remaining))
    
    def _maybe_cleanup(self):
        """按间隔清理过期键"""
        now = time.time()
        if now - self._last_cleanup < self.CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        self._cleanup()
    
    def _cleanup(self):
        """清理过期键"""
        now = time.time()
        expired_keys = [k for k, v in self._expires.items() if v < now]
        for key in expired_keys:
            self._store.pop(key, None)
            self._expires.pop(key, None)
    
    def _force_cleanup(self):
        """强制清理：删除过期键 + 最早的键"""
        self._cleanup()
        # 如果仍然超过限制，删除最早过期的键
        if len(self._store) >= self.MAX_ENTRIES:
            sorted_items = sorted(
                [(k, self._expires.get(k, float('inf'))) for k in self._store],
                key=lambda x: x[1]
            )
            # 删除一半
            for key, _ in sorted_items[:len(sorted_items) // 2]:
                self._store.pop(key, None)
                self._expires.pop(key, None)


class CacheService:
    """
    缓存服务
    优先使用Redis，不可用时降级到内存缓存
    """
    
    _redis_client = None
    _memory_cache = MemoryCache()
    _use_redis = False
    
    @classmethod
    def init_redis(cls, redis_url=None):
        """
        初始化Redis连接
        
        Args:
            redis_url: Redis连接URL，如 redis://localhost:6379/0
        """
        if not redis_url:
            import os
            redis_url = os.getenv('REDIS_URL', '')
        
        if not redis_url:
            cls._use_redis = False
            return False
        
        try:
            import redis
            cls._redis_client = redis.from_url(redis_url, decode_responses=True)
            cls._redis_client.ping()
            cls._use_redis = True
            return True
        except Exception as e:
            print(f'[Cache] Redis连接失败，使用内存缓存: {e}')
            cls._use_redis = False
            return False
    
    @classmethod
    def _get_client(cls):
        """获取缓存客户端"""
        if cls._use_redis and cls._redis_client:
            return cls._redis_client
        return cls._memory_cache
    
    @classmethod
    def get(cls, key):
        """获取缓存值"""
        client = cls._get_client()
        value = client.get(key)
        if value and cls._use_redis:
            try:
                return json.loads(value)
            except:
                return value
        return value
    
    @classmethod
    def set(cls, key, value, ttl=3600):
        """
        设置缓存
        
        Args:
            key: 键
            value: 值
            ttl: 过期时间（秒）
        """
        client = cls._get_client()
        if cls._use_redis:
            value = json.dumps(value) if not isinstance(value, str) else value
        client.set(key, value, ex=ttl)
    
    @classmethod
    def delete(cls, key):
        """删除缓存"""
        client = cls._get_client()
        client.delete(key)
    
    @classmethod
    def exists(cls, key):
        """检查键是否存在"""
        client = cls._get_client()
        return client.exists(key)
    
    @classmethod
    def incr(cls, key):
        """自增"""
        client = cls._get_client()
        return client.incr(key)
    
    @classmethod
    def expire(cls, key, seconds):
        """设置过期时间"""
        client = cls._get_client()
        client.expire(key, seconds)
    
    @classmethod
    def get_or_set(cls, key, factory, ttl=3600):
        """
        获取缓存，不存在则设置
        
        Args:
            key: 键
            factory: 生成值的函数
            ttl: 过期时间
        """
        value = cls.get(key)
        if value is None:
            value = factory()
            cls.set(key, value, ttl)
        return value
    
    @classmethod
    def clear_all(cls):
        """
        清除所有缓存
        """
        if cls._use_redis and cls._redis_client:
            cls._redis_client.flushdb()
        else:
            cls._memory_cache.clear()
    
    @classmethod
    def clear_pattern(cls, pattern):
        """
        清除匹配模式的所有键
        
        Args:
            pattern: 键模式，如 "user:*"
        """
        if cls._use_redis and cls._redis_client:
            keys = cls._redis_client.keys(pattern)
            if keys:
                cls._redis_client.delete(*keys)
        else:
            # 内存缓存不支持模式匹配，只能全部清除
            keys_to_delete = [k for k in cls._memory_cache._store.keys() 
                            if k.startswith(pattern.replace('*', ''))]
            for key in keys_to_delete:
                cls._memory_cache.delete(key)


def cached(prefix, ttl=3600, key_func=None):
    """
    缓存装饰器
    
    Args:
        prefix: 缓存键前缀
        ttl: 过期时间（秒）
        key_func: 自定义生成缓存键的函数
        
    Usage:
        @cached('user', ttl=300)
        def get_user(user_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = f'{prefix}:{key_func(*args, **kwargs)}'
            else:
                key_parts = [str(a) for a in args] + [f'{k}={v}' for k, v in sorted(kwargs.items())]
                cache_key = f'{prefix}:{":".join(key_parts)}'
            
            # 尝试获取缓存
            cached_value = CacheService.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 执行函数
            result = f(*args, **kwargs)
            
            # 设置缓存
            CacheService.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator
