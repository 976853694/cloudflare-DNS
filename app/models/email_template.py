"""
邮件模板模型
支持自定义邮件模板内容
"""
from datetime import datetime
from app import db
from app.utils.timezone import now as beijing_now


class EmailTemplate(db.Model):
    """邮件模板模型"""
    __tablename__ = 'email_templates'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(50), unique=True, nullable=False, comment='模板代码')
    name = db.Column(db.String(100), nullable=False, comment='模板名称')
    subject = db.Column(db.String(200), nullable=False, comment='邮件主题')
    content = db.Column(db.Text, nullable=False, comment='邮件内容(HTML)')
    variables = db.Column(db.Text, nullable=True, comment='可用变量说明(JSON)')
    status = db.Column(db.SmallInteger, default=1, nullable=False, comment='状态 1=启用 0=禁用')
    created_at = db.Column(db.DateTime, default=beijing_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=beijing_now, onupdate=beijing_now, nullable=False)
    
    # 默认模板定义
    DEFAULT_TEMPLATES = {
        # ========== 验证类邮件 ==========
        'register': {
            'name': '注册验证',
            'subject': '【{{site_name}}】欢迎注册',
            'content': '''<h2>欢迎注册</h2>
<p>请点击下方按钮完成邮箱验证并设置密码：</p>
<p style="margin:20px 0;"><a href="{{verify_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">验证邮箱</a></p>
<p style="color:#999;font-size:12px;">此链接30分钟内有效，请尽快完成验证。</p>
<p style="color:#999;font-size:12px;">如非本人操作，请忽略此邮件。</p>''',
            'variables': '{"site_name": "站点名称", "verify_url": "验证链接", "token": "验证令牌"}',
            'category': 'verification'
        },
        'reset_password': {
            'name': '重置密码',
            'subject': '【{{site_name}}】重置密码',
            'content': '''<h2>重置密码</h2>
<p>您正在重置密码，请点击下方按钮设置新密码：</p>
<p style="margin:20px 0;"><a href="{{verify_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">重置密码</a></p>
<p style="color:#999;font-size:12px;">此链接30分钟内有效，请尽快完成操作。</p>
<p style="color:#999;font-size:12px;">如非本人操作，请忽略此邮件。</p>''',
            'variables': '{"site_name": "站点名称", "verify_url": "验证链接", "token": "验证令牌"}',
            'category': 'verification'
        },
        'change_email': {
            'name': '邮箱变更',
            'subject': '【{{site_name}}】邮箱变更确认',
            'content': '''<h2>邮箱变更</h2>
<p>您正在变更邮箱地址，请点击下方按钮确认：</p>
<p style="margin:20px 0;"><a href="{{verify_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">确认变更</a></p>
<p style="color:#999;font-size:12px;">此链接30分钟内有效，请尽快完成操作。</p>
<p style="color:#999;font-size:12px;">如非本人操作，请忽略此邮件。</p>''',
            'variables': '{"site_name": "站点名称", "verify_url": "验证链接", "token": "验证令牌"}',
            'category': 'verification'
        },
        'domain_expiry': {
            'name': '域名到期提醒',
            'subject': '【{{site_name}}】域名即将到期提醒',
            'content': '''<h2>域名到期提醒</h2>
<p>您的域名 <strong>{{domain_name}}</strong> 将于 <strong>{{days_remaining}}天后</strong> 到期。</p>
<p>到期时间: {{expires_at}}</p>
<p>请及时续费以避免服务中断。</p>
<p style="margin:20px 0;"><a href="{{renew_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">立即续费</a></p>''',
            'variables': '{"site_name": "站点名称", "domain_name": "域名", "days_remaining": "剩余天数", "expires_at": "到期时间", "renew_url": "续费链接"}',
            'category': 'domain'
        },
        'domain_deleted': {
            'name': '域名删除通知',
            'subject': '【{{site_name}}】域名已删除通知',
            'content': '''<h2 style="color:#e74c3c;">域名删除通知</h2>
<p>您的域名 <strong>{{domain_name}}</strong> 因到期超过3天未续费，已被系统自动删除。</p>
<p>到期时间: {{expires_at}}</p>
<p>删除时间: {{deleted_at}}</p>
<p style="color:#666;margin-top:20px;">如需继续使用，请重新申请域名。</p>
<p style="margin:20px 0;"><a href="{{new_domain_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">申请新域名</a></p>''',
            'variables': '{"site_name": "站点名称", "domain_name": "域名", "expires_at": "到期时间", "deleted_at": "删除时间", "new_domain_url": "申请新域名链接"}',
            'category': 'domain'
        },
        'auto_renew_success': {
            'name': '自动续费成功',
            'subject': '【{{site_name}}】域名自动续费成功',
            'content': '''<h2 style="color:#27ae60;">自动续费成功</h2>
<p>您的域名 <strong>{{domain_name}}</strong> 已自动续费成功。</p>
<p>续费套餐: {{plan_name}}</p>
<p>扣款金额: ¥{{price}}</p>
<p>新到期时间: {{new_expires_at}}</p>
<p>账户余额: {{balance}}</p>
<p style="margin:20px 0;"><a href="{{domain_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">查看域名</a></p>''',
            'variables': '{"site_name": "站点名称", "domain_name": "域名", "plan_name": "套餐名称", "price": "扣款金额", "new_expires_at": "新到期时间", "balance": "账户余额", "domain_url": "域名详情链接"}',
            'category': 'domain'
        },
        'auto_renew_failed': {
            'name': '自动续费失败',
            'subject': '【{{site_name}}】域名自动续费失败',
            'content': '''<h2 style="color:#e74c3c;">自动续费失败</h2>
<p>您的域名 <strong>{{domain_name}}</strong> 自动续费失败。</p>
<p>失败原因: {{reason}}</p>
<p>到期时间: {{expires_at}}</p>
<p>请及时充值并手动续费，以避免域名被停用。</p>
<p style="margin:20px 0;"><a href="{{renew_url}}" style="display:inline-block;padding:12px 40px;background:#e74c3c;color:#fff;text-decoration:none;border-radius:6px;">立即续费</a></p>''',
            'variables': '{"site_name": "站点名称", "domain_name": "域名", "reason": "失败原因", "expires_at": "到期时间", "renew_url": "续费链接"}',
            'category': 'domain'
        },
        'change_email_verify': {
            'name': '修改邮箱验证',
            'subject': '【{{site_name}}】修改邮箱',
            'content': '''<h2>修改邮箱</h2>
<p>您正在申请修改邮箱地址，请点击下方按钮验证身份后输入新邮箱：</p>
<p style="margin:20px 0;"><a href="{{verify_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">验证身份</a></p>
<p style="color:#999;font-size:12px;">此链接30分钟内有效，请尽快完成操作。</p>
<p style="color:#999;font-size:12px;">如非本人操作，请忽略此邮件。</p>''',
            'variables': '{"site_name": "站点名称", "verify_url": "验证链接", "token": "验证令牌"}',
            'category': 'verification'
        },
        'change_password': {
            'name': '修改密码验证',
            'subject': '【{{site_name}}】修改密码',
            'content': '''<h2>修改密码</h2>
<p>您正在修改密码，请点击下方按钮验证身份并设置新密码：</p>
<p style="margin:20px 0;"><a href="{{verify_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">修改密码</a></p>
<p style="color:#999;font-size:12px;">此链接30分钟内有效，请尽快完成操作。</p>
<p style="color:#999;font-size:12px;">如非本人操作，请忽略此邮件。</p>''',
            'variables': '{"site_name": "站点名称", "verify_url": "验证链接", "token": "验证令牌"}',
            'category': 'verification'
        },
        'reactivate': {
            'name': '重新激活账户',
            'subject': '【{{site_name}}】重新激活账户',
            'content': '''<h2>重新激活账户</h2>
<p>您的账户处于沉睡状态，需要重新验证邮箱才能登录。请点击下方按钮激活账户：</p>
<p style="margin:20px 0;"><a href="{{verify_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">激活账户</a></p>
<p style="color:#999;font-size:12px;">此链接30分钟内有效，请尽快完成操作。</p>
<p style="color:#999;font-size:12px;">如非本人操作，请忽略此邮件。</p>''',
            'variables': '{"site_name": "站点名称", "verify_url": "验证链接", "token": "验证令牌"}',
            'category': 'verification'
        },
        'magic_link': {
            'name': '邮箱链接登录',
            'subject': '【{{site_name}}】您的登录链接',
            'content': '''<h2>邮箱链接登录</h2>
<p>您正在使用邮箱链接登录，请点击下方按钮完成登录：</p>
<p style="margin:20px 0;"><a href="{{login_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">点击登录</a></p>
<p style="color:#999;font-size:12px;">此链接 {{expire_minutes}} 分钟内有效，请尽快完成登录。</p>
<p style="color:#999;font-size:12px;">如果按钮无法点击，请复制以下链接到浏览器打开：</p>
<p style="color:#666;font-size:12px;word-break:break-all;">{{login_url}}</p>
<p style="color:#999;font-size:12px;margin-top:20px;">如非本人操作，请忽略此邮件。</p>''',
            'variables': '{"site_name": "站点名称", "login_url": "登录链接", "expire_minutes": "有效期(分钟)"}',
            'category': 'verification'
        },
        
        # ========== 域名类邮件 ==========
        'dns_cleanup': {
            'name': 'DNS记录清理通知',
            'subject': '【{{site_name}}】DNS记录已清理通知',
            'content': '''<h2>DNS记录清理通知</h2>
<p>您的域名 <strong>{{domain_name}}</strong> 因到期超过3天未续费，其DNS记录已被系统清理。</p>
<p>域名仍然保留，如需继续使用，请续费后重新添加DNS记录。</p>
<p style="margin:20px 0;"><a href="{{renew_url}}" style="display:inline-block;padding:12px 40px;background:#1a1a1a;color:#fff;text-decoration:none;border-radius:6px;">前往续费</a></p>''',
            'variables': '{"site_name": "站点名称", "domain_name": "域名", "renew_url": "续费链接"}',
            'category': 'domain'
        },
        'idle_domain_reminder': {
            'name': '空置域名提醒',
            'subject': '【{{site_name}}】域名 {{domain_name}} 尚未添加DNS记录',
            'content': '''<h2>域名空置提醒</h2>
<p>尊敬的 <strong>{{username}}</strong>，</p>
<p>您注册的域名 <strong>{{domain_name}}</strong> 已经 <strong>{{days}} 天</strong>未添加任何DNS解析记录。</p>
<p>为了合理利用资源，系统将在 <strong>{{delete_days}} 天</strong>后自动删除该域名。</p>
<p>如果您需要继续使用该域名，请尽快添加DNS记录。</p>
<p style="margin:20px 0;"><a href="{{site_url}}/user/domains" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;">立即添加记录</a></p>
<p style="color:#666;font-size:12px;">如果您已转移NS记录到其他服务商，请忽略此邮件。</p>
<p style="color:#999;font-size:12px;">此邮件由系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "用户名", "domain_name": "域名", "days": "空置天数", "delete_days": "删除天数", "site_url": "站点URL"}',
            'category': 'domain'
        },
        'idle_domain_deleted': {
            'name': '空置域名删除通知',
            'subject': '【{{site_name}}】域名 {{domain_name}} 已被删除',
            'content': '''<h2>域名删除通知</h2>
<p>尊敬的 <strong>{{username}}</strong>，</p>
<p>您注册的域名 <strong>{{domain_name}}</strong> 因长期未添加DNS记录（超过 <strong>{{days}} 天</strong>），已被系统自动删除。</p>
<p>如果您仍需使用该域名，可以重新注册。</p>
<p style="margin:20px 0;"><a href="{{site_url}}/user/domains" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;">重新注册域名</a></p>
<p style="color:#999;font-size:12px;">此邮件由系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "用户名", "domain_name": "域名", "days": "空置天数", "site_url": "站点URL"}',
            'category': 'domain'
        },
        
        # ========== 工单类邮件 ==========
        'ticket_new': {
            'name': '新工单通知',
            'subject': '【{{site_name}}】新工单 - {{ticket_no}}',
            'content': '''<h2>📩 新工单通知</h2>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">工单号：</span>
<span style="color:#333;font-weight:bold;">{{ticket_no}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">发起人：</span>
<span style="color:#333;">{{from_user}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">标题：</span>
<span style="color:#333;font-weight:bold;">{{subject}}</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">内容：</span>
<p style="color:#333;margin:10px 0 0 0;white-space:pre-wrap;">{{content}}</p>
</td></tr>
</table>
<p style="margin:20px 0;text-align:center;"><a href="{{ticket_url}}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">查看工单</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "ticket_no": "工单号", "from_user": "发起人", "subject": "工单标题", "content": "工单内容", "ticket_url": "工单链接"}',
            'category': 'ticket'
        },
        'ticket_reply': {
            'name': '工单回复通知',
            'subject': '【{{site_name}}】工单回复 - {{ticket_no}}',
            'content': '''<h2>💬 工单回复通知</h2>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">工单号：</span>
<span style="color:#333;font-weight:bold;">{{ticket_no}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">工单标题：</span>
<span style="color:#333;">{{subject}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">回复人：</span>
<span style="color:#333;">{{reply_user}}</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">回复内容：</span>
<p style="color:#333;margin:10px 0 0 0;white-space:pre-wrap;">{{reply_content}}</p>
</td></tr>
</table>
<p style="margin:20px 0;text-align:center;"><a href="{{ticket_url}}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">查看工单</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "ticket_no": "工单号", "subject": "工单标题", "reply_user": "回复人", "reply_content": "回复内容", "ticket_url": "工单链接"}',
            'category': 'ticket'
        },
        'ticket_closed': {
            'name': '工单关闭通知',
            'subject': '【{{site_name}}】工单已关闭 - {{ticket_no}}',
            'content': '''<h2>✅ 工单已关闭</h2>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">工单号：</span>
<span style="color:#333;font-weight:bold;">{{ticket_no}}</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">工单标题：</span>
<span style="color:#333;">{{subject}}</span>
</td></tr>
</table>
<p style="color:#666;">您的工单已处理完毕并关闭。如有其他问题，欢迎创建新工单。</p>
<p style="margin:20px 0;text-align:center;"><a href="{{ticket_url}}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">查看工单</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "ticket_no": "工单号", "subject": "工单标题", "ticket_url": "工单链接"}',
            'category': 'ticket'
        },
        
        # ========== 套餐类邮件 ==========
        'free_plan_submitted': {
            'name': '免费套餐申请提交',
            'subject': '【{{site_name}}】新的免费套餐申请 - {{username}}',
            'content': '''<h2>🎁 新的免费套餐申请</h2>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">申请用户：</span>
<span style="color:#333;font-weight:bold;">{{username}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">申请套餐：</span>
<span style="color:#333;">{{plan_name}}</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">申请理由：</span>
<p style="color:#333;margin:10px 0 0 0;white-space:pre-wrap;">{{apply_reason}}</p>
</td></tr>
</table>
<p style="margin:20px 0;text-align:center;"><a href="{{admin_url}}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">前往审核</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "申请用户", "plan_name": "套餐名称", "apply_reason": "申请理由", "admin_url": "审核链接"}',
            'category': 'plan'
        },
        'free_plan_approved': {
            'name': '免费套餐申请通过',
            'subject': '【{{site_name}}】免费套餐申请已通过',
            'content': '''<h2 style="color:#10B981;">🎉 申请已通过</h2>
<p>尊敬的 <strong>{{username}}</strong>，</p>
<p>恭喜您！您申请的免费套餐已通过审核。</p>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">套餐名称：</span>
<span style="color:#333;font-weight:bold;">{{plan_name}}</span>
</td></tr>
{{admin_note_html}}
{{provision_error_html}}
</table>
<p>您现在可以使用该套餐注册域名了。</p>
<p style="margin:20px 0;text-align:center;"><a href="{{domain_url}}" style="display:inline-block;padding:12px 40px;background:#10B981;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">立即注册域名</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "用户名", "plan_name": "套餐名称", "domain_url": "域名注册链接", "admin_note_html": "管理员备注HTML(可选)", "provision_error_html": "开通失败提示HTML(可选)"}',
            'category': 'plan'
        },
        'free_plan_auto_provisioned': {
            'name': '免费套餐自动开通成功',
            'subject': '【{{site_name}}】免费域名已开通',
            'content': '''<h2 style="color:#10B981;">🎉 域名已自动开通</h2>
<p>尊敬的 <strong>{{username}}</strong>，</p>
<p>恭喜您！您的免费套餐申请已通过审核，域名已自动为您开通。</p>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">域名：</span>
<span style="color:#333;font-weight:bold;font-size:16px;">{{subdomain_name}}</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">套餐：</span>
<span style="color:#333;font-weight:bold;">{{plan_name}}</span>
</td></tr>
</table>
<div style="background:#DBEAFE;border-left:4px solid #3B82F6;padding:15px;margin:20px 0;border-radius:4px;">
<p style="margin:0;color:#1E40AF;font-size:13px;">💡 <strong>下一步：</strong>您可以立即为域名添加DNS解析记录，开始使用您的域名。</p>
</div>
<p style="margin:20px 0;text-align:center;">
<a href="{{dns_url}}" style="display:inline-block;padding:12px 40px;background:#10B981;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;margin-right:10px;">管理DNS记录</a>
<a href="{{domain_url}}" style="display:inline-block;padding:12px 40px;background:#6B7280;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">查看我的域名</a>
</p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "用户名", "subdomain_name": "子域名全名", "plan_name": "套餐名称", "dns_url": "DNS管理链接", "domain_url": "域名列表链接"}',
            'category': 'plan'
        },
        'free_plan_rejected': {
            'name': '免费套餐申请拒绝',
            'subject': '【{{site_name}}】免费套餐申请未通过',
            'content': '''<h2 style="color:#EF4444;">❌ 申请未通过</h2>
<p>尊敬的 <strong>{{username}}</strong>，</p>
<p>很抱歉，您申请的免费套餐未能通过审核。</p>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">套餐名称：</span>
<span style="color:#333;font-weight:bold;">{{plan_name}}</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">拒绝原因：</span>
<p style="color:#333;margin:10px 0 0 0;white-space:pre-wrap;">{{rejection_reason}}</p>
</td></tr>
</table>
<p>您可以在7天后重新申请，或选择购买付费套餐。</p>
<p style="margin:20px 0;text-align:center;"><a href="{{applications_url}}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">查看申请记录</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "用户名", "plan_name": "套餐名称", "rejection_reason": "拒绝原因", "applications_url": "申请记录链接"}',
            'category': 'plan'
        },
        
        # ========== 托管商类邮件 ==========
        'host_application_submitted': {
            'name': '托管商申请提交通知',
            'subject': '【{{site_name}}】新的托管商申请 - {{username}}',
            'content': '''<h2>🏢 新的托管商申请</h2>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">申请用户：</span>
<span style="color:#333;font-weight:bold;">{{username}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">联系邮箱：</span>
<span style="color:#333;">{{email}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">公司名称：</span>
<span style="color:#333;">{{company_name}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">联系方式：</span>
<span style="color:#333;">{{contact_info}}</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">申请理由：</span>
<p style="color:#333;margin:10px 0 0 0;white-space:pre-wrap;">{{reason}}</p>
</td></tr>
</table>
<p style="margin:20px 0;text-align:center;"><a href="{{admin_url}}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">前往审核</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "申请用户", "email": "联系邮箱", "company_name": "公司名称", "contact_info": "联系方式", "reason": "申请理由", "admin_url": "审核链接"}',
            'category': 'host'
        },
        'host_application_approved': {
            'name': '托管商申请审核通过',
            'subject': '【{{site_name}}】托管商申请已通过',
            'content': '''<h2 style="color:#10B981;">🎉 申请已通过</h2>
<p>尊敬的 <strong>{{username}}</strong>，</p>
<p>恭喜您！您的托管商申请已通过审核。</p>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">公司名称：</span>
<span style="color:#333;font-weight:bold;">{{company_name}}</span>
</td></tr>
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">佣金比例：</span>
<span style="color:#333;font-weight:bold;">{{commission_rate}}%</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">管理员备注：</span>
<p style="color:#333;margin:10px 0 0 0;white-space:pre-wrap;">{{admin_note}}</p>
</td></tr>
</table>
<p>您现在可以开始推广域名服务并获得佣金了。</p>
<p style="margin:20px 0;text-align:center;"><a href="{{host_url}}" style="display:inline-block;padding:12px 40px;background:#10B981;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">进入托管商中心</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "用户名", "company_name": "公司名称", "commission_rate": "佣金比例", "admin_note": "管理员备注", "host_url": "托管商中心链接"}',
            'category': 'host'
        },
        'host_application_rejected': {
            'name': '托管商申请审核拒绝',
            'subject': '【{{site_name}}】托管商申请未通过',
            'content': '''<h2 style="color:#EF4444;">❌ 申请未通过</h2>
<p>尊敬的 <strong>{{username}}</strong>，</p>
<p>很抱歉，您的托管商申请未能通过审核。</p>
<table width="100%" style="background:#f8f9fa;border-radius:8px;padding:20px;border-collapse:collapse;margin:20px 0;">
<tr><td style="padding:10px 20px;border-bottom:1px solid #eee;">
<span style="color:#999;">公司名称：</span>
<span style="color:#333;font-weight:bold;">{{company_name}}</span>
</td></tr>
<tr><td style="padding:10px 20px;">
<span style="color:#999;">拒绝原因：</span>
<p style="color:#333;margin:10px 0 0 0;white-space:pre-wrap;">{{rejection_reason}}</p>
</td></tr>
</table>
<p>如有疑问，请联系管理员。</p>
<p style="margin:20px 0;text-align:center;"><a href="{{host_url}}" style="display:inline-block;padding:12px 40px;background:#4F46E5;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">查看申请记录</a></p>
<p style="color:#999;font-size:12px;">此邮件由 {{site_name}} 系统自动发送，请勿回复。</p>''',
            'variables': '{"site_name": "站点名称", "username": "用户名", "company_name": "公司名称", "rejection_reason": "拒绝原因", "host_url": "托管商中心链接"}',
            'category': 'host'
        }
    }
    
    @classmethod
    def get_template(cls, code):
        """获取模板，优先从数据库获取，否则返回默认模板"""
        template = cls.query.filter_by(code=code, status=1).first()
        if template:
            return template
        # 返回默认模板
        if code in cls.DEFAULT_TEMPLATES:
            default = cls.DEFAULT_TEMPLATES[code]
            return cls(
                code=code,
                name=default['name'],
                subject=default['subject'],
                content=default['content'],
                variables=default['variables']
            )
        return None
    
    @classmethod
    def render(cls, code, variables=None):
        """
        渲染模板
        
        Args:
            code: 模板代码
            variables: 变量字典
            
        Returns:
            tuple: (subject, html_content) 或 (None, None)
        """
        template = cls.get_template(code)
        if not template:
            return None, None
        
        variables = variables or {}
        
        # 使用 Jinja2 渲染模板
        try:
            from jinja2 import Template
            
            # 渲染主题
            subject_template = Template(template.subject)
            subject = subject_template.render(**variables)
            
            # 渲染内容
            content_template = Template(template.content)
            content = content_template.render(**variables)
            
            # 包装成完整的 HTML 邮件
            html = cls._wrap_html(content)
            return subject, html
        except Exception as e:
            # 如果 Jinja2 渲染失败，回退到简单替换
            subject = template.subject
            content = template.content
            
            for key, value in variables.items():
                placeholder = '{{' + key + '}}'
                subject = subject.replace(placeholder, str(value))
                content = content.replace(placeholder, str(value))
            
            html = cls._wrap_html(content)
            return subject, html
    
    @classmethod
    def _wrap_html(cls, content):
        """包装成完整的 HTML 邮件"""
        return f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
<tr><td style="padding:40px;color:#333;font-size:14px;line-height:1.8;">
{content}
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>'''
    
    @classmethod
    def init_defaults(cls):
        """初始化默认模板到数据库"""
        for code, info in cls.DEFAULT_TEMPLATES.items():
            if not cls.query.filter_by(code=code).first():
                template = cls(
                    code=code,
                    name=info['name'],
                    subject=info['subject'],
                    content=info['content'],
                    variables=info['variables']
                )
                db.session.add(template)
        db.session.commit()
    
    def to_dict(self):
        import json
        # 从 DEFAULT_TEMPLATES 获取分类信息
        category = None
        if self.code in self.DEFAULT_TEMPLATES:
            default = self.DEFAULT_TEMPLATES[self.code]
            category = default.get('category')
        
        # 安全解析 variables 字段
        variables = {}
        if self.variables:
            try:
                # 尝试作为 JSON 解析
                variables = json.loads(self.variables)
            except (json.JSONDecodeError, ValueError):
                # 如果不是 JSON，可能是旧格式的逗号分隔字符串
                # 将其转换为字典格式（键和值相同）
                try:
                    var_list = [v.strip() for v in self.variables.split(',') if v.strip()]
                    variables = {v: v for v in var_list}
                except:
                    # 如果解析失败，返回空字典
                    variables = {}
        
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'subject': self.subject,
            'content': self.content,
            'variables': variables,
            'status': self.status,
            'category': category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
