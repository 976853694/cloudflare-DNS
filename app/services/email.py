"""
邮件发送服务 - 支持多账户轮询发送
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from typing import Optional, Tuple
from app.models import Setting


class EmailService:
    """邮件发送服务 - 支持 SMTP 和阿里云 DirectMail，支持多账户轮询"""
    
    # ==================== 多账户相关方法 ====================
    
    @staticmethod
    def use_legacy_config() -> bool:
        """检查是否应使用旧配置（无多账户时回退）"""
        try:
            from app.models.email_account import EmailAccount
            count = EmailAccount.query.count()
            return count == 0
        except Exception:
            return True
    
    @staticmethod
    def select_available_account():
        """
        选择可用账户（按优先级，跳过配额耗尽和禁用的）
        返回: EmailAccount 或 None
        """
        try:
            from app.models.email_account import EmailAccount
            accounts = EmailAccount.get_available_accounts()
            return accounts[0] if accounts else None
        except Exception:
            return None
    
    @staticmethod
    def send_via_account(account, to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """通过指定账户发送邮件"""
        from app.models.email_account import EmailAccount
        
        config = account.get_config()
        
        if account.type == EmailAccount.TYPE_SMTP:
            return EmailService._send_smtp(config, to_email, subject, html_content)
        elif account.type == EmailAccount.TYPE_ALIYUN:
            return EmailService._send_aliyun(config, to_email, subject, html_content)
        else:
            return False, f'不支持的账户类型: {account.type}'
    
    # ==================== 核心发送方法 ====================
    
    @staticmethod
    def send(to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """
        发送邮件 - 自动选择可用账户或回退到旧配置
        使用轮询机制均匀分配发送任务
        """
        # 检查是否使用旧配置
        if EmailService.use_legacy_config():
            return EmailService._send_legacy(to_email, subject, html_content)
        
        # 使用多账户发送（轮询机制）
        from app.models.email_account import EmailAccount
        
        # 获取发送最少的账户
        account = EmailAccount.get_next_account_for_send()
        
        if not account:
            # 没有可用账户，尝试回退到旧配置
            if EmailService.is_configured():
                return EmailService._send_legacy(to_email, subject, html_content)
            return False, '没有可用的邮箱账户'
        
        # 尝试发送
        success, msg = EmailService.send_via_account(account, to_email, subject, html_content)
        if success:
            # 发送成功，增加计数
            account.increment_sent()
            return True, msg
        
        # 发送失败，尝试其他账户
        accounts = EmailAccount.get_available_accounts()
        for other_account in accounts:
            if other_account.id == account.id:
                continue  # 跳过已尝试的账户
            
            success, msg = EmailService.send_via_account(other_account, to_email, subject, html_content)
            if success:
                other_account.increment_sent()
                return True, msg
        
        return False, f'所有账户发送失败: {msg}'
    
    @staticmethod
    def _send_legacy(to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """使用旧配置发送邮件"""
        provider = EmailService.get_email_provider()
        
        if provider == 'aliyun':
            return EmailService.send_via_aliyun(to_email, subject, html_content)
        else:
            return EmailService.send_via_smtp(to_email, subject, html_content)
    
    # ==================== 旧配置兼容方法 ====================
    
    @staticmethod
    def get_email_provider():
        """获取邮件发送方式（旧配置）"""
        return Setting.get('email_provider', 'smtp')
    
    @staticmethod
    def get_smtp_config():
        """获取SMTP配置（旧配置）"""
        return {
            'host': Setting.get('smtp_host', ''),
            'port': int(Setting.get('smtp_port', 465) or 465),
            'user': Setting.get('smtp_user', ''),
            'password': Setting.get('smtp_password', ''),
            'from_name': Setting.get('smtp_from_name', '六趣DNS'),
            'ssl': Setting.get('smtp_ssl', '1') == '1'
        }
    
    @staticmethod
    def get_aliyun_config():
        """获取阿里云邮件推送配置（旧配置）"""
        return {
            'access_key_id': Setting.get('aliyun_dm_access_key_id', ''),
            'access_key_secret': Setting.get('aliyun_dm_access_key_secret', ''),
            'account_name': Setting.get('aliyun_dm_account', ''),
            'from_name': Setting.get('aliyun_dm_from_name', '六趣DNS'),
            'region': Setting.get('aliyun_dm_region', 'cn-hangzhou')
        }
    
    @staticmethod
    def is_configured():
        """检查邮件服务是否已配置"""
        # 先检查多账户
        if not EmailService.use_legacy_config():
            return True
        
        # 检查旧配置
        provider = EmailService.get_email_provider()
        
        if provider == 'aliyun':
            config = EmailService.get_aliyun_config()
            return bool(config['access_key_id'] and config['access_key_secret'] and config['account_name'])
        else:
            config = EmailService.get_smtp_config()
            return bool(config['host'] and config['user'] and config['password'])
    
    # ==================== SMTP 发送实现 ====================
    
    @staticmethod
    def _send_smtp(config: dict, to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """通过 SMTP 发送邮件（内部方法）"""
        if not config.get('host') or not config.get('user'):
            return False, 'SMTP配置不完整'
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(subject, 'utf-8')
        from_name = config.get('from_name', '六趣DNS')
        msg['From'] = formataddr((Header(from_name, 'utf-8').encode(), config['user']))
        msg['To'] = formataddr(('', to_email))
        
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        try:
            port = int(config.get('port', 465))
            ssl = config.get('ssl', True)
            if isinstance(ssl, str):
                ssl = ssl == '1' or ssl.lower() == 'true'
            
            if ssl:
                server = smtplib.SMTP_SSL(config['host'], port, timeout=10)
            else:
                server = smtplib.SMTP(config['host'], port, timeout=10)
                server.starttls()
            
            server.login(config['user'], config['password'])
            server.sendmail(config['user'], [to_email], msg.as_string())
            server.quit()
            return True, '发送成功'
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def send_via_smtp(to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """通过 SMTP 发送邮件（使用旧配置）"""
        config = EmailService.get_smtp_config()
        return EmailService._send_smtp(config, to_email, subject, html_content)
    
    # ==================== 阿里云发送实现 ====================
    
    @staticmethod
    def _send_aliyun(config: dict, to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """通过阿里云 DirectMail API 发送邮件（内部方法）"""
        if not config.get('access_key_id') or not config.get('access_key_secret') or not config.get('account_name'):
            return False, '阿里云邮件服务配置不完整'
        
        try:
            from alibabacloud_dm20151123.client import Client as DmClient
            from alibabacloud_dm20151123 import models as dm_models
            from alibabacloud_tea_openapi import models as open_api_models
            
            region = config.get('region', 'cn-hangzhou')
            api_config = open_api_models.Config(
                access_key_id=config['access_key_id'],
                access_key_secret=config['access_key_secret']
            )
            api_config.endpoint = f'dm.{region}.aliyuncs.com'
            
            client = DmClient(api_config)
            
            from_name = config.get('from_name', '六趣DNS')
            request = dm_models.SingleSendMailRequest(
                account_name=config['account_name'],
                address_type=1,
                reply_to_address=False,
                to_address=to_email,
                subject=subject,
                html_body=html_content,
                from_alias=from_name
            )
            
            response = client.single_send_mail(request)
            
            if response.body and response.body.env_id:
                return True, f'发送成功 (EnvId: {response.body.env_id})'
            return True, '发送成功'
            
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            elif hasattr(e, 'data') and e.data:
                error_msg = e.data.get('Message', str(e))
            return False, f'阿里云邮件发送失败: {error_msg}'
    
    @staticmethod
    def send_via_aliyun(to_email: str, subject: str, html_content: str) -> Tuple[bool, str]:
        """通过阿里云 DirectMail API 发送邮件（使用旧配置）"""
        config = EmailService.get_aliyun_config()
        return EmailService._send_aliyun(config, to_email, subject, html_content)
    
    # ==================== 其他方法 ====================
    
    @staticmethod
    def send_verification(to_email: str, token: str, verification_type: str, site_url: str, invite_code: str = None) -> Tuple[bool, str]:
        """发送验证邮件"""
        from app.services.email_templates import EmailTemplateService
        
        # 构建验证链接
        verify_url = f"{site_url}/verify?token={token}&type={verification_type}"
        
        # 如果有邀请码，添加到 URL 参数中
        if invite_code:
            verify_url += f"&invite_code={invite_code}"
        
        # 使用统一的模板渲染方法
        subject, html = EmailTemplateService.render_email(verification_type, {
            'verify_url': verify_url,
            'token': token,
            'invite_code': invite_code
        })
        
        if not subject or not html:
            return False, f'邮件模板 {verification_type} 不存在'
        
        return EmailService.send(to_email, subject, html)
    
    @staticmethod
    def test_connection() -> Tuple[bool, str]:
        """测试邮件服务连接（旧配置）"""
        provider = EmailService.get_email_provider()
        
        if provider == 'aliyun':
            config = EmailService.get_aliyun_config()
            if not config['access_key_id'] or not config['access_key_secret'] or not config['account_name']:
                return False, '阿里云邮件服务未配置完整'
            
            try:
                from alibabacloud_dm20151123.client import Client as DmClient
                from alibabacloud_tea_openapi import models as open_api_models
                
                api_config = open_api_models.Config(
                    access_key_id=config['access_key_id'],
                    access_key_secret=config['access_key_secret']
                )
                api_config.endpoint = f'dm.{config["region"]}.aliyuncs.com'
                
                client = DmClient(api_config)
                return True, '阿里云邮件服务连接成功'
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'message'):
                    error_msg = e.message
                return False, f'阿里云邮件服务连接失败: {error_msg}'
        else:
            config = EmailService.get_smtp_config()
            if not config['host'] or not config['user'] or not config['password']:
                return False, 'SMTP配置不完整'
            
            try:
                if config['ssl']:
                    server = smtplib.SMTP_SSL(config['host'], config['port'], timeout=10)
                else:
                    server = smtplib.SMTP(config['host'], config['port'], timeout=10)
                    server.starttls()
                
                server.login(config['user'], config['password'])
                server.quit()
                return True, 'SMTP连接成功'
            except smtplib.SMTPAuthenticationError:
                return False, 'SMTP认证失败,请检查用户名和密码'
            except smtplib.SMTPConnectError:
                return False, 'SMTP连接失败,请检查服务器地址和端口'
            except Exception as e:
                return False, f'SMTP连接失败: {str(e)}'
    
    @staticmethod
    def test_account(account) -> Tuple[bool, str]:
        """测试指定邮箱账户连接"""
        from app.models.email_account import EmailAccount
        
        config = account.get_config()
        
        if account.type == EmailAccount.TYPE_SMTP:
            if not config.get('host') or not config.get('user') or not config.get('password'):
                return False, 'SMTP配置不完整'
            
            try:
                port = int(config.get('port', 465))
                ssl = config.get('ssl', True)
                if isinstance(ssl, str):
                    ssl = ssl == '1' or ssl.lower() == 'true'
                
                if ssl:
                    server = smtplib.SMTP_SSL(config['host'], port, timeout=10)
                else:
                    server = smtplib.SMTP(config['host'], port, timeout=10)
                    server.starttls()
                
                server.login(config['user'], config['password'])
                server.quit()
                return True, 'SMTP连接成功'
            except smtplib.SMTPAuthenticationError:
                return False, 'SMTP认证失败,请检查用户名和密码'
            except smtplib.SMTPConnectError:
                return False, 'SMTP连接失败,请检查服务器地址和端口'
            except Exception as e:
                return False, f'SMTP连接失败: {str(e)}'
        
        elif account.type == EmailAccount.TYPE_ALIYUN:
            if not config.get('access_key_id') or not config.get('access_key_secret') or not config.get('account_name'):
                return False, '阿里云邮件服务配置不完整'
            
            try:
                from alibabacloud_dm20151123.client import Client as DmClient
                from alibabacloud_tea_openapi import models as open_api_models
                
                region = config.get('region', 'cn-hangzhou')
                api_config = open_api_models.Config(
                    access_key_id=config['access_key_id'],
                    access_key_secret=config['access_key_secret']
                )
                api_config.endpoint = f'dm.{region}.aliyuncs.com'
                
                client = DmClient(api_config)
                return True, '阿里云邮件服务连接成功'
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'message'):
                    error_msg = e.message
                return False, f'阿里云邮件服务连接失败: {error_msg}'
        
        else:
            return False, f'不支持的账户类型: {account.type}'
    
    @staticmethod
    def send_test_email(to_email: str) -> Tuple[bool, str]:
        """发送测试邮件"""
        is_valid, msg = EmailService.validate_email_format(to_email)
        if not is_valid:
            return False, msg
        
        if not EmailService.is_configured():
            return False, '邮件服务未配置'
        
        subject = '六趣DNS - 邮件服务测试'
        html_content = '''
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #4F46E5;">邮件服务测试</h2>
            <p>这是一封测试邮件,用于验证邮件服务配置是否正确。</p>
            <p>如果您收到这封邮件,说明邮件服务配置成功!</p>
            <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 20px 0;">
            <p style="color: #6B7280; font-size: 14px;">此邮件由六趣DNS系统自动发送,请勿回复。</p>
        </div>
        '''
        
        success, message = EmailService.send(to_email, subject, html_content)
        if success:
            return True, f'测试邮件已发送到 {to_email}'
        else:
            return False, f'测试邮件发送失败: {message}'
    
    @staticmethod
    def validate_email_format(email: str) -> Tuple[bool, str]:
        """验证邮箱格式"""
        import re
        
        if not email:
            return False, '邮箱地址不能为空'
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            return False, '邮箱格式不正确'
        
        if len(email) > 254:
            return False, '邮箱地址过长'
        
        try:
            local, domain = email.rsplit('@', 1)
            if len(local) > 64:
                return False, '邮箱用户名部分过长'
            if len(domain) > 253:
                return False, '邮箱域名部分过长'
        except ValueError:
            return False, '邮箱格式不正确'
        
        return True, '邮箱格式正确'
