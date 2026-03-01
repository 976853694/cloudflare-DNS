"""NodeLoc OAuth 服务"""
import requests


class NodeLocOAuthService:
    """NodeLoc OAuth 认证服务"""
    
    BASE_URL = 'https://www.nodeloc.com'
    AUTHORIZE_URL = f'{BASE_URL}/oauth-provider/authorize'
    TOKEN_URL = f'{BASE_URL}/oauth-provider/token'
    USER_API_URL = f'{BASE_URL}/oauth-provider/userinfo'
    
    @classmethod
    def _get_config(cls):
        """从数据库获取 NodeLoc OAuth 配置"""
        from app.models import Setting
        return {
            'enabled': Setting.get('nodeloc_oauth_enabled', '0') == '1',
            'client_id': Setting.get('nodeloc_client_id', ''),
            'client_secret': Setting.get('nodeloc_client_secret', '')
        }
    
    @classmethod
    def is_configured(cls):
        """检查 NodeLoc OAuth 是否已配置并启用"""
        config = cls._get_config()
        return config['enabled'] and bool(config['client_id'] and config['client_secret'])
    
    @classmethod
    def get_authorize_url(cls, redirect_uri, state=None):
        """获取 NodeLoc 授权 URL"""
        config = cls._get_config()
        client_id = config['client_id']
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid profile email',
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
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }, timeout=10)
            
            data = resp.json()
            if 'access_token' in data:
                return data['access_token'], None
            return None, data.get('error_description', data.get('error', '获取 token 失败'))
        except Exception as e:
            return None, str(e)
    
    @classmethod
    def get_user_info(cls, access_token):
        """获取 NodeLoc 用户信息"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            resp = requests.get(cls.USER_API_URL, headers=headers, timeout=10)
            if resp.status_code != 200:
                return None, '获取用户信息失败'
            
            user_data = resp.json()
            nodeloc_id = str(user_data.get('id'))
            username = user_data.get('username')
            name = user_data.get('name') or username
            email = user_data.get('email')
            avatar_url = user_data.get('avatar_url')
            trust_level = user_data.get('trust_level', 0)
            
            return {
                'nodeloc_id': nodeloc_id,
                'username': username,
                'name': name,
                'email': email,
                'avatar_url': avatar_url,
                'trust_level': trust_level,
            }, None
        except Exception as e:
            return None, str(e)
