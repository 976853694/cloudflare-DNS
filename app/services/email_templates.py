"""
邮件模板服务
从数据库模板渲染邮件内容
"""
from app.models import Setting, EmailTemplate


class EmailTemplateService:
    """邮件模板服务"""
    
    @classmethod
    def get_site_name(cls):
        """获取站点名称"""
        return Setting.get('site_name', '六趣DNS')
    
    @classmethod
    def render_email(cls, code, variables=None):
        """
        统一的邮件渲染方法
        
        Args:
            code: 模板代码
            variables: 变量字典
            
        Returns:
            tuple: (subject, html_content) 或 (None, None)
        """
        # 自动添加 site_name 变量
        if variables is None:
            variables = {}
        if 'site_name' not in variables:
            variables['site_name'] = cls.get_site_name()
        
        # 使用 EmailTemplate 模型渲染
        return EmailTemplate.render(code, variables)
