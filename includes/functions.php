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

/**
 * 验证DNS记录内容是否有效
 * @param string $type 记录类型
 * @param string $content 记录内容
 * @return array ['valid' => bool, 'message' => string]
 */
function validateDNSRecordContent($type, $content) {
    $content = trim($content);
    
    switch (strtoupper($type)) {
        case 'A':
            // 验证IPv4地址
            if (!filter_var($content, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4)) {
                return ['valid' => false, 'message' => '无效的IPv4地址格式！'];
            }
            
            // 检查是否为私有IP地址（Cloudflare不允许）
            if (isPrivateIP($content)) {
                return ['valid' => false, 'message' => '不能使用私有IP地址（如 10.x.x.x, 172.16-31.x.x, 192.168.x.x）！Cloudflare不支持私有IP地址。'];
            }
            
            // 检查是否为保留IP地址
            if (isReservedIP($content)) {
                return ['valid' => false, 'message' => '不能使用保留IP地址（如 0.0.0.0, 127.x.x.x, 169.254.x.x 等）！'];
            }
            break;
            
        case 'AAAA':
            // 验证IPv6地址
            if (!filter_var($content, FILTER_VALIDATE_IP, FILTER_FLAG_IPV6)) {
                return ['valid' => false, 'message' => '无效的IPv6地址格式！'];
            }
            break;
            
        case 'CNAME':
            // CNAME值应该是域名格式
            if (empty($content) || !preg_match('/^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.?$/', $content)) {
                return ['valid' => false, 'message' => '无效的域名格式！'];
            }
            break;
            
        case 'MX':
            // MX记录格式: "优先级 邮件服务器"
            $parts = preg_split('/\s+/', $content, 2);
            if (count($parts) < 2) {
                return ['valid' => false, 'message' => 'MX记录格式错误！应为：优先级 邮件服务器（如：10 mail.example.com）'];
            }
            if (!is_numeric($parts[0]) || $parts[0] < 0 || $parts[0] > 65535) {
                return ['valid' => false, 'message' => 'MX记录优先级必须是0-65535之间的数字！'];
            }
            break;
            
        case 'TXT':
            // TXT记录长度限制
            if (strlen($content) > 4096) {
                return ['valid' => false, 'message' => 'TXT记录内容过长！最大支持4096个字符。'];
            }
            break;
    }
    
    return ['valid' => true, 'message' => ''];
}

/**
 * 检查是否为私有IP地址
 * @param string $ip IP地址
 * @return bool
 */
function isPrivateIP($ip) {
    // 使用PHP内置函数检查私有IP
    $ip_long = ip2long($ip);
    
    if ($ip_long === false) {
        return false;
    }
    
    // 私有IP范围:
    // 10.0.0.0 – 10.255.255.255
    // 172.16.0.0 – 172.31.255.255
    // 192.168.0.0 – 192.168.255.255
    
    return (
        ($ip_long >= ip2long('10.0.0.0') && $ip_long <= ip2long('10.255.255.255')) ||
        ($ip_long >= ip2long('172.16.0.0') && $ip_long <= ip2long('172.31.255.255')) ||
        ($ip_long >= ip2long('192.168.0.0') && $ip_long <= ip2long('192.168.255.255'))
    );
}

/**
 * 检查是否为保留IP地址
 * @param string $ip IP地址
 * @return bool
 */
function isReservedIP($ip) {
    $ip_long = ip2long($ip);
    
    if ($ip_long === false) {
        return false;
    }
    
    // 保留IP范围:
    // 0.0.0.0/8 - 当前网络
    // 127.0.0.0/8 - 回环地址
    // 169.254.0.0/16 - 链路本地地址
    // 224.0.0.0/4 - 多播地址
    // 240.0.0.0/4 - 保留地址
    
    return (
        ($ip_long >= ip2long('0.0.0.0') && $ip_long <= ip2long('0.255.255.255')) ||
        ($ip_long >= ip2long('127.0.0.0') && $ip_long <= ip2long('127.255.255.255')) ||
        ($ip_long >= ip2long('169.254.0.0') && $ip_long <= ip2long('169.254.255.255')) ||
        ($ip_long >= ip2long('224.0.0.0') && $ip_long <= ip2long('239.255.255.255')) ||
        ($ip_long >= ip2long('240.0.0.0') && $ip_long <= ip2long('255.255.255.255'))
    );
}

/**
 * 检查DNS记录冲突（本地数据库）
 * @param array $existing_records 现有记录数组
 * @param string $new_type 新记录类型
 * @param string $new_content 新记录内容
 * @return array ['hasConflict' => bool, 'message' => string]
 */
function checkLocalDNSConflict($existing_records, $new_type, $new_content) {
    if (empty($existing_records)) {
        return ['hasConflict' => false, 'message' => ''];
    }
    
    $new_type = strtoupper(trim($new_type));
    $new_content = trim($new_content);
    
    foreach ($existing_records as $record) {
        $record_type = strtoupper(trim($record['type']));
        $record_content = trim($record['content']);
        
        // 检查完全相同的记录（同类型同内容）
        if ($record_type === $new_type && $record_content === $new_content) {
            return [
                'hasConflict' => true,
                'message' => "该DNS记录已存在！类型: {$new_type}, 内容: {$new_content}"
            ];
        }
        
        // 对于A记录，不允许同一子域名有多个不同IP
        if ($new_type === 'A' && $record_type === 'A' && $record_content !== $new_content) {
            return [
                'hasConflict' => true,
                'message' => "该子域名已存在A记录（IP: {$record_content}）！一个子域名只能有一个A记录。如需更换IP，请先删除现有记录。"
            ];
        }
        
        // 对于AAAA记录，不允许同一子域名有多个不同IPv6
        if ($new_type === 'AAAA' && $record_type === 'AAAA' && $record_content !== $new_content) {
            return [
                'hasConflict' => true,
                'message' => "该子域名已存在AAAA记录（IPv6: {$record_content}）！一个子域名只能有一个AAAA记录。如需更换IP，请先删除现有记录。"
            ];
        }
        
        // CNAME记录不能与其他任何记录共存
        if ($new_type === 'CNAME' || $record_type === 'CNAME') {
            return [
                'hasConflict' => true,
                'message' => "CNAME记录不能与其他记录类型共存！该子域名已有 {$record_type} 记录。"
            ];
        }
        
        // 对于MX记录，不允许完全相同的优先级和服务器
        if ($new_type === 'MX' && $record_type === 'MX') {
            // MX记录格式: "优先级 服务器"
            $new_parts = preg_split('/\s+/', $new_content, 2);
            $record_parts = preg_split('/\s+/', $record_content, 2);
            
            if (count($new_parts) >= 2 && count($record_parts) >= 2) {
                if ($new_parts[0] === $record_parts[0] && $new_parts[1] === $record_parts[1]) {
                    return [
                        'hasConflict' => true,
                        'message' => "该MX记录已存在！优先级: {$new_parts[0]}, 服务器: {$new_parts[1]}"
                    ];
                }
            }
        }
    }
    
    return ['hasConflict' => false, 'message' => ''];
}