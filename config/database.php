<?php
/**
 * 数据库配置和初始化
 */

class Database {
    private static $instance = null;
    private $db;
    
    private function __construct() {
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
        // 使用较短的超时时间，防止卡死
        $this->db->busyTimeout(10000); // 10秒超时
        $this->db->exec('PRAGMA journal_mode = WAL');
        $this->db->exec('PRAGMA synchronous = NORMAL');
        $this->db->exec('PRAGMA cache_size = -4000'); // 4MB cache
        $this->db->exec('PRAGMA temp_store = MEMORY');
        $this->db->exec('PRAGMA locking_mode = NORMAL'); // 避免独占锁
        $this->db->exec('PRAGMA page_size = 4096');
        $this->db->exec('PRAGMA foreign_keys = ON');
        
        $this->initTables();
        
        // 自动执行数据库升级（安装时）
        autoUpgradeOnInstall();
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
    
    private function initTables() {
        // 使用事务批量创建表，提高性能
        $this->db->exec('BEGIN TRANSACTION');
        
        try {
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
            provider_type TEXT DEFAULT 'cloudflare',
            provider_uid TEXT DEFAULT '',
            api_base_url TEXT DEFAULT '',
            expiration_time TEXT DEFAULT NULL,
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
        
        // 为domains表添加新字段（支持多DNS提供商）
        $this->addDomainsProviderFields();
        
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
            target_user_ids TEXT DEFAULT NULL,
            auto_close_seconds INTEGER DEFAULT 0,
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
        
        // 初始化用户组表（如果不存在则创建）
        $this->initUserGroupTables();
        
            // 提交事务
            $this->db->exec('COMMIT');
        } catch (Exception $e) {
            // 回滚事务
            $this->db->exec('ROLLBACK');
            throw $e;
        }
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
    
    /**
     * 为domains表添加多DNS提供商支持字段
     */
    private function addDomainsProviderFields() {
        try {
            $columns = $this->db->query("PRAGMA table_info(domains)");
            $existing_columns = [];
            
            if ($columns) {
                while ($column = $columns->fetchArray(SQLITE3_ASSOC)) {
                    $existing_columns[] = $column['name'];
                }
            }
            
            // 添加provider_type字段
            if (!in_array('provider_type', $existing_columns)) {
                $this->db->exec("ALTER TABLE domains ADD COLUMN provider_type TEXT DEFAULT 'cloudflare'");
            }
            
            // 添加provider_uid字段
            if (!in_array('provider_uid', $existing_columns)) {
                $this->db->exec("ALTER TABLE domains ADD COLUMN provider_uid TEXT DEFAULT ''");
            }
            
            // 添加api_base_url字段
            if (!in_array('api_base_url', $existing_columns)) {
                $this->db->exec("ALTER TABLE domains ADD COLUMN api_base_url TEXT DEFAULT ''");
            }
            
            // 添加expiration_time字段
            if (!in_array('expiration_time', $existing_columns)) {
                $this->db->exec("ALTER TABLE domains ADD COLUMN expiration_time TEXT DEFAULT NULL");
            }
            
        } catch (Exception $e) {
            // 忽略错误，字段可能已存在
        }
    }
    
    /**
     * 初始化用户组相关表
     * 在 initTables() 方法中调用
     */
    private function initUserGroupTables() {
        // 1. 创建用户组表
        $this->db->exec("CREATE TABLE IF NOT EXISTS user_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            points_per_record INTEGER DEFAULT 1,
            description TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            can_access_all_domains INTEGER DEFAULT 0,
            max_records INTEGER DEFAULT -1,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
        
        // 2. 创建用户组域名权限表
        $this->db->exec("CREATE TABLE IF NOT EXISTS user_group_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            domain_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES user_groups(id) ON DELETE CASCADE,
            FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
            UNIQUE(group_id, domain_id)
        )");
        
        // 3. 检查并添加 users 表的 group_id 字段
        try {
            $columns = $this->db->query("PRAGMA table_info(users)");
            $has_group_id = false;
            
            if ($columns) {
                while ($column = $columns->fetchArray(SQLITE3_ASSOC)) {
                    if ($column['name'] === 'group_id') {
                        $has_group_id = true;
                        break;
                    }
                }
            }
            
            if (!$has_group_id) {
                $this->db->exec("ALTER TABLE users ADD COLUMN group_id INTEGER DEFAULT 1");
                $this->db->exec("ALTER TABLE users ADD COLUMN group_changed_at TIMESTAMP DEFAULT NULL");
                $this->db->exec("ALTER TABLE users ADD COLUMN group_changed_by INTEGER DEFAULT NULL");
            }
        } catch (Exception $e) {
            // 忽略错误，字段可能已存在
        }
        
        // 4. 插入默认用户组数据
        $this->insertDefaultUserGroups();
        
        // 5. 创建索引
        try {
            $this->db->exec("CREATE INDEX IF NOT EXISTS idx_users_group_id ON users(group_id)");
            $this->db->exec("CREATE INDEX IF NOT EXISTS idx_user_group_domains_group ON user_group_domains(group_id)");
            $this->db->exec("CREATE INDEX IF NOT EXISTS idx_user_group_domains_domain ON user_group_domains(domain_id)");
        } catch (Exception $e) {
            // 忽略索引创建错误
        }
    }
    
    /**
     * 插入默认用户组数据
     */
    private function insertDefaultUserGroups() {
        $default_groups = [
            ['default', '默认组', 1, '普通用户，基础权限', 0, 0, 100],
            ['vip', 'VIP组', 1, 'VIP用户，享受更多域名权限', 10, 0, 500],
            ['svip', 'SVIP组', 0, '超级VIP用户，免积分解析，全域名权限', 20, 1, -1]
        ];
        
        foreach ($default_groups as $group) {
            try {
                // 检查是否已存在
                $exists = $this->db->querySingle("SELECT COUNT(*) FROM user_groups WHERE group_name = '{$group[0]}'");
                if (!$exists) {
                    $stmt = $this->db->prepare("
                        INSERT INTO user_groups 
                        (group_name, display_name, points_per_record, description, priority, can_access_all_domains, max_records) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ");
                    $stmt->bindValue(1, $group[0], SQLITE3_TEXT);
                    $stmt->bindValue(2, $group[1], SQLITE3_TEXT);
                    $stmt->bindValue(3, $group[2], SQLITE3_INTEGER);
                    $stmt->bindValue(4, $group[3], SQLITE3_TEXT);
                    $stmt->bindValue(5, $group[4], SQLITE3_INTEGER);
                    $stmt->bindValue(6, $group[5], SQLITE3_INTEGER);
                    $stmt->bindValue(7, $group[6], SQLITE3_INTEGER);
                    $stmt->execute();
                }
            } catch (Exception $e) {
                // 忽略插入错误
                error_log("插入默认用户组失败: " . $e->getMessage());
            }
        }
    }
}

/**
 * 数据库迁移函数 - 从 migrate.php 整合
 */
function migrateDatabase() {
    $db = Database::getInstance()->getConnection();
    
    // 检查并添加缺失的字段
    $migrations = [
        // DNS记录表增强
        "ALTER TABLE dns_records ADD COLUMN remark TEXT DEFAULT ''",
        "ALTER TABLE dns_records ADD COLUMN ttl INTEGER DEFAULT 300", 
        "ALTER TABLE dns_records ADD COLUMN priority INTEGER DEFAULT NULL",
        
        // 用户表OAuth支持
        "ALTER TABLE users ADD COLUMN github_id TEXT",
        "ALTER TABLE users ADD COLUMN github_username TEXT", 
        "ALTER TABLE users ADD COLUMN avatar_url TEXT",
        "ALTER TABLE users ADD COLUMN oauth_provider TEXT",
        "ALTER TABLE users ADD COLUMN github_bonus_received INTEGER DEFAULT 0",
        
        // 邀请表升级
        "ALTER TABLE invitations ADD COLUMN use_count INTEGER DEFAULT 0",
        "ALTER TABLE invitations ADD COLUMN total_rewards INTEGER DEFAULT 0", 
        "ALTER TABLE invitations ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE invitations ADD COLUMN last_used_at TIMESTAMP DEFAULT NULL",
        
        // 域名表提供商支持
        "ALTER TABLE domains ADD COLUMN provider_type TEXT DEFAULT 'cloudflare'",
        "ALTER TABLE domains ADD COLUMN provider_uid TEXT",
        "ALTER TABLE domains ADD COLUMN api_base_url TEXT"
    ];
    
    foreach ($migrations as $sql) {
        try {
            $db->exec($sql);
        } catch (Exception $e) {
            // 忽略已存在字段的错误
            if (!strpos($e->getMessage(), 'duplicate column name')) {
                error_log("Migration error: " . $e->getMessage());
            }
        }
    }
    
    // 创建索引
    $indexes = [
        "CREATE INDEX IF NOT EXISTS idx_users_github_id ON users(github_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_oauth_provider ON users(oauth_provider)",
        "CREATE INDEX IF NOT EXISTS idx_dns_records_domain_id ON dns_records(domain_id)",
        "CREATE INDEX IF NOT EXISTS idx_domains_provider_type ON domains(provider_type)"
    ];
    
    foreach ($indexes as $sql) {
        try {
            $db->exec($sql);
        } catch (Exception $e) {
            error_log("Index creation error: " . $e->getMessage());
        }
    }
    
    return true;
}

/**
 * 数据库修复函数 - 从 repair_database.php 整合  
 */
function repairDatabase() {
    try {
        $db = Database::getInstance()->getConnection();
        
        // 检查必需的表
        $requiredTables = [
            'users', 'admins', 'domains', 'dns_records', 'settings',
            'card_keys', 'card_key_usage', 'action_logs', 'dns_record_types',
            'invitations', 'invitation_uses', 'announcements', 'user_announcement_views',
            'blocked_prefixes', 'login_attempts', 'cloudflare_accounts', 'rainbow_accounts'
        ];
        
        $existingTables = [];
        $result = $db->query("SELECT name FROM sqlite_master WHERE type='table'");
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $existingTables[] = $row['name'];
        }
        
        $missingTables = array_diff($requiredTables, $existingTables);
        if (!empty($missingTables)) {
            error_log("Missing tables: " . implode(', ', $missingTables));
            return false;
        }
        
        // 自动运行数据库升级
        migrateDatabase();
        
        return true;
        
    } catch (Exception $e) {
        error_log("Database repair failed: " . $e->getMessage());
        return false;
    }
}

/**
 * 数据库升级类 - 从 database_upgrade.php 整合
 */
class DatabaseUpgrade {
    private $db;
    private $current_version = '1.6.0';
    
    // 数据库版本升级规则
    private $database_versions = [
        '1.0.0' => 'createBaseTables',
        '1.1.0' => 'addUserOAuthFields', 
        '1.2.0' => 'addInvitationSystem',
        '1.3.0' => 'addAnnouncementSystem',
        '1.4.0' => 'addSecurityTables',
        '1.5.0' => 'addIndexes',
        '1.6.0' => 'addMissingFields'
    ];
    
    public function __construct($silent = false) {
        try {
            $this->db = Database::getInstance()->getConnection();
            if (!$silent) {
                echo "<h2>数据库升级工具</h2>";
            }
        } catch (Exception $e) {
            if (!$silent) {
                die("数据库连接失败: " . $e->getMessage());
            }
            throw $e;
        }
    }
    
    /**
     * 执行数据库升级
     */
    public function upgrade($silent = false) {
        if (!$silent) {
            echo "<div style='font-family: monospace; background: #f5f5f5; padding: 20px;'>";
        }
        
        // 创建版本表
        $this->createVersionTable();
        
        // 获取当前数据库版本
        $current_db_version = $this->getCurrentDatabaseVersion();
        if (!$silent) {
            echo "<p><strong>当前数据库版本:</strong> $current_db_version</p>";
            echo "<p><strong>目标版本:</strong> {$this->current_version}</p>";
        }
        
        // 执行升级
        $upgraded = false;
        foreach ($this->database_versions as $version => $method) {
            if (version_compare($current_db_version, $version, '<')) {
                if (!$silent) {
                    echo "<h3>升级到版本 $version</h3>";
                }
                
                try {
                    $this->$method($silent);
                    $this->updateDatabaseVersion($version);
                    if (!$silent) {
                        echo "<p style='color: green;'>✅ 版本 $version 升级成功</p>";
                    }
                    $upgraded = true;
                } catch (Exception $e) {
                    if (!$silent) {
                        echo "<p style='color: red;'>❌ 版本 $version 升级失败: " . $e->getMessage() . "</p>";
                    }
                    throw $e;
                }
            }
        }
        
        if (!$upgraded && !$silent) {
            echo "<p style='color: blue;'>📋 数据库已是最新版本，无需升级</p>";
        }
        
        if (!$silent) {
            echo "</div>";
        }
        
        return $upgraded;
    }
    
    /**
     * 创建版本表
     */
    private function createVersionTable() {
        $this->db->exec("CREATE TABLE IF NOT EXISTS database_versions (
            version TEXT PRIMARY KEY,
            upgraded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
    }
    
    /**
     * 获取当前数据库版本
     */
    private function getCurrentDatabaseVersion() {
        try {
            $result = $this->db->querySingle("SELECT MAX(version) FROM database_versions");
            return $result ?: '0.0.0';
        } catch (Exception $e) {
            return '0.0.0';
        }
    }
    
    /**
     * 更新数据库版本
     */
    private function updateDatabaseVersion($version) {
        $stmt = $this->db->prepare("INSERT OR REPLACE INTO database_versions (version) VALUES (?)");
        $stmt->bindValue(1, $version, SQLITE3_TEXT);
        $stmt->execute();
    }
    
    /**
     * 创建基础表 - 版本 1.0.0
     */
    private function createBaseTables($silent = false) {
        // 这些表通常在 Database::initTables() 中已创建
        // 此方法主要用于确保基础表存在
        if (!$silent) {
            echo "<p style='color: green;'>✅ 基础表检查完成</p>";
        }
    }
    
    /**
     * 添加OAuth字段 - 版本 1.1.0
     */
    private function addUserOAuthFields($silent = false) {
        $this->addColumnIfNotExists('users', 'github_id', 'TEXT', $silent);
        $this->addColumnIfNotExists('users', 'github_username', 'TEXT', $silent);
        $this->addColumnIfNotExists('users', 'avatar_url', 'TEXT', $silent);
        $this->addColumnIfNotExists('users', 'oauth_provider', 'TEXT', $silent);
        $this->addColumnIfNotExists('users', 'github_bonus_received', 'INTEGER DEFAULT 0', $silent);
    }
    
    /**
     * 添加邀请系统 - 版本 1.2.0
     */
    private function addInvitationSystem($silent = false) {
        $this->addColumnIfNotExists('invitations', 'use_count', 'INTEGER DEFAULT 0', $silent);
        $this->addColumnIfNotExists('invitations', 'total_rewards', 'INTEGER DEFAULT 0', $silent);
        $this->addColumnIfNotExists('invitations', 'is_active', 'INTEGER DEFAULT 1', $silent);
        $this->addColumnIfNotExists('invitations', 'last_used_at', 'TIMESTAMP DEFAULT NULL', $silent);
    }
    
    /**
     * 添加公告系统 - 版本 1.3.0
     */
    private function addAnnouncementSystem($silent = false) {
        $this->addColumnIfNotExists('announcements', 'is_active', 'INTEGER DEFAULT 1', $silent);
        $this->addColumnIfNotExists('announcements', 'type', 'TEXT DEFAULT "info"', $silent);
    }
    
    /**
     * 添加安全表 - 版本 1.4.0
     */
    private function addSecurityTables($silent = false) {
        $this->addColumnIfNotExists('blocked_prefixes', 'is_active', 'INTEGER DEFAULT 1', $silent);
        $this->addColumnIfNotExists('login_attempts', 'success', 'INTEGER DEFAULT 0', $silent);
    }
    
    /**
     * 添加索引 - 版本 1.5.0
     */
    private function addIndexes($silent = false) {
        $indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_github_id ON users(github_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_oauth_provider ON users(oauth_provider)",
            "CREATE INDEX IF NOT EXISTS idx_dns_records_domain_id ON dns_records(domain_id)",
            "CREATE INDEX IF NOT EXISTS idx_domains_provider_type ON domains(provider_type)"
        ];
        
        foreach ($indexes as $sql) {
            try {
                $this->db->exec($sql);
            } catch (Exception $e) {
                if (!$silent) {
                    echo "<p style='color: red;'>❌ 创建索引失败: " . $e->getMessage() . "</p>";
                }
            }
        }
        
        if (!$silent) {
            echo "<p style='color: green;'>✅ 索引创建完成</p>";
        }
    }
    
    /**
     * 添加缺失字段 - 版本 1.6.0
     */
    private function addMissingFields($silent = false) {
        // DNS记录表增强
        $this->addColumnIfNotExists('dns_records', 'remark', 'TEXT DEFAULT ""', $silent);
        $this->addColumnIfNotExists('dns_records', 'ttl', 'INTEGER DEFAULT 300', $silent);
        $this->addColumnIfNotExists('dns_records', 'priority', 'INTEGER DEFAULT NULL', $silent);
        
        // 用户表积分字段
        $this->addColumnIfNotExists('users', 'credits', 'INTEGER DEFAULT 0', $silent);
        
        // 登录尝试表增强
        $this->addColumnIfNotExists('login_attempts', 'ip', 'TEXT', $silent);
        $this->addColumnIfNotExists('login_attempts', 'user_agent', 'TEXT', $silent);
        
        // 添加SMTP配置到settings表
        $this->addSMTPSettings($silent);
        
        // 域名表多提供商支持
        $this->addColumnIfNotExists('domains', 'provider_type', 'TEXT DEFAULT "cloudflare"', $silent);
        $this->addColumnIfNotExists('domains', 'provider_uid', 'TEXT', $silent);
        $this->addColumnIfNotExists('domains', 'api_base_url', 'TEXT', $silent);
    }
    
    /**
     * 安全地添加字段
     */
    private function addColumnIfNotExists($table, $column, $definition, $silent = false) {
        $columns = [];
        $result = $this->db->query("PRAGMA table_info($table)");
        if ($result) {
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $columns[] = $row['name'];
            }
            
            if (!in_array($column, $columns)) {
                try {
                    $this->db->exec("ALTER TABLE $table ADD COLUMN $column $definition");
                    if (!$silent) {
                        echo "<p style='color: green;'>✅ 添加字段 $table.$column</p>";
                    }
                } catch (Exception $e) {
                    if (!$silent) {
                        echo "<p style='color: red;'>❌ 添加字段 $table.$column 失败: " . $e->getMessage() . "</p>";
                    }
                    throw $e;
                }
            }
        }
    }
    
    /**
     * 添加SMTP配置设置
     */
    private function addSMTPSettings($silent = false) {
        $smtp_settings = [
            'smtp_enabled' => '1',
            'smtp_host' => 'smtp.qq.com',
            'smtp_port' => '465',
            'smtp_username' => '邮箱',
            'smtp_password' => '授权码',
            'smtp_secure' => 'ssl',
            'smtp_from_name' => '六趣DNS',
            'smtp_debug' => '0'
        ];
        
        foreach ($smtp_settings as $key => $value) {
            try {
                // 检查设置是否已存在
                $exists = $this->db->querySingle("SELECT COUNT(*) FROM settings WHERE setting_key = '$key'");
                if (!$exists) {
                    $stmt = $this->db->prepare("INSERT INTO settings (setting_key, setting_value, description) VALUES (?, ?, ?)");
                    $stmt->bindValue(1, $key, SQLITE3_TEXT);
                    $stmt->bindValue(2, $value, SQLITE3_TEXT);
                    $stmt->bindValue(3, $this->getSMTPDescription($key), SQLITE3_TEXT);
                    $stmt->execute();
                    
                    if (!$silent) {
                        echo "<p style='color: green;'>✅ 添加SMTP设置: $key</p>";
                    }
                }
            } catch (Exception $e) {
                if (!$silent) {
                    echo "<p style='color: red;'>❌ 添加SMTP设置失败: $key - " . $e->getMessage() . "</p>";
                }
            }
        }
    }
    
    /**
     * 获取SMTP设置描述
     */
    private function getSMTPDescription($key) {
        $descriptions = [
            'smtp_enabled' => '是否启用SMTP邮件发送',
            'smtp_host' => 'SMTP服务器地址',
            'smtp_port' => 'SMTP服务器端口',
            'smtp_username' => 'SMTP用户名（发件邮箱）',
            'smtp_password' => 'SMTP密码或授权码',
            'smtp_secure' => 'SMTP安全连接类型（ssl/tls）',
            'smtp_from_name' => '发件人显示名称',
            'smtp_debug' => 'SMTP调试模式（0-3）'
        ];
        
        return $descriptions[$key] ?? '';
    }
}

/**
 * 执行自动数据库升级 - 用于安装时调用
 */
function autoUpgradeDatabase() {
    try {
        $upgrader = new DatabaseUpgrade(true); // 静默模式
        return $upgrader->upgrade(true);
    } catch (Exception $e) {
        error_log("Auto database upgrade failed: " . $e->getMessage());
        return false;
    }
}

/**
 * 安装时自动执行数据库升级 - 全局函数
 */
function autoUpgradeOnInstall() {
    try {
        // 检查是否是首次安装（没有version表或version表为空）
        $version_exists = false;
        try {
            $db = Database::getInstance()->getConnection();
            $db->querySingle("SELECT COUNT(*) FROM database_versions");
            $version_exists = true;
        } catch (Exception $e) {
            // 表不存在，是首次安装
        }
        
        if (!$version_exists) {
            // 首次安装，静默执行升级
            autoUpgradeDatabase();
        }
    } catch (Exception $e) {
        // 静默处理错误，不影响正常安装
        error_log("Auto upgrade on install failed: " . $e->getMessage());
    }
}