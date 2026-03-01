"""GitHub OAuth 服务"""
import requests


class GitHubOAuthService:
    """GitHub OAuth 认证服务"""
    
    AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
    TOKEN_URL = 'https://github.com/login/oauth/access_token'
    USER_API_URL = 'https://api.github.com/user'
    USER_EMAILS_URL = 'https://api.github.com/user/emails'
    
    @classmethod
    def _get_config(cls):
        """从数据库获取 GitHub OAuth 配置"""
        from app.models import Setting
        return {
            'enabled': Setting.get('github_oauth_enabled', '0') == '1',
            'client_id': Setting.get('github_client_id', ''),
            'client_secret': Setting.get('github_client_secret', '')
        }
    
    @classmethod
    def is_configured(cls):
        """检查 GitHub OAuth 是否已配置并启用"""
        config = cls._get_config()
        return config['enabled'] and bool(config['client_id'] and config['client_secret'])
    
    @classmethod
    def get_authorize_url(cls, redirect_uri, state=None):
        """获取 GitHub 授权 URL"""
        config = cls._get_config()
        client_id = config['client_id']
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': 'user:email',
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
            import logging
            logging.info(f'GitHub OAuth: redirect_uri={redirect_uri}')
            
            resp = requests.post(cls.TOKEN_URL, data={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'redirect_uri': redirect_uri,
            }, headers={
                'Accept': 'application/json'
            }, timeout=10)
            
            data = resp.json()
            logging.info(f'GitHub OAuth response: {data}')
            
            if 'access_token' in data:
                return data['access_token'], None
            return None, data.get('error_description', data.get('error', '获取 token 失败'))
        except Exception as e:
            import logging
            logging.error(f'GitHub OAuth error: {e}')
            return None, str(e)
    
    @classmethod
    def get_user_info(cls, access_token):
        """获取 GitHub 用户信息"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            # 获取用户基本信息
            resp = requests.get(cls.USER_API_URL, headers=headers, timeout=10)
            if resp.status_code != 200:
                return None, '获取用户信息失败'
            
            user_data = resp.json()
            github_id = str(user_data.get('id'))
            username = user_data.get('login')
            email = user_data.get('email')
            
            # 如果邮箱为空，尝试获取用户邮箱列表
            if not email:
                email_resp = requests.get(cls.USER_EMAILS_URL, headers=headers, timeout=10)
                if email_resp.status_code == 200:
                    emails = email_resp.json()
                    # 优先使用主邮箱
                    for e in emails:
                        if e.get('primary') and e.get('verified'):
                            email = e.get('email')
                            break
                    # 如果没有主邮箱，使用第一个已验证的邮箱
                    if not email:
                        for e in emails:
                            if e.get('verified'):
                                email = e.get('email')
                                break
            
            return {
                'github_id': github_id,
                'username': username,
                'email': email,
                'avatar_url': user_data.get('avatar_url'),
                'name': user_data.get('name'),
            }, None
        except Exception as e:
            return None, str(e)
