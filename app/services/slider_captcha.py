"""
滑块验证码服务
纯本地实现，使用 CSS 生成抽象背景，无需外部图片资源
支持内存存储和 Redis 存储（多进程环境推荐使用 Redis）
"""
import secrets
import random
import time
import os
import math
from typing import Tuple, Optional


class SliderCaptchaService:
    """滑块验证码服务"""
    
    # 内存存储：{token: {'puzzle_x': int, 'puzzle_y': int, 'style_type': str, 'attempts': int, 'expires': timestamp}}
    _slider_store = {}
    
    # Redis 客户端（延迟初始化）
    _redis_client = None
    _redis_initialized = False
    
    # 配置常量
    EXPIRE_SECONDS = 120          # Token 有效期（秒）
    MAX_ATTEMPTS = 3              # 最大尝试次数
    POSITION_TOLERANCE = 5        # 位置容差（像素）
    MIN_SLIDE_TIME = 300          # 最小滑动时间（毫秒）
    MAX_SLIDE_TIME = 10000        # 最大滑动时间（毫秒）
    MIN_TRAJECTORY_POINTS = 10    # 最小轨迹点数
    MIN_Y_STDDEV = 1.0            # 最小 Y 轴标准差
    
    # 验证码尺寸
    BG_WIDTH = 300                # 背景宽度
    BG_HEIGHT = 150               # 背景高度
    PUZZLE_SIZE = 50              # 缺口大小
    
    # 缺口位置范围（确保在可见区域内，且留出拼图块起始空间）
    PUZZLE_X_MIN = 120            # X 坐标最小值（留出左侧空间给拼图块起始位置）
    PUZZLE_X_MAX = 230            # X 坐标最大值（300 - 50 - 20 边距）
    PUZZLE_Y_MIN = 30             # Y 坐标最小值
    PUZZLE_Y_MAX = 70             # Y 坐标最大值（150 - 50 - 30 边距）
    
    # 最大存储数量（内存模式）
    MAX_STORE_SIZE = 500
    
    # Redis key 前缀
    REDIS_KEY_PREFIX = 'slider_captcha:'
    
    # 背景样式类型
    STYLE_TYPES = [
        'gradient_overlay',    # 多层渐变叠加
        'stripe_gradient',     # 条纹渐变
        'radial_gradient',     # 圆形渐变
        'grid_pattern',        # 网格图案
        'wave_gradient',       # 波浪渐变
        'mosaic_effect'        # 马赛克效果
    ]

    @classmethod
    def _get_redis(cls):
        """获取 Redis 客户端（如果配置了的话）"""
        if cls._redis_initialized:
            if cls._redis_client:
                try:
                    cls._redis_client.ping()
                    return cls._redis_client
                except Exception as e:
                    print(f'[SliderCaptcha] Redis connection lost: {e}, reconnecting...')
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
                print('[SliderCaptcha] Using Redis storage')
            except Exception as e:
                print(f'[SliderCaptcha] Redis connection failed: {e}, using memory storage')
                cls._redis_client = None
        else:
            print('[SliderCaptcha] No REDIS_URL configured, using memory storage')
        
        return cls._redis_client
    
    @classmethod
    def _cleanup_expired(cls):
        """清理过期的验证码（仅内存模式）"""
        now = time.time()
        expired_keys = [
            k for k, v in cls._slider_store.items() 
            if v.get('expires', 0) < now
        ]
        for key in expired_keys:
            cls._slider_store.pop(key, None)
        
        if len(cls._slider_store) > cls.MAX_STORE_SIZE:
            sorted_items = sorted(
                cls._slider_store.items(), 
                key=lambda x: x[1].get('expires', 0)
            )
            for key, _ in sorted_items[:len(cls._slider_store) - cls.MAX_STORE_SIZE]:
                cls._slider_store.pop(key, None)
    
    @classmethod
    def _generate_background_style(cls) -> Tuple[str, dict]:
        """
        生成随机背景样式
        
        Returns:
            (style_type: str, style_params: dict)
        """
        style_type = random.choice(cls.STYLE_TYPES)
        
        # 生成随机颜色
        def random_color():
            """生成随机颜色"""
            colors = [
                '#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe',
                '#43e97b', '#38f9d7', '#fa709a', '#fee140', '#30cfd0', '#330867',
                '#a8edea', '#fed6e3', '#5ee7df', '#b490ca', '#d299c2', '#fef9d7',
                '#89f7fe', '#66a6ff', '#ff6b6b', '#4ecdc4', '#45b7d1', '#96e6a1',
                '#dfe6e9', '#b2bec3', '#636e72', '#2d3436', '#fd79a8', '#e84393'
            ]
            return random.choice(colors)
        
        def random_angle():
            """生成随机角度"""
            return random.randint(0, 360)
        
        style_params = {
            'colors': [random_color() for _ in range(3)],
            'angles': [random_angle() for _ in range(3)]
        }
        
        # 根据样式类型添加特定参数
        if style_type == 'stripe_gradient':
            style_params['stripe_width'] = random.randint(8, 15)
        elif style_type == 'grid_pattern':
            style_params['grid_size'] = random.randint(15, 25)
        elif style_type == 'radial_gradient':
            style_params['circles'] = [
                {'x': random.randint(10, 90), 'y': random.randint(10, 90)},
                {'x': random.randint(10, 90), 'y': random.randint(10, 90)},
                {'x': random.randint(10, 90), 'y': random.randint(10, 90)}
            ]
        elif style_type == 'mosaic_effect':
            style_params['colors'].append(random_color())  # 马赛克需要更多颜色
        
        return style_type, style_params

    @classmethod
    def generate(cls) -> dict:
        """
        生成滑块验证码
        
        Returns:
            {
                'token': str,           # 唯一令牌
                'style_type': str,      # 背景样式类型
                'style_params': dict,   # 背景样式参数（颜色等）
                'puzzle_y': int         # 缺口 Y 坐标（X 坐标不返回，保密）
            }
        """
        redis_client = cls._get_redis()
        
        # 生成唯一 Token（使用安全随机数）
        token = secrets.token_urlsafe(24)
        
        # 生成随机缺口位置
        puzzle_x = random.randint(cls.PUZZLE_X_MIN, cls.PUZZLE_X_MAX)
        puzzle_y = random.randint(cls.PUZZLE_Y_MIN, cls.PUZZLE_Y_MAX)
        
        # 生成随机背景样式
        style_type, style_params = cls._generate_background_style()
        
        # 存储数据
        data = {
            'puzzle_x': puzzle_x,
            'puzzle_y': puzzle_y,
            'style_type': style_type,
            'attempts': 0,
            'created_at': int(time.time())
        }
        
        stored_in_redis = False
        if redis_client:
            try:
                import json
                redis_key = cls.REDIS_KEY_PREFIX + token
                redis_client.setex(redis_key, cls.EXPIRE_SECONDS, json.dumps(data))
                stored_in_redis = True
            except Exception as e:
                print(f'[SliderCaptcha] Redis error during generate: {e}')
                cls._redis_initialized = False
                cls._redis_client = None
        
        if not stored_in_redis:
            cls._cleanup_expired()
            data['expires'] = time.time() + cls.EXPIRE_SECONDS
            cls._slider_store[token] = data
        
        return {
            'token': token,
            'style_type': style_type,
            'style_params': style_params,
            'puzzle_x': puzzle_x,  # 缺口 X 坐标（用于前端显示）
            'puzzle_y': puzzle_y   # 缺口 Y 坐标
        }
    
    @classmethod
    def _get_stored_data(cls, token: str) -> Optional[dict]:
        """获取存储的验证码数据"""
        redis_client = cls._get_redis()
        
        if redis_client:
            try:
                import json
                redis_key = cls.REDIS_KEY_PREFIX + token
                data_str = redis_client.get(redis_key)
                if data_str:
                    return json.loads(data_str)
                return None
            except Exception as e:
                print(f'[SliderCaptcha] Redis error during get: {e}')
                cls._redis_initialized = False
                cls._redis_client = None
        
        # 内存模式
        data = cls._slider_store.get(token)
        if data:
            if data.get('expires', 0) < time.time():
                cls._slider_store.pop(token, None)
                return None
            return data
        return None
    
    @classmethod
    def _update_attempts(cls, token: str, attempts: int):
        """更新尝试次数"""
        redis_client = cls._get_redis()
        
        if redis_client:
            try:
                import json
                redis_key = cls.REDIS_KEY_PREFIX + token
                data_str = redis_client.get(redis_key)
                if data_str:
                    data = json.loads(data_str)
                    data['attempts'] = attempts
                    ttl = redis_client.ttl(redis_key)
                    if ttl > 0:
                        redis_client.setex(redis_key, ttl, json.dumps(data))
            except Exception as e:
                print(f'[SliderCaptcha] Redis error during update: {e}')
        else:
            if token in cls._slider_store:
                cls._slider_store[token]['attempts'] = attempts
    
    @classmethod
    def _remove_token(cls, token: str):
        """删除 Token"""
        redis_client = cls._get_redis()
        
        if redis_client:
            try:
                redis_key = cls.REDIS_KEY_PREFIX + token
                redis_client.delete(redis_key)
            except Exception as e:
                print(f'[SliderCaptcha] Redis error during remove: {e}')
        else:
            cls._slider_store.pop(token, None)

    @classmethod
    def _analyze_trajectory(cls, trajectory: list) -> Tuple[bool, str]:
        """
        分析轨迹数据，判断是否为机器人
        
        Args:
            trajectory: 轨迹数据 [{'x': int, 'y': int, 't': int}, ...]
        
        Returns:
            (is_human: bool, reason: str)
        """
        if not trajectory or len(trajectory) < 2:
            return False, '轨迹数据不足'
        
        # 检查轨迹点数
        if len(trajectory) < cls.MIN_TRAJECTORY_POINTS:
            return False, f'轨迹点数不足（需要至少 {cls.MIN_TRAJECTORY_POINTS} 个点）'
        
        # 计算滑动时间
        try:
            start_time = trajectory[0].get('t', 0)
            end_time = trajectory[-1].get('t', 0)
            slide_time = end_time - start_time
        except (KeyError, TypeError):
            return False, '轨迹数据格式错误'
        
        # 检查滑动时间范围
        if slide_time < cls.MIN_SLIDE_TIME:
            return False, f'滑动时间过短（{slide_time}ms < {cls.MIN_SLIDE_TIME}ms）'
        
        if slide_time > cls.MAX_SLIDE_TIME:
            return False, f'滑动时间过长（{slide_time}ms > {cls.MAX_SLIDE_TIME}ms）'
        
        # 计算 Y 轴标准差（检测自然抖动）
        try:
            y_values = [point.get('y', 0) for point in trajectory]
            if len(y_values) > 1:
                mean_y = sum(y_values) / len(y_values)
                variance = sum((y - mean_y) ** 2 for y in y_values) / len(y_values)
                stddev = math.sqrt(variance)
                
                if stddev < cls.MIN_Y_STDDEV:
                    return False, f'轨迹过于平直（Y轴标准差 {stddev:.2f} < {cls.MIN_Y_STDDEV}）'
        except (TypeError, ValueError):
            return False, '轨迹数据计算错误'
        
        return True, 'OK'
    
    @classmethod
    def verify(cls, token: str, position: int, trajectory: list = None) -> Tuple[bool, str]:
        """
        验证滑块
        
        Args:
            token: 验证码令牌
            position: 用户滑动到的 X 坐标
            trajectory: 轨迹数据 [{'x': int, 'y': int, 't': int}, ...]
        
        Returns:
            (success: bool, message: str)
        """
        if not token:
            return False, '验证码令牌不能为空'
        
        # 获取存储的数据
        data = cls._get_stored_data(token)
        
        if not data:
            return False, '验证码已失效，请刷新'
        
        # 检查尝试次数
        attempts = data.get('attempts', 0)
        if attempts >= cls.MAX_ATTEMPTS:
            cls._remove_token(token)
            return False, '验证码已失效，请刷新'
        
        # 分析轨迹（如果提供了轨迹数据）
        if trajectory:
            is_human, reason = cls._analyze_trajectory(trajectory)
            if not is_human:
                # 轨迹分析失败，增加尝试次数
                cls._update_attempts(token, attempts + 1)
                if attempts + 1 >= cls.MAX_ATTEMPTS:
                    cls._remove_token(token)
                    return False, '验证码已失效，请刷新'
                return False, '验证失败，请重试'
        
        # 验证位置
        puzzle_x = data.get('puzzle_x', 0)
        position_diff = abs(position - puzzle_x)
        
        if position_diff <= cls.POSITION_TOLERANCE:
            # 验证成功，删除 Token（一次性使用）
            cls._remove_token(token)
            return True, '验证成功'
        else:
            # 验证失败，增加尝试次数
            cls._update_attempts(token, attempts + 1)
            if attempts + 1 >= cls.MAX_ATTEMPTS:
                cls._remove_token(token)
                return False, '验证码已失效，请刷新'
            return False, '验证失败，请重试'
