<?php
/**
 * 数据库配置和初始化
 */

class Database {
    private static $instance = null;
    private $db;
    
    private function __construct() {
        // MySQL 数据库配置
        $host = 'localhost';
        $dbname = 'cloudflare_dns';
        $username = 'root';
        $password = '';
        $charset = 'utf8mb4';
        
        // 创建MySQL数据库连接
        try {
            $dsn = "mysql:host=$host;dbname=$dbname;charset=$charset";
            $options = [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
                PDO::ATTR_PERSISTENT => false
            ];
            
            $this->db = new PDO($dsn, $username, $password, $options);
            
            // 设置MySQL连接参数
            $this->db->exec("SET NAMES '$charset'");
            $this->db->exec("SET time_zone = '+00:00'");
            $this->db->exec("SET sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'");
            
        } catch (PDOException $e) {
            throw new Exception("数据库连接失败: " . $e->getMessage());
        }
        
        $this->initTables();
    }
    
    public static function getInstance() {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }
    
    public function getConnection() {
        return $this->db;
    }
    
    public function getPDO() {
        return $this->db;
    }
    
    private function initTables() {
        // 创建用户表
        $this->db->exec("CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            points INT DEFAULT 100,
            status TINYINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建管理员表
        $this->db->exec("CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建域名表
        $this->db->exec("CREATE TABLE IF NOT EXISTS domains (
            id INT AUTO_INCREMENT PRIMARY KEY,
            domain_name VARCHAR(255) NOT NULL UNIQUE,
            api_key TEXT NOT NULL,
            email VARCHAR(255) NOT NULL,
            zone_id VARCHAR(255) NOT NULL,
            proxied_default TINYINT DEFAULT 1,
            status TINYINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建DNS记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS dns_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            domain_id INT,
            subdomain VARCHAR(255) NOT NULL,
            type VARCHAR(10) NOT NULL,
            content TEXT NOT NULL,
            proxied TINYINT DEFAULT 0,
            cloudflare_id VARCHAR(255),
            status TINYINT DEFAULT 1,
            is_system TINYINT DEFAULT 0,
            remark TEXT DEFAULT '',
            ttl INT DEFAULT 1,
            priority INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
            INDEX idx_user_id (user_id),
            INDEX idx_domain_id (domain_id),
            INDEX idx_subdomain (subdomain),
            INDEX idx_type (type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 检查并添加 is_system 字段（如果不存在）
        try {
            $stmt = $this->db->query("SHOW COLUMNS FROM dns_records LIKE 'is_system'");
            if ($stmt->rowCount() === 0) {
                $this->db->exec("ALTER TABLE dns_records ADD COLUMN is_system TINYINT DEFAULT 0");
            }
        } catch (Exception $e) {
            // 字段可能已存在，忽略错误
        }
        
        // 创建系统设置表
        $this->db->exec("CREATE TABLE IF NOT EXISTS settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(255) NOT NULL UNIQUE,
            setting_value TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建卡密表
        $this->db->exec("CREATE TABLE IF NOT EXISTS card_keys (
            id INT AUTO_INCREMENT PRIMARY KEY,
            card_key VARCHAR(255) NOT NULL UNIQUE,
            points INT NOT NULL,
            max_uses INT DEFAULT 1,
            used_count INT DEFAULT 0,
            status TINYINT DEFAULT 1,
            created_by INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES admins(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建卡密使用记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS card_key_usage (
            id INT AUTO_INCREMENT PRIMARY KEY,
            card_key_id INT,
            user_id INT,
            points_added INT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (card_key_id) REFERENCES card_keys(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_card_key_id (card_key_id),
            INDEX idx_user_id (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建操作日志表
        $this->db->exec("CREATE TABLE IF NOT EXISTS action_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_type VARCHAR(50) NOT NULL,
            user_id INT NOT NULL,
            action VARCHAR(255) NOT NULL,
            details TEXT,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_user_type (user_type),
            INDEX idx_user_id (user_id),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建DNS记录类型表
        $this->db->exec("CREATE TABLE IF NOT EXISTS dns_record_types (
            id INT AUTO_INCREMENT PRIMARY KEY,
            type_name VARCHAR(10) NOT NULL UNIQUE,
            description TEXT,
            enabled TINYINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建邀请记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS invitations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            inviter_id INT NOT NULL,
            invitation_code VARCHAR(255) NOT NULL UNIQUE,
            reward_points INT DEFAULT 0,
            use_count INT DEFAULT 0,
            total_rewards INT DEFAULT 0,
            is_active TINYINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP NULL DEFAULT NULL,
            FOREIGN KEY (inviter_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_inviter_id (inviter_id),
            INDEX idx_invitation_code (invitation_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建邀请使用记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS invitation_uses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            invitation_id INT NOT NULL,
            invitee_id INT NOT NULL,
            reward_points INT DEFAULT 0,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invitation_id) REFERENCES invitations(id) ON DELETE CASCADE,
            FOREIGN KEY (invitee_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_invitation_id (invitation_id),
            INDEX idx_invitee_id (invitee_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建公告表
        $this->db->exec("CREATE TABLE IF NOT EXISTS announcements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            type VARCHAR(20) DEFAULT 'info',
            is_active TINYINT DEFAULT 1,
            show_frequency VARCHAR(20) DEFAULT 'once',
            interval_hours INT DEFAULT 24,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_is_active (is_active),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建用户公告查看记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS user_announcement_views (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            announcement_id INT NOT NULL,
            last_viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            view_count INT DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (announcement_id) REFERENCES announcements(id) ON DELETE CASCADE,
            UNIQUE KEY unique_user_announcement (user_id, announcement_id),
            INDEX idx_user_id (user_id),
            INDEX idx_announcement_id (announcement_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建禁用前缀表
        $this->db->exec("CREATE TABLE IF NOT EXISTS blocked_prefixes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            prefix VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            is_active TINYINT DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_prefix (prefix),
            INDEX idx_is_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 创建登录尝试记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS login_attempts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ip_address VARCHAR(45) NOT NULL,
            username VARCHAR(255) NOT NULL,
            type VARCHAR(20) NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success TINYINT DEFAULT 0,
            INDEX idx_ip_address (ip_address),
            INDEX idx_username (username),
            INDEX idx_attempt_time (attempt_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci");
        
        // 插入默认管理员账户（仅在未安装时）
        if (!file_exists(__DIR__ . '/../data/install.lock')) {
            $stmt = $this->db->query("SELECT COUNT(*) FROM admins WHERE username = 'admin'");
            $admin_exists = $stmt->fetchColumn();
            if (!$admin_exists) {
                $password = password_hash('admin123456', PASSWORD_DEFAULT);
                $stmt = $this->db->prepare("INSERT INTO admins (username, password, email) VALUES (?, ?, ?)");
                $stmt->execute(['admin', $password, 'admin@example.com']);
            }
        }
        
        // 插入默认设置
        $this->insertDefaultSettings();
        
        // 插入默认DNS记录类型
        $this->insertDefaultDNSTypes();
    }
    
    
    private function insertDefaultSettings() {
        $default_settings = [
            ['points_per_record', '1', '每条DNS记录消耗积分'],
            ['default_user_points', '5', '新用户默认积分'],
            ['site_name', '六趣DNS域名分发系统', '网站名称'],
            ['allow_registration', '1', '是否允许用户注册'],
            ['invitation_enabled', '1', '是否启用邀请系统'],
            ['invitation_reward_points', '10', '邀请成功奖励积分'],
            ['invitee_bonus_points', '5', '被邀请用户额外积分']
        ];
        
        foreach ($default_settings as $setting) {
            $stmt = $this->db->query("SELECT COUNT(*) FROM settings WHERE setting_key = '{$setting[0]}'");
            $exists = $stmt->fetchColumn();
            if (!$exists) {
                $stmt = $this->db->prepare("INSERT INTO settings (setting_key, setting_value, description) VALUES (?, ?, ?)");
                $stmt->execute([$setting[0], $setting[1], $setting[2]]);
            }
        }
    }
    
    private function insertDefaultDNSTypes() {
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
            $stmt = $this->db->query("SELECT COUNT(*) FROM dns_record_types WHERE type_name = '{$type[0]}'");
            $exists = $stmt->fetchColumn();
            if (!$exists) {
                $stmt = $this->db->prepare("INSERT INTO dns_record_types (type_name, description, enabled) VALUES (?, ?, ?)");
                $stmt->execute([$type[0], $type[1], $type[2]]);
            }
        }
    }
}