"""
会话管理器

管理用户会话状态，支持 Redis 存储和内存存储：
- 购买流程状态
- DNS添加状态
- 卡密兑换状态
- 管理员操作状态
- 托管商操作状态
- 域名转移状态
- 积分操作状态
- 工单操作状态
"""

import json
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List


class SessionManager:
    """用户会话状态管理"""
    
    # 会话状态常量
    # 转移相关
    TRANSFER_INPUT_USER = 'transfer_input_user'      # 输入接收用户
    TRANSFER_INPUT_CODE = 'transfer_input_code'      # 输入验证码
    # 积分相关
    POINTS_INPUT_AMOUNT = 'points_input_amount'      # 输入兑换数量
    # 工单相关
    TICKET_INPUT_SUBJECT = 'ticket_input_subject'    # 输入工单主题
    TICKET_INPUT_CONTENT = 'ticket_input_content'    # 输入工单内容
    TICKET_INPUT_REPLY = 'ticket_input_reply'        # 输入工单回复
    
    # 不同操作类型的超时时间（秒）
    TIMEOUT_MAP = {
        'buying': 600,      # 10分钟 - 购买流程
        'buy_': 600,        # 10分钟 - 购买流程（新前缀）
        'dns': 300,         # 5分钟 - DNS操作
        'dns_': 300,        # 5分钟 - DNS操作（新前缀）
        'redeem': 300,      # 5分钟 - 卡密兑换
        'admin': 300,       # 5分钟 - 管理员操作
        'admin_': 300,      # 5分钟 - 管理员操作（新前缀）
        'host': 300,        # 5分钟 - 托管商操作
        'hc_': 300,         # 5分钟 - 托管商中心操作
        'settings': 300,    # 5分钟 - 设置操作
        'search': 300,      # 5分钟 - 搜索操作
        'transfer': 600,    # 10分钟 - 域名转移
        'transfer_': 600,   # 10分钟 - 域名转移（新前缀）
        'points': 300,      # 5分钟 - 积分操作
        'points_': 300,     # 5分钟 - 积分操作（新前缀）
        'ticket': 600,      # 10分钟 - 工单操作
        'ticket_': 600,     # 10分钟 - 工单操作（新前缀）
        'bind_': 300,       # 5分钟 - 绑定操作
        'account_': 300,    # 5分钟 - 账户操作
    }
    
    # 全局会话超时时间（30分钟）
    SESSION_TIMEOUT = 1800
    
    # 默认超时时间
    DEFAULT_TIMEOUT = 300
    
    # Redis key 前缀
    REDIS_KEY_PREFIX = 'tg_session:'
    
    # Redis 客户端（延迟初始化）
    _redis_client = None
    _redis_initialized = False
    
    # 内存存储（Redis 不可用时的备选）
    _memory_store: Dict[int, Dict[str, Any]] = {}
    
    @classmethod
    def _get_redis(cls):
        """获取 Redis 客户端（如果配置了的话）"""
        if cls._redis_initialized:
            if cls._redis_client:
                try:
                    cls._redis_client.ping()
                    return cls._redis_client
                except Exception as e:
                    print(f'[TG Session] Redis connection lost: {e}, reconnecting...')
                    cls._redis_initialized = False
            else:
                return None
        
        cls._redis_initialized = True
        redis_url = os.getenv('REDIS_URL')
        
        if redis_url:
            try:
                import redis
                cls._redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                cls._redis_client.ping()
                print('[TG Session] Using Redis storage')
            except Exception as e:
                print(f'[TG Session] Redis connection failed: {e}, using memory storage')
                cls._redis_client = None
        else:
            print('[TG Session] No REDIS_URL configured, using memory storage')
        
        return cls._redis_client
    
    @classmethod
    def _get_key(cls, telegram_id: int) -> str:
        """生成 Redis key"""
        return f"{cls.REDIS_KEY_PREFIX}{telegram_id}"
    
    @classmethod
    def _get_timeout(cls, state: str) -> int:
        """根据状态类型获取超时时间"""
        if not state:
            return cls.DEFAULT_TIMEOUT
        prefix = state.split(':')[0]
        return cls.TIMEOUT_MAP.get(prefix, cls.DEFAULT_TIMEOUT)
    
    @classmethod
    def _cleanup_memory(cls):
        """清理内存中过期的会话"""
        now = time.time()
        expired_keys = [
            k for k, v in cls._memory_store.items()
            if v.get('expires', 0) < now
        ]
        for key in expired_keys:
            cls._memory_store.pop(key, None)
    
    @classmethod
    def get_state(cls, telegram_id: int) -> Optional[Dict[str, Any]]:
        """
        获取用户会话状态
        
        Args:
            telegram_id: Telegram 用户 ID
            
        Returns:
            会话数据字典，包含 state、data、created_at 字段
            如果不存在或已过期，返回 None
        """
        redis_client = cls._get_redis()
        
        if redis_client:
            try:
                key = cls._get_key(telegram_id)
                data = redis_client.get(key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                print(f'[TG Session] Redis get error: {e}')
                cls._redis_initialized = False
                cls._redis_client = None
        
        # 内存模式
        stored = cls._memory_store.get(telegram_id)
        if not stored:
            return None
        
        # 检查是否过期
        if stored.get('expires', 0) < time.time():
            cls._memory_store.pop(telegram_id, None)
            return None
        
        return {
            'state': stored.get('state'),
            'data': stored.get('data', {}),
            'created_at': stored.get('created_at')
        }
    
    @classmethod
    def set_state(cls, telegram_id: int, state: str, data: Dict[str, Any] = None) -> bool:
        """
        设置用户会话状态
        
        Args:
            telegram_id: Telegram 用户 ID
            state: 状态标识，格式为 "类型:子状态"，如 "buying:input_prefix"
            data: 附加数据
            
        Returns:
            是否设置成功
        """
        timeout = cls._get_timeout(state)
        created_at = datetime.now().isoformat()
        
        session_data = {
            'state': state,
            'data': data or {},
            'created_at': created_at
        }
        
        redis_client = cls._get_redis()
        
        if redis_client:
            try:
                key = cls._get_key(telegram_id)
                redis_client.setex(key, timeout, json.dumps(session_data))
                return True
            except Exception as e:
                print(f'[TG Session] Redis set error: {e}')
                cls._redis_initialized = False
                cls._redis_client = None
        
        # 内存模式
        cls._cleanup_memory()
        cls._memory_store[telegram_id] = {
            'state': state,
            'data': data or {},
            'created_at': created_at,
            'expires': time.time() + timeout
        }
        return True
    
    @classmethod
    def update_data(cls, telegram_id: int, **kwargs) -> bool:
        """
        更新会话数据（保持状态不变）
        
        Args:
            telegram_id: Telegram 用户 ID
            **kwargs: 要更新的数据字段
            
        Returns:
            是否更新成功
        """
        session = cls.get_state(telegram_id)
        if not session:
            return False
        
        session['data'].update(kwargs)
        return cls.set_state(telegram_id, session['state'], session['data'])
    
    @classmethod
    def clear_state(cls, telegram_id: int) -> bool:
        """
        清除用户会话状态
        
        Args:
            telegram_id: Telegram 用户 ID
            
        Returns:
            是否清除成功
        """
        redis_client = cls._get_redis()
        
        if redis_client:
            try:
                key = cls._get_key(telegram_id)
                redis_client.delete(key)
                return True
            except Exception as e:
                print(f'[TG Session] Redis delete error: {e}')
                cls._redis_initialized = False
                cls._redis_client = None
        
        # 内存模式
        cls._memory_store.pop(telegram_id, None)
        return True
    
    @classmethod
    def is_in_state(cls, telegram_id: int, state_prefix: str = None) -> bool:
        """
        检查用户是否处于某个状态
        
        Args:
            telegram_id: Telegram 用户 ID
            state_prefix: 状态前缀，如 "buying"、"dns"，为 None 则检查是否有任何状态
            
        Returns:
            是否处于指定状态
        """
        session = cls.get_state(telegram_id)
        if not session:
            return False
        
        if state_prefix is None:
            return True
        
        current_state = session.get('state', '')
        return current_state.startswith(state_prefix)
    
    @classmethod
    def get_data(cls, telegram_id: int, key: str = None, default: Any = None) -> Any:
        """
        获取会话数据
        
        Args:
            telegram_id: Telegram 用户 ID
            key: 数据键名，为 None 则返回全部数据
            default: 默认值
            
        Returns:
            数据值或默认值
        """
        session = cls.get_state(telegram_id)
        if not session:
            return default
        
        data = session.get('data', {})
        if key is None:
            return data
        
        return data.get(key, default)
    
    # ==================== 简化 API ====================
    
    @classmethod
    def get(cls, telegram_id: int, state_key: str, default: Any = None) -> Any:
        """
        获取指定状态的数据（简化 API）
        
        Args:
            telegram_id: Telegram 用户 ID
            state_key: 状态键名
            default: 默认值
            
        Returns:
            状态数据或默认值
        """
        session = cls.get_state(telegram_id)
        if not session:
            return default
        
        current_state = session.get('state', '')
        if current_state == state_key or current_state.startswith(f'{state_key}:'):
            return session.get('data', default)
        
        return default
    
    @classmethod
    def set(cls, telegram_id: int, state_key: str, data: Dict[str, Any] = None) -> bool:
        """
        设置状态（简化 API）
        
        Args:
            telegram_id: Telegram 用户 ID
            state_key: 状态键名
            data: 状态数据
            
        Returns:
            是否成功
        """
        return cls.set_state(telegram_id, state_key, data)
    
    @classmethod
    def clear(cls, telegram_id: int, state_key: str = None) -> bool:
        """
        清除状态（简化 API）
        
        Args:
            telegram_id: Telegram 用户 ID
            state_key: 状态键名（可选，用于验证当前状态）
            
        Returns:
            是否成功
        """
        if state_key:
            session = cls.get_state(telegram_id)
            if session:
                current_state = session.get('state', '')
                if not (current_state == state_key or current_state.startswith(f'{state_key}:')):
                    return False
        
        return cls.clear_state(telegram_id)
    
    @classmethod
    def has_active_session(cls, telegram_id: int) -> bool:
        """
        检查是否有活跃会话
        
        Args:
            telegram_id: Telegram 用户 ID
            
        Returns:
            是否有活跃会话
        """
        return cls.get_state(telegram_id) is not None
    
    @classmethod
    def get_remaining_time(cls, telegram_id: int) -> int:
        """
        获取会话剩余时间（秒）
        
        Args:
            telegram_id: Telegram 用户 ID
            
        Returns:
            剩余秒数，无会话返回 0
        """
        redis_client = cls._get_redis()
        
        if redis_client:
            try:
                key = cls._get_key(telegram_id)
                ttl = redis_client.ttl(key)
                return max(0, ttl)
            except Exception as e:
                print(f'[TG Session] Redis TTL error: {e}')
        
        # 内存模式
        stored = cls._memory_store.get(telegram_id)
        if not stored:
            return 0
        
        remaining = stored.get('expires', 0) - time.time()
        return max(0, int(remaining))
    
    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        """
        清理过期会话
        
        Returns:
            清理的会话数量
        """
        redis_client = cls._get_redis()
        
        # Redis 模式下会话自动过期，无需手动清理
        if redis_client:
            return 0
        
        # 内存模式：清理过期会话
        now = time.time()
        expired_keys = [
            k for k, v in cls._memory_store.items()
            if v.get('expires', 0) < now
        ]
        
        for key in expired_keys:
            cls._memory_store.pop(key, None)
        
        if expired_keys:
            print(f'[TG Session] Cleaned up {len(expired_keys)} expired sessions')
        
        return len(expired_keys)
    
    @classmethod
    def get_all_active_sessions(cls) -> List[Dict[str, Any]]:
        """
        获取所有活跃会话（用于调试）
        
        Returns:
            活跃会话列表
        """
        redis_client = cls._get_redis()
        
        if redis_client:
            try:
                keys = redis_client.keys(f'{cls.REDIS_KEY_PREFIX}*')
                sessions = []
                for key in keys:
                    data = redis_client.get(key)
                    if data:
                        session = json.loads(data)
                        session['telegram_id'] = key.replace(cls.REDIS_KEY_PREFIX, '')
                        sessions.append(session)
                return sessions
            except Exception as e:
                print(f'[TG Session] Redis keys error: {e}')
                return []
        
        # 内存模式
        cls._cleanup_memory()
        return [
            {
                'telegram_id': k,
                'state': v.get('state'),
                'data': v.get('data', {}),
                'created_at': v.get('created_at'),
                'expires_in': max(0, int(v.get('expires', 0) - time.time()))
            }
            for k, v in cls._memory_store.items()
        ]
