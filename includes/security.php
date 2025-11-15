<?php
/**
 * 安全防护功能类
 */

class Security {
    private static $max_attempts = 5; // 最大尝试次数
    private static $lockout_time = 900; // 锁定时间（15分钟）
    
    /**
     * 记录登录失败
     */
    public static function recordFailedLogin($ip, $username, $type = 'user') {
        $db = Database::getInstance()->getConnection();
        
        // 创建登录失败记录表
        $db->exec("CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            username TEXT NOT NULL,
            type TEXT NOT NULL,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
        
        // 记录失败尝试
        $stmt = $db->prepare("INSERT INTO login_attempts (ip_address, username, type) VALUES (?, ?, ?)");
        $stmt->bindValue(1, $ip, SQLITE3_TEXT);
        $stmt->bindValue(2, $username, SQLITE3_TEXT);
        $stmt->bindValue(3, $type, SQLITE3_TEXT);
        $stmt->execute();
        
        // 清理过期记录（保留24小时内的记录）
        $db->exec("DELETE FROM login_attempts WHERE attempt_time < datetime('now', '-24 hours')");
    }
    
    /**
     * 检查IP是否被锁定
     */
    public static function isIpLocked($ip, $type = 'user') {
        $db = Database::getInstance()->getConnection();
        
        // 检查表是否存在
        $table_exists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'");
        if (!$table_exists) {
            return false;
        }
        
        // 计算锁定时间点
        $lockout_start = date('Y-m-d H:i:s', time() - self::$lockout_time);
        
        // 查询指定时间内的失败次数
        $stmt = $db->prepare("SELECT COUNT(*) FROM login_attempts WHERE ip_address = ? AND type = ? AND attempt_time > ?");
        $stmt->bindValue(1, $ip, SQLITE3_TEXT);
        $stmt->bindValue(2, $type, SQLITE3_TEXT);
        $stmt->bindValue(3, $lockout_start, SQLITE3_TEXT);
        $result = $stmt->execute();
        $count = $result->fetchArray(SQLITE3_NUM)[0];
        
        return $count >= self::$max_attempts;
    }
    
    /**
     * 获取剩余锁定时间
     */
    public static function getRemainingLockTime($ip, $type = 'user') {
        $db = Database::getInstance()->getConnection();
        
        // 检查表是否存在
        $table_exists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'");
        if (!$table_exists) {
            return 0;
        }
        
        // 获取最近一次失败尝试的时间
        $stmt = $db->prepare("SELECT attempt_time FROM login_attempts WHERE ip_address = ? AND type = ? ORDER BY attempt_time DESC LIMIT 1");
        $stmt->bindValue(1, $ip, SQLITE3_TEXT);
        $stmt->bindValue(2, $type, SQLITE3_TEXT);
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        
        if (!$row) {
            return 0;
        }
        
        $last_attempt = strtotime($row['attempt_time']);
        $unlock_time = $last_attempt + self::$lockout_time;
        $remaining = $unlock_time - time();
        
        return max(0, $remaining);
    }
    
    /**
     * 清除IP的失败记录（登录成功后调用）
     */
    public static function clearFailedAttempts($ip, $type = 'user') {
        $db = Database::getInstance()->getConnection();
        
        // 检查表是否存在
        $table_exists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'");
        if (!$table_exists) {
            return;
        }
        
        $stmt = $db->prepare("DELETE FROM login_attempts WHERE ip_address = ? AND type = ?");
        $stmt->bindValue(1, $ip, SQLITE3_TEXT);
        $stmt->bindValue(2, $type, SQLITE3_TEXT);
        $stmt->execute();
    }
    
    /**
     * 格式化剩余时间
     */
    public static function formatRemainingTime($seconds) {
        if ($seconds <= 0) {
            return '0秒';
        }
        
        $minutes = floor($seconds / 60);
        $seconds = $seconds % 60;
        
        if ($minutes > 0) {
            return $minutes . '分' . $seconds . '秒';
        } else {
            return $seconds . '秒';
        }
    }
    
    /**
     * 生成CSRF令牌
     */
    public static function generateCSRFToken() {
        if (session_status() === PHP_SESSION_NONE) {
            session_start();
        }
        
        if (!isset($_SESSION['csrf_token'])) {
            $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
        }
        
        return $_SESSION['csrf_token'];
    }
    
    /**
     * 验证CSRF令牌
     */
    public static function validateCSRFToken($token) {
        if (session_status() === PHP_SESSION_NONE) {
            session_start();
        }
        
        if (!isset($_SESSION['csrf_token'])) {
            return false;
        }
        
        return hash_equals($_SESSION['csrf_token'], $token);
    }
    
    /**
     * 生成一次性操作令牌（用于防止重放攻击）
     * @param string $action 操作类型
     * @param int $record_id 记录ID
     * @return string 令牌
     */
    public static function generateActionToken($action, $record_id = 0) {
        if (session_status() === PHP_SESSION_NONE) {
            session_start();
        }
        
        $token = bin2hex(random_bytes(16));
        $key = 'action_token_' . $action . '_' . $record_id;
        
        // 存储令牌和时间戳
        $_SESSION[$key] = [
            'token' => $token,
            'timestamp' => time()
        ];
        
        return $token;
    }
    
    /**
     * 验证并消费一次性操作令牌
     * @param string $action 操作类型
     * @param int $record_id 记录ID
     * @param string $token 提供的令牌
     * @return bool 是否验证通过
     */
    public static function validateAndConsumeActionToken($action, $record_id, $token) {
        if (session_status() === PHP_SESSION_NONE) {
            session_start();
        }
        
        $key = 'action_token_' . $action . '_' . $record_id;
        
        if (!isset($_SESSION[$key])) {
            return false;
        }
        
        $stored = $_SESSION[$key];
        
        // 检查令牌是否过期（5分钟有效期）
        if (time() - $stored['timestamp'] > 300) {
            unset($_SESSION[$key]);
            return false;
        }
        
        // 验证令牌
        if (!hash_equals($stored['token'], $token)) {
            return false;
        }
        
        // 消费令牌（删除，防止重复使用）
        unset($_SESSION[$key]);
        
        return true;
    }
    
    /**
     * 检查操作频率限制
     * @param int $user_id 用户ID
     * @param string $action 操作类型
     * @param int $max_operations 最大操作次数
     * @param int $time_window 时间窗口（秒）
     * @return array ['allowed' => bool, 'remaining_time' => int]
     */
    public static function checkOperationRateLimit($user_id, $action, $max_operations = 10, $time_window = 60) {
        $db = Database::getInstance()->getConnection();
        
        // 确保表和索引存在
        self::ensureOperationLogsTable($db);
        
        // 清理过期记录
        $db->exec("DELETE FROM operation_logs WHERE operation_time < datetime('now', '-1 hour')");
        
        // 检查时间窗口内的操作次数
        $window_start = date('Y-m-d H:i:s', time() - $time_window);
        $stmt = $db->prepare("SELECT COUNT(*) as count, MIN(operation_time) as first_op 
                              FROM operation_logs 
                              WHERE user_id = ? AND action = ? AND operation_time > ?");
        $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
        $stmt->bindValue(2, $action, SQLITE3_TEXT);
        $stmt->bindValue(3, $window_start, SQLITE3_TEXT);
        $result = $stmt->execute();
        $row = $result->fetchArray(SQLITE3_ASSOC);
        
        $count = intval($row['count']);
        
        if ($count >= $max_operations) {
            // 计算需要等待的时间
            $first_op_time = strtotime($row['first_op']);
            $remaining_time = $time_window - (time() - $first_op_time);
            
            return [
                'allowed' => false,
                'remaining_time' => max(0, $remaining_time),
                'message' => "操作过于频繁，请在 " . max(1, ceil($remaining_time)) . " 秒后重试"
            ];
        }
        
        return [
            'allowed' => true,
            'remaining_time' => 0,
            'message' => ''
        ];
    }
    
    /**
     * 记录操作
     * @param int $user_id 用户ID
     * @param string $action 操作类型
     */
    public static function logOperation($user_id, $action) {
        $db = Database::getInstance()->getConnection();
        
        // 确保表存在
        self::ensureOperationLogsTable($db);
        
        $ip = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
        
        $stmt = $db->prepare("INSERT INTO operation_logs (user_id, action, ip_address) VALUES (?, ?, ?)");
        $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
        $stmt->bindValue(2, $action, SQLITE3_TEXT);
        $stmt->bindValue(3, $ip, SQLITE3_TEXT);
        $stmt->execute();
    }
    
    /**
     * 确保 operation_logs 表和索引存在
     * @param SQLite3 $db 数据库连接
     */
    private static function ensureOperationLogsTable($db) {
        static $initialized = false;
        
        if ($initialized) {
            return;
        }
        
        try {
            // 检查表是否存在
            $tableExists = $db->querySingle(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='operation_logs'"
            );
            
            if (!$tableExists) {
                // 创建表
                $db->exec("CREATE TABLE IF NOT EXISTS operation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    ip_address TEXT,
                    operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )");
                
                // 创建索引
                $db->exec("CREATE INDEX IF NOT EXISTS idx_user_action ON operation_logs(user_id, action, operation_time)");
                
                error_log("✓ Security: 已创建 operation_logs 表和索引");
            } else {
                // 表存在，确保索引存在
                $db->exec("CREATE INDEX IF NOT EXISTS idx_user_action ON operation_logs(user_id, action, operation_time)");
            }
            
            $initialized = true;
        } catch (Exception $e) {
            error_log("创建 operation_logs 表失败: " . $e->getMessage());
            throw $e;
        }
    }
}
?>