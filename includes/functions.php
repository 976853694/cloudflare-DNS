<?php
/**
 * 公共函数库
 */

/**
 * 安全地获取POST数据
 */
function getPost($key, $default = '') {
    if (!isset($_POST[$key])) {
        return $default;
    }
    
    $value = $_POST[$key];
    
    // 如果是数组，递归处理每个元素
    if (is_array($value)) {
        return array_map('trim', $value);
    }
    
    // 如果是字符串，直接trim
    return trim($value);
}

/**
 * 安全地获取GET数据
 */
function getGet($key, $default = '') {
    return isset($_GET[$key]) ? trim($_GET[$key]) : $default;
}

/**
 * 重定向函数
 */
function redirect($url) {
    header("Location: $url");
    exit;
}

/**
 * 显示成功消息
 */
function showSuccess($message) {
    $_SESSION['success_message'] = $message;
}

/**
 * 显示错误消息
 */
function showError($message) {
    $_SESSION['error_message'] = $message;
}

/**
 * 显示警告消息
 */
function showWarning($message) {
    $_SESSION['warning_message'] = $message;
}

/**
 * 获取并清除消息
 */
function getMessages() {
    $messages = [];
    if (isset($_SESSION['success_message'])) {
        $messages['success'] = $_SESSION['success_message'];
        unset($_SESSION['success_message']);
    }
    if (isset($_SESSION['error_message'])) {
        $messages['error'] = $_SESSION['error_message'];
        unset($_SESSION['error_message']);
    }
    if (isset($_SESSION['warning_message'])) {
        $messages['warning'] = $_SESSION['warning_message'];
        unset($_SESSION['warning_message']);
    }
    return $messages;
}

/**
 * 验证邮箱格式
 */
function isValidEmail($email) {
    return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;
}

/**
 * 验证域名格式
 */
function isValidDomain($domain) {
    return preg_match('/^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$/', $domain);
}

/**
 * 生成随机字符串
 */
function generateRandomString($length = 10) {
    return substr(str_shuffle(str_repeat($x='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', ceil($length/strlen($x)) )),1,$length);
}

/**
 * 格式化时间
 */
function formatTime($timestamp) {
    return date('Y-m-d H:i:s', strtotime($timestamp));
}

/**
 * 获取启用的DNS记录类型
 */
function getEnabledDNSTypes() {
    $db = Database::getInstance()->getConnection();
    $types = [];
    
    $result = $db->query("SELECT * FROM dns_record_types WHERE enabled = 1 ORDER BY type_name");
    while ($row = $result->fetch(PDO::FETCH_ASSOC)) {
        $types[] = $row;
    }
    
    return $types;
}

/**
 * 检查DNS记录类型是否启用
 */
function isDNSTypeEnabled($type) {
    $db = Database::getInstance()->getConnection();
    $stmt = $db->query("SELECT enabled FROM dns_record_types WHERE type_name = '$type'");
    $enabled = $stmt ? $stmt->fetchColumn() : false;
    return (bool)$enabled;
}

/**
 * 检查用户是否登录
 */
function checkUserLogin() {
    if (!isset($_SESSION['user_logged_in']) || !isset($_SESSION['user_id'])) {
        redirect('/user/login.php');
    }
}

/**
 * 检查管理员是否登录
 */
function checkAdminLogin() {
    if (!isset($_SESSION['admin_logged_in']) || !isset($_SESSION['admin_id'])) {
        redirect('/admin/login.php');
    }
}

/**
 * 获取系统设置
 */
function getSetting($key, $default = '') {
    $db = Database::getInstance()->getConnection();
    $stmt = $db->query("SELECT setting_value FROM settings WHERE setting_key = '$key'");
    $value = $stmt ? $stmt->fetchColumn() : null;
    return $value !== null ? $value : $default;
}

/**
 * 更新系统设置
 */
function updateSetting($key, $value) {
    $db = Database::getInstance()->getConnection();
    
    // 检查设置是否存在
    $stmt = $db->prepare("SELECT COUNT(*) FROM settings WHERE setting_key = ?");
    $stmt->execute([$key]);
    $exists = $stmt->fetchColumn();
    
    if ($exists) {
        // 更新现有设置
        $stmt = $db->prepare("UPDATE settings SET setting_value = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_key = ?");
        return $stmt->execute([$value, $key]);
    } else {
        // 插入新设置
        $stmt = $db->prepare("INSERT INTO settings (setting_key, setting_value, created_at, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)");
        return $stmt->execute([$key, $value]);
    }
}

/**
 * 记录操作日志
 */
function logAction($user_type, $user_id, $action, $details = '') {
    $db = Database::getInstance()->getConnection();
    
    // 创建日志表（如果不存在）
    $db->exec("CREATE TABLE IF NOT EXISTS action_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_type TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )");
    
    $stmt = $db->prepare("INSERT INTO action_logs (user_type, user_id, action, details, ip_address) VALUES (?, ?, ?, ?, ?)");
    $stmt->execute([$user_type, $user_id, $action, $details, $_SERVER['REMOTE_ADDR'] ?? '']);
}

/**
 * 获取用户需要显示的公告
 */
function getUserAnnouncements($user_id) {
    $db = Database::getInstance()->getConnection();
    $announcements = [];
    
    // 获取所有启用的公告
    $result = $db->query("SELECT * FROM announcements WHERE is_active = 1 ORDER BY created_at DESC");
    
    while ($row = $result->fetch(PDO::FETCH_ASSOC)) {
        $announcement_id = $row['id'];
        $show_frequency = $row['show_frequency'];
        $interval_hours = $row['interval_hours'];
        
        // 检查用户是否已查看过此公告
        $stmt = $db->query("
            SELECT * FROM user_announcement_views 
            WHERE user_id = $user_id AND announcement_id = $announcement_id
        ");
        $view_record = $stmt ? $stmt->fetch(PDO::FETCH_ASSOC) : false;
        
        $should_show = false;
        
        switch ($show_frequency) {
            case 'once':
                // 仅显示一次，如果没有查看记录则显示
                $should_show = !$view_record;
                break;
                
            case 'login':
                // 每次登录都显示
                $should_show = true;
                break;
                
            case 'daily':
                // 每日显示一次
                if (!$view_record) {
                    $should_show = true;
                } else {
                    $last_viewed = strtotime($view_record['last_viewed_at']);
                    $now = time();
                    $hours_passed = ($now - $last_viewed) / 3600;
                    $should_show = $hours_passed >= 24;
                }
                break;
                
            case 'interval':
                // 自定义间隔
                if (!$view_record) {
                    $should_show = true;
                } else {
                    $last_viewed = strtotime($view_record['last_viewed_at']);
                    $now = time();
                    $hours_passed = ($now - $last_viewed) / 3600;
                    $should_show = $hours_passed >= $interval_hours;
                }
                break;
        }
        
        if ($should_show) {
            $announcements[] = $row;
        }
    }
    
    return $announcements;
}

/**
 * 记录用户查看公告
 */
function markAnnouncementViewed($user_id, $announcement_id) {
    $db = Database::getInstance()->getConnection();
    
    // 检查是否已有记录
    $existing = $db->querySingle("
        SELECT * FROM user_announcement_views 
        WHERE user_id = $user_id AND announcement_id = $announcement_id
    ", true);
    
    if ($existing) {
        // 更新查看时间和次数
        $new_count = $existing['view_count'] + 1;
        $stmt = $db->prepare("
            UPDATE user_announcement_views 
            SET last_viewed_at = CURRENT_TIMESTAMP, view_count = ? 
            WHERE user_id = ? AND announcement_id = ?
        ");
        $stmt->execute([$new_count, $user_id, $announcement_id]);
    } else {
        // 创建新记录
        $stmt = $db->prepare("
            INSERT INTO user_announcement_views (user_id, announcement_id, last_viewed_at, view_count) 
            VALUES (?, ?, CURRENT_TIMESTAMP, 1)
        ");
        $stmt->execute([$user_id, $announcement_id]);
    }
}

/**
 * 检查DNS前缀是否被拦截
 */
function isSubdomainBlocked($subdomain) {
    $db = Database::getInstance()->getConnection();
    
    // 将子域名转换为小写进行比较
    $subdomain = strtolower(trim($subdomain));
    
    // 检查是否有启用的拦截前缀匹配
    $stmt = $db->query("
        SELECT COUNT(*) FROM blocked_prefixes 
        WHERE is_active = 1 AND prefix = '$subdomain'
    ");
    $result = $stmt ? $stmt->fetchColumn() : 0;
    
    return $result > 0;
}

/**
 * 获取所有启用的拦截前缀
 */
function getBlockedPrefixes() {
    $db = Database::getInstance()->getConnection();
    $prefixes = [];
    
    $result = $db->query("SELECT prefix FROM blocked_prefixes WHERE is_active = 1 ORDER BY prefix ASC");
    while ($row = $result->fetch(PDO::FETCH_ASSOC)) {
        $prefixes[] = $row['prefix'];
    }
    
    return $prefixes;
}