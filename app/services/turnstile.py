"""
Cloudflare Turnstile 验证服务
"""
import requests
from app.models import Setting


class TurnstileService:
    """Cloudflare Turnstile 验证服务"""
    
    VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
    
    @classmethod
    def is_enabled(cls) -> bool:
        """检查是否启用 Turnstile"""
        enabled = Setting.get('turnstile_enabled', '0')
        site_key = Setting.get('turnstile_site_key', '')
        secret_key = Setting.get('turnstile_secret_key', '')
        return enabled == '1' and bool(site_key) and bool(secret_key)
    
    @classmethod
    def get_site_key(cls) -> str:
        """获取 Site Key"""
        return Setting.get('turnstile_site_key', '')
    
    @classmethod
    def verify(cls, token: str, remote_ip: str = None) -> tuple[bool, str]:
        """
        验证 Turnstile token
        
        Args:
            token: 前端传来的 cf-turnstile-response
            remote_ip: 用户 IP（可选）
            
        Returns:
            (success, message)
        """
        if not token:
            return False, '验证码不能为空'
        
        secret_key = Setting.get('turnstile_secret_key', '')
        if not secret_key:
            return False, 'Turnstile 未配置'
        
        try:
            data = {
                'secret': secret_key,
                'response': token
            }
            if remote_ip:
                data['remoteip'] = remote_ip
            
            response = requests.post(cls.VERIFY_URL, data=data, timeout=10)
            result = response.json()
            
            if result.get('success'):
                return True, '验证成功'
            else:
                error_codes = result.get('error-codes', [])
                if 'invalid-input-response' in error_codes:
                    return False, '验证码无效或已过期'
                elif 'timeout-or-duplicate' in error_codes:
                    return False, '验证码已过期，请刷新重试'
                else:
                    return False, '验证失败'
                    
        except requests.Timeout:
            return False, '验证超时，请重试'
        except Exception as e:
            return False, f'验证异常: {str(e)}'
    
    @classmethod
    def get_config(cls) -> dict:
        """获取前端配置"""
        return {
            'enabled': cls.is_enabled(),
            'site_key': cls.get_site_key() if cls.is_enabled() else ''
        }
