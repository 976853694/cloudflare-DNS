"""
阿里云短信服务（号码认证服务）
"""
import json
import random
import string
import hmac
import hashlib
import base64
import urllib.parse
import uuid
from datetime import datetime
import requests
from flask import current_app
from app.models import Setting


class SmsService:
    """阿里云号码认证短信服务"""
    
    # API 端点（号码认证服务）
    API_ENDPOINT = 'https://dypnsapi.aliyuncs.com'
    
    # 模板类型映射
    TEMPLATE_LOGIN = 'login'           # 登录/注册
    TEMPLATE_CHANGE_PHONE = 'change'   # 修改绑定手机号
    TEMPLATE_RESET_PWD = 'reset'       # 重置密码
    TEMPLATE_BIND_PHONE = 'bind'       # 绑定新手机号
    TEMPLATE_VERIFY_PHONE = 'verify'   # 验证绑定手机号
    
    @classmethod
    def is_enabled(cls):
        """检查短信服务是否启用"""
        return Setting.get('sms_enabled', '0') == '1'
    
    @classmethod
    def get_credentials(cls):
        """获取阿里云凭证"""
        access_key_id = Setting.get('aliyun_sms_access_key_id', '')
        access_key_secret = Setting.get('aliyun_sms_access_key_secret', '')
        return access_key_id, access_key_secret
    
    @classmethod
    def get_template_code(cls, template_type):
        """获取模板CODE"""
        template_map = {
            cls.TEMPLATE_LOGIN: current_app.config.get('ALIYUN_SMS_TPL_LOGIN', '100001'),
            cls.TEMPLATE_CHANGE_PHONE: current_app.config.get('ALIYUN_SMS_TPL_CHANGE_PHONE', '100002'),
            cls.TEMPLATE_RESET_PWD: current_app.config.get('ALIYUN_SMS_TPL_RESET_PWD', '100003'),
            cls.TEMPLATE_BIND_PHONE: current_app.config.get('ALIYUN_SMS_TPL_BIND_PHONE', '100004'),
            cls.TEMPLATE_VERIFY_PHONE: current_app.config.get('ALIYUN_SMS_TPL_VERIFY_PHONE', '100005'),
        }
        return template_map.get(template_type, template_map[cls.TEMPLATE_LOGIN])
    
    @classmethod
    def generate_code(cls, length=6):
        """生成随机验证码"""
        return ''.join(random.choices(string.digits, k=length))
    
    @classmethod
    def get_code_expire_minutes(cls):
        """获取验证码有效期（分钟）"""
        return current_app.config.get('ALIYUN_SMS_CODE_EXPIRE', 5)
    
    @classmethod
    def _percent_encode(cls, s):
        """URL编码（阿里云特殊要求）"""
        return urllib.parse.quote(str(s), safe='~')
    
    @classmethod
    def _sign(cls, params, access_key_secret):
        """生成签名"""
        # 按参数名排序
        sorted_params = sorted(params.items())
        # 构造待签名字符串
        query_string = '&'.join([
            f'{cls._percent_encode(k)}={cls._percent_encode(v)}'
            for k, v in sorted_params
        ])
        string_to_sign = f'GET&%2F&{cls._percent_encode(query_string)}'
        # HMAC-SHA1 签名
        key = (access_key_secret + '&').encode('utf-8')
        signature = hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    @classmethod
    def send_code(cls, phone, code, template_type=None):
        """
        发送验证码短信（号码认证服务）
        
        Args:
            phone: 手机号
            code: 验证码
            template_type: 模板类型（login/change/reset/bind/verify）
        
        Returns:
            (success: bool, message: str)
        """
        if not cls.is_enabled():
            return False, '短信服务未启用'
        
        access_key_id, access_key_secret = cls.get_credentials()
        if not access_key_id or not access_key_secret:
            return False, '短信服务未配置'
        
        # 获取配置
        sign_name = current_app.config.get('ALIYUN_SMS_SIGN_NAME', '速通互联验证码')
        template_code = cls.get_template_code(template_type or cls.TEMPLATE_LOGIN)
        expire_minutes = cls.get_code_expire_minutes()
        
        # 构造请求参数（号码认证服务 SendSmsVerifyCode）
        params = {
            'AccessKeyId': access_key_id,
            'Action': 'SendSmsVerifyCode',
            'Format': 'JSON',
            'PhoneNumber': phone,
            'RegionId': 'cn-hangzhou',
            'SignName': sign_name,
            'SignatureMethod': 'HMAC-SHA1',
            'SignatureNonce': str(uuid.uuid4()),
            'SignatureVersion': '1.0',
            'TemplateCode': template_code,
            'TemplateParam': json.dumps({'code': code, 'min': str(expire_minutes)}),
            'Timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'Version': '2017-05-25',
        }
        
        # 生成签名
        params['Signature'] = cls._sign(params, access_key_secret)
        
        try:
            # 发送请求
            response = requests.get(cls.API_ENDPOINT, params=params, timeout=10)
            result = response.json()
            
            if result.get('Code') == 'OK':
                current_app.logger.info(f'短信发送成功: {phone}')
                return True, '发送成功'
            else:
                error_msg = result.get('Message', '未知错误')
                current_app.logger.error(f'短信发送失败: {phone}, 错误: {error_msg}, 响应: {result}')
                return False, f'发送失败: {error_msg}'
                
        except requests.RequestException as e:
            current_app.logger.error(f'短信发送异常: {phone}, 错误: {str(e)}')
            return False, f'网络错误: {str(e)}'
        except Exception as e:
            current_app.logger.error(f'短信发送异常: {phone}, 错误: {str(e)}')
            return False, f'发送异常: {str(e)}'
    
    @classmethod
    def send_login_code(cls, phone, code):
        """发送登录/注册验证码"""
        return cls.send_code(phone, code, cls.TEMPLATE_LOGIN)
    
    @classmethod
    def send_change_phone_code(cls, phone, code):
        """发送修改手机号验证码"""
        return cls.send_code(phone, code, cls.TEMPLATE_CHANGE_PHONE)
    
    @classmethod
    def send_reset_pwd_code(cls, phone, code):
        """发送重置密码验证码"""
        return cls.send_code(phone, code, cls.TEMPLATE_RESET_PWD)
    
    @classmethod
    def send_bind_phone_code(cls, phone, code):
        """发送绑定新手机验证码"""
        return cls.send_code(phone, code, cls.TEMPLATE_BIND_PHONE)
    
    @classmethod
    def send_verify_phone_code(cls, phone, code):
        """发送验证绑定手机验证码"""
        return cls.send_code(phone, code, cls.TEMPLATE_VERIFY_PHONE)
