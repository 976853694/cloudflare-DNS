from app.routes.auth import auth_bp
from app.routes.domain import domain_bp
from app.routes.record import record_bp
from app.routes.admin import admin_bp  # 已拆分为子模块
from app.routes.main import main_bp
from app.routes.security import security_bp
from app.routes.coupon import coupon_bp
from app.routes.whois import whois_bp
from app.routes.points import points_bp

__all__ = ['auth_bp', 'domain_bp', 'record_bp', 'admin_bp', 'main_bp', 'security_bp', 'coupon_bp', 'whois_bp', 'points_bp']
