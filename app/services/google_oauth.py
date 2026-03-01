"""Google OAuth 服务"""
import requests


class GoogleOAuthService:
    """Google OAuth 认证服务"""
    
    AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
    TOKEN_URL = 'https://oauth2.googleapis.com/token'
    USER_API_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'
    
    @classmethod
    def _get_config(cls):
        """从数据库获取 Google OAuth 配置"""
        from app.models import Setting
        return {
            'enabled': Setting.get('google_oauth_enabled', '0') == '1',
            'client_id': Setting.get('google_client_id', ''),
            'client_secret': Setting.get('google_client_secret', '')
        }
    
    @classmethod
    def is_configured(cls):
        """检查 Google OAuth 是否已配置并启用"""
        config = cls._get_config()
        return config['enabled'] and bool(config['client_id'] and config['client_secret'])
    
    @classmethod
    def get_authorize_url(cls, redirect_uri, state=None):
        """获取 Google 授权 URL"""
        config = cls._get_config()
        client_id = config['client_id']
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'select_account',
        }
        if state:
            params['state'] = state
        
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        return f'{cls.AUTHORIZE_URL}?{query}'
    
    @classmethod
    def get_access_token(cls, code, redirect_uri):
        """用授权码换取 access_token"""
        config = cls._get_config()
        client_id = config['client_id']
        client_secret = config['client_secret']
        
        try:
            resp = requests.post(cls.TOKEN_URL, data={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            }, headers={
                'Accept': 'application/json'
            }, timeout=10)
            
            data = resp.json()
            if 'access_token' in data:
                return data['access_token'], None
            return None, data.get('error_description', '获取 token 失败')
        except Exception as e:
            return None, str(e)
    
    @classmethod
    def get_user_info(cls, access_token):
        """获取 Google 用户信息"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            resp = requests.get(cls.USER_API_URL, headers=headers, timeout=10)
            if resp.status_code != 200:
                return None, '获取用户信息失败'
            
            user_data = resp.json()
            google_id = str(user_data.get('id'))
            email = user_data.get('email')
            name = user_data.get('name')
            picture = user_data.get('picture')
            
            return {
                'google_id': google_id,
                'email': email,
                'name': name,
                'avatar_url': picture,
            }, None
        except Exception as e:
            return None, str(e)
