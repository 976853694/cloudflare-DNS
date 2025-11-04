<?php
/**
 * 数据库升级脚本
 * 
 * 使用说明：
 * 1. 访问此文件可以自动检测和升级数据库结构
 * 2. 新功能需要的数据库变更必须添加到此脚本中
 * 3. 脚本会自动检测现有结构，只创建缺失的表和字段
 * 
 * 版本管理：
 * - 每次数据库结构变更时，增加版本号
 * - 在 $database_versions 数组中添加新的升级规则
 */

// 设置错误报告
error_reporting(E_ALL);
ini_set('display_errors', 1);

// 包含数据库类
require_once __DIR__ . '/database.php';

class DatabaseUpgrade {
    private $db;
    private $current_version = '1.0.0';
    
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
    
    public function __construct() {
        try {
            $this->db = Database::getInstance()->getConnection();
            echo "<h2>数据库升级工具</h2>";
        } catch (Exception $e) {
            die("数据库连接失败: " . $e->getMessage());
        }
    }
    
    /**
     * 执行数据库升级
     */
    public function upgrade() {
        echo "<div style='font-family: monospace; background: #f5f5f5; padding: 20px;'>";
        
        // 创建版本表
        $this->createVersionTable();
        
        // 获取当前数据库版本
        $current_db_version = $this->getCurrentDatabaseVersion();
        echo "<p><strong>当前数据库版本:</strong> $current_db_version</p>";
        echo "<p><strong>目标版本:</strong> {$this->current_version}</p>";
        
        // 执行升级
        $upgraded = false;
        foreach ($this->database_versions as $version => $method) {
            if (version_compare($current_db_version, $version, '<')) {
                echo "<h3>升级到版本 $version</h3>";
                
                try {
                    $this->$method();
                    $this->updateDatabaseVersion($version);
                    echo "<p style='color: green;'>✅ 版本 $version 升级成功</p>";
                    $upgraded = true;
                } catch (Exception $e) {
                    echo "<p style='color: red;'>❌ 版本 $version 升级失败: " . $e->getMessage() . "</p>";
                    break;
                }
            }
        }
        
        if (!$upgraded) {
            echo "<p style='color: blue;'>📋 数据库已是最新版本，无需升级</p>";
        }
        
        // 验证数据库完整性
        $this->validateDatabase();
        
        echo "</div>";
    }
    
    /**
     * 创建版本管理表
     */
    private function createVersionTable() {
        $sql = "CREATE TABLE IF NOT EXISTS database_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            upgraded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )";
        $this->db->exec($sql);
    }
    
    /**
     * 获取当前数据库版本
     */
    private function getCurrentDatabaseVersion() {
        $version = $this->db->querySingle("SELECT version FROM database_versions ORDER BY id DESC LIMIT 1");
        return $version ?: '0.0.0';
    }
    
    /**
     * 更新数据库版本
     */
    private function updateDatabaseVersion($version) {
        $stmt = $this->db->prepare("INSERT INTO database_versions (version) VALUES (?)");
        $stmt->bindValue(1, $version, SQLITE3_TEXT);
        $stmt->execute();
    }
    
    /**
     * 版本 1.0.0 - 创建基础表
     */
    private function createBaseTables() {
        echo "<p>创建基础表...</p>";
        
        // 用户表
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
        
        // 管理员表
        $this->db->exec("CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
        
        // 域名表
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
        
        // DNS记录表
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (domain_id) REFERENCES domains(id)
        )");
        
        // 系统设置表
        $this->db->exec("CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT NOT NULL UNIQUE,
            setting_value TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
        
        // 卡密表
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
        
        // 卡密使用记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS card_key_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_key_id INTEGER,
            user_id INTEGER,
            points_added INTEGER,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (card_key_id) REFERENCES card_keys(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )");
        
        // 操作日志表
        $this->db->exec("CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
        
        // DNS记录类型表
        $this->db->exec("CREATE TABLE IF NOT EXISTS dns_record_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_name VARCHAR(10) NOT NULL UNIQUE,
            display_name VARCHAR(50) NOT NULL,
            description TEXT,
            enabled INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )");
        
        // Cloudflare账户表
        $this->db->exec("CREATE TABLE IF NOT EXISTS cloudflare_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            api_key TEXT NOT NULL,
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
        
        $this->insertDefaultSettings();
        $this->insertDefaultDNSTypes();
    }
    
    /**
     * 版本 1.1.0 - 添加用户OAuth字段
     */
    private function addUserOAuthFields() {
        echo "<p>添加用户OAuth相关字段...</p>";
        
        $this->addColumnIfNotExists('users', 'github_id', 'TEXT');
        $this->addColumnIfNotExists('users', 'github_username', 'TEXT');
        $this->addColumnIfNotExists('users', 'avatar_url', 'TEXT');
        $this->addColumnIfNotExists('users', 'oauth_provider', 'TEXT');
        $this->addColumnIfNotExists('users', 'github_bonus_received', 'INTEGER DEFAULT 0');
        $this->addColumnIfNotExists('users', 'last_login_at', 'TIMESTAMP');
        $this->addColumnIfNotExists('users', 'login_count', 'INTEGER DEFAULT 0');
    }
    
    /**
     * 版本 1.2.0 - 添加邀请系统
     */
    private function addInvitationSystem() {
        echo "<p>创建邀请系统表...</p>";
        
        // 邀请表
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
            max_uses INTEGER DEFAULT 0,
            description TEXT,
            FOREIGN KEY (inviter_id) REFERENCES users(id)
        )");
        
        // 邀请使用记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS invitation_uses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invitation_id INTEGER NOT NULL,
            invitee_id INTEGER NOT NULL,
            reward_points INTEGER DEFAULT 0,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (invitation_id) REFERENCES invitations(id),
            FOREIGN KEY (invitee_id) REFERENCES users(id)
        )");
    }
    
    /**
     * 版本 1.3.0 - 添加公告系统
     */
    private function addAnnouncementSystem() {
        echo "<p>创建公告系统表...</p>";
        
        // 公告表
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
        
        // 用户公告查看记录表
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
    }
    
    /**
     * 版本 1.4.0 - 添加安全相关表
     */
    private function addSecurityTables() {
        echo "<p>创建安全相关表...</p>";
        
        // 禁用前缀表
        $this->db->exec("CREATE TABLE IF NOT EXISTS blocked_prefixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prefix TEXT NOT NULL UNIQUE,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )");
        
        // 登录尝试记录表
        $this->db->exec("CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            username TEXT NOT NULL,
            type TEXT NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success INTEGER DEFAULT 0,
            user_type TEXT DEFAULT 'user',
            user_agent TEXT
        )");
    }
    
    /**
     * 版本 1.5.0 - 添加数据库索引
     */
    private function addIndexes() {
        echo "<p>创建数据库索引...</p>";
        
        $indexes = [
            'idx_users_github_id' => 'CREATE INDEX IF NOT EXISTS idx_users_github_id ON users(github_id)',
            'idx_users_oauth_provider' => 'CREATE INDEX IF NOT EXISTS idx_users_oauth_provider ON users(oauth_provider)',
            'idx_dns_records_user_id' => 'CREATE INDEX IF NOT EXISTS idx_dns_records_user_id ON dns_records(user_id)',
            'idx_dns_records_domain_id' => 'CREATE INDEX IF NOT EXISTS idx_dns_records_domain_id ON dns_records(domain_id)',
            'idx_invitations_inviter_id' => 'CREATE INDEX IF NOT EXISTS idx_invitations_inviter_id ON invitations(inviter_id)',
            'idx_invitation_uses_invitation_id' => 'CREATE INDEX IF NOT EXISTS idx_invitation_uses_invitation_id ON invitation_uses(invitation_id)',
            'idx_login_attempts_ip' => 'CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address)',
            'idx_action_logs_user' => 'CREATE INDEX IF NOT EXISTS idx_action_logs_user ON action_logs(user_type, user_id)',
            'idx_user_announcement_views_user' => 'CREATE INDEX IF NOT EXISTS idx_user_announcement_views_user ON user_announcement_views(user_id)'
        ];
        
        foreach ($indexes as $name => $sql) {
            try {
                $this->db->exec($sql);
            } catch (Exception $e) {
                echo "<p style='color: orange;'>⚠️ 索引 $name 创建失败: " . $e->getMessage() . "</p>";
            }
        }
    }
    
    /**
     * 版本 1.6.0 - 添加缺失字段
     */
    private function addMissingFields() {
        echo "<p>添加缺失的字段...</p>";
        
        // 域名表字段
        $this->addColumnIfNotExists('domains', 'account_id', 'TEXT');
        $this->addColumnIfNotExists('domains', 'is_default', 'INTEGER DEFAULT 0');
        
        // DNS记录表字段
        $this->addColumnIfNotExists('dns_records', 'remark', 'TEXT DEFAULT \'\'');
        $this->addColumnIfNotExists('dns_records', 'ttl', 'INTEGER DEFAULT 1');
        $this->addColumnIfNotExists('dns_records', 'priority', 'INTEGER');
        
        // 公告表字段
        $this->addColumnIfNotExists('announcements', 'target_user_ids', 'TEXT DEFAULT NULL');
        $this->addColumnIfNotExists('announcements', 'auto_close_seconds', 'INTEGER DEFAULT 0');
    }
    
    /**
     * 检查字段是否存在，不存在则添加
     */
    private function addColumnIfNotExists($table, $column, $definition) {
        $columns = [];
        $result = $this->db->query("PRAGMA table_info($table)");
        if ($result) {
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $columns[] = $row['name'];
            }
            
            if (!in_array($column, $columns)) {
                try {
                    $this->db->exec("ALTER TABLE $table ADD COLUMN $column $definition");
                    echo "<p style='color: green;'>✅ 添加字段 $table.$column</p>";
                } catch (Exception $e) {
                    echo "<p style='color: red;'>❌ 添加字段 $table.$column 失败: " . $e->getMessage() . "</p>";
                }
            }
        }
    }
    
    /**
     * 插入默认设置
     */
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
            $stmt = $this->db->prepare("SELECT COUNT(*) FROM settings WHERE setting_key = ?");
            $stmt->bindValue(1, $setting[0], SQLITE3_TEXT);
            $result = $stmt->execute();
            $exists = $result->fetchArray(SQLITE3_NUM)[0];
            
            if (!$exists) {
                $stmt = $this->db->prepare("INSERT INTO settings (setting_key, setting_value, description) VALUES (?, ?, ?)");
                $stmt->bindValue(1, $setting[0], SQLITE3_TEXT);
                $stmt->bindValue(2, $setting[1], SQLITE3_TEXT);
                $stmt->bindValue(3, $setting[2], SQLITE3_TEXT);
                $stmt->execute();
            }
        }
    }
    
    /**
     * 插入默认DNS类型
     */
    private function insertDefaultDNSTypes() {
        $default_types = [
            ['A', 'A记录', 'IPv4地址记录', 1],
            ['AAAA', 'AAAA记录', 'IPv6地址记录', 1],
            ['CNAME', 'CNAME记录', '别名记录', 1],
            ['MX', 'MX记录', '邮件交换记录', 1],
            ['TXT', 'TXT记录', '文本记录', 1],
            ['NS', 'NS记录', '名称服务器记录', 0],
            ['PTR', 'PTR记录', '反向解析记录', 0],
            ['SRV', 'SRV记录', '服务记录', 0],
            ['CAA', 'CAA记录', '证书颁发机构授权记录', 0]
        ];
        
        foreach ($default_types as $type) {
            $stmt = $this->db->prepare("SELECT COUNT(*) FROM dns_record_types WHERE type_name = ?");
            $stmt->bindValue(1, $type[0], SQLITE3_TEXT);
            $result = $stmt->execute();
            $exists = $result->fetchArray(SQLITE3_NUM)[0];
            
            if (!$exists) {
                $stmt = $this->db->prepare("INSERT INTO dns_record_types (type_name, display_name, description, enabled) VALUES (?, ?, ?, ?)");
                $stmt->bindValue(1, $type[0], SQLITE3_TEXT);
                $stmt->bindValue(2, $type[1], SQLITE3_TEXT);
                $stmt->bindValue(3, $type[2], SQLITE3_TEXT);
                $stmt->bindValue(4, $type[3], SQLITE3_INTEGER);
                $stmt->execute();
            }
        }
    }
    
    /**
     * 验证数据库完整性
     */
    private function validateDatabase() {
        echo "<h3>数据库完整性验证</h3>";
        
        $required_tables = [
            'users', 'admins', 'domains', 'dns_records', 'settings',
            'card_keys', 'card_key_usage', 'action_logs', 'dns_record_types',
            'invitations', 'invitation_uses', 'announcements', 'user_announcement_views',
            'blocked_prefixes', 'login_attempts', 'cloudflare_accounts', 'database_versions'
        ];
        
        $existing_tables = [];
        $result = $this->db->query("SELECT name FROM sqlite_master WHERE type='table'");
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $existing_tables[] = $row['name'];
        }
        
        $missing_tables = array_diff($required_tables, $existing_tables);
        
        if (empty($missing_tables)) {
            echo "<p style='color: green;'>✅ 所有必需的表都存在</p>";
        } else {
            echo "<p style='color: red;'>❌ 缺失表: " . implode(', ', $missing_tables) . "</p>";
        }
        
        // 验证关键字段
        $critical_fields = [
            'users' => ['github_id', 'points', 'status'],
            'invitations' => ['last_used_at', 'is_active', 'use_count'],
            'card_keys' => ['used_count', 'status'],
            'announcements' => ['is_active', 'type', 'target_user_ids', 'auto_close_seconds'],
            'login_attempts' => ['success', 'user_type']
        ];
        
        foreach ($critical_fields as $table => $fields) {
            if (in_array($table, $existing_tables)) {
                $table_columns = [];
                $result = $this->db->query("PRAGMA table_info($table)");
                while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                    $table_columns[] = $row['name'];
                }
                
                $missing_fields = array_diff($fields, $table_columns);
                if (empty($missing_fields)) {
                    echo "<p style='color: green;'>✅ 表 $table 字段完整</p>";
                } else {
                    echo "<p style='color: red;'>❌ 表 $table 缺失字段: " . implode(', ', $missing_fields) . "</p>";
                }
            }
        }
        
        echo "<p><strong>数据库升级完成！</strong></p>";
    }
}

// 执行升级
if (basename($_SERVER['PHP_SELF']) === 'database_upgrade.php') {
    $upgrader = new DatabaseUpgrade();
    $upgrader->upgrade();
}
?>