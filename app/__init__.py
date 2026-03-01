from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
import pymysql
import os

from config import config

db = SQLAlchemy()
jwt = JWTManager()


def ensure_database_exists(app_config):
    """确保数据库存在，如果不存在则自动创建"""
    try:
        db_host = app_config.get('DB_HOST', 'localhost')
        db_port = int(app_config.get('DB_PORT', 3306))
        db_user = app_config.get('DB_USER', 'root')
        db_password = app_config.get('DB_PASSWORD', '')
        db_name = app_config.get('DB_NAME', 'dns_system')
        
        conn = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[OK] Database '{db_name}' ready")
    except Exception as e:
        print(f"[WARN] Database check failed: {e}")


def create_app(config_name=None):
    """Application factory"""
    if config_name is None:
        import os
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='../static')
    
    app.config.from_object(config[config_name])
    
    # 自动创建数据库
    if config_name != 'testing':
        ensure_database_exists(app.config)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # 初始化日志系统
    from app.utils.logger import setup_logger
    logger = setup_logger(app)
    
    # 配置验证（生产环境）
    if config_name == 'production':
        from app.utils.config_validator import ConfigValidator
        if not ConfigValidator.validate_and_log(app.config, is_production=True):
            logger.warning('配置验证未通过，请检查配置项')
    
    # Register blueprints
    from app.routes import auth_bp, domain_bp, record_bp, admin_bp, main_bp, security_bp, coupon_bp
    from app.routes.health import health_bp
    from app.routes.app_update import app_update_bp
    from app.routes.open_api import open_api_bp
    from app.routes.host import host_bp
    from app.routes.admin.email_test import bp as email_test_bp
    from app.routes.admin.email_campaigns import bp as email_campaigns_bp
    from app.routes.admin.user_activity import bp as user_activity_bp
    from app.routes.admin.email_accounts import bp as email_accounts_bp
    from app.routes.cron import cron_bp
    from app.routes.admin.backup import backup_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(domain_bp, url_prefix='/api')
    app.register_blueprint(record_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(security_bp, url_prefix='/api/security')  # 安全设置
    app.register_blueprint(coupon_bp, url_prefix='/api')  # 优惠券
    app.register_blueprint(health_bp)  # 健康检查端点
    app.register_blueprint(app_update_bp, url_prefix='/api/app')  # APP更新
    app.register_blueprint(open_api_bp, url_prefix='/api/open')  # 开放API
    app.register_blueprint(host_bp, url_prefix='/api/host')  # 托管商
    app.register_blueprint(email_test_bp)  # 邮件测试
    app.register_blueprint(email_campaigns_bp)  # 群发邮件
    app.register_blueprint(user_activity_bp)  # 用户活跃度
    app.register_blueprint(email_accounts_bp)  # 邮箱账户管理
    app.register_blueprint(cron_bp, url_prefix='/api/cron')  # 定时任务外部调用
    app.register_blueprint(backup_bp)  # 数据库备份
    from app.routes.whois import whois_bp
    app.register_blueprint(whois_bp)  # WHOIS 查询
    from app.routes.points import points_bp
    app.register_blueprint(points_bp)  # 积分系统
    from app.routes.ticket import ticket_bp
    app.register_blueprint(ticket_bp)  # 工单系统
    from app.routes.transfer import transfer_bp
    app.register_blueprint(transfer_bp)  # 域名转移（用户端）
    from app.routes.admin_transfer import admin_transfer_bp
    app.register_blueprint(admin_transfer_bp)  # 域名转移（管理端）
    from app.routes.free_plan_application import free_plan_app_bp
    app.register_blueprint(free_plan_app_bp, url_prefix='/api')  # 免费套餐申请（用户端）
    
    # JWT error handlers with logging
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        logger.debug(f"Token expired: {jwt_payload}")
        return {'code': 401, 'message': 'Token已过期', 'error': 'expired'}, 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        logger.debug(f"Invalid token: {error}")
        return {'code': 401, 'message': 'Token无效', 'error': 'invalid'}, 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        from flask import request
        auth_header = request.headers.get('Authorization', 'None')
        logger.debug(f"Missing/unauthorized token. Auth header: {auth_header[:50] if auth_header else 'None'}...")
        return {'code': 401, 'message': '缺少认证Token', 'error': 'missing'}, 401
    
    # 版本强制更新检查中间件
    from app.utils.version_check import init_version_check
    init_version_check(app)
    
    # Create tables and default admin
    with app.app_context():
        # 确保所有模型被导入，以便 db.create_all() 能创建所有表
        from app.models import (User, CloudflareAccount, Domain, Subdomain, DnsRecord, 
                                 Setting, OperationLog, Plan, RedeemCode, PurchaseRecord,
                                 Announcement, AnnouncementRead, EmailVerification, DnsChannel,
                                 EmailTemplate, UserActivity, EmailCampaign, EmailLog)
        db.create_all()
        _run_migrations()
        _create_default_admin()
        _init_default_settings()
        _init_email_templates()
        _migrate_legacy_email_config()
        _recover_interrupted_campaigns()
    
    # 注册上下文处理器
    @app.context_processor
    def inject_settings():
        from app.models import Setting
        return {'site_settings': Setting.get_all()}
    
    # 初始化后台任务管理器
    if config_name != 'testing':
        try:
            from app.services.background_tasks import BackgroundTaskManager
            max_workers = app.config.get('BACKGROUND_TASK_WORKERS', 2)
            max_queue = app.config.get('BACKGROUND_TASK_MAX_QUEUE', 100)
            BackgroundTaskManager.initialize(max_workers=max_workers, max_queue_size=max_queue)
            logger.info(f"BackgroundTaskManager initialized")
        except Exception as e:
            logger.warning(f"BackgroundTaskManager init failed: {e}")
    
    # 初始化定时任务（非测试环境）
    if config_name != 'testing':
        # 检查是否在 Flask reloader 子进程中（避免重复启动）
        import os
        is_reloader = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        
        try:
            from app.services.scheduler import init_scheduler
            init_scheduler(app)
        except Exception as e:
            logger.warning(f"Scheduler init failed: {e}")
        
        # 初始化 Telegram 机器人（只在主进程或 reloader 进程中启动一次）
        if is_reloader or not app.debug:
            try:
                from app.services.telegram_bot import TelegramBotService
                TelegramBotService.init_app(app)
            except Exception as e:
                logger.warning(f"Telegram bot init failed: {e}")
        
    logger.info(f"Application started in {config_name} mode")
    return app


def _create_default_admin():
    """创建默认管理员账户（如果不存在）"""
    from app.models import User
    
    if User.query.filter_by(role='admin').first() is None:
        admin = User(
            username='admin',
            email='admin@qq.com',
            role='admin',
            max_domains=999
        )
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("[OK] Default admin created: admin@qq.com / admin123")


def _init_default_settings():
    """初始化默认系统设置"""
    from app.models import Setting
    Setting.init_defaults()


def _init_email_templates():
    """初始化默认邮件模板"""
    from app.models.email_template import EmailTemplate
    EmailTemplate.init_defaults()


def _migrate_legacy_email_config():
    """自动迁移旧版邮件配置到新版邮箱账户"""
    from app.models import Setting
    from app.models.email_account import EmailAccount
    
    # 检查是否已有邮箱账户
    existing_count = EmailAccount.query.count()
    if existing_count > 0:
        return  # 已有账户，不需要迁移
    
    # 检查旧配置
    provider = Setting.get('email_provider', 'smtp')
    
    if provider == 'aliyun':
        # 检查阿里云配置
        access_key_id = Setting.get('aliyun_dm_access_key_id', '')
        access_key_secret = Setting.get('aliyun_dm_access_key_secret', '')
        account_name = Setting.get('aliyun_dm_account', '')
        
        if not access_key_id or not access_key_secret or not account_name:
            return  # 没有有效的旧配置
        
        config = {
            'access_key_id': access_key_id,
            'access_key_secret': access_key_secret,
            'account_name': account_name,
            'from_name': Setting.get('aliyun_dm_from_name', '六趣DNS'),
            'region': Setting.get('aliyun_dm_region', 'cn-hangzhou')
        }
        account_type = EmailAccount.TYPE_ALIYUN
        account_name = '阿里云邮件推送 (自动导入)'
    else:
        # 检查SMTP配置
        smtp_host = Setting.get('smtp_host', '')
        smtp_user = Setting.get('smtp_user', '')
        smtp_password = Setting.get('smtp_password', '')
        
        if not smtp_host or not smtp_user or not smtp_password:
            return  # 没有有效的旧配置
        
        config = {
            'host': smtp_host,
            'port': int(Setting.get('smtp_port', 465) or 465),
            'user': smtp_user,
            'password': smtp_password,
            'from_name': Setting.get('smtp_from_name', '六趣DNS'),
            'ssl': Setting.get('smtp_ssl', '1') == '1'
        }
        account_type = EmailAccount.TYPE_SMTP
        account_name = f'SMTP - {smtp_host} (自动导入)'
    
    # 创建新账户
    try:
        account = EmailAccount(
            name=account_name,
            type=account_type,
            daily_limit=500,
            priority=10,
            enabled=True
        )
        account.set_config(config)
        db.session.add(account)
        db.session.commit()
        print(f"[OK] Legacy email config migrated: {account_name}")
    except Exception as e:
        print(f"[WARN] Legacy email config migration failed: {e}")
        db.session.rollback()


def _recover_interrupted_campaigns():
    """恢复应用重启时中断的邮件群发任务"""
    from app.models import EmailCampaign
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # 查询状态为 sending 的任务
        interrupted_campaigns = EmailCampaign.query.filter_by(status=EmailCampaign.STATUS_SENDING).all()
        
        if interrupted_campaigns:
            for campaign in interrupted_campaigns:
                campaign.status = EmailCampaign.STATUS_FAILED
                logger.info(f'应用重启，邮件群发任务 {campaign.id} 已标记为失败')
            
            db.session.commit()
            print(f"[OK] Recovered {len(interrupted_campaigns)} interrupted email campaigns")
    except Exception as e:
        logger.error(f'恢复中断任务失败: {e}')
        print(f"[WARN] Failed to recover interrupted campaigns: {e}")


def _run_migrations():
    """执行数据库迁移，为已有表添加新字段"""
    from sqlalchemy import text, inspect
    
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    migrations_run = []
    
    def get_columns(table_name):
        if table_name not in tables:
            return []
        return [col['name'] for col in inspector.get_columns(table_name)]
    
    def add_column(table, column, definition):
        try:
            db.session.execute(text(f"ALTER TABLE `{table}` ADD COLUMN {definition}"))
            migrations_run.append(f'{table}.{column}')
            return True
        except Exception as e:
            if 'Duplicate column' not in str(e):
                print(f"[WARN] Migration {table}.{column} failed: {e}")
            return False
    
    # ========== subdomains 表迁移 ==========
    if 'subdomains' in tables:
        subdomain_cols = get_columns('subdomains')
        
        if 'ns_mode' not in subdomain_cols:
            add_column('subdomains', 'ns_mode', 
                "`ns_mode` TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'NS模式'")
        
        if 'ns_servers' not in subdomain_cols:
            add_column('subdomains', 'ns_servers', 
                "`ns_servers` VARCHAR(500) DEFAULT NULL COMMENT 'NS服务器JSON'")
        
        if 'ns_changed_at' not in subdomain_cols:
            add_column('subdomains', 'ns_changed_at', 
                "`ns_changed_at` DATETIME DEFAULT NULL COMMENT 'NS修改时间'")
        
        if 'auto_renew' not in subdomain_cols:
            add_column('subdomains', 'auto_renew', 
                "`auto_renew` TINYINT NOT NULL DEFAULT 0 COMMENT '自动续费'")
    
    # ========== users 表迁移 ==========
    if 'users' in tables:
        user_cols = get_columns('users')
        
        if 'github_id' not in user_cols:
            add_column('users', 'github_id', 
                "`github_id` VARCHAR(50) DEFAULT NULL COMMENT 'GitHub OAuth ID'")
            # 添加唯一索引
            try:
                db.session.execute(text(
                    "ALTER TABLE `users` ADD UNIQUE INDEX `uk_github_id` (`github_id`)"
                ))
            except Exception as e:
                if 'Duplicate' not in str(e):
                    pass
        
        if 'google_id' not in user_cols:
            add_column('users', 'google_id', 
                "`google_id` VARCHAR(50) DEFAULT NULL COMMENT 'Google OAuth ID'")
            # 添加唯一索引
            try:
                db.session.execute(text(
                    "ALTER TABLE `users` ADD UNIQUE INDEX `uk_google_id` (`google_id`)"
                ))
            except Exception as e:
                if 'Duplicate' not in str(e):
                    pass
        
        if 'nodeloc_id' not in user_cols:
            add_column('users', 'nodeloc_id', 
                "`nodeloc_id` VARCHAR(50) DEFAULT NULL COMMENT 'NodeLoc OAuth ID'")
            # 添加唯一索引
            try:
                db.session.execute(text(
                    "ALTER TABLE `users` ADD UNIQUE INDEX `uk_nodeloc_id` (`nodeloc_id`)"
                ))
            except Exception as e:
                if 'Duplicate' not in str(e):
                    pass
        
        if 'totp_secret' not in user_cols:
            add_column('users', 'totp_secret', 
                "`totp_secret` VARCHAR(64) DEFAULT NULL COMMENT 'TOTP密钥'")
        
        if 'totp_enabled' not in user_cols:
            add_column('users', 'totp_enabled', 
                "`totp_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT '2FA开关'")
        
        if 'backup_codes' not in user_cols:
            add_column('users', 'backup_codes', 
                "`backup_codes` TEXT DEFAULT NULL COMMENT '备用码JSON'")
        
        if 'allowed_ips' not in user_cols:
            add_column('users', 'allowed_ips', 
                "`allowed_ips` TEXT DEFAULT NULL COMMENT '允许IP JSON'")
        
        if 'last_login_at' not in user_cols:
            add_column('users', 'last_login_at', 
                "`last_login_at` DATETIME DEFAULT NULL COMMENT '最后登录时间'")
        
        if 'last_login_ip' not in user_cols:
            add_column('users', 'last_login_ip', 
                "`last_login_ip` VARCHAR(45) DEFAULT NULL COMMENT '最后登录IP'")
        
        # API相关字段
        if 'api_key' not in user_cols:
            add_column('users', 'api_key', 
                "`api_key` VARCHAR(64) DEFAULT NULL COMMENT 'API密钥'")
            try:
                db.session.execute(text(
                    "ALTER TABLE `users` ADD UNIQUE INDEX `uk_api_key` (`api_key`)"
                ))
            except:
                pass
        
        if 'api_secret' not in user_cols:
            add_column('users', 'api_secret', 
                "`api_secret` VARCHAR(64) DEFAULT NULL COMMENT 'API密钥'")
        
        if 'api_enabled' not in user_cols:
            add_column('users', 'api_enabled', 
                "`api_enabled` TINYINT NOT NULL DEFAULT 0 COMMENT 'API启用状态'")
        
        if 'api_ip_whitelist' not in user_cols:
            add_column('users', 'api_ip_whitelist', 
                "`api_ip_whitelist` TEXT DEFAULT NULL COMMENT 'API IP白名单JSON'")
        
        # 手机号字段
        if 'phone' not in user_cols:
            add_column('users', 'phone', 
                "`phone` VARCHAR(20) DEFAULT NULL COMMENT '手机号'")
            # 添加唯一索引
            try:
                db.session.execute(text(
                    "ALTER TABLE `users` ADD UNIQUE INDEX `uk_phone` (`phone`)"
                ))
            except Exception as e:
                if 'Duplicate' not in str(e):
                    pass
        
        # 实名认证字段
        if 'real_name' not in user_cols:
            add_column('users', 'real_name', 
                "`real_name` VARCHAR(50) DEFAULT NULL COMMENT '真实姓名'")
        
        if 'id_card' not in user_cols:
            add_column('users', 'id_card', 
                "`id_card` VARCHAR(18) DEFAULT NULL COMMENT '身份证号'")
        
        if 'verified' not in user_cols:
            add_column('users', 'verified', 
                "`verified` SMALLINT NOT NULL DEFAULT 0 COMMENT '实名认证状态'")
        
        if 'verified_at' not in user_cols:
            add_column('users', 'verified_at', 
                "`verified_at` DATETIME DEFAULT NULL COMMENT '实名认证时间'")
        
        # TG 通知设置字段
        if 'tg_notify_domain_expire' not in user_cols:
            add_column('users', 'tg_notify_domain_expire', 
                "`tg_notify_domain_expire` TINYINT NOT NULL DEFAULT 1 COMMENT 'TG域名到期通知'")
        
        if 'tg_notify_purchase' not in user_cols:
            add_column('users', 'tg_notify_purchase', 
                "`tg_notify_purchase` TINYINT NOT NULL DEFAULT 1 COMMENT 'TG购买成功通知'")
        
        if 'tg_notify_balance' not in user_cols:
            add_column('users', 'tg_notify_balance', 
                "`tg_notify_balance` TINYINT NOT NULL DEFAULT 1 COMMENT 'TG余额变动通知'")
        
        if 'tg_notify_announcement' not in user_cols:
            add_column('users', 'tg_notify_announcement', 
                "`tg_notify_announcement` TINYINT NOT NULL DEFAULT 1 COMMENT 'TG系统公告通知'")
        
        if 'tg_notify_order' not in user_cols:
            add_column('users', 'tg_notify_order', 
                "`tg_notify_order` TINYINT NOT NULL DEFAULT 1 COMMENT 'TG托管商订单通知'")
        
        if 'tg_notify_daily' not in user_cols:
            add_column('users', 'tg_notify_daily', 
                "`tg_notify_daily` TINYINT NOT NULL DEFAULT 1 COMMENT 'TG管理员每日报表'")
        
        if 'tg_language' not in user_cols:
            add_column('users', 'tg_language', 
                "`tg_language` VARCHAR(10) DEFAULT 'zh' COMMENT 'TG语言设置'")
        
        # 迁移 role 字段以支持 demo 角色
        try:
            db.session.execute(text(
                "ALTER TABLE `users` MODIFY COLUMN `role` ENUM('user', 'admin', 'demo') NOT NULL DEFAULT 'user'"
            ))
            migrations_run.append('users.role(add demo)')
        except Exception as e:
            if 'Duplicate' not in str(e) and 'already' not in str(e).lower():
                pass  # 忽略已存在的情况
        
        # 迁移 password_hash 字段允许 NULL（OAuth 用户没有密码）
        try:
            db.session.execute(text(
                "ALTER TABLE `users` MODIFY COLUMN `password_hash` VARCHAR(255) NULL"
            ))
            migrations_run.append('users.password_hash(nullable)')
        except Exception as e:
            if 'Duplicate' not in str(e) and 'already' not in str(e).lower():
                pass  # 忽略已存在的情况
    
    # ========== 新建 ip_blacklist 表 ==========
    if 'ip_blacklist' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `ip_blacklist` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `ip_address` VARCHAR(45) NOT NULL UNIQUE,
                    `reason` VARCHAR(255) DEFAULT NULL,
                    `blocked_by` INT DEFAULT NULL,
                    `expires_at` DATETIME DEFAULT NULL,
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            migrations_run.append('ip_blacklist(table)')
        except Exception as e:
            print(f"[WARN] Create ip_blacklist failed: {e}")
    
    # ========== 新建 coupons 表 ==========
    if 'coupons' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `coupons` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `code` VARCHAR(32) NOT NULL UNIQUE,
                    `name` VARCHAR(100) NOT NULL,
                    `type` VARCHAR(20) NOT NULL DEFAULT 'percent',
                    `value` DECIMAL(10,2) NOT NULL,
                    `min_amount` DECIMAL(10,2) NOT NULL DEFAULT 0,
                    `max_discount` DECIMAL(10,2) DEFAULT NULL,
                    `total_count` INT NOT NULL DEFAULT -1,
                    `used_count` INT NOT NULL DEFAULT 0,
                    `per_user_limit` INT NOT NULL DEFAULT 1,
                    `applicable_plans` TEXT DEFAULT NULL,
                    `status` TINYINT NOT NULL DEFAULT 1,
                    `starts_at` DATETIME DEFAULT NULL,
                    `expires_at` DATETIME DEFAULT NULL,
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            migrations_run.append('coupons(table)')
        except Exception as e:
            print(f"[WARN] Create coupons failed: {e}")
    
    # ========== coupons 表迁移 ==========
    if 'coupons' in tables:
        coupon_cols = get_columns('coupons')
        if 'excluded_domains' not in coupon_cols:
            add_column('coupons', 'excluded_domains', 
                "`excluded_domains` TEXT DEFAULT NULL COMMENT '排除域名ID JSON'")
        if 'applicable_type' not in coupon_cols:
            add_column('coupons', 'applicable_type', 
                "`applicable_type` VARCHAR(20) NOT NULL DEFAULT 'all' COMMENT '适用产品类型: all/domain'")
    
    # ========== 新建 coupon_usages 表 ==========
    if 'coupon_usages' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `coupon_usages` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `coupon_id` INT NOT NULL,
                    `user_id` INT NOT NULL,
                    `order_id` INT DEFAULT NULL,
                    `original_price` DECIMAL(10,2) NOT NULL,
                    `discount_amount` DECIMAL(10,2) NOT NULL,
                    `final_price` DECIMAL(10,2) NOT NULL,
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    KEY `idx_coupon_id` (`coupon_id`),
                    KEY `idx_user_id` (`user_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            migrations_run.append('coupon_usages(table)')
        except Exception as e:
            print(f"[WARN] Create coupon_usages failed: {e}")
    
    # ========== 新建 plan_domains 表（套餐-域名多对多关联）==========
    if 'plan_domains' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `plan_domains` (
                    `plan_id` INT NOT NULL,
                    `domain_id` INT NOT NULL,
                    PRIMARY KEY (`plan_id`, `domain_id`),
                    KEY `idx_domain_id` (`domain_id`),
                    CONSTRAINT `fk_plan_domains_plan` FOREIGN KEY (`plan_id`) REFERENCES `plans` (`id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_plan_domains_domain` FOREIGN KEY (`domain_id`) REFERENCES `domains` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='套餐-域名关联表'
            """))
            migrations_run.append('plan_domains(table)')
            
            # 迁移现有数据：将 plans.domain_id 数据迁移到关联表
            try:
                db.session.execute(text("""
                    INSERT IGNORE INTO `plan_domains` (`plan_id`, `domain_id`)
                    SELECT `id`, `domain_id` FROM `plans` WHERE `domain_id` IS NOT NULL
                """))
                print("[OK] Migrated existing plan-domain relationships")
            except Exception as e:
                print(f"[WARN] Plan data migration failed: {e}")
        except Exception as e:
            print(f"[WARN] Create plan_domains failed: {e}")
    
    # ========== plans 表迁移：删除旧的 domain_id 字段 ==========
    if 'plans' in tables:
        plan_cols = get_columns('plans')
        if 'domain_id' in plan_cols:
            try:
                # 查找并删除所有外键约束
                try:
                    result = db.session.execute(text("""
                        SELECT CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE 
                        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'plans' 
                        AND COLUMN_NAME = 'domain_id' AND REFERENCED_TABLE_NAME IS NOT NULL
                    """))
                    for row in result:
                        fk_name = row[0]
                        try:
                            db.session.execute(text(f"ALTER TABLE `plans` DROP FOREIGN KEY `{fk_name}`"))
                        except:
                            pass
                except:
                    pass
                # 删除 domain_id 字段
                db.session.execute(text("ALTER TABLE `plans` DROP COLUMN `domain_id`"))
                migrations_run.append('plans.domain_id(drop)')
            except Exception as e:
                if 'Unknown column' not in str(e) and "check that column" not in str(e).lower():
                    print(f"[WARN] Drop plans.domain_id failed: {e}")
    
    # ========== domains 表迁移（上游关联）==========
    if 'domains' in tables:
        domain_cols = get_columns('domains')
        if 'upstream_domain_id' not in domain_cols:
            add_column('domains', 'upstream_domain_id', 
                "`upstream_domain_id` INT DEFAULT NULL COMMENT '上游域名ID'")
        if 'allow_ns_transfer' not in domain_cols:
            add_column('domains', 'allow_ns_transfer', 
                "`allow_ns_transfer` SMALLINT NOT NULL DEFAULT 1 COMMENT '是否允许NS转移 (1允许/0禁止)'")
    
    # ========== plans 表迁移（上游关联）==========
    if 'plans' in tables:
        plan_cols = get_columns('plans')
        if 'upstream_plan_id' not in plan_cols:
            add_column('plans', 'upstream_plan_id', 
                "`upstream_plan_id` INT DEFAULT NULL COMMENT '上游套餐ID'")
        if 'upstream_price' not in plan_cols:
            add_column('plans', 'upstream_price', 
                "`upstream_price` DECIMAL(10,2) DEFAULT NULL COMMENT '上游成本价'")
        if 'dns_channel_id' not in plan_cols:
            add_column('plans', 'dns_channel_id', 
                "`dns_channel_id` INT DEFAULT NULL COMMENT '关联渠道ID'")
    
    # ========== plans 表迁移（免费套餐相关）==========
    if 'plans' in tables:
        plan_cols = get_columns('plans')
        if 'is_free' not in plan_cols:
            add_column('plans', 'is_free', 
                "`is_free` TINYINT NOT NULL DEFAULT 0 COMMENT '是否免费套餐'")
        if 'max_purchase_count' not in plan_cols:
            add_column('plans', 'max_purchase_count', 
                "`max_purchase_count` INT NOT NULL DEFAULT 0 COMMENT '最大购买次数(0=不限)'")
        if 'renew_before_days' not in plan_cols:
            add_column('plans', 'renew_before_days', 
                "`renew_before_days` INT NOT NULL DEFAULT 0 COMMENT '到期前多少天可续费(0=不限)'")
        if 'points_per_day' not in plan_cols:
            add_column('plans', 'points_per_day', 
                "`points_per_day` INT NOT NULL DEFAULT 0 COMMENT '每天所需积分(0=不支持积分续费)'")
    
    # ========== subdomains 表迁移（上游关联）==========
    if 'subdomains' in tables:
        subdomain_cols = get_columns('subdomains')
        if 'upstream_subdomain_id' not in subdomain_cols:
            add_column('subdomains', 'upstream_subdomain_id', 
                "`upstream_subdomain_id` INT DEFAULT NULL COMMENT '上游子域名ID'")
    
    # ========== email_verifications 表迁移 ==========
    if 'email_verifications' in tables:
        ev_cols = get_columns('email_verifications')
        if 'invite_code' not in ev_cols:
            add_column('email_verifications', 'invite_code', 
                "`invite_code` VARCHAR(20) DEFAULT NULL COMMENT '关联的邀请码'")
    
    # ========== 新建 free_plan_applications 表（免费套餐申请）==========
    if 'free_plan_applications' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `free_plan_applications` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL COMMENT '申请用户ID',
                    `plan_id` INT NOT NULL COMMENT '申请的套餐ID',
                    `domain_id` INT DEFAULT NULL COMMENT '选择的域名ID',
                    `subdomain_name` VARCHAR(63) DEFAULT NULL COMMENT '预填的域名前缀',
                    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '申请状态: pending/approved/rejected/cancelled/used',
                    `apply_reason` TEXT NOT NULL COMMENT '申请理由',
                    `admin_note` TEXT DEFAULT NULL COMMENT '管理员备注',
                    `rejection_reason` TEXT DEFAULT NULL COMMENT '拒绝原因',
                    `reviewed_by` INT DEFAULT NULL COMMENT '审核人ID',
                    `reviewed_at` DATETIME DEFAULT NULL COMMENT '审核时间',
                    `ip_address` VARCHAR(45) DEFAULT NULL COMMENT '申请时的IP地址',
                    `user_info_snapshot` TEXT DEFAULT NULL COMMENT '用户信息快照(JSON)',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
                    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX `idx_user_id` (`user_id`),
                    INDEX `idx_plan_id` (`plan_id`),
                    INDEX `idx_status` (`status`),
                    INDEX `idx_created_at` (`created_at`),
                    CONSTRAINT `fk_free_plan_app_user` FOREIGN KEY (`user_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_free_plan_app_plan` FOREIGN KEY (`plan_id`) 
                        REFERENCES `plans` (`id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_free_plan_app_domain` FOREIGN KEY (`domain_id`) 
                        REFERENCES `domains` (`id`) ON DELETE SET NULL,
                    CONSTRAINT `fk_free_plan_app_reviewer` FOREIGN KEY (`reviewed_by`) 
                        REFERENCES `users` (`id`) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='免费套餐申请表'
            """))
            migrations_run.append('free_plan_applications(table)')
        except Exception as e:
            print(f"[WARN] Create free_plan_applications failed: {e}")
    
    # ========== free_plan_applications 表迁移（自动开通字段）==========
    if 'free_plan_applications' in tables:
        fpa_cols = get_columns('free_plan_applications')
        
        if 'provision_attempted' not in fpa_cols:
            add_column('free_plan_applications', 'provision_attempted',
                "`provision_attempted` TINYINT NOT NULL DEFAULT 0 COMMENT '是否尝试过自动开通 0=否 1=是'")
        
        if 'provision_error' not in fpa_cols:
            add_column('free_plan_applications', 'provision_error',
                "`provision_error` TEXT DEFAULT NULL COMMENT '自动开通失败原因'")
        
        if 'subdomain_id' not in fpa_cols:
            add_column('free_plan_applications', 'subdomain_id',
                "`subdomain_id` INT DEFAULT NULL COMMENT '自动创建的子域名ID'")
            # 添加外键约束
            try:
                db.session.execute(text("""
                    ALTER TABLE `free_plan_applications` 
                    ADD CONSTRAINT `fk_free_plan_app_subdomain` 
                    FOREIGN KEY (`subdomain_id`) REFERENCES `subdomains` (`id`) ON DELETE SET NULL
                """))
            except Exception as e:
                if 'Duplicate' not in str(e):
                    print(f"[WARN] Add FK free_plan_app_subdomain failed: {e}")
        
        # 托管商审核相关字段
        if 'host_review_status' not in fpa_cols:
            add_column('free_plan_applications', 'host_review_status',
                "`host_review_status` VARCHAR(20) DEFAULT NULL COMMENT '托管商审核状态: null=未审核, approved=通过, rejected=拒绝'")
        
        if 'host_reviewed_by' not in fpa_cols:
            add_column('free_plan_applications', 'host_reviewed_by',
                "`host_reviewed_by` INT DEFAULT NULL COMMENT '托管商审核人ID'")
            # 添加外键约束
            try:
                db.session.execute(text("""
                    ALTER TABLE `free_plan_applications` 
                    ADD CONSTRAINT `fk_free_plan_app_host_reviewer` 
                    FOREIGN KEY (`host_reviewed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
                """))
            except Exception as e:
                if 'Duplicate' not in str(e):
                    print(f"[WARN] Add FK free_plan_app_host_reviewer failed: {e}")
        
        if 'host_reviewed_at' not in fpa_cols:
            add_column('free_plan_applications', 'host_reviewed_at',
                "`host_reviewed_at` DATETIME DEFAULT NULL COMMENT '托管商审核时间'")
        
        if 'host_rejection_reason' not in fpa_cols:
            add_column('free_plan_applications', 'host_rejection_reason',
                "`host_rejection_reason` TEXT DEFAULT NULL COMMENT '托管商拒绝原因'")
        
        if 'host_admin_note' not in fpa_cols:
            add_column('free_plan_applications', 'host_admin_note',
                "`host_admin_note` TEXT DEFAULT NULL COMMENT '托管商备注'")
        
        # 将 subdomain_name 字段改为 NOT NULL（先更新空值，再修改约束）
        try:
            # 检查字段是否允许 NULL
            result = db.session.execute(text("""
                SELECT IS_NULLABLE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'free_plan_applications' 
                AND COLUMN_NAME = 'subdomain_name'
            """)).fetchone()
            
            if result and result[0] == 'YES':
                # 先将空值更新为空字符串（如果有的话）
                db.session.execute(text("""
                    UPDATE `free_plan_applications` 
                    SET `subdomain_name` = '' 
                    WHERE `subdomain_name` IS NULL OR `subdomain_name` = ''
                """))
                db.session.commit()
                
                # 修改字段为 NOT NULL
                db.session.execute(text("""
                    ALTER TABLE `free_plan_applications` 
                    MODIFY COLUMN `subdomain_name` VARCHAR(63) NOT NULL COMMENT '域名前缀（必填）'
                """))
                migrations_run.append('free_plan_applications.subdomain_name(NOT NULL)')
                print("[INFO] Updated free_plan_applications.subdomain_name to NOT NULL")
        except Exception as e:
            print(f"[WARN] Update subdomain_name constraint failed: {e}")
    
    # ========== DNS 渠道迁移 ==========
    _migrate_dns_channels(tables, get_columns, add_column, migrations_run)
    
    # ========== 托管商相关迁移 ==========
    _migrate_host_features(tables, get_columns, add_column, migrations_run)
    
    # ========== 新建 app_versions 表 ==========
    if 'app_versions' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `app_versions` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `platform` VARCHAR(20) NOT NULL COMMENT '平台 android/ios',
                    `version` VARCHAR(20) NOT NULL COMMENT '版本号',
                    `build` INT NOT NULL COMMENT '构建号',
                    `download_url` VARCHAR(500) NOT NULL COMMENT '下载地址',
                    `file_size` VARCHAR(20) DEFAULT NULL COMMENT '文件大小',
                    `update_log` TEXT DEFAULT NULL COMMENT '更新日志',
                    `force_update` SMALLINT NOT NULL DEFAULT 0 COMMENT '强制更新',
                    `min_version` VARCHAR(20) DEFAULT NULL COMMENT '最低支持版本',
                    `status` SMALLINT NOT NULL DEFAULT 1 COMMENT '状态',
                    `download_count` INT NOT NULL DEFAULT 0 COMMENT '下载次数',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY `uk_platform_version` (`platform`, `version`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='APP版本表'
            """))
            migrations_run.append('app_versions(table)')
        except Exception as e:
            print(f"[WARN] Create app_versions failed: {e}")
    
    # ========== 新建 sms_verifications 表 ==========
    if 'sms_verifications' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `sms_verifications` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `phone` VARCHAR(20) NOT NULL COMMENT '手机号',
                    `code` VARCHAR(10) NOT NULL COMMENT '验证码',
                    `type` VARCHAR(20) NOT NULL DEFAULT 'login' COMMENT '验证码类型',
                    `user_id` INT DEFAULT NULL COMMENT '关联用户ID',
                    `used` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否已使用',
                    `expires_at` DATETIME NOT NULL COMMENT '过期时间',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    KEY `idx_phone` (`phone`),
                    KEY `idx_phone_type` (`phone`, `type`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='短信验证码表'
            """))
            migrations_run.append('sms_verifications(table)')
        except Exception as e:
            print(f"[WARN] Create sms_verifications failed: {e}")
    
    # ========== telegram_bots 表迁移（API地址）==========
    if 'telegram_bots' in tables:
        tg_cols = get_columns('telegram_bots')
        if 'api_urls' not in tg_cols:
            add_column('telegram_bots', 'api_urls', 
                "`api_urls` TEXT DEFAULT NULL COMMENT 'API地址列表(JSON)'")
        if 'ad_button' not in tg_cols:
            add_column('telegram_bots', 'ad_button', 
                "`ad_button` TEXT DEFAULT NULL COMMENT '全局广告按钮(每行一个,格式:文字,链接)'")
    
    # ========== 用户管理增强功能迁移 ==========
    
    # ========== users 表迁移（活跃度相关字段）==========
    if 'users' in tables:
        user_cols = get_columns('users')
        if 'login_count' not in user_cols:
            add_column('users', 'login_count', 
                "`login_count` INT NOT NULL DEFAULT 0 COMMENT '登录次数'")
        if 'last_activity_at' not in user_cols:
            add_column('users', 'last_activity_at', 
                "`last_activity_at` DATETIME DEFAULT NULL COMMENT '最后活动时间'")
        if 'activity_score' not in user_cols:
            add_column('users', 'activity_score', 
                "`activity_score` INT NOT NULL DEFAULT 0 COMMENT '活跃度分数'")
        
        # 初始化现有用户的 last_activity_at（使用 last_login_at 或 created_at）
        try:
            db.session.execute(text("""
                UPDATE `users` 
                SET `last_activity_at` = COALESCE(`last_login_at`, `created_at`)
                WHERE `last_activity_at` IS NULL
            """))
            db.session.commit()
        except Exception as e:
            print(f"[WARN] Init last_activity_at failed: {e}")
    
    # ========== subdomains 表迁移（空置检测相关字段）==========
    if 'subdomains' in tables:
        subdomain_cols = get_columns('subdomains')
        if 'first_record_at' not in subdomain_cols:
            add_column('subdomains', 'first_record_at', 
                "`first_record_at` DATETIME DEFAULT NULL COMMENT '首次添加DNS记录时间'")
        if 'last_record_activity_at' not in subdomain_cols:
            add_column('subdomains', 'last_record_activity_at', 
                "`last_record_activity_at` DATETIME DEFAULT NULL COMMENT '最后DNS记录活动时间'")
        if 'idle_reminder_sent_at' not in subdomain_cols:
            add_column('subdomains', 'idle_reminder_sent_at', 
                "`idle_reminder_sent_at` DATETIME DEFAULT NULL COMMENT '空置提醒邮件发送时间'")
    
    # ========== 新建 user_activities 表 ==========
    if 'user_activities' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `user_activities` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL,
                    `activity_type` VARCHAR(50) NOT NULL COMMENT '活动类型',
                    `activity_data` TEXT COMMENT '活动详情(JSON)',
                    `ip_address` VARCHAR(45),
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX `idx_user_id` (`user_id`),
                    INDEX `idx_activity_type` (`activity_type`),
                    INDEX `idx_created_at` (`created_at`),
                    CONSTRAINT `fk_user_activities_user` FOREIGN KEY (`user_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户活动记录表'
            """))
            migrations_run.append('user_activities(table)')
        except Exception as e:
            print(f"[WARN] Create user_activities failed: {e}")
    
    # ========== 新建 email_campaigns 表 ==========
    if 'email_campaigns' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `email_campaigns` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `name` VARCHAR(100) NOT NULL COMMENT '任务名称',
                    `subject` VARCHAR(200) NOT NULL COMMENT '邮件主题',
                    `content` TEXT NOT NULL COMMENT '邮件内容(HTML)',
                    `recipient_filter` TEXT COMMENT '收件人筛选条件(JSON)',
                    `recipient_count` INT DEFAULT 0 COMMENT '收件人数量',
                    `sent_count` INT DEFAULT 0 COMMENT '已发送数量',
                    `success_count` INT DEFAULT 0 COMMENT '成功数量',
                    `failed_count` INT DEFAULT 0 COMMENT '失败数量',
                    `status` VARCHAR(20) DEFAULT 'draft' COMMENT '状态',
                    `scheduled_at` DATETIME COMMENT '定时发送时间',
                    `started_at` DATETIME COMMENT '开始发送时间',
                    `completed_at` DATETIME COMMENT '完成时间',
                    `created_by` INT NOT NULL COMMENT '创建人ID',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX `idx_status` (`status`),
                    INDEX `idx_created_by` (`created_by`),
                    CONSTRAINT `fk_email_campaigns_user` FOREIGN KEY (`created_by`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='邮件群发任务表'
            """))
            migrations_run.append('email_campaigns(table)')
        except Exception as e:
            print(f"[WARN] Create email_campaigns failed: {e}")
    
    # ========== 新建 email_logs 表 ==========
    if 'email_logs' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `email_logs` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `campaign_id` INT COMMENT '关联的群发任务ID',
                    `user_id` INT COMMENT '收件人用户ID',
                    `to_email` VARCHAR(100) NOT NULL COMMENT '收件人邮箱',
                    `subject` VARCHAR(200) NOT NULL COMMENT '邮件主题',
                    `content` TEXT COMMENT '邮件内容',
                    `status` VARCHAR(20) DEFAULT 'pending' COMMENT '状态',
                    `error_message` TEXT COMMENT '失败原因',
                    `sent_at` DATETIME COMMENT '发送时间',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX `idx_campaign_id` (`campaign_id`),
                    INDEX `idx_user_id` (`user_id`),
                    INDEX `idx_status` (`status`),
                    INDEX `idx_sent_at` (`sent_at`),
                    CONSTRAINT `fk_email_logs_campaign` FOREIGN KEY (`campaign_id`) 
                        REFERENCES `email_campaigns` (`id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_email_logs_user` FOREIGN KEY (`user_id`) 
                        REFERENCES `users` (`id`) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='邮件发送日志表'
            """))
            migrations_run.append('email_logs(table)')
        except Exception as e:
            print(f"[WARN] Create email_logs failed: {e}")
    
    # ========== email_templates 表迁移（字符集修复）==========
    if 'email_templates' in tables:
        try:
            # 修改表字符集为 utf8mb4
            db.session.execute(text(
                "ALTER TABLE `email_templates` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            ))
            migrations_run.append('email_templates(charset utf8mb4)')
        except Exception as e:
            if 'converted' not in str(e).lower() and 'already' not in str(e).lower():
                print(f"[WARN] email_templates charset migration failed: {e}")
    
    # ========== 新建 telegram_bind_codes 表 ==========
    if 'telegram_bind_codes' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `telegram_bind_codes` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL COMMENT '用户ID',
                    `code` VARCHAR(10) NOT NULL UNIQUE COMMENT '绑定码',
                    `expires_at` DATETIME NOT NULL COMMENT '过期时间',
                    `used` TINYINT NOT NULL DEFAULT 0 COMMENT '是否已使用',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    KEY `idx_user_id` (`user_id`),
                    KEY `idx_code` (`code`),
                    CONSTRAINT `fk_tg_bind_codes_user` FOREIGN KEY (`user_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Telegram绑定码表'
            """))
            migrations_run.append('telegram_bind_codes(table)')
        except Exception as e:
            print(f"[WARN] Create telegram_bind_codes failed: {e}")
    
    # ========== 新建 email_accounts 表（多邮箱账户）==========
    if 'email_accounts' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `email_accounts` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `name` VARCHAR(100) NOT NULL COMMENT '账户名称',
                    `type` VARCHAR(20) NOT NULL COMMENT '账户类型: smtp/aliyun',
                    `config` TEXT NOT NULL COMMENT '配置JSON',
                    `daily_limit` INT NOT NULL DEFAULT 500 COMMENT '日发送限额(0/-1无限)',
                    `daily_sent` INT NOT NULL DEFAULT 0 COMMENT '今日已发送',
                    `last_reset_at` DATETIME DEFAULT NULL COMMENT '上次重置时间',
                    `last_sent_at` DATETIME DEFAULT NULL COMMENT '上次发送时间',
                    `priority` INT NOT NULL DEFAULT 10 COMMENT '优先级(越小越优先)',
                    `enabled` TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                    INDEX `idx_enabled_priority` (`enabled`, `priority`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='邮箱账户表'
            """))
            migrations_run.append('email_accounts(table)')
        except Exception as e:
            print(f"[WARN] Create email_accounts failed: {e}")
    
    # ========== 积分系统迁移 ==========
    _migrate_points_system(tables, get_columns, add_column, migrations_run)
    
    # ========== 工单系统迁移 ==========
    _migrate_ticket_system(tables, get_columns, add_column, migrations_run)
    
    # ========== 域名转移表 ==========
    if 'domain_transfers' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `domain_transfers` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `subdomain_id` INT NOT NULL COMMENT '子域名ID',
                    `subdomain_name` VARCHAR(255) NOT NULL COMMENT '子域名全名',
                    `from_user_id` INT NOT NULL COMMENT '原所有者ID',
                    `from_username` VARCHAR(100) NOT NULL COMMENT '原所有者用户名',
                    `to_user_id` INT DEFAULT NULL COMMENT '新所有者ID',
                    `to_username` VARCHAR(100) NOT NULL COMMENT '目标用户名',
                    `fee_points` INT NOT NULL DEFAULT 0 COMMENT '手续费（积分）',
                    `verify_code` VARCHAR(10) DEFAULT NULL COMMENT '验证码',
                    `verify_expires` DATETIME DEFAULT NULL COMMENT '验证码过期时间',
                    `code_sent_at` DATETIME DEFAULT NULL COMMENT '验证码发送时间',
                    `status` TINYINT NOT NULL DEFAULT 0 COMMENT '状态：0=待验证，1=已完成，2=已取消，3=已过期',
                    `remark` VARCHAR(500) DEFAULT NULL COMMENT '备注',
                    `admin_remark` VARCHAR(500) DEFAULT NULL COMMENT '管理员备注',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `completed_at` DATETIME DEFAULT NULL COMMENT '完成时间',
                    INDEX `idx_subdomain` (`subdomain_id`),
                    INDEX `idx_from_user` (`from_user_id`),
                    INDEX `idx_to_user` (`to_user_id`),
                    INDEX `idx_status` (`status`),
                    INDEX `idx_created_at` (`created_at`),
                    FOREIGN KEY (`subdomain_id`) REFERENCES `subdomains`(`id`) ON DELETE CASCADE,
                    FOREIGN KEY (`from_user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='域名转移记录表'
            """))
            migrations_run.append('domain_transfers(table)')
        except Exception as e:
            print(f"[WARN] Create domain_transfers failed: {e}")
    
    # ========== 侧边栏菜单配置表 ==========
    if 'sidebar_menus' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `sidebar_menus` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `menu_type` VARCHAR(20) NOT NULL COMMENT '菜单类型: admin/user',
                    `menu_key` VARCHAR(50) NOT NULL COMMENT '菜单唯一标识',
                    `parent_key` VARCHAR(50) DEFAULT NULL COMMENT '父菜单标识(二级菜单用)',
                    `name_zh` VARCHAR(50) NOT NULL COMMENT '中文名称',
                    `name_en` VARCHAR(50) NOT NULL COMMENT '英文名称',
                    `icon` TEXT DEFAULT NULL COMMENT '图标SVG',
                    `url` VARCHAR(200) DEFAULT NULL COMMENT '链接地址',
                    `sort_order` INT NOT NULL DEFAULT 0 COMMENT '排序',
                    `visible` TINYINT NOT NULL DEFAULT 1 COMMENT '是否显示',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY `uk_type_key` (`menu_type`, `menu_key`),
                    INDEX `idx_type_parent` (`menu_type`, `parent_key`),
                    INDEX `idx_sort` (`sort_order`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='侧边栏菜单配置表'
            """))
            migrations_run.append('sidebar_menus(table)')
            # 初始化默认菜单数据
            _init_default_sidebar_menus()
        except Exception as e:
            print(f"[WARN] Create sidebar_menus failed: {e}")
    
    # ========== 新建 magic_link_tokens 表（邮箱链接登录）==========
    if 'magic_link_tokens' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `magic_link_tokens` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL COMMENT '用户ID',
                    `token` VARCHAR(64) NOT NULL COMMENT '登录令牌',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    `expires_at` DATETIME NOT NULL COMMENT '过期时间',
                    `used_at` DATETIME DEFAULT NULL COMMENT '使用时间',
                    `created_ip` VARCHAR(45) DEFAULT NULL COMMENT '创建时IP',
                    `used_ip` VARCHAR(45) DEFAULT NULL COMMENT '使用时IP',
                    UNIQUE KEY `uk_token` (`token`),
                    KEY `idx_user_id` (`user_id`),
                    KEY `idx_expires_at` (`expires_at`),
                    CONSTRAINT `fk_magic_link_user` FOREIGN KEY (`user_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='邮箱链接登录令牌表'
            """))
            migrations_run.append('magic_link_tokens(table)')
        except Exception as e:
            print(f"[WARN] Create magic_link_tokens failed: {e}")
    
    # ========== 更新侧边栏菜单（每次启动都执行）==========
    if 'sidebar_menus' in tables:
        try:
            _init_default_sidebar_menus()
            migrations_run.append('sidebar_menus(sync)')
        except Exception as e:
            print(f"[WARN] Sync sidebar_menus failed: {e}")
    
    # ========== 删除虚拟主机相关的侧边栏菜单 ==========
    if 'sidebar_menus' in tables:
        try:
            # 删除虚拟主机相关的菜单项（包括父菜单和子菜单）
            vhost_menu_keys = [
                'vhost',           # 虚拟主机父菜单
                'vhost_servers',   # 宝塔管理
                'vhost_plans',     # 套餐管理
                'vhost_instances', # 主机管理
                'vhost_orders',    # 订单管理
                'my_hosts',        # 我的主机
                'buy_host'         # 购买主机
            ]
            
            deleted_count = 0
            for menu_key in vhost_menu_keys:
                result = db.session.execute(text("""
                    DELETE FROM sidebar_menus 
                    WHERE menu_key = :menu_key
                """), {'menu_key': menu_key})
                deleted_count += result.rowcount
            
            if deleted_count > 0:
                migrations_run.append(f'sidebar_menus.remove_vhost({deleted_count} items)')
        except Exception as e:
            print(f"[WARN] Remove vhost menus failed: {e}")
    
    # ========== 批量更新所有菜单图标 ==========
    if 'sidebar_menus' in tables:
        try:
            # 定义所有图标
            icons = {
                'home': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>',
                'content': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"></path>',
                'server': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"></path>',
                'list': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path>',
                'plan': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path>',
                'domain': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path>',
                'search': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path>',
                'clock': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
                'transfer': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"></path>',
                'users': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"></path>',
                'activity': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path>',
                'gift': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7"></path>',
                'star': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"></path>',
                'ban': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"></path>',
                'cart': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"></path>',
                'code': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>',
                'ticket': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z"></path>',
                'database': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"></path>',
                'folder': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path>',
                'building': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"></path>',
                'finance': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>',
                'settings': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>',
                'bell': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path>',
                'mail': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>',
                'download': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>',
                'shield': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>',
                'key': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"></path>',
                'phone': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"></path>',
                'dns': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>',
                'menu': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>',
                'plus': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path>',
                'user': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>',
                'lock': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>',
                'briefcase': '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>',
            }
            
            # 定义菜单键与图标的映射关系
            menu_icon_mapping = {
                # 管理后台一级菜单
                'home': 'home',
                'domain_manage': 'domain',
                'user_manage': 'users',
                'finance': 'finance',
                'host': 'building',
                'content': 'content',
                'system': 'settings',
                # 管理后台子菜单
                'channels': 'server',
                'domains': 'list',
                'plans': 'plan',
                'free_plan_applications': 'folder',  # 申请管理
                'subdomains': 'domain',
                'dns_records': 'search',
                'idle_domains': 'clock',
                'transfers': 'transfer',
                'users': 'users',
                'user_activity': 'activity',
                'invites': 'gift',
                'points': 'star',
                'ip_blacklist': 'ban',
                'orders': 'cart',
                'redeem_codes': 'code',
                'coupons': 'ticket',
                'host_applications': 'folder',
                'host_hosts': 'building',
                'host_withdrawals': 'finance',
                'host_settings': 'settings',
                'announcements': 'bell',
                'tickets': 'ticket',
                'email_campaigns': 'mail',
                'app_versions': 'download',
                'email_templates': 'mail',
                'settings': 'settings',
                'security_settings': 'shield',
                'oauth_settings': 'key',
                'telegram': 'phone',
                'cron': 'clock',
                'backup': 'database',
                'logs': 'dns',
                'sidebar_menus': 'menu',
                # 站点设置父菜单和子菜单
                'settings_group': 'briefcase',  # 站点设置父菜单使用公文包图标
                'site_settings': 'settings',
                'domain_settings': 'domain',
                'points_settings': 'star',
                # 用户端一级菜单
                'dashboard': 'home',
                'domain_manage': 'domain',
                'order_center': 'cart',
                'account_settings': 'user',
                'whois': 'search',
                'tickets': 'ticket',
                # 用户端子菜单
                'my_domains': 'list',
                'buy_domain': 'plus',
                'my_applications': 'folder',
                'order_history': 'cart',
                'redeem_code': 'code',
                'points_center': 'star',
                'profile': 'user',
                'security': 'lock',
                'api_manage': 'key',
                'announcements': 'bell',
                'invite': 'gift',
            }
            
            # 批量更新图标
            updated_count = 0
            for menu_key, icon_key in menu_icon_mapping.items():
                if icon_key in icons:
                    try:
                        result = db.session.execute(text("""
                            UPDATE `sidebar_menus` 
                            SET `icon` = :icon 
                            WHERE `menu_key` = :menu_key AND `icon` IS NULL
                        """), {'icon': icons[icon_key], 'menu_key': menu_key})
                        if result.rowcount > 0:
                            updated_count += result.rowcount
                    except Exception as e:
                        print(f"[WARN] Update {menu_key} icon failed: {e}")
            
            if updated_count > 0:
                migrations_run.append(f'sidebar_menus.icons({updated_count} menus)')
        except Exception as e:
            print(f"[WARN] Batch update menu icons failed: {e}")
    
    # ========== email_campaigns 表迁移 ==========
    if 'email_campaigns' in tables:
        ec_cols = get_columns('email_campaigns')
        if 'task_id' not in ec_cols:
            add_column('email_campaigns', 'task_id',
                "`task_id` VARCHAR(64) DEFAULT NULL COMMENT '后台任务ID'")
    
    # ========== host_applications 表迁移：添加外键约束 ==========
    if 'host_applications' in tables:
        try:
            # 检查是否已有外键约束
            result = db.session.execute(text("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'host_applications' 
                AND COLUMN_NAME = 'user_id' 
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """))
            has_fk = result.fetchone() is not None
            
            if not has_fk:
                # 先清理无效数据（user_id 引用不存在的用户）
                db.session.execute(text("""
                    DELETE FROM host_applications 
                    WHERE user_id NOT IN (SELECT id FROM users)
                """))
                
                # 清理 reviewed_by 引用不存在的用户
                db.session.execute(text("""
                    UPDATE host_applications 
                    SET reviewed_by = NULL 
                    WHERE reviewed_by IS NOT NULL 
                    AND reviewed_by NOT IN (SELECT id FROM users)
                """))
                
                # 添加外键约束
                db.session.execute(text("""
                    ALTER TABLE `host_applications` 
                    ADD CONSTRAINT `fk_host_applications_user` 
                    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
                """))
                migrations_run.append('host_applications.user_id(fk)')
                
                # 添加 reviewed_by 外键约束
                db.session.execute(text("""
                    ALTER TABLE `host_applications` 
                    ADD CONSTRAINT `fk_host_applications_reviewer` 
                    FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
                """))
                migrations_run.append('host_applications.reviewed_by(fk)')
        except Exception as e:
            if 'Duplicate' not in str(e) and 'already exists' not in str(e).lower():
                print(f"[WARN] Add host_applications foreign keys failed: {e}")
    
    # ========== host_transactions 表迁移：添加外键约束 ==========
    if 'host_transactions' in tables:
        try:
            # 检查是否已有外键约束
            result = db.session.execute(text("""
                SELECT CONSTRAINT_NAME 
                FROM information_schema.KEY_COLUMN_USAGE 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'host_transactions' 
                AND COLUMN_NAME = 'host_id' 
                AND REFERENCED_TABLE_NAME IS NOT NULL
            """))
            has_fk = result.fetchone() is not None
            
            if not has_fk:
                # 先清理无效数据
                db.session.execute(text("""
                    DELETE FROM host_transactions 
                    WHERE host_id NOT IN (SELECT id FROM users)
                """))
                
                db.session.execute(text("""
                    DELETE FROM host_transactions 
                    WHERE purchase_record_id NOT IN (SELECT id FROM purchase_records)
                """))
                
                db.session.execute(text("""
                    UPDATE host_transactions 
                    SET domain_id = NULL 
                    WHERE domain_id IS NOT NULL 
                    AND domain_id NOT IN (SELECT id FROM domains)
                """))
                
                # 添加外键约束
                db.session.execute(text("""
                    ALTER TABLE `host_transactions` 
                    ADD CONSTRAINT `fk_host_transactions_host` 
                    FOREIGN KEY (`host_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
                """))
                migrations_run.append('host_transactions.host_id(fk)')
                
                # 添加 purchase_record_id 外键约束
                db.session.execute(text("""
                    ALTER TABLE `host_transactions` 
                    ADD CONSTRAINT `fk_host_transactions_purchase` 
                    FOREIGN KEY (`purchase_record_id`) REFERENCES `purchase_records` (`id`) ON DELETE CASCADE
                """))
                migrations_run.append('host_transactions.purchase_record_id(fk)')
                
                # 添加 domain_id 外键约束
                db.session.execute(text("""
                    ALTER TABLE `host_transactions` 
                    ADD CONSTRAINT `fk_host_transactions_domain` 
                    FOREIGN KEY (`domain_id`) REFERENCES `domains` (`id`) ON DELETE SET NULL
                """))
                migrations_run.append('host_transactions.domain_id(fk)')
        except Exception as e:
            if 'Duplicate' not in str(e) and 'already exists' not in str(e).lower():
                print(f"[WARN] Add host_transactions foreign keys failed: {e}")
    
    # ========== 插入托管商申请相关邮件模板 ==========
    # 提交迁移
    if migrations_run:
        db.session.commit()
        print(f"[OK] Migrations applied: {', '.join(migrations_run)}")


def _migrate_dns_channels(tables, get_columns, add_column, migrations_run):
    """DNS 渠道迁移：创建 dns_channels 表并迁移 cf_accounts 数据"""
    from sqlalchemy import text
    
    # 1. 为 domains 表添加新列
    if 'domains' in tables:
        domain_cols = get_columns('domains')
        
        if 'dns_channel_id' not in domain_cols:
            try:
                db.session.execute(text(
                    "ALTER TABLE `domains` ADD COLUMN `dns_channel_id` INT NULL AFTER `cf_account_id`"
                ))
                migrations_run.append('domains.dns_channel_id')
            except Exception as e:
                if 'Duplicate column' not in str(e):
                    print(f"[WARN] Add domains.dns_channel_id failed: {e}")
        
        if 'zone_id' not in domain_cols:
            try:
                db.session.execute(text(
                    "ALTER TABLE `domains` ADD COLUMN `zone_id` VARCHAR(100) NULL AFTER `cf_zone_id`"
                ))
                migrations_run.append('domains.zone_id')
            except Exception as e:
                if 'Duplicate column' not in str(e):
                    print(f"[WARN] Add domains.zone_id failed: {e}")
    
    # 2. 创建 dns_channels 表
    if 'dns_channels' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `dns_channels` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `name` VARCHAR(100) NOT NULL COMMENT '渠道名称',
                    `provider_type` VARCHAR(20) NOT NULL COMMENT '服务商类型',
                    `credentials` TEXT NOT NULL COMMENT '加密凭据JSON',
                    `status` SMALLINT DEFAULT 1 NOT NULL COMMENT '状态 1=启用 0=禁用',
                    `config` TEXT NULL COMMENT '渠道配置JSON',
                    `remark` VARCHAR(255) NULL COMMENT '备注',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='DNS渠道表'
            """))
            migrations_run.append('dns_channels(table)')
            db.session.commit()
        except Exception as e:
            print(f"[WARN] Create dns_channels failed: {e}")
            return
    
    # 3. 迁移 cf_accounts 数据到 dns_channels
    if 'cf_accounts' in tables and 'dns_channels' in tables:
        try:
            # 检查是否已有迁移数据
            result = db.session.execute(text("SELECT COUNT(*) FROM dns_channels WHERE remark LIKE '%从 cf_accounts 迁移%'"))
            migrated_count = result.scalar()
            
            if migrated_count == 0:
                # 获取所有 cf_accounts
                cf_accounts = db.session.execute(text(
                    "SELECT id, name, api_key, api_token, email, status FROM cf_accounts"
                )).fetchall()
                
                if cf_accounts:
                    from app.models import DnsChannel
                    account_mapping = {}
                    
                    for cf in cf_accounts:
                        cf_id, cf_name, api_key, api_token, email, status = cf
                        
                        # 构建凭据
                        credentials = {}
                        if api_key and email:
                            credentials = {'api_key': api_key, 'email': email}
                        elif api_token:
                            credentials = {'api_token': api_token}
                        
                        # 创建新渠道
                        channel = DnsChannel(
                            name=cf_name,
                            provider_type='cloudflare',
                            status=status,
                            remark=f'从 cf_accounts 迁移 (原ID: {cf_id})'
                        )
                        channel.set_credentials(credentials)
                        db.session.add(channel)
                        db.session.flush()
                        
                        account_mapping[cf_id] = channel.id
                    
                    db.session.commit()
                    migrations_run.append(f'dns_channels(migrate {len(account_mapping)} accounts)')
                    
                    # 4. 更新域名关联
                    updated = 0
                    for old_id, new_id in account_mapping.items():
                        result = db.session.execute(text(
                            "UPDATE domains SET dns_channel_id = :new_id, zone_id = COALESCE(zone_id, cf_zone_id) "
                            "WHERE cf_account_id = :old_id AND (dns_channel_id IS NULL OR dns_channel_id = 0)"
                        ), {'new_id': new_id, 'old_id': old_id})
                        updated += result.rowcount
                    
                    if updated > 0:
                        db.session.commit()
                        migrations_run.append(f'domains.dns_channel_id(update {updated})')
        except Exception as e:
            print(f"[WARN] Migrate cf_accounts to dns_channels failed: {e}")
    
    # 5. 添加外键约束（可选）
    if 'domains' in tables and 'dns_channels' in tables:
        try:
            result = db.session.execute(text(
                "SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'domains' "
                "AND COLUMN_NAME = 'dns_channel_id' AND REFERENCED_TABLE_NAME = 'dns_channels'"
            ))
            if result.scalar() == 0:
                db.session.execute(text(
                    "ALTER TABLE domains ADD CONSTRAINT fk_domains_dns_channel "
                    "FOREIGN KEY (dns_channel_id) REFERENCES dns_channels(id) ON DELETE SET NULL"
                ))
                migrations_run.append('domains.fk_dns_channel')
        except Exception as e:
            # 外键约束失败可以忽略
            pass


def _migrate_host_features(tables, get_columns, add_column, migrations_run):
    """托管商功能迁移"""
    from sqlalchemy import text
    
    # ========== users 表托管商字段 ==========
    if 'users' in tables:
        user_cols = get_columns('users')
        
        if 'host_status' not in user_cols:
            add_column('users', 'host_status', 
                "`host_status` VARCHAR(20) NOT NULL DEFAULT 'none' COMMENT '托管商状态'")
        
        if 'host_balance' not in user_cols:
            add_column('users', 'host_balance', 
                "`host_balance` DECIMAL(10,2) NOT NULL DEFAULT 0 COMMENT '托管收益余额'")
        
        if 'host_commission_rate' not in user_cols:
            add_column('users', 'host_commission_rate', 
                "`host_commission_rate` DECIMAL(5,2) DEFAULT NULL COMMENT '个人抽成比例'")
        
        if 'host_approved_at' not in user_cols:
            add_column('users', 'host_approved_at', 
                "`host_approved_at` DATETIME DEFAULT NULL COMMENT '托管商审核通过时间'")
        
        # 新增：暂停相关字段
        if 'host_suspended_at' not in user_cols:
            add_column('users', 'host_suspended_at', 
                "`host_suspended_at` DATETIME DEFAULT NULL COMMENT '托管商暂停时间'")
        
        if 'host_suspended_reason' not in user_cols:
            add_column('users', 'host_suspended_reason', 
                "`host_suspended_reason` VARCHAR(255) DEFAULT NULL COMMENT '托管商暂停原因'")
    
    # ========== dns_channels 表 owner_id 字段 ==========
    if 'dns_channels' in tables:
        channel_cols = get_columns('dns_channels')
        if 'owner_id' not in channel_cols:
            add_column('dns_channels', 'owner_id', 
                "`owner_id` INT DEFAULT NULL COMMENT '所属用户ID'")
    
    # ========== domains 表 owner_id 字段 ==========
    if 'domains' in tables:
        domain_cols = get_columns('domains')
        if 'owner_id' not in domain_cols:
            add_column('domains', 'owner_id', 
                "`owner_id` INT DEFAULT NULL COMMENT '所属用户ID'")
    
    # ========== plans 表 owner_id 字段 ==========
    if 'plans' in tables:
        plan_cols = get_columns('plans')
        if 'owner_id' not in plan_cols:
            add_column('plans', 'owner_id', 
                "`owner_id` INT DEFAULT NULL COMMENT '所属用户ID'")
    
    # ========== 新建 host_applications 表 ==========
    if 'host_applications' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `host_applications` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL COMMENT '申请用户ID',
                    `reason` TEXT NOT NULL COMMENT '申请理由',
                    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '申请状态',
                    `admin_remark` VARCHAR(255) DEFAULT NULL COMMENT '管理员备注',
                    `reviewed_by` INT DEFAULT NULL COMMENT '审核管理员ID',
                    `reviewed_at` DATETIME DEFAULT NULL COMMENT '审核时间',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY `idx_user_id` (`user_id`),
                    KEY `idx_status` (`status`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='托管商申请表'
            """))
            migrations_run.append('host_applications(table)')
        except Exception as e:
            print(f"[WARN] Create host_applications failed: {e}")
    
    # ========== 新建 host_transactions 表 ==========
    if 'host_transactions' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `host_transactions` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `host_id` INT NOT NULL COMMENT '托管商用户ID',
                    `purchase_record_id` INT NOT NULL COMMENT '购买记录ID',
                    `domain_id` INT DEFAULT NULL COMMENT '域名ID',
                    `total_amount` DECIMAL(10,2) NOT NULL COMMENT '订单总额',
                    `platform_fee` DECIMAL(10,2) NOT NULL COMMENT '平台抽成',
                    `host_earnings` DECIMAL(10,2) NOT NULL COMMENT '托管商收益',
                    `commission_rate` DECIMAL(5,2) NOT NULL COMMENT '当时的抽成比例',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    KEY `idx_host_id` (`host_id`),
                    KEY `idx_domain_id` (`domain_id`),
                    KEY `idx_created_at` (`created_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='托管商交易表'
            """))
            migrations_run.append('host_transactions(table)')
        except Exception as e:
            print(f"[WARN] Create host_transactions failed: {e}")
    
    # ========== 新建 host_withdrawals 表 ==========
    if 'host_withdrawals' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `host_withdrawals` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `host_id` INT NOT NULL COMMENT '托管商用户ID',
                    `amount` DECIMAL(10,2) NOT NULL COMMENT '提现金额',
                    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '提现状态',
                    `payment_method` VARCHAR(50) DEFAULT NULL COMMENT '收款方式',
                    `payment_account` VARCHAR(100) DEFAULT NULL COMMENT '收款账号',
                    `payment_name` VARCHAR(50) DEFAULT NULL COMMENT '收款人姓名',
                    `admin_remark` VARCHAR(255) DEFAULT NULL COMMENT '管理员备注',
                    `reviewed_by` INT DEFAULT NULL COMMENT '审核管理员ID',
                    `reviewed_at` DATETIME DEFAULT NULL COMMENT '审核时间',
                    `completed_at` DATETIME DEFAULT NULL COMMENT '完成时间',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    KEY `idx_host_id` (`host_id`),
                    KEY `idx_status` (`status`),
                    KEY `idx_created_at` (`created_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='托管商提现表'
            """))
            migrations_run.append('host_withdrawals(table)')
        except Exception as e:
            print(f"[WARN] Create host_withdrawals failed: {e}")

    # ========== 新建 cron_logs 表（定时任务执行日志）==========
    if 'cron_logs' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `cron_logs` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `task_id` VARCHAR(50) NOT NULL COMMENT '任务ID',
                    `task_name` VARCHAR(100) NOT NULL COMMENT '任务名称',
                    `triggered_by` VARCHAR(20) NOT NULL DEFAULT 'scheduler' COMMENT '触发方式: scheduler/manual/external',
                    `status` VARCHAR(20) NOT NULL DEFAULT 'running' COMMENT '执行状态: running/success/failed',
                    `result` TEXT COMMENT '执行结果',
                    `error_message` TEXT COMMENT '错误信息',
                    `started_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
                    `finished_at` DATETIME COMMENT '结束时间',
                    `duration` INT COMMENT '执行耗时(秒)',
                    INDEX `idx_task_id` (`task_id`),
                    INDEX `idx_status` (`status`),
                    INDEX `idx_started_at` (`started_at`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定时任务执行日志表'
            """))
            migrations_run.append('cron_logs(table)')
        except Exception as e:
            print(f"[WARN] Create cron_logs failed: {e}")


def _migrate_points_system(tables, get_columns, add_column, migrations_run):
    """积分系统迁移"""
    from sqlalchemy import text
    
    # ========== users 表迁移（积分相关字段）==========
    if 'users' in tables:
        user_cols = get_columns('users')
        
        if 'points' not in user_cols:
            add_column('users', 'points', 
                "`points` INT NOT NULL DEFAULT 0 COMMENT '当前积分'")
        
        if 'total_points' not in user_cols:
            add_column('users', 'total_points', 
                "`total_points` INT NOT NULL DEFAULT 0 COMMENT '累计获得积分'")
        
        if 'invite_code' not in user_cols:
            add_column('users', 'invite_code', 
                "`invite_code` VARCHAR(20) DEFAULT NULL COMMENT '邀请码'")
            # 添加唯一索引
            try:
                db.session.execute(text(
                    "ALTER TABLE `users` ADD UNIQUE INDEX `uk_invite_code` (`invite_code`)"
                ))
            except Exception as e:
                if 'Duplicate' not in str(e):
                    pass
    
    # ========== 新建 point_records 表 ==========
    if 'point_records' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `point_records` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL COMMENT '用户ID',
                    `type` VARCHAR(20) NOT NULL COMMENT '类型',
                    `points` INT NOT NULL COMMENT '变动积分',
                    `balance` INT NOT NULL COMMENT '变动后余额',
                    `description` VARCHAR(200) DEFAULT NULL COMMENT '描述',
                    `related_id` INT DEFAULT NULL COMMENT '关联ID',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX `idx_user` (`user_id`),
                    INDEX `idx_type` (`type`),
                    INDEX `idx_created` (`created_at`),
                    CONSTRAINT `fk_point_records_user` FOREIGN KEY (`user_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='积分变动记录表'
            """))
            migrations_run.append('point_records(table)')
        except Exception as e:
            print(f"[WARN] Create point_records failed: {e}")
    
    # ========== 新建 user_signins 表 ==========
    if 'user_signins' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `user_signins` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` INT NOT NULL COMMENT '用户ID',
                    `signin_date` DATE NOT NULL COMMENT '签到日期',
                    `continuous_days` INT NOT NULL DEFAULT 1 COMMENT '当前连续天数',
                    `points_earned` INT NOT NULL COMMENT '本次获得积分',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY `uk_user_date` (`user_id`, `signin_date`),
                    INDEX `idx_user` (`user_id`),
                    CONSTRAINT `fk_user_signins_user` FOREIGN KEY (`user_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户签到记录表'
            """))
            migrations_run.append('user_signins(table)')
        except Exception as e:
            print(f"[WARN] Create user_signins failed: {e}")
    
    # ========== 新建 user_invites 表 ==========
    if 'user_invites' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `user_invites` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `inviter_id` INT NOT NULL COMMENT '邀请人',
                    `invitee_id` INT NOT NULL COMMENT '被邀请人',
                    `invite_code` VARCHAR(20) NOT NULL COMMENT '使用的邀请码',
                    `register_reward` INT NOT NULL DEFAULT 0 COMMENT '注册奖励积分(邀请人)',
                    `recharge_reward` INT NOT NULL DEFAULT 0 COMMENT '首充奖励积分(邀请人)',
                    `invitee_reward` INT NOT NULL DEFAULT 0 COMMENT '被邀请人奖励积分',
                    `status` TINYINT NOT NULL DEFAULT 0 COMMENT '状态：0=已注册，1=已首充',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX `idx_inviter` (`inviter_id`),
                    INDEX `idx_invitee` (`invitee_id`),
                    UNIQUE KEY `uk_invitee` (`invitee_id`),
                    CONSTRAINT `fk_user_invites_inviter` FOREIGN KEY (`inviter_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_user_invites_invitee` FOREIGN KEY (`invitee_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户邀请记录表'
            """))
            migrations_run.append('user_invites(table)')
        except Exception as e:
            print(f"[WARN] Create user_invites failed: {e}")
    
    # ========== user_invites 表迁移（被邀请人奖励字段）==========
    if 'user_invites' in tables:
        invite_cols = get_columns('user_invites')
        if 'invitee_reward' not in invite_cols:
            add_column('user_invites', 'invitee_reward', 
                "`invitee_reward` INT NOT NULL DEFAULT 0 COMMENT '被邀请人奖励积分'")


def _migrate_ticket_system(tables, get_columns, add_column, migrations_run):
    """工单系统迁移"""
    from sqlalchemy import text
    
    # ========== 新建 tickets 表 ==========
    if 'tickets' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `tickets` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `ticket_no` VARCHAR(20) NOT NULL UNIQUE COMMENT '工单编号',
                    `type` SMALLINT NOT NULL DEFAULT 2 COMMENT '类型：1=用户对用户，2=用户对管理员',
                    `from_user_id` INT NOT NULL COMMENT '发起人',
                    `to_user_id` INT DEFAULT NULL COMMENT '接收人',
                    `subject` VARCHAR(200) NOT NULL COMMENT '工单标题',
                    `content` TEXT NOT NULL COMMENT '工单内容',
                    `status` SMALLINT NOT NULL DEFAULT 0 COMMENT '状态：0=待处理，1=处理中，2=已关闭',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX `idx_from_user` (`from_user_id`),
                    INDEX `idx_to_user` (`to_user_id`),
                    INDEX `idx_status` (`status`),
                    CONSTRAINT `fk_tickets_from_user` FOREIGN KEY (`from_user_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_tickets_to_user` FOREIGN KEY (`to_user_id`) 
                        REFERENCES `users` (`id`) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单表'
            """))
            migrations_run.append('tickets(table)')
        except Exception as e:
            print(f"[WARN] Create tickets failed: {e}")
    
    # ========== 新建 ticket_replies 表 ==========
    if 'ticket_replies' not in tables:
        try:
            db.session.execute(text("""
                CREATE TABLE `ticket_replies` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `ticket_id` INT NOT NULL COMMENT '工单ID',
                    `user_id` INT NOT NULL COMMENT '回复人',
                    `content` TEXT NOT NULL COMMENT '回复内容',
                    `is_read` SMALLINT NOT NULL DEFAULT 0 COMMENT '是否已读：0=未读，1=已读',
                    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX `idx_ticket` (`ticket_id`),
                    INDEX `idx_user` (`user_id`),
                    CONSTRAINT `fk_ticket_replies_ticket` FOREIGN KEY (`ticket_id`) 
                        REFERENCES `tickets` (`id`) ON DELETE CASCADE,
                    CONSTRAINT `fk_ticket_replies_user` FOREIGN KEY (`user_id`) 
                        REFERENCES `users` (`id`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='工单回复表'
            """))
            migrations_run.append('ticket_replies(table)')
        except Exception as e:
            print(f"[WARN] Create ticket_replies failed: {e}")


def _init_default_sidebar_menus():
    """初始化默认侧边栏菜单配置"""
    from sqlalchemy import text
    
    # 管理后台菜单配置
    admin_menus = [
        # 一级菜单
        ('admin', 'home', None, '首页', 'Home', '/admin', 1),
        ('admin', 'domain_manage', None, '域名管理', 'Domain', None, 10),
        ('admin', 'user_manage', None, '用户管理', 'Users', None, 20),
        ('admin', 'finance', None, '财务管理', 'Finance', None, 30),
        ('admin', 'host', None, '托管管理', 'Hosting', None, 40),
        ('admin', 'content', None, '内容管理', 'Content', None, 50),
        ('admin', 'system', None, '系统设置', 'System', None, 60),
        # 域名管理子菜单
        ('admin', 'channels', 'domain_manage', '渠道管理', 'Channels', '/admin/channels', 1),
        ('admin', 'domains', 'domain_manage', '域名列表', 'Domains', '/admin/domains', 2),
        ('admin', 'plans', 'domain_manage', '套餐管理', 'Plans', '/admin/plans', 3),
        ('admin', 'free_plan_applications', 'domain_manage', '申请管理', 'Application Mgmt', '/admin/free-plan-applications', 4),
        ('admin', 'subdomains', 'domain_manage', '用户域名', 'User Domains', '/admin/subdomains', 5),
        ('admin', 'dns_records', 'domain_manage', 'DNS查询', 'DNS Query', '/admin/dns-records', 6),
        ('admin', 'idle_domains', 'domain_manage', '闲置域名', 'Idle Domains', '/admin/idle-domains', 7),
        ('admin', 'transfers', 'domain_manage', '转移管理', 'Transfers', '/admin/transfers', 8),
        # 用户管理子菜单
        ('admin', 'users', 'user_manage', '用户列表', 'User List', '/admin/users', 1),
        ('admin', 'user_activity', 'user_manage', '用户活跃', 'User Activity', '/admin/user-activity', 2),
        ('admin', 'invites', 'user_manage', '邀请记录', 'Invites', '/admin/invites', 3),
        ('admin', 'points', 'user_manage', '积分记录', 'Points', '/admin/points', 4),
        ('admin', 'ip_blacklist', 'user_manage', 'IP黑名单', 'IP Blacklist', '/admin/ip-blacklist', 5),
        # 财务管理子菜单
        ('admin', 'orders', 'finance', '订单记录', 'Orders', '/admin/orders', 1),
        ('admin', 'redeem_codes', 'finance', '兑换码', 'Redeem Codes', '/admin/redeem-codes', 2),
        ('admin', 'coupons', 'finance', '优惠券', 'Coupons', '/admin/coupons', 3),
        # 托管管理子菜单
        ('admin', 'host_applications', 'host', '托管申请', 'Applications', '/admin/host/applications', 1),
        ('admin', 'host_hosts', 'host', '托管商列表', 'Hosts', '/admin/host/hosts', 2),
        ('admin', 'host_withdrawals', 'host', '提现管理', 'Withdrawals', '/admin/host/withdrawals', 3),
        ('admin', 'host_settings', 'host', '托管设置', 'Settings', '/admin/host/settings', 4),
        # 内容管理子菜单
        ('admin', 'announcements', 'content', '公告管理', 'Announcements', '/admin/announcements', 1),
        ('admin', 'tickets', 'content', '工单管理', 'Tickets', '/admin/tickets', 2),
        ('admin', 'email_campaigns', 'content', '群发邮件', 'Email Campaigns', '/admin/email-campaigns', 3),
        ('admin', 'app_versions', 'content', 'APP版本', 'App Versions', '/admin/app-versions', 4),
        ('admin', 'email_templates', 'content', '邮件模板', 'Email Templates', '/admin/email-templates', 5),
        # 系统设置子菜单
        ('admin', 'settings', 'system', '系统设置', 'System Settings', '/admin/settings', 1),
        ('admin', 'security_settings', 'system', '安全设置', 'Security', '/admin/security-settings', 2),
        ('admin', 'oauth_settings', 'system', '快捷登录', 'OAuth Login', '/admin/oauth-settings', 3),
        ('admin', 'telegram', 'system', 'Telegram机器人', 'Telegram Bot', '/admin/telegram', 4),
        ('admin', 'cron', 'system', '定时任务', 'Cron Tasks', '/admin/cron', 5),
        ('admin', 'backup', 'system', '数据备份', 'Backup', '/admin/backup', 6),
        ('admin', 'logs', 'system', '操作日志', 'Logs', '/admin/logs', 7),
        ('admin', 'sidebar_menus', 'system', '菜单管理', 'Menu Settings', '/admin/sidebar', 8),
        # 站点设置父菜单（新增）
        ('admin', 'settings_group', None, '站点设置', 'Site Settings', None, 90),
        # 站点设置子菜单
        ('admin', 'domain_settings', 'settings_group', '域名管理设置', 'Domain Settings', '/admin/domain-settings', 2),
        ('admin', 'points_settings', 'settings_group', '积分系统设置', 'Points Settings', '/admin/points-settings', 3),
    ]
    
    # 用户前台菜单配置
    user_menus = [
        # 一级菜单
        ('user', 'dashboard', None, '控制台', 'Dashboard', '/user', 1),
        ('user', 'domain_manage', None, '域名管理', 'Domain', None, 10),
        ('user', 'order_center', None, '订单中心', 'Orders', None, 20),
        ('user', 'account_settings', None, '账户设置', 'Account', None, 30),
        ('user', 'whois', None, 'WHOIS查询', 'WHOIS', '/whois', 40),
        ('user', 'tickets', None, '工单中心', 'Tickets', '/tickets', 50),
        ('user', 'host', None, '托管商入口', 'Hosting', '/host', 60),
        # 域名管理子菜单
        ('user', 'my_domains', 'domain_manage', '我的域名', 'My Domains', '/user/domains', 1),
        ('user', 'buy_domain', 'domain_manage', '购买域名', 'Buy Domain', '/user/domains/new', 2),
        ('user', 'my_applications', 'domain_manage', '我的申请', 'My Applications', '/my-applications', 3),
        ('user', 'transfers', 'domain_manage', '转移记录', 'Transfers', '/user/transfers', 4),
        # 订单中心子菜单
        ('user', 'order_history', 'order_center', '订单记录', 'Order History', '/user/orders', 1),
        ('user', 'redeem_code', 'order_center', '兑换码', 'Redeem Code', '/user/redeem', 2),
        ('user', 'points_center', 'order_center', '积分中心', 'Points', '/points', 3),
        # 账户设置子菜单
        ('user', 'profile', 'account_settings', '个人资料', 'Profile', '/user/profile', 1),
        ('user', 'security', 'account_settings', '安全设置', 'Security', '/user/security', 2),
        ('user', 'api_manage', 'account_settings', 'API管理', 'API', '/user/api', 3),
        ('user', 'announcements', 'account_settings', '系统公告', 'Announcements', '/user/announcements', 4),
        ('user', 'invite', 'account_settings', '邀请好友', 'Invite', '/invite', 5),
    ]
    
    all_menus = admin_menus + user_menus
    
    for menu in all_menus:
        try:
            db.session.execute(text("""
                INSERT INTO `sidebar_menus` 
                (`menu_type`, `menu_key`, `parent_key`, `name_zh`, `name_en`, `url`, `sort_order`, `visible`)
                VALUES (:menu_type, :menu_key, :parent_key, :name_zh, :name_en, :url, :sort_order, 1)
                ON DUPLICATE KEY UPDATE
                    `name_zh` = VALUES(`name_zh`),
                    `name_en` = VALUES(`name_en`),
                    `url` = VALUES(`url`),
                    `sort_order` = VALUES(`sort_order`),
                    `parent_key` = VALUES(`parent_key`)
            """), {
                'menu_type': menu[0],
                'menu_key': menu[1],
                'parent_key': menu[2],
                'name_zh': menu[3],
                'name_en': menu[4],
                'url': menu[5],
                'sort_order': menu[6]
            })
        except Exception as e:
            print(f"[WARN] Insert/Update menu {menu[1]} failed: {e}")
    
    db.session.commit()
    print("[OK] Default sidebar menus initialized/updated")
