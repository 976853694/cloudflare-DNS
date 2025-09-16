<?php

/**
 * 数据库配置和初始化
 */

class Database
{
    private static $instance = null;
    private $db;

    private function __construct()
    {
        $db_file = __DIR__ . '/../data/cloudflare_dns.db';

        // 确保数据目录存在
        $data_dir = dirname($db_file);
        if (!is_dir($data_dir)) {
            mkdir($data_dir, 0755, true);
        }

        // 创建数据库连接并设置优化参数
        $this->db = new SQLite3($db_file);
        $this->db->enableExceptions(true);

        // 设置SQLite优化参数以减少锁定问题
        $this->db->exec('PRAGMA journal_mode = WAL');
        $this->db->exec('PRAGMA synchronous = NORMAL');
        $this->db->exec('PRAGMA cache_size = 1000');
        $this->db->exec('PRAGMA temp_store = MEMORY');
        $this->db->exec('PRAGMA busy_timeout = 30000');
        $this->db->exec('PRAGMA foreign_keys = ON'); // TODO : 问题-1

        $this->initTables();
    }

    public static function getInstance()
    {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    public function getConnection()
    {
        return $this->db;
    }

    private function initTables()
    {
        // 创建用户表
        $this->db->exec("CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT,
            points INTEGER DEFAULT 100,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");

        // 创建管理员表
        $this->db->exec("CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");

        // 创建域名表
        $this->db->exec("CREATE TABLE IF NOT EXISTS domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_name TEXT NOT NULL UNIQUE,
            api_key TEXT NOT NULL,
            email TEXT NOT NULL,
            zone_id TEXT NOT NULL,
            proxied_default BOOLEAN DEFAULT 1,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");

        // 创建DNS记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS dns_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            domain_id INTEGER,
            subdomain TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            proxied INTEGER DEFAULT 0,
            cloudflare_id TEXT,
            status INTEGER DEFAULT 1,
            is_system INTEGER DEFAULT 0,
            remark TEXT DEFAULT '',
            ttl INTEGER DEFAULT 1,
            priority INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (domain_id) REFERENCES domains(id)
        )");

        // 为现有表添加 is_system 字段（如果不存在）
        try {
            $columns = $this->db->query("PRAGMA table_info(dns_records)");
            if ($columns) {
                $has_is_system = false;
                while ($column = $columns->fetchArray(SQLITE3_ASSOC)) {
                    if ($column['name'] === 'is_system') {
                        $has_is_system = true;
                        break;
                    }
                }
                if (!$has_is_system) {
                    $this->db->exec("ALTER TABLE dns_records ADD COLUMN is_system INTEGER DEFAULT 0");
                }
            }
        } catch (Exception $e) {
            // 如果检查失败，尝试直接添加字段（可能已存在）
            try {
                $this->db->exec("ALTER TABLE dns_records ADD COLUMN is_system INTEGER DEFAULT 0");
            } catch (Exception $e2) {
                // 字段可能已存在，忽略错误
            }
        }

        // 创建系统设置表
        $this->db->exec("CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT NOT NULL UNIQUE,
            setting_value TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");

        // 创建卡密表
        $this->db->exec("CREATE TABLE IF NOT EXISTS card_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_key TEXT NOT NULL UNIQUE,
            points INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            status INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES admins(id)
        )");

        // 创建卡密使用记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS card_key_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_key_id INTEGER,
            user_id INTEGER,
            points_added INTEGER,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (card_key_id) REFERENCES card_keys(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )");

        // 创建操作日志表
        $this->db->exec("CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");

        // 创建DNS记录类型表
        $this->db->exec("CREATE TABLE IF NOT EXISTS dns_record_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name TEXT NOT NULL UNIQUE,
            description TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");

        // 创建邀请记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id INTEGER NOT NULL,
            invitation_code TEXT NOT NULL UNIQUE,
            reward_points INTEGER DEFAULT 0,
            use_count INTEGER DEFAULT 0,
            total_rewards INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (inviter_id) REFERENCES users(id)
        )");

        // 创建邀请使用记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS invitation_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invitation_id INTEGER NOT NULL,
            invitee_id INTEGER NOT NULL,
            reward_points INTEGER DEFAULT 0,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invitation_id) REFERENCES invitations(id),
            FOREIGN KEY (invitee_id) REFERENCES users(id)
        )");

        // 创建公告表
        $this->db->exec("CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            is_active INTEGER DEFAULT 1,
            show_frequency TEXT DEFAULT 'once',
            interval_hours INTEGER DEFAULT 24,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )");

        // 创建用户公告查看记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS user_announcement_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            announcement_id INTEGER NOT NULL,
            last_viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            view_count INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (announcement_id) REFERENCES announcements(id),
            UNIQUE(user_id, announcement_id)
        )");

        // 创建禁用前缀表
        $this->db->exec("CREATE TABLE IF NOT EXISTS blocked_prefixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prefix TEXT NOT NULL UNIQUE,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )");

        // 创建登录尝试记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            username TEXT NOT NULL,
            type TEXT NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0
        )");

        // BY Senvinn
        // 创建邮箱验证表
        $this->db->exec("CREATE TABLE IF NOT EXISTS email_verify (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_address TEXT NOT NULL UNIQUE,
                email_verify_code TEXT NOT NULL,
                isVerified INTEGER DEFAULT 0 NOT NULL,
                verify_code_created_at TIMESTAMP DEFAULT current_timestamp
        )");

        // 插入默认管理员账户（仅在未安装时）
        if (!file_exists(__DIR__ . '/../data/install.lock')) {
            $admin_exists = $this->db->querySingle("SELECT COUNT(*) FROM admins WHERE username = 'admin'");
            if (!$admin_exists) {
                $password = password_hash('admin123456', PASSWORD_DEFAULT);
                $stmt = $this->db->prepare("INSERT INTO admins (username, password, email) VALUES (?, ?, ?)");
                $stmt->bindValue(1, 'admin', SQLITE3_TEXT);
                $stmt->bindValue(2, $password, SQLITE3_TEXT);
                $stmt->bindValue(3, 'admin@example.com', SQLITE3_TEXT);
                $stmt->execute();
            }
        }

        // 插入默认设置
        $this->insertDefaultSettings();

        // 插入默认DNS记录类型
        $this->insertDefaultDNSTypes();
    }


    private function insertDefaultSettings()
    {
        $default_settings = [
            ['points_per_record', '1', '每条DNS记录消耗积分'],
            ['default_user_points', '5', '新用户默认积分'],
            ['site_name', '六趣DNS域名分发系统', '网站名称'],
            ['allow_registration', '1', '是否允许用户注册'],
            ['invitation_enabled', '1', '是否启用邀请系统'],
            ['invitation_reward_points', '10', '邀请成功奖励积分'],
            ['invitee_bonus_points', '5', '被邀请用户额外积分'],
            //邮箱验证 BY Senvinn
            ['mail_verify_enabled', '0', '是否启用注册验证邮箱'],
            ['smtp_host', 'smtp.qq.com', '邮箱服务器'],
            ['smtp_username', 'rensenwen@qq.com', '发送者邮箱'],
            ['smtp_password', 'your_authorization_code', '邮箱授权码'],
            ['mail_username', '管理员', '发送者邮箱名'],
            ['mail_subject', '注册验证码', '邮件主题'],
            ['mail_body', '<h2>您好，您的注册验证码为: <strong>{code}</h2>', '邮件正文']
        ];

        foreach ($default_settings as $setting) {
            $exists = $this->db->querySingle("SELECT COUNT(*) FROM settings WHERE setting_key = '{$setting[0]}'");
            if (!$exists) {
                $stmt = $this->db->prepare("INSERT INTO settings (setting_key, setting_value, description) VALUES (?, ?, ?)");
                $stmt->bindValue(1, $setting[0], SQLITE3_TEXT);
                $stmt->bindValue(2, $setting[1], SQLITE3_TEXT);
                $stmt->bindValue(3, $setting[2], SQLITE3_TEXT);
                $stmt->execute();
            }
        }
    }

    private function insertDefaultDNSTypes()
    {
        $default_types = [
            ['A', 'IPv4地址记录', 1],
            ['AAAA', 'IPv6地址记录', 1],
            ['CNAME', '别名记录', 1],
            ['MX', '邮件交换记录', 1],
            ['TXT', '文本记录', 1],
            ['NS', '名称服务器记录', 0],
            ['PTR', '反向解析记录', 0],
            ['SRV', '服务记录', 0],
            ['CAA', '证书颁发机构授权记录', 0]
        ];

        foreach ($default_types as $type) {
            $exists = $this->db->querySingle("SELECT COUNT(*) FROM dns_record_types WHERE type_name = '{$type[0]}'");
            if (!$exists) {
                $stmt = $this->db->prepare("INSERT INTO dns_record_types (type_name, description, enabled) VALUES (?, ?, ?)");
                $stmt->bindValue(1, $type[0], SQLITE3_TEXT);
                $stmt->bindValue(2, $type[1], SQLITE3_TEXT);
                $stmt->bindValue(3, $type[2], SQLITE3_INTEGER);
                $stmt->execute();
            }
        }
    }
}
