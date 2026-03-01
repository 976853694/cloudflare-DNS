from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/login')
def login_page():
    return render_template('login.html')


@main_bp.route('/register')
def register_page():
    from app.models import Setting
    oauth_providers = {
        'github_enabled': Setting.get('github_oauth_enabled', '0') == '1',
        'google_enabled': Setting.get('google_oauth_enabled', '0') == '1',
        'nodeloc_enabled': Setting.get('nodeloc_oauth_enabled', '0') == '1'
    }
    return render_template('register.html', oauth_providers=oauth_providers)


@main_bp.route('/magic-link')
def magic_link_verify_page():
    """邮箱链接登录验证页面"""
    return render_template('magic_link_verify.html')


@main_bp.route('/dashboard')
def dashboard_page():
    from flask import redirect
    return redirect('/user')


@main_bp.route('/user')
def user_index():
    return render_template('user/index.html')


@main_bp.route('/user/profile')
def user_profile():
    return render_template('user/profile.html')


@main_bp.route('/user/domains')
def user_domains():
    return render_template('user/domains.html')


@main_bp.route('/user/domains/new')
def user_domain_new():
    return render_template('user/domain_new.html')


@main_bp.route('/user/domains/<int:subdomain_id>')
def user_domain_detail(subdomain_id):
    return render_template('user/domain_detail.html')


@main_bp.route('/admin')
@main_bp.route('/admin/')
@main_bp.route('/admin/index')
@main_bp.route('/admin/dashboard')
def admin_page():
    return render_template('admin/index.html')


@main_bp.route('/admin/channels')
def admin_channels():
    return render_template('admin/channels.html')


@main_bp.route('/admin/domains')
def admin_domains():
    return render_template('admin/domains.html')


@main_bp.route('/admin/users')
def admin_users():
    return render_template('admin/users.html')


@main_bp.route('/admin/invites')
def admin_invites():
    return render_template('admin/invites.html')


@main_bp.route('/admin/points')
def admin_points():
    return render_template('admin/points.html')


@main_bp.route('/admin/settings')
def admin_settings():
    return render_template('admin/settings.html')


@main_bp.route('/admin/domain-settings')
def admin_domain_settings():
    return render_template('admin/domain_settings.html')


@main_bp.route('/admin/points-settings')
def admin_points_settings():
    return render_template('admin/points_settings.html')


@main_bp.route('/admin/security-settings')
def admin_security_settings():
    return render_template('admin/security_settings.html')


@main_bp.route('/admin/logs')
def admin_logs():
    return render_template('admin/logs.html')


@main_bp.route('/admin/dns-records')
def admin_dns_records():
    return render_template('admin/dns_records.html')


@main_bp.route('/admin/plans')
def admin_plans():
    return render_template('admin/plans.html')


@main_bp.route('/admin/free-plan-applications')
def admin_free_plan_applications():
    return render_template('admin/free_plan_applications.html')


@main_bp.route('/admin/redeem-codes')
def admin_redeem_codes():
    return render_template('admin/redeem_codes.html')


@main_bp.route('/user/redeem')
def user_redeem():
    return render_template('user/redeem.html')


@main_bp.route('/user/orders')
def user_orders():
    return render_template('user/orders.html')


@main_bp.route('/admin/orders')
def admin_orders():
    return render_template('admin/orders.html')


@main_bp.route('/admin/announcements')
def admin_announcements():
    return render_template('admin/announcements.html')


@main_bp.route('/admin/subdomains')
def admin_subdomains():
    return render_template('admin/subdomains.html')


@main_bp.route('/admin/ip-blacklist')
def admin_ip_blacklist():
    return render_template('admin/ip_blacklist.html')


@main_bp.route('/admin/coupons')
def admin_coupons():
    return render_template('admin/coupons.html')


@main_bp.route('/admin/app-versions')
def admin_app_versions():
    return render_template('admin/app_versions.html')


@main_bp.route('/admin/email-templates')
def admin_email_templates():
    return render_template('admin/email_templates.html')


@main_bp.route('/admin/email-campaigns')
def admin_email_campaigns():
    return render_template('admin/email_campaigns.html')


@main_bp.route('/admin/user-activity')
def admin_user_activity():
    return render_template('admin/user_activity.html')


@main_bp.route('/admin/oauth-settings')
def admin_oauth_settings():
    return render_template('admin/oauth_settings.html')


@main_bp.route('/admin/telegram')
def admin_telegram():
    return render_template('admin/telegram.html')


@main_bp.route('/admin/idle-domains')
def admin_idle_domains():
    return render_template('admin/idle_domains.html')


@main_bp.route('/user/security')
def user_security():
    return render_template('user/security.html')


@main_bp.route('/user/api')
def user_api():
    return render_template('user/api.html')


@main_bp.route('/user/announcements')
def user_announcements():
    return render_template('user/announcements.html')


@main_bp.route('/free-plans')
def free_plans():
    # 免费套餐已合并到购买域名页面
    return redirect('/user/domains/new')


@main_bp.route('/my-applications')
def my_applications():
    return render_template('my_applications.html')


@main_bp.route('/verify')
def verify_page():
    return render_template('verify.html')


@main_bp.route('/forgot-password')
def forgot_password_page():
    return render_template('forgot_password.html')


@main_bp.route('/reset-password')
def reset_password_page():
    return render_template('reset_password.html')


@main_bp.route('/set-password')
def set_password_page():
    return render_template('set_password.html')


@main_bp.route('/privacy')
def privacy_page():
    return render_template('privacy.html')


@main_bp.route('/abuse')
def abuse_page():
    return render_template('abuse.html')


# ==================== 托管商页面 ====================
@main_bp.route('/host')
def host_index():
    return render_template('host/index.html')


@main_bp.route('/host/apply')
def host_apply():
    return render_template('host/apply.html')


@main_bp.route('/host/channels')
def host_channels():
    return render_template('host/channels.html')


@main_bp.route('/host/domains')
def host_domains():
    return render_template('host/domains.html')


@main_bp.route('/host/plans')
def host_plans():
    return render_template('host/plans.html')


@main_bp.route('/host/transactions')
def host_transactions():
    return render_template('host/transactions.html')


@main_bp.route('/host/earnings')
def host_earnings():
    return render_template('host/earnings.html')


@main_bp.route('/host/free-plan-applications')
def host_free_plan_applications():
    return render_template('host_free_plan_applications.html')


@main_bp.route('/host/free-plan-applications/<int:application_id>')
def host_free_plan_application_detail(application_id):
    return render_template('host_free_plan_application_detail.html')


# ==================== 管理员托管管理页面 ====================
@main_bp.route('/admin/host/applications')
def admin_host_applications():
    return render_template('admin/host/applications.html')


@main_bp.route('/admin/host/hosts')
def admin_host_hosts():
    return render_template('admin/host/hosts.html')


@main_bp.route('/admin/host/settings')
def admin_host_settings():
    return render_template('admin/host/settings.html')


@main_bp.route('/admin/host/withdrawals')
def admin_host_withdrawals():
    return render_template('admin/host/withdrawals.html')


# ==================== 虚拟主机管理页面 ====================
@main_bp.route('/admin/vhost/servers')
def admin_vhost_servers():
    return render_template('admin/vhost/servers.html')


@main_bp.route('/admin/vhost/plans')
def admin_vhost_plans():
    return render_template('admin/vhost/plans.html')


@main_bp.route('/admin/vhost/instances')
def admin_vhost_instances():
    return render_template('admin/vhost/instances.html')


@main_bp.route('/admin/vhost/orders')
def admin_vhost_orders():
    return render_template('admin/vhost/orders.html')


# ==================== 用户虚拟主机页面 ====================
@main_bp.route('/vhost')
def user_vhost():
    return render_template('user/vhost/index.html')


@main_bp.route('/vhost/purchase')
def user_vhost_purchase():
    return render_template('user/vhost/purchase.html')


@main_bp.route('/vhost/instances')
def user_vhost_instances():
    return render_template('user/vhost/instances.html')


@main_bp.route('/vhost/instances/<int:instance_id>')
def user_vhost_detail(instance_id):
    return render_template('user/vhost/detail.html')


@main_bp.route('/vhost/instances/<int:instance_id>/files')
def user_vhost_files(instance_id):
    return render_template('user/vhost/files.html')


# ==================== 定时任务管理页面 ====================
@main_bp.route('/admin/cron')
def admin_cron():
    return render_template('admin/cron.html')


# ==================== 数据库备份管理页面 ====================
@main_bp.route('/admin/backup')
def admin_backup():
    return render_template('admin/backup.html')


# ==================== WHOIS 查询页面 ====================
@main_bp.route('/whois')
def whois_page():
    return render_template('whois.html')


# ==================== 积分系统页面 ====================
@main_bp.route('/points')
def points_page():
    return render_template('points.html')


@main_bp.route('/invite')
def invite_page():
    return render_template('invite.html')


# ==================== 工单系统页面 ====================
@main_bp.route('/tickets')
def tickets_page():
    return render_template('tickets.html')


@main_bp.route('/tickets/<int:ticket_id>')
def ticket_detail_page(ticket_id):
    return render_template('ticket_detail.html')


# ==================== 管理员工单管理页面 ====================
@main_bp.route('/admin/tickets')
def admin_tickets():
    return render_template('admin/tickets.html')


@main_bp.route('/admin/tickets/<int:ticket_id>')
def admin_ticket_detail(ticket_id):
    return render_template('admin/ticket_detail.html')


# ==================== 域名转移页面 ====================
@main_bp.route('/user/domain/<int:subdomain_id>/transfer')
def user_domain_transfer(subdomain_id):
    return render_template('user/domain_transfer.html')


@main_bp.route('/user/transfers')
def user_transfers():
    return render_template('user/transfers.html')


@main_bp.route('/admin/transfers')
def admin_transfers():
    return render_template('admin/transfers.html')


# ==================== 侧边栏菜单管理页面 ====================
@main_bp.route('/admin/sidebar')
def admin_sidebar():
    return render_template('admin/sidebar.html')


# ==================== 插件管理页面 ====================
@main_bp.route('/admin/plugins')
def admin_plugins():
    return render_template('admin/plugins.html')
