"""
管理员侧边栏菜单管理路由
"""
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from app import db
from app.models import User, OperationLog
from app.models.sidebar_menu import SidebarMenu
from app.routes.admin import admin_bp
from app.routes.admin.decorators import admin_required, demo_forbidden
from app.utils.ip_utils import get_real_ip


@admin_bp.route('/sidebar/menus', methods=['GET'])
@admin_required
def get_sidebar_menus():
    """获取所有菜单配置"""
    menu_type = request.args.get('type', 'admin')
    
    try:
        # 检查是否有数据，没有则初始化
        count = SidebarMenu.query.count()
        if count == 0:
            _init_sidebar_menus_data()
        
        menus = SidebarMenu.get_menus_by_type(menu_type)
        structured = SidebarMenu.get_structured_menus(menu_type, visible_only=False)
    except Exception as e:
        print(f"[WARN] Get sidebar menus failed: {e}")
        menus = []
        structured = []
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'menus': menus,
            'structured': structured
        }
    })


@admin_bp.route('/sidebar/menus/visible', methods=['GET'])
def get_visible_menus():
    """获取可见菜单（前端渲染用，无需登录）"""
    menu_type = request.args.get('type', 'admin')
    
    try:
        # 检查是否有数据，没有则初始化
        count = SidebarMenu.query.count()
        if count == 0:
            _init_sidebar_menus_data()
        
        structured = SidebarMenu.get_structured_menus(menu_type, visible_only=True)
    except Exception as e:
        # 数据库表不存在或其他错误，返回空数组
        print(f"[WARN] Get sidebar menus failed: {e}")
        structured = []
    
    return jsonify({
        'code': 200,
        'message': 'success',
        'data': {
            'menus': structured
        }
    })


def _init_sidebar_menus_data():
    """初始化侧边栏菜单数据"""
    from sqlalchemy import text
    
    # 清除所有旧数据重新初始化
    try:
        SidebarMenu.query.delete()
        db.session.commit()
        print("[OK] Cleared old menu data")
    except Exception as e:
        db.session.rollback()
        print(f"[WARN] Clear menu data failed: {e}")
    
    # 图标定义
    icons = {
        'home': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>',
        'domain': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path>',
        'users': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>',
        'finance': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
        'server': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"></path>',
        'building': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>',
        'content': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"></path>',
        'settings': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>',
        'folder': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>',
        'cart': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"></path>',
        'user': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>',
        'search': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>',
        'ticket': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z"></path>',
        'briefcase': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>',
        'list': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>',
        'plan': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path>',
        'dns': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>',
        'clock': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
        'transfer': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>',
        'activity': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>',
        'gift': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"></path>',
        'shield': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>',
        'ban': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path>',
        'code': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>',
        'mail': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>',
        'bell': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path>',
        'database': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path>',
        'chart': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>',
        'phone': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>',
        'lock': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>',
        'key': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>',
        'star': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>',
        'plus': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>',
        'download': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>',
        'menu': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>',
        'puzzle': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 4a2 2 0 114 0v1a1 1 0 001 1h3a1 1 0 011 1v3a1 1 0 01-1 1h-1a2 2 0 100 4h1a1 1 0 011 1v3a1 1 0 01-1 1h-3a1 1 0 01-1-1v-1a2 2 0 10-4 0v1a1 1 0 01-1 1H7a1 1 0 01-1-1v-3a1 1 0 00-1-1H4a2 2 0 110-4h1a1 1 0 001-1V7a1 1 0 011-1h3a1 1 0 001-1V4z"></path>',
    }
    
    # 管理后台菜单配置: (menu_type, menu_key, parent_key, name_zh, name_en, url, sort_order, icon_key)
    admin_menus = [
        ('admin', 'home', None, '首页', 'Home', '/admin', 1, 'home'),
        ('admin', 'domain_manage', None, '域名管理', 'Domain', None, 10, 'domain'),
        ('admin', 'user_manage', None, '用户管理', 'Users', None, 20, 'users'),
        ('admin', 'finance', None, '财务管理', 'Finance', None, 30, 'finance'),
        ('admin', 'vhost', None, '虚拟主机', 'Virtual Host', None, 40, 'server'),
        ('admin', 'host', None, '托管管理', 'Hosting', None, 50, 'building'),
        ('admin', 'content', None, '内容管理', 'Content', None, 60, 'content'),
        ('admin', 'system', None, '系统设置', 'System', None, 70, 'settings'),
        # 域名管理子菜单
        ('admin', 'channels', 'domain_manage', '渠道管理', 'Channels', '/admin/channels', 1, 'server'),
        ('admin', 'domains', 'domain_manage', '域名列表', 'Domains', '/admin/domains', 2, 'list'),
        ('admin', 'plans', 'domain_manage', '套餐管理', 'Plans', '/admin/plans', 3, 'plan'),
        ('admin', 'subdomains', 'domain_manage', '用户域名', 'User Domains', '/admin/subdomains', 4, 'domain'),
        ('admin', 'dns_records', 'domain_manage', 'DNS查询', 'DNS Query', '/admin/dns-records', 5, 'search'),
        ('admin', 'idle_domains', 'domain_manage', '闲置域名', 'Idle Domains', '/admin/idle-domains', 6, 'clock'),
        ('admin', 'transfers', 'domain_manage', '转移管理', 'Transfers', '/admin/transfers', 7, 'transfer'),
        # 用户管理子菜单
        ('admin', 'users', 'user_manage', '用户列表', 'User List', '/admin/users', 1, 'users'),
        ('admin', 'user_activity', 'user_manage', '用户活跃', 'User Activity', '/admin/user-activity', 2, 'activity'),
        ('admin', 'invites', 'user_manage', '邀请记录', 'Invites', '/admin/invites', 3, 'gift'),
        ('admin', 'points', 'user_manage', '积分记录', 'Points', '/admin/points', 4, 'star'),
        ('admin', 'ip_blacklist', 'user_manage', 'IP黑名单', 'IP Blacklist', '/admin/ip-blacklist', 5, 'ban'),
        # 财务管理子菜单
        ('admin', 'orders', 'finance', '订单记录', 'Orders', '/admin/orders', 1, 'cart'),
        ('admin', 'redeem_codes', 'finance', '兑换码', 'Redeem Codes', '/admin/redeem-codes', 2, 'code'),
        ('admin', 'coupons', 'finance', '优惠券', 'Coupons', '/admin/coupons', 3, 'ticket'),
        # 虚拟主机子菜单
        ('admin', 'vhost_servers', 'vhost', '宝塔管理', 'Servers', '/admin/vhost/servers', 1, 'server'),
        ('admin', 'vhost_plans', 'vhost', '套餐管理', 'Plans', '/admin/vhost/plans', 2, 'plan'),
        ('admin', 'vhost_instances', 'vhost', '主机管理', 'Instances', '/admin/vhost/instances', 3, 'database'),
        ('admin', 'vhost_orders', 'vhost', '订单管理', 'Orders', '/admin/vhost/orders', 4, 'cart'),
        # 托管管理子菜单
        ('admin', 'host_applications', 'host', '托管申请', 'Applications', '/admin/host/applications', 1, 'folder'),
        ('admin', 'host_hosts', 'host', '托管商列表', 'Hosts', '/admin/host/hosts', 2, 'building'),
        ('admin', 'host_withdrawals', 'host', '提现管理', 'Withdrawals', '/admin/host/withdrawals', 3, 'finance'),
        ('admin', 'host_settings', 'host', '托管设置', 'Settings', '/admin/host/settings', 4, 'settings'),
        # 内容管理子菜单
        ('admin', 'announcements', 'content', '公告管理', 'Announcements', '/admin/announcements', 1, 'bell'),
        ('admin', 'tickets', 'content', '工单管理', 'Tickets', '/admin/tickets', 2, 'ticket'),
        ('admin', 'email_campaigns', 'content', '群发邮件', 'Email Campaigns', '/admin/email-campaigns', 3, 'mail'),
        ('admin', 'app_versions', 'content', 'APP版本', 'App Versions', '/admin/app-versions', 4, 'download'),
        ('admin', 'email_templates', 'content', '邮件模板', 'Email Templates', '/admin/email-templates', 5, 'mail'),
        # 系统设置子菜单
        ('admin', 'settings', 'system', '站点设置', 'Site Settings', '/admin/settings', 1, 'settings'),
        ('admin', 'security_settings', 'system', '安全设置', 'Security', '/admin/security-settings', 2, 'shield'),
        ('admin', 'oauth_settings', 'system', '快捷登录', 'OAuth Login', '/admin/oauth-settings', 3, 'key'),
        ('admin', 'telegram', 'system', 'Telegram机器人', 'Telegram Bot', '/admin/telegram', 4, 'phone'),
        ('admin', 'cron', 'system', '定时任务', 'Cron Tasks', '/admin/cron', 5, 'clock'),
        ('admin', 'backup', 'system', '数据备份', 'Backup', '/admin/backup', 6, 'database'),
        ('admin', 'logs', 'system', '操作日志', 'Logs', '/admin/logs', 7, 'dns'),
        ('admin', 'sidebar_menus', 'system', '菜单管理', 'Menu Settings', '/admin/sidebar', 8, 'menu'),
        ('admin', 'plugins', 'system', '插件管理', 'Plugins', '/admin/plugins', 9, 'puzzle'),
        # 站点设置父菜单
        ('admin', 'settings_group', None, '站点设置', 'Site Settings', None, 90, 'briefcase'),
        # 站点设置子菜单
        ('admin', 'domain_settings', 'settings_group', '域名管理设置', 'Domain Settings', '/admin/domain-settings', 2, 'domain'),
        ('admin', 'points_settings', 'settings_group', '积分系统设置', 'Points Settings', '/admin/points-settings', 3, 'star'),
    ]
    
    user_menus = [
        # 一级菜单
        ('user', 'dashboard', None, '控制台', 'Dashboard', '/user', 1, 'home'),
        ('user', 'domain_manage', None, '域名管理', 'Domain', None, 10, 'domain'),
        ('user', 'vhost', None, '虚拟主机', 'Virtual Host', None, 20, 'server'),
        ('user', 'order_center', None, '订单中心', 'Orders', None, 30, 'cart'),
        ('user', 'account_settings', None, '账户设置', 'Account', None, 40, 'user'),
        ('user', 'whois', None, 'WHOIS查询', 'WHOIS', '/whois', 50, 'search'),
        ('user', 'tickets', None, '工单中心', 'Tickets', '/tickets', 60, 'ticket'),
        ('user', 'host', None, '托管商入口', 'Hosting', '/host', 70, 'briefcase'),
        # 域名管理子菜单
        ('user', 'my_domains', 'domain_manage', '我的域名', 'My Domains', '/user/domains', 1, 'list'),
        ('user', 'buy_domain', 'domain_manage', '购买域名', 'Buy Domain', '/user/domains/new', 2, 'plus'),
        ('user', 'my_applications', 'domain_manage', '我的申请', 'My Applications', '/my-applications', 3, 'folder'),
        ('user', 'transfers', 'domain_manage', '转移记录', 'Transfers', '/user/transfers', 4, 'transfer'),
        # 虚拟主机子菜单
        ('user', 'my_hosts', 'vhost', '我的主机', 'My Hosts', '/vhost/instances', 1, 'server'),
        ('user', 'buy_host', 'vhost', '购买主机', 'Buy Host', '/vhost/purchase', 2, 'plus'),
        # 订单中心子菜单
        ('user', 'order_history', 'order_center', '订单记录', 'Order History', '/user/orders', 1, 'cart'),
        ('user', 'redeem_code', 'order_center', '兑换码', 'Redeem Code', '/user/redeem', 2, 'code'),
        ('user', 'points_center', 'order_center', '积分中心', 'Points', '/points', 3, 'star'),
        # 账户设置子菜单
        ('user', 'profile', 'account_settings', '个人资料', 'Profile', '/user/profile', 1, 'user'),
        ('user', 'security', 'account_settings', '安全设置', 'Security', '/user/security', 2, 'lock'),
        ('user', 'api_manage', 'account_settings', 'API管理', 'API', '/user/api', 3, 'key'),
        ('user', 'announcements', 'account_settings', '系统公告', 'Announcements', '/user/announcements', 4, 'bell'),
        ('user', 'invite', 'account_settings', '邀请好友', 'Invite', '/invite', 5, 'gift'),
    ]
    
    all_menus = admin_menus + user_menus
    
    success_count = 0
    for menu in all_menus:
        try:
            icon_svg = icons.get(menu[7]) if len(menu) > 7 and menu[7] else None
            new_menu = SidebarMenu(
                menu_type=menu[0],
                menu_key=menu[1],
                parent_key=menu[2],
                name_zh=menu[3],
                name_en=menu[4],
                url=menu[5],
                sort_order=menu[6],
                icon=icon_svg,
                visible=1
            )
            db.session.add(new_menu)
            success_count += 1
        except Exception as e:
            print(f"[WARN] Insert menu {menu[1]} failed: {e}")
    
    try:
        db.session.commit()
        print(f"[OK] Sidebar menus data initialized, {success_count} menus created")
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Commit failed: {e}")


@admin_bp.route('/sidebar/menus/visibility', methods=['PUT'])
@admin_required
@demo_forbidden
def update_menu_visibility():
    """更新菜单可见性"""
    data = request.get_json()
    menu_type = data.get('menu_type', 'admin')
    menu_key = data.get('menu_key')
    visible = data.get('visible', True)
    
    if not menu_key:
        return jsonify({'code': 400, 'message': '缺少菜单标识'}), 400
    
    success = SidebarMenu.update_visibility(menu_type, menu_key, visible)
    
    if success:
        # 记录操作日志
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        OperationLog.log(
            user_id=user_id,
            username=user.username if user else None,
            action=OperationLog.ACTION_UPDATE,
            target_type='sidebar_menu',
            target_id=menu_key,
            detail=f'更新菜单 {menu_key} 可见性为 {visible}',
            ip_address=get_real_ip()
        )
        
        return jsonify({
            'code': 200,
            'message': '更新成功'
        })
    
    return jsonify({'code': 404, 'message': '菜单不存在'}), 404


@admin_bp.route('/sidebar/menus/sort', methods=['PUT'])
@admin_required
@demo_forbidden
def update_menu_sort():
    """批量更新菜单排序"""
    data = request.get_json()
    menu_type = data.get('menu_type', 'admin')
    menu_orders = data.get('orders', [])
    
    if not menu_orders:
        return jsonify({'code': 400, 'message': '缺少排序数据'}), 400
    
    SidebarMenu.update_sort_order(menu_type, menu_orders)
    
    # 记录操作日志
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='sidebar_menu',
        detail=f'更新 {menu_type} 菜单排序',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '排序更新成功'
    })


@admin_bp.route('/sidebar/menus/reset', methods=['POST'])
@admin_required
@demo_forbidden
def reset_sidebar_menus():
    """重置菜单数据（清除并重新初始化）"""
    try:
        _init_sidebar_menus_data()
        
        # 记录操作日志
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        OperationLog.log(
            user_id=user_id,
            username=user.username if user else None,
            action=OperationLog.ACTION_UPDATE,
            target_type='sidebar_menu',
            detail='重置侧边栏菜单数据',
            ip_address=get_real_ip()
        )
        
        return jsonify({
            'code': 200,
            'message': '菜单数据已重置'
        })
    except Exception as e:
        return jsonify({'code': 500, 'message': f'重置失败: {str(e)}'}), 500


@admin_bp.route('/sidebar/menus/batch', methods=['PUT'])
@admin_required
@demo_forbidden
def batch_update_menus():
    """批量更新菜单配置（排序+可见性）"""
    data = request.get_json()
    menu_type = data.get('menu_type', 'admin')
    menus = data.get('menus', [])
    
    if not menus:
        return jsonify({'code': 400, 'message': '缺少菜单数据'}), 400
    
    for item in menus:
        menu = SidebarMenu.query.filter_by(
            menu_type=menu_type, 
            menu_key=item.get('menu_key')
        ).first()
        if menu:
            if 'sort_order' in item:
                menu.sort_order = item['sort_order']
            if 'visible' in item:
                menu.visible = 1 if item['visible'] else 0
    
    db.session.commit()
    
    # 记录操作日志
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    OperationLog.log(
        user_id=user_id,
        username=user.username if user else None,
        action=OperationLog.ACTION_UPDATE,
        target_type='sidebar_menu',
        detail=f'批量更新 {menu_type} 菜单配置',
        ip_address=get_real_ip()
    )
    
    return jsonify({
        'code': 200,
        'message': '保存成功'
    })
