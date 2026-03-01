"""
验证码服务
使用内存存储验证码
"""
import base64
import random
import string
import time
from io import BytesIO
from captcha.image import ImageCaptcha


class CaptchaService:
    """验证码服务（内存存储）"""
    
    # 内存存储验证码：{captcha_id: {'code': str, 'expires': timestamp, 'attempts': int}}
    _captcha_store = {}
    
    # 验证码有效期（秒）
    CAPTCHA_EXPIRE_SECONDS = 300  # 5分钟
    
    # 最大存储数量（内存模式）
    MAX_STORE_SIZE = 500
    
    @classmethod
    def _cleanup_expired(cls):
        """清理过期的验证码"""
        now = time.time()
        expired_keys = [
            k for k, v in cls._captcha_store.items() 
            if v.get('expires', 0) < now
        ]
        for key in expired_keys:
            cls._captcha_store.pop(key, None)
        
        # 如果仍然超过最大数量，删除最早的
        if len(cls._captcha_store) > cls.MAX_STORE_SIZE:
            sorted_items = sorted(
                cls._captcha_store.items(), 
                key=lambda x: x[1].get('expires', 0)
            )
            for key, _ in sorted_items[:len(cls._captcha_store) - cls.MAX_STORE_SIZE]:
                cls._captcha_store.pop(key, None)
    
    @classmethod
    def generate(cls, captcha_id: str = None, length: int = 4) -> dict:
        """
        生成验证码
        :param captcha_id: 验证码ID，为空则自动生成
        :param length: 验证码长度
        :return: {'id': str, 'image': base64_string}
        """
        if not captcha_id:
            # 生成唯一ID
            captcha_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        
        # 生成4位纯数字验证码
        code = ''.join(random.choices('0123456789', k=length))
        
        # 生成图片
        image = ImageCaptcha(width=120, height=40, font_sizes=(32, 36))
        data = image.generate(code)
        
        # 转为 base64
        buffer = BytesIO()
        buffer.write(data.read())
        base64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # 内存存储
        cls._cleanup_expired()
        cls._captcha_store[captcha_id] = {
            'code': code,
            'expires': time.time() + cls.CAPTCHA_EXPIRE_SECONDS,
            'attempts': 0
        }
        
        print(f'[Captcha] Generated: id={captcha_id}, code={code}, stored in Memory (total: {len(cls._captcha_store)})')
        
        return {
            'id': captcha_id,
            'image': f'data:image/png;base64,{base64_image}'
        }
    
    @classmethod
    def verify(cls, captcha_id: str, code: str, remove: bool = True) -> bool:
        """
        验证验证码
        :param captcha_id: 验证码ID
        :param code: 用户输入的验证码
        :param remove: 验证后是否删除（仅验证成功时删除）
        :return: 是否正确
        """
        if not captcha_id or not code:
            print(f'[Captcha] Verify failed: empty captcha_id={captcha_id} or code={code}')
            return False
        
        # 标准化输入（去除空格）
        code = code.strip()
        
        # 内存模式
        stored = cls._captcha_store.get(captcha_id)
        if not stored:
            print(f'[Captcha] Verify failed: captcha_id={captcha_id} not found in memory. Store has {len(cls._captcha_store)} items')
            # 打印当前存储的所有 key（调试用，生产环境可删除）
            if len(cls._captcha_store) < 10:
                print(f'[Captcha] Current keys in memory: {list(cls._captcha_store.keys())}')
            return False
        
        # 检查是否过期
        if stored.get('expires', 0) < time.time():
            cls._captcha_store.pop(captcha_id, None)
            print(f'[Captcha] Verify failed: captcha_id={captcha_id} expired')
            return False
        
        # 检查尝试次数（最多3次）
        attempts = stored.get('attempts', 0)
        if attempts >= 3:
            print(f'[Captcha] Verify failed: captcha_id={captcha_id} too many attempts ({attempts})')
            cls._captcha_store.pop(captcha_id, None)
            return False
        
        stored_code = stored.get('code', '')
        is_valid = stored_code == code
        print(f'[Captcha] Verify (Memory): captcha_id={captcha_id}, input={code}, stored={stored_code}, valid={is_valid}, attempts={attempts+1}')
        
        if is_valid:
            # 验证成功，删除验证码
            if remove:
                cls._captcha_store.pop(captcha_id, None)
        else:
            # 验证失败，增加尝试次数
            stored['attempts'] = attempts + 1
        
        return is_valid
    
    @classmethod
    def remove(cls, captcha_id: str):
        """删除验证码"""
        cls._captcha_store.pop(captcha_id, None)
    
    @classmethod
    def get_store_size(cls) -> int:
        """获取当前存储的验证码数量（调试用）"""
        return len(cls._captcha_store)
