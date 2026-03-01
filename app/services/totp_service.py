"""
TOTP双因素认证服务
基于时间的一次性密码(Time-based One-Time Password)
"""
import hmac
import hashlib
import struct
import time
import base64
import secrets


class TOTPService:
    """TOTP服务"""
    
    # 默认配置
    DIGITS = 6  # 验证码位数
    PERIOD = 30  # 有效期（秒）
    ALGORITHM = 'SHA1'
    
    @classmethod
    def generate_secret(cls, length=32):
        """
        生成密钥
        
        Args:
            length: 密钥长度
            
        Returns:
            str: Base32编码的密钥
        """
        # 生成随机字节
        random_bytes = secrets.token_bytes(length)
        # Base32编码
        return base64.b32encode(random_bytes).decode('utf-8').rstrip('=')
    
    @classmethod
    def get_totp(cls, secret, timestamp=None):
        """
        生成TOTP验证码
        
        Args:
            secret: Base32编码的密钥
            timestamp: 时间戳（可选，默认当前时间）
            
        Returns:
            str: 6位验证码
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        # 计算时间计数器
        counter = timestamp // cls.PERIOD
        
        # 解码密钥
        secret_bytes = cls._decode_secret(secret)
        
        # 生成HMAC
        counter_bytes = struct.pack('>Q', counter)
        hmac_hash = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()
        
        # 动态截断
        offset = hmac_hash[-1] & 0x0F
        code = struct.unpack('>I', hmac_hash[offset:offset + 4])[0]
        code = (code & 0x7FFFFFFF) % (10 ** cls.DIGITS)
        
        return str(code).zfill(cls.DIGITS)
    
    @classmethod
    def verify(cls, secret, code, window=1):
        """
        验证TOTP码
        
        Args:
            secret: Base32编码的密钥
            code: 用户输入的验证码
            window: 允许的时间窗口偏移（前后各多少个周期）
            
        Returns:
            bool: 是否验证通过
        """
        if not code or len(code) != cls.DIGITS:
            return False
        
        current_time = int(time.time())
        
        # 检查当前及前后窗口
        for offset in range(-window, window + 1):
            check_time = current_time + (offset * cls.PERIOD)
            if cls.get_totp(secret, check_time) == code:
                return True
        
        return False
    
    @classmethod
    def get_provisioning_uri(cls, secret, email, issuer='六趣DNS'):
        """
        生成配置URI（用于二维码）
        
        Args:
            secret: Base32编码的密钥
            email: 用户邮箱
            issuer: 应用名称
            
        Returns:
            str: otpauth:// URI
        """
        from urllib.parse import quote
        
        # 确保密钥是标准格式
        secret_clean = secret.replace(' ', '').upper()
        
        uri = f'otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret_clean}&issuer={quote(issuer)}&algorithm={cls.ALGORITHM}&digits={cls.DIGITS}&period={cls.PERIOD}'
        
        return uri
    
    @classmethod
    def generate_qr_code(cls, uri):
        """
        生成二维码（Base64图片）
        
        Args:
            uri: otpauth:// URI
            
        Returns:
            str: Base64编码的PNG图片
        """
        try:
            import qrcode
            import io
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            import base64
            return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode()
        except ImportError:
            # 如果没有安装qrcode库，返回None
            return None
    
    @classmethod
    def _decode_secret(cls, secret):
        """解码Base32密钥"""
        # 添加填充
        secret = secret.upper()
        padding = 8 - (len(secret) % 8)
        if padding != 8:
            secret += '=' * padding
        return base64.b32decode(secret)
    
    @classmethod
    def generate_backup_codes(cls, count=10):
        """
        生成备用码
        
        Args:
            count: 生成数量
            
        Returns:
            list: 备用码列表
        """
        codes = []
        for _ in range(count):
            # 生成8位随机码
            code = ''.join([str(secrets.randbelow(10)) for _ in range(8)])
            # 格式化为 XXXX-XXXX
            codes.append(f'{code[:4]}-{code[4:]}')
        return codes
