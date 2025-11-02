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
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $types[] = $row;
    }
    
    return $types;
}

/**
 * 检查DNS记录类型是否启用
 */
function isDNSTypeEnabled($type) {
    $db = Database::getInstance()->getConnection();
    $enabled = $db->querySingle("SELECT enabled FROM dns_record_types WHERE type_name = '$type'");
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
    $value = $db->querySingle("SELECT setting_value FROM settings WHERE setting_key = '$key'");
    return $value !== null ? $value : $default;
}

/**
 * 更新系统设置
 */
function updateSetting($key, $value) {
    $db = Database::getInstance()->getConnection();
    
    // 检查设置是否存在
    $stmt = $db->prepare("SELECT COUNT(*) FROM settings WHERE setting_key = ?");
    $stmt->bindValue(1, $key, SQLITE3_TEXT);
    $result = $stmt->execute();
    $exists = $result->fetchArray(SQLITE3_NUM)[0];
    
    if ($exists) {
        // 更新现有设置
        $stmt = $db->prepare("UPDATE settings SET setting_value = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_key = ?");
        $stmt->bindValue(1, $value, SQLITE3_TEXT);
        $stmt->bindValue(2, $key, SQLITE3_TEXT);
        return $stmt->execute();
    } else {
        // 插入新设置
        $stmt = $db->prepare("INSERT INTO settings (setting_key, setting_value, created_at, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)");
        $stmt->bindValue(1, $key, SQLITE3_TEXT);
        $stmt->bindValue(2, $value, SQLITE3_TEXT);
        return $stmt->execute();
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
    $stmt->bindValue(1, $user_type, SQLITE3_TEXT);
    $stmt->bindValue(2, $user_id, SQLITE3_INTEGER);
    $stmt->bindValue(3, $action, SQLITE3_TEXT);
    $stmt->bindValue(4, $details, SQLITE3_TEXT);
    $stmt->bindValue(5, $_SERVER['REMOTE_ADDR'] ?? '', SQLITE3_TEXT);
    $stmt->execute();
}

/**
 * 获取用户需要显示的公告
 */
function getUserAnnouncements($user_id) {
    $db = Database::getInstance()->getConnection();
    $announcements = [];
    
    // 获取所有启用的公告
    $result = $db->query("SELECT * FROM announcements WHERE is_active = 1 ORDER BY created_at DESC");
    
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $announcement_id = $row['id'];
        $show_frequency = $row['show_frequency'];
        $interval_hours = $row['interval_hours'];
        $target_user_ids = $row['target_user_ids'];
        
        // 检查是否为用户专属公告
        if (!empty($target_user_ids)) {
            // 将目标用户ID字符串转换为数组
            $target_ids = array_map('trim', explode(',', $target_user_ids));
            // 如果当前用户不在目标用户列表中，跳过此公告
            if (!in_array((string)$user_id, $target_ids)) {
                continue;
            }
        }
        
        // 检查用户是否已查看过此公告
        $view_record = $db->querySingle("
            SELECT * FROM user_announcement_views 
            WHERE user_id = $user_id AND announcement_id = $announcement_id
        ", true);
        
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
        $stmt->bindValue(1, $new_count, SQLITE3_INTEGER);
        $stmt->bindValue(2, $user_id, SQLITE3_INTEGER);
        $stmt->bindValue(3, $announcement_id, SQLITE3_INTEGER);
        $stmt->execute();
    } else {
        // 创建新记录
        $stmt = $db->prepare("
            INSERT INTO user_announcement_views (user_id, announcement_id, last_viewed_at, view_count) 
            VALUES (?, ?, CURRENT_TIMESTAMP, 1)
        ");
        $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
        $stmt->bindValue(2, $announcement_id, SQLITE3_INTEGER);
        $stmt->execute();
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
    $result = $db->querySingle("
        SELECT COUNT(*) FROM blocked_prefixes 
        WHERE is_active = 1 AND prefix = '$subdomain'
    ");
    
    return $result > 0;
}

/**
 * 获取所有启用的拦截前缀
 */
function getBlockedPrefixes() {
    $db = Database::getInstance()->getConnection();
    $prefixes = [];
    
    $result = $db->query("SELECT prefix FROM blocked_prefixes WHERE is_active = 1 ORDER BY prefix ASC");
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $prefixes[] = $row['prefix'];
    }
    
    return $prefixes;
}

/**
 * 获取用户组信息
 * @param int $user_id 用户ID
 * @return array|null 用户组信息
 */
function getUserGroup($user_id) {
    require_once __DIR__ . '/user_groups.php';
    $manager = new UserGroupManager();
    return $manager->getUserGroup($user_id);
}

/**
 * 检查用户是否有权限访问指定域名
 * @param int $user_id 用户ID
 * @param int $domain_id 域名ID
 * @return bool
 */
function checkUserDomainPermission($user_id, $domain_id) {
    require_once __DIR__ . '/user_groups.php';
    $manager = new UserGroupManager();
    return $manager->checkDomainPermission($user_id, $domain_id);
}

/**
 * 获取用户可访问的域名列表
 * @param int $user_id 用户ID
 * @return array 域名数组
 */
function getUserAccessibleDomains($user_id) {
    require_once __DIR__ . '/user_groups.php';
    $manager = new UserGroupManager();
    return $manager->getAccessibleDomains($user_id);
}

/**
 * 获取用户添加记录所需积分
 * @param int $user_id 用户ID
 * @return int 所需积分数
 */
function getRequiredPoints($user_id) {
    require_once __DIR__ . '/user_groups.php';
    $manager = new UserGroupManager();
    return $manager->getRequiredPoints($user_id);
}

/**
 * 检查用户是否达到记录数量限制
 * @param int $user_id 用户ID
 * @return bool true=未达到限制，false=已达到限制
 */
function checkUserRecordLimit($user_id) {
    require_once __DIR__ . '/user_groups.php';
    $manager = new UserGroupManager();
    return $manager->checkRecordLimit($user_id);
}

/**
 * 获取用户当前记录数
 * @param int $user_id 用户ID
 * @return int 当前记录数
 */
function getUserCurrentRecordCount($user_id) {
    require_once __DIR__ . '/user_groups.php';
    $manager = new UserGroupManager();
    return $manager->getCurrentRecordCount($user_id);
}

/**
 * 获取域名whois信息
 * @param string $domain 域名
 * @return array|null 返回whois信息，失败返回null
 */
function getDomainWhoisInfo($domain) {
    try {
        $api_url = "https://api.whoiscx.com/whois/?domain=" . urlencode($domain);
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $api_url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 10);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        
        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($http_code == 200 && $response) {
            $data = json_decode($response, true);
            if (isset($data['status']) && $data['status'] == 1 && isset($data['data']['info'])) {
                return $data['data']['info'];
            }
        }
        
        return null;
    } catch (Exception $e) {
        error_log("获取域名whois信息失败: " . $e->getMessage());
        return null;
    }
}

/**
 * 获取域名到期时间
 * @param string $domain 域名
 * @return string|null 返回到期时间，如果是永久域名或获取失败返回null
 */
function getDomainExpirationTime($domain) {
    $whois_info = getDomainWhoisInfo($domain);
    
    if ($whois_info && isset($whois_info['expiration_time']) && !empty($whois_info['expiration_time'])) {
        return $whois_info['expiration_time'];
    }
    
    // 如果没有expiration_time参数，说明是永久域名或无法获取
    return null;
}