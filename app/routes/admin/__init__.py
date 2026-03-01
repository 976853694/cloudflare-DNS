"""
管理员路由模块
拆分为多个子模块以提高可维护性
"""
from flask import Blueprint

admin_bp = Blueprint('admin', __name__)

# 导入子模块路由
from app.routes.admin import stats
from app.routes.admin import users
from app.routes.admin import domains
from app.routes.admin import channels
from app.routes.admin import settings
from app.routes.admin import logs
from app.routes.admin import dns_records
from app.routes.admin import plans
from app.routes.admin import redeem_codes
from app.routes.admin import purchase_records
from app.routes.admin import announcements
from app.routes.admin import subdomains
from app.routes.admin import import_export
from app.routes.admin import charts
from app.routes.admin import ip_blacklist
from app.routes.admin import coupons
from app.routes.admin import app_versions
from app.routes.admin import email_templates
from app.routes.admin import host
from app.routes.admin import telegram
from app.routes.admin import idle_domains
from app.routes.admin import cron
from app.routes.admin import backup
from app.routes.admin import tickets
from app.routes.admin import points
from app.routes.admin import sidebar
from app.routes.admin import free_plan_applications
from app.routes.admin import invites

__all__ = ['admin_bp']
