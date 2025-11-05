<?php
/**
 * 渠道管理主页面
 * 统一管理所有渠道类型
 */
session_start();
require_once __DIR__ . '/../config/database.php';
require_once __DIR__ . '/../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 确保数据库表结构完整
initializeChannelTables($db);

/**
 * 初始化渠道管理相关的数据库表
 */
function initializeChannelTables($db) {
    try {
        // 创建或确保 cloudflare_accounts 表存在
        $db->exec("CREATE TABLE IF NOT EXISTS cloudflare_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            api_key TEXT NOT NULL DEFAULT '',
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            account_name TEXT DEFAULT '',
            description TEXT DEFAULT ''
        )");
        
        // 创建或确保 rainbow_accounts 表存在
        $db->exec("CREATE TABLE IF NOT EXISTS rainbow_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            provider_uid TEXT DEFAULT '',
            api_key TEXT NOT NULL DEFAULT '',
            api_base_url TEXT DEFAULT '',
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            account_name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            description TEXT DEFAULT ''
        )");
        
        // 检查并添加缺失的字段到 cloudflare_accounts
        $cf_columns = [];
        $result = $db->query("PRAGMA table_info(cloudflare_accounts)");
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $cf_columns[] = $row['name'];
        }
        
        if (!in_array('account_name', $cf_columns)) {
            $db->exec("ALTER TABLE cloudflare_accounts ADD COLUMN account_name TEXT DEFAULT ''");
        }
        if (!in_array('description', $cf_columns)) {
            $db->exec("ALTER TABLE cloudflare_accounts ADD COLUMN description TEXT DEFAULT ''");
        }
        
        // 检查并添加缺失的字段到 rainbow_accounts
        $rainbow_columns = [];
        $result = $db->query("PRAGMA table_info(rainbow_accounts)");
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $rainbow_columns[] = $row['name'];
        }
        
        if (!in_array('account_name', $rainbow_columns)) {
            $db->exec("ALTER TABLE rainbow_accounts ADD COLUMN account_name TEXT DEFAULT ''");
        }
        if (!in_array('email', $rainbow_columns)) {
            $db->exec("ALTER TABLE rainbow_accounts ADD COLUMN email TEXT DEFAULT ''");
        }
        if (!in_array('description', $rainbow_columns)) {
            $db->exec("ALTER TABLE rainbow_accounts ADD COLUMN description TEXT DEFAULT ''");
        }
        
        // 创建或确保 dnspod_accounts 表存在
        $db->exec("CREATE TABLE IF NOT EXISTS dnspod_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            account_name TEXT DEFAULT '',
            secret_id TEXT NOT NULL DEFAULT '',
            secret_key TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
        
        // 创建或确保 powerdns_accounts 表存在
        $db->exec("CREATE TABLE IF NOT EXISTS powerdns_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '',
            account_name TEXT DEFAULT '',
            api_url TEXT NOT NULL DEFAULT '',
            api_key TEXT NOT NULL DEFAULT '',
            server_id TEXT DEFAULT 'localhost',
            description TEXT DEFAULT '',
            status INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )");
        
        // 确保 domains 表支持自定义渠道
        $domain_columns = [];
        $result = $db->query("PRAGMA table_info(domains)");
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $domain_columns[] = $row['name'];
        }
        
        if (!in_array('provider_type', $domain_columns)) {
            $db->exec("ALTER TABLE domains ADD COLUMN provider_type TEXT DEFAULT 'cloudflare'");
        }
        if (!in_array('api_base_url', $domain_columns)) {
            $db->exec("ALTER TABLE domains ADD COLUMN api_base_url TEXT DEFAULT ''");
        }
        if (!in_array('provider_uid', $domain_columns)) {
            $db->exec("ALTER TABLE domains ADD COLUMN provider_uid TEXT DEFAULT ''");
        }
        
    } catch (Exception $e) {
        error_log("Channel tables initialization error: " . $e->getMessage());
    }
}

// 处理添加渠道
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_channel'])) {
    // 开启详细日志记录
    $log_file = __DIR__ . '/../data/channel_add_debug.log';
    $log_data = [
        'time' => date('Y-m-d H:i:s'),
        'post_data' => $_POST,
        'session_id' => session_id()
    ];
    file_put_contents($log_file, json_encode($log_data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) . "\n\n", FILE_APPEND);
    
    $channel_type = trim($_POST['channel_type']);
    $channel_name = trim($_POST['channel_name']);
    $api_key = trim($_POST['api_key']);
    $email = trim($_POST['email']);
    $zone_id = trim($_POST['zone_id']);
    $api_base_url = trim($_POST['api_base_url']);
    $provider_uid = trim($_POST['provider_uid']);
    $status = isset($_POST['status']) ? 1 : 0;
    $description = trim($_POST['description']);
    
    file_put_contents($log_file, "开始处理 {$channel_type} 渠道添加\n", FILE_APPEND);
    
    try {
        if ($channel_type === 'cloudflare') {
            // 添加Cloudflare渠道
            $stmt = $db->prepare("
                INSERT INTO cloudflare_accounts (name, account_name, api_key, email, description, status, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ");
            $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(3, $api_key, SQLITE3_TEXT);
            $stmt->bindValue(4, $email, SQLITE3_TEXT);
            $stmt->bindValue(5, $description, SQLITE3_TEXT);
            $stmt->bindValue(6, $status, SQLITE3_INTEGER);
            
        } else if ($channel_type === 'rainbow') {
            // 添加彩虹DNS渠道 - 验证必需字段
            file_put_contents($log_file, "彩虹DNS验证开始\n", FILE_APPEND);
            file_put_contents($log_file, "api_base_url: {$api_base_url}\n", FILE_APPEND);
            file_put_contents($log_file, "provider_uid: {$provider_uid}\n", FILE_APPEND);
            file_put_contents($log_file, "api_key: " . substr($api_key, 0, 10) . "...\n", FILE_APPEND);
            
            if (empty($api_base_url) || empty($provider_uid) || empty($api_key)) {
                file_put_contents($log_file, "字段验证失败\n", FILE_APPEND);
                throw new Exception('彩虹DNS需要填写API密钥、API基础URL和用户ID');
            }
            
            // 验证彩虹DNS API
            file_put_contents($log_file, "开始API验证\n", FILE_APPEND);
            require_once __DIR__ . '/../config/rainbow_dns.php';
            $rainbow_api = new RainbowDNSAPI($provider_uid, $api_key, $api_base_url);
            
            $verify_result = $rainbow_api->verifyCredentials();
            file_put_contents($log_file, "API验证结果: " . ($verify_result ? '成功' : '失败') . "\n", FILE_APPEND);
            
            if (!$verify_result) {
                $details = $rainbow_api->getVerificationDetails();
                file_put_contents($log_file, "验证详情: " . json_encode($details, JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND);
                throw new Exception('彩虹DNS API验证失败: ' . ($details['error_message'] ?? '未知错误'));
            }
            
            file_put_contents($log_file, "API验证通过，准备插入数据库\n", FILE_APPEND);
            
            $stmt = $db->prepare("
                INSERT INTO rainbow_accounts (name, account_name, api_key, email, api_base_url, provider_uid, description, status, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ");
            $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(3, $api_key, SQLITE3_TEXT);
            $stmt->bindValue(4, $email ?: '', SQLITE3_TEXT); // 邮箱可选，为空时设为空字符串
            $stmt->bindValue(5, $api_base_url, SQLITE3_TEXT);
            $stmt->bindValue(6, $provider_uid, SQLITE3_TEXT);
            $stmt->bindValue(7, $description, SQLITE3_TEXT);
            $stmt->bindValue(8, $status, SQLITE3_INTEGER);
            
        } else if ($channel_type === 'dnspod') {
            // 添加DNSPod渠道 - 验证必需字段
            if (empty($api_key) || empty($provider_uid)) {
                throw new Exception('DNSPod需要填写SecretId和SecretKey');
            }
            
            $stmt = $db->prepare("
                INSERT INTO dnspod_accounts (name, account_name, secret_id, secret_key, description, status, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ");
            $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(3, $api_key, SQLITE3_TEXT); // API密钥作为SecretId
            $stmt->bindValue(4, $provider_uid, SQLITE3_TEXT); // 用户ID作为SecretKey
            $stmt->bindValue(5, $description, SQLITE3_TEXT);
            $stmt->bindValue(6, $status, SQLITE3_INTEGER);
            
        } else if ($channel_type === 'powerdns') {
            // 添加PowerDNS渠道 - 验证必需字段
            if (empty($api_base_url) || empty($api_key)) {
                throw new Exception('PowerDNS需要填写API URL和API密钥');
            }
            
            $stmt = $db->prepare("
                INSERT INTO powerdns_accounts (name, account_name, api_url, api_key, server_id, description, status, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ");
            $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(3, $api_base_url, SQLITE3_TEXT); // API基础URL
            $stmt->bindValue(4, $api_key, SQLITE3_TEXT);
            $stmt->bindValue(5, $provider_uid ?: 'localhost', SQLITE3_TEXT); // 服务器ID，默认localhost
            $stmt->bindValue(6, $description, SQLITE3_TEXT);
            $stmt->bindValue(7, $status, SQLITE3_INTEGER);
            
        } else if ($channel_type === 'custom') {
            // 添加自定义渠道 - 存储在domains表中
            $stmt = $db->prepare("
                INSERT INTO domains (domain_name, api_key, email, zone_id, provider_type, api_base_url, provider_uid, status, created_at) 
                VALUES (?, ?, ?, ?, 'custom', ?, ?, ?, datetime('now'))
            ");
            $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
            $stmt->bindValue(2, $api_key, SQLITE3_TEXT);
            $stmt->bindValue(3, $email, SQLITE3_TEXT);
            $stmt->bindValue(4, $zone_id, SQLITE3_TEXT);
            $stmt->bindValue(5, $api_base_url, SQLITE3_TEXT);
            $stmt->bindValue(6, $provider_uid, SQLITE3_TEXT);
            $stmt->bindValue(7, $status, SQLITE3_INTEGER);
        }
        
        if (isset($stmt) && $stmt->execute()) {
            // 记录操作日志
            $channel_id = $db->lastInsertRowID();
            file_put_contents($log_file, "数据库插入成功，ID: {$channel_id}\n", FILE_APPEND);
            
            if (function_exists('logAction')) {
                logAction('admin', $_SESSION['admin_id'] ?? 0, 'add_channel', "添加{$channel_type}渠道: {$channel_name}");
            }
            showSuccess(ucfirst($channel_type) . ' 渠道添加成功！');
            file_put_contents($log_file, "成功消息已设置\n", FILE_APPEND);
        } else {
            $error_info = $db->lastErrorMsg();
            file_put_contents($log_file, "数据库插入失败: {$error_info}\n", FILE_APPEND);
            showError('渠道添加失败: ' . $error_info);
        }
        
    } catch (Exception $e) {
        file_put_contents($log_file, "异常捕获: " . $e->getMessage() . "\n", FILE_APPEND);
        file_put_contents($log_file, "异常跟踪: " . $e->getTraceAsString() . "\n", FILE_APPEND);
        showError('添加失败：' . $e->getMessage());
    }
    
    file_put_contents($log_file, "准备重定向\n", FILE_APPEND);
    file_put_contents($log_file, "Session消息: " . json_encode($_SESSION, JSON_UNESCAPED_UNICODE) . "\n\n", FILE_APPEND);
    
    header("Location: channels_management.php");
    exit;
}

// 处理删除渠道
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete_channel'])) {
    $channel_id = (int)$_POST['channel_id'];
    $channel_type = $_POST['channel_type'];
    
    try {
        if ($channel_type === 'cloudflare') {
            $stmt = $db->prepare("DELETE FROM cloudflare_accounts WHERE id = ?");
        } else if ($channel_type === 'rainbow') {
            $stmt = $db->prepare("DELETE FROM rainbow_accounts WHERE id = ?");
        } else if ($channel_type === 'dnspod') {
            $stmt = $db->prepare("DELETE FROM dnspod_accounts WHERE id = ?");
        } else if ($channel_type === 'powerdns') {
            $stmt = $db->prepare("DELETE FROM powerdns_accounts WHERE id = ?");
        } else if ($channel_type === 'custom') {
            $stmt = $db->prepare("DELETE FROM domains WHERE id = ? AND provider_type = 'custom'");
        }
        
        $stmt->bindValue(1, $channel_id, SQLITE3_INTEGER);
        
        if ($stmt->execute()) {
            showSuccess('渠道删除成功！');
        } else {
            showError('渠道删除失败');
        }
        
    } catch (Exception $e) {
        showError('删除失败：' . $e->getMessage());
    }
    
    header("Location: channels_management.php");
    exit;
}

// 处理编辑渠道
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_channel'])) {
    $channel_id = (int)$_POST['channel_id'];
    $channel_type = $_POST['channel_type'];
    $channel_name = trim($_POST['channel_name']);
    $email = trim($_POST['email']);
    $api_key = trim($_POST['api_key']);
    $zone_id = trim($_POST['zone_id']);
    $api_base_url = trim($_POST['api_base_url']);
    $provider_uid = trim($_POST['provider_uid']);
    $description = trim($_POST['description']);
    
    try {
        if ($channel_type === 'cloudflare') {
            if (!empty($api_key)) {
                $stmt = $db->prepare("UPDATE cloudflare_accounts SET name = ?, account_name = ?, email = ?, api_key = ?, description = ? WHERE id = ?");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(3, $email, SQLITE3_TEXT);
                $stmt->bindValue(4, $api_key, SQLITE3_TEXT);
                $stmt->bindValue(5, $description, SQLITE3_TEXT);
                $stmt->bindValue(6, $channel_id, SQLITE3_INTEGER);
            } else {
                $stmt = $db->prepare("UPDATE cloudflare_accounts SET name = ?, account_name = ?, email = ?, description = ? WHERE id = ?");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(3, $email, SQLITE3_TEXT);
                $stmt->bindValue(4, $description, SQLITE3_TEXT);
                $stmt->bindValue(5, $channel_id, SQLITE3_INTEGER);
            }
        } else if ($channel_type === 'rainbow') {
            // 验证彩虹DNS必需字段
            if (empty($api_base_url) || empty($provider_uid)) {
                throw new Exception('彩虹DNS需要填写API基础URL和用户ID');
            }
            
            if (!empty($api_key)) {
                $stmt = $db->prepare("UPDATE rainbow_accounts SET name = ?, account_name = ?, email = ?, api_key = ?, api_base_url = ?, provider_uid = ?, description = ? WHERE id = ?");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(3, $email ?: '', SQLITE3_TEXT); // 邮箱可选
                $stmt->bindValue(4, $api_key, SQLITE3_TEXT);
                $stmt->bindValue(5, $api_base_url, SQLITE3_TEXT);
                $stmt->bindValue(6, $provider_uid, SQLITE3_TEXT);
                $stmt->bindValue(7, $description, SQLITE3_TEXT);
                $stmt->bindValue(8, $channel_id, SQLITE3_INTEGER);
            } else {
                $stmt = $db->prepare("UPDATE rainbow_accounts SET name = ?, account_name = ?, email = ?, api_base_url = ?, provider_uid = ?, description = ? WHERE id = ?");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(3, $email ?: '', SQLITE3_TEXT); // 邮箱可选
                $stmt->bindValue(4, $api_base_url, SQLITE3_TEXT);
                $stmt->bindValue(5, $provider_uid, SQLITE3_TEXT);
                $stmt->bindValue(6, $description, SQLITE3_TEXT);
                $stmt->bindValue(7, $channel_id, SQLITE3_INTEGER);
            }
        } else if ($channel_type === 'dnspod') {
            // 更新DNSPod渠道
            if (!empty($api_key) && !empty($provider_uid)) {
                $stmt = $db->prepare("UPDATE dnspod_accounts SET name = ?, account_name = ?, secret_id = ?, secret_key = ?, description = ? WHERE id = ?");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(3, $api_key, SQLITE3_TEXT);
                $stmt->bindValue(4, $provider_uid, SQLITE3_TEXT);
                $stmt->bindValue(5, $description, SQLITE3_TEXT);
                $stmt->bindValue(6, $channel_id, SQLITE3_INTEGER);
            } else {
                $stmt = $db->prepare("UPDATE dnspod_accounts SET name = ?, account_name = ?, description = ? WHERE id = ?");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(3, $description, SQLITE3_TEXT);
                $stmt->bindValue(4, $channel_id, SQLITE3_INTEGER);
            }
        } else if ($channel_type === 'powerdns') {
            // 更新PowerDNS渠道
            if (!empty($api_key) && !empty($api_base_url)) {
                $stmt = $db->prepare("UPDATE powerdns_accounts SET name = ?, account_name = ?, api_url = ?, api_key = ?, server_id = ?, description = ? WHERE id = ?");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(3, $api_base_url, SQLITE3_TEXT);
                $stmt->bindValue(4, $api_key, SQLITE3_TEXT);
                $stmt->bindValue(5, $provider_uid ?: 'localhost', SQLITE3_TEXT);
                $stmt->bindValue(6, $description, SQLITE3_TEXT);
                $stmt->bindValue(7, $channel_id, SQLITE3_INTEGER);
            } else {
                $stmt = $db->prepare("UPDATE powerdns_accounts SET name = ?, account_name = ?, api_url = ?, server_id = ?, description = ? WHERE id = ?");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(3, $api_base_url, SQLITE3_TEXT);
                $stmt->bindValue(4, $provider_uid ?: 'localhost', SQLITE3_TEXT);
                $stmt->bindValue(5, $description, SQLITE3_TEXT);
                $stmt->bindValue(6, $channel_id, SQLITE3_INTEGER);
            }
        } else if ($channel_type === 'custom') {
            if (!empty($api_key)) {
                $stmt = $db->prepare("UPDATE domains SET domain_name = ?, email = ?, api_key = ?, zone_id = ?, api_base_url = ?, provider_uid = ? WHERE id = ? AND provider_type = 'custom'");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $email, SQLITE3_TEXT);
                $stmt->bindValue(3, $api_key, SQLITE3_TEXT);
                $stmt->bindValue(4, $zone_id, SQLITE3_TEXT);
                $stmt->bindValue(5, $api_base_url, SQLITE3_TEXT);
                $stmt->bindValue(6, $provider_uid, SQLITE3_TEXT);
                $stmt->bindValue(7, $channel_id, SQLITE3_INTEGER);
            } else {
                $stmt = $db->prepare("UPDATE domains SET domain_name = ?, email = ?, zone_id = ?, api_base_url = ?, provider_uid = ? WHERE id = ? AND provider_type = 'custom'");
                $stmt->bindValue(1, $channel_name, SQLITE3_TEXT);
                $stmt->bindValue(2, $email, SQLITE3_TEXT);
                $stmt->bindValue(3, $zone_id, SQLITE3_TEXT);
                $stmt->bindValue(4, $api_base_url, SQLITE3_TEXT);
                $stmt->bindValue(5, $provider_uid, SQLITE3_TEXT);
                $stmt->bindValue(6, $channel_id, SQLITE3_INTEGER);
            }
        }
        
        if ($stmt->execute()) {
            showSuccess('渠道更新成功！');
        } else {
            showError('渠道更新失败');
        }
        
    } catch (Exception $e) {
        showError('更新失败：' . $e->getMessage());
    }
    
    header("Location: channels_management.php");
    exit;
}

// 处理更新渠道状态
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['toggle_status'])) {
    $channel_id = (int)$_POST['channel_id'];
    $channel_type = $_POST['channel_type'];
    $new_status = (int)$_POST['new_status'];
    
    try {
        if ($channel_type === 'cloudflare') {
            $stmt = $db->prepare("UPDATE cloudflare_accounts SET status = ? WHERE id = ?");
        } else if ($channel_type === 'rainbow') {
            $stmt = $db->prepare("UPDATE rainbow_accounts SET status = ? WHERE id = ?");
        } else if ($channel_type === 'dnspod') {
            $stmt = $db->prepare("UPDATE dnspod_accounts SET status = ? WHERE id = ?");
        } else if ($channel_type === 'powerdns') {
            $stmt = $db->prepare("UPDATE powerdns_accounts SET status = ? WHERE id = ?");
        } else if ($channel_type === 'custom') {
            $stmt = $db->prepare("UPDATE domains SET status = ? WHERE id = ? AND provider_type = 'custom'");
        }
        
        $stmt->bindValue(1, $new_status, SQLITE3_INTEGER);
        $stmt->bindValue(2, $channel_id, SQLITE3_INTEGER);
        
        if ($stmt->execute()) {
            showSuccess('渠道状态更新成功！');
        } else {
            showError('状态更新失败');
        }
        
    } catch (Exception $e) {
        showError('更新失败：' . $e->getMessage());
    }
    
    header("Location: channels_management.php");
    exit;
}

// 获取所有渠道数据
$channels = [];

// 获取Cloudflare渠道
$cf_result = $db->query("SELECT id, COALESCE(NULLIF(account_name, ''), name) as name, api_key, email, description, status, created_at, 'cloudflare' as type FROM cloudflare_accounts ORDER BY created_at DESC");
while ($row = $cf_result->fetchArray(SQLITE3_ASSOC)) {
    $channels[] = $row;
}

// 获取彩虹DNS渠道
$rainbow_result = $db->query("SELECT id, COALESCE(NULLIF(account_name, ''), name) as name, api_key, email, api_base_url, provider_uid, description, status, created_at, 'rainbow' as type FROM rainbow_accounts ORDER BY created_at DESC");
while ($row = $rainbow_result->fetchArray(SQLITE3_ASSOC)) {
    $channels[] = $row;
}

// 获取DNSPod渠道
$dnspod_result = $db->query("SELECT id, COALESCE(NULLIF(account_name, ''), name) as name, secret_id as api_key, secret_key as provider_uid, description, status, created_at, 'dnspod' as type FROM dnspod_accounts ORDER BY created_at DESC");
while ($row = $dnspod_result->fetchArray(SQLITE3_ASSOC)) {
    $channels[] = $row;
}

// 获取PowerDNS渠道
$powerdns_result = $db->query("SELECT id, COALESCE(NULLIF(account_name, ''), name) as name, api_key, api_url as api_base_url, server_id as provider_uid, description, status, created_at, 'powerdns' as type FROM powerdns_accounts ORDER BY created_at DESC");
while ($row = $powerdns_result->fetchArray(SQLITE3_ASSOC)) {
    $channels[] = $row;
}

// 获取自定义渠道
$custom_result = $db->query("SELECT id, domain_name as name, api_key, email, zone_id, api_base_url, provider_uid, status, created_at, 'custom' as type FROM domains WHERE provider_type = 'custom' ORDER BY created_at DESC");
while ($row = $custom_result->fetchArray(SQLITE3_ASSOC)) {
    $channels[] = $row;
}

// 按创建时间重新排序
usort($channels, function($a, $b) {
    return strtotime($b['created_at']) - strtotime($a['created_at']);
});

// 获取统计信息
$stats = [
    'total_channels' => count($channels),
    'active_channels' => count(array_filter($channels, function($c) { return $c['status'] == 1; })),
    'cloudflare_count' => count(array_filter($channels, function($c) { return $c['type'] == 'cloudflare'; })),
    'rainbow_count' => count(array_filter($channels, function($c) { return $c['type'] == 'rainbow'; })),
    'dnspod_count' => count(array_filter($channels, function($c) { return $c['type'] == 'dnspod'; })),
    'powerdns_count' => count(array_filter($channels, function($c) { return $c['type'] == 'powerdns'; })),
    'custom_count' => count(array_filter($channels, function($c) { return $c['type'] == 'custom'; }))
];

$page_title = '渠道管理';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2"><i class="fas fa-plug me-2"></i>渠道管理</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addChannelModal">
                        <i class="fas fa-plus me-1"></i>添加渠道
                    </button>
                </div>
            </div>
            
            <?php if ($messages): ?>
                <?php foreach ($messages as $type => $content): ?>
                    <div class="alert alert-<?php echo $type; ?> alert-dismissible fade show" role="alert">
                        <?php echo htmlspecialchars($content); ?>
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                <?php endforeach; ?>
            <?php endif; ?>
            
            <!-- 统计卡片 -->
            <div class="row mb-4">
                <div class="col-lg-3 col-md-6 mb-3">
                    <div class="card border-start border-primary border-4 shadow h-100">
                        <div class="card-body">
                            <div class="d-flex align-items-center">
                                <div class="flex-grow-1">
                                    <div class="small fw-bold text-primary text-uppercase mb-1">总渠道数</div>
                                    <div class="h5 fw-bold text-dark mb-0"><?php echo $stats['total_channels']; ?></div>
                                </div>
                                <div class="flex-shrink-0">
                                    <i class="fas fa-plug fa-2x text-muted"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-3 col-md-6 mb-3">
                    <div class="card border-start border-success border-4 shadow h-100">
                        <div class="card-body">
                            <div class="d-flex align-items-center">
                                <div class="flex-grow-1">
                                    <div class="small fw-bold text-success text-uppercase mb-1">活跃渠道</div>
                                    <div class="h5 fw-bold text-dark mb-0"><?php echo $stats['active_channels']; ?></div>
                                </div>
                                <div class="flex-shrink-0">
                                    <i class="fas fa-check-circle fa-2x text-muted"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-3 col-md-6 mb-3">
                    <div class="card border-start border-info border-4 shadow h-100">
                        <div class="card-body">
                            <div class="d-flex align-items-center">
                                <div class="flex-grow-1">
                                    <div class="small fw-bold text-info text-uppercase mb-1">Cloudflare</div>
                                    <div class="h5 fw-bold text-dark mb-0"><?php echo $stats['cloudflare_count']; ?></div>
                                </div>
                                <div class="flex-shrink-0">
                                    <i class="fab fa-cloudflare fa-2x text-muted"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-lg-3 col-md-6 mb-3">
                    <div class="card border-start border-warning border-4 shadow h-100">
                        <div class="card-body">
                            <div class="d-flex align-items-center">
                                <div class="flex-grow-1">
                                    <div class="small fw-bold text-warning text-uppercase mb-1">其他渠道</div>
                                    <div class="h5 fw-bold text-dark mb-0"><?php echo $stats['rainbow_count'] + $stats['custom_count']; ?></div>
                                </div>
                                <div class="flex-shrink-0">
                                    <i class="fas fa-server fa-2x text-muted"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 渠道列表 -->
            <div class="card shadow mb-4">
                <div class="card-header py-3 d-flex justify-content-between align-items-center">
                    <h6 class="m-0 fw-bold text-primary">渠道列表</h6>
                    <span class="badge bg-secondary"><?php echo count($channels); ?> 个渠道</span>
                </div>
                <div class="card-body">
                    <?php if (empty($channels)): ?>
                        <div class="text-center py-5">
                            <i class="fas fa-plug fa-3x text-muted mb-3"></i>
                            <h5 class="text-muted">暂无渠道</h5>
                            <p class="text-muted">点击上方"添加渠道"按钮创建第一个渠道</p>
                            <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addChannelModal">
                                <i class="fas fa-plus me-1"></i>立即添加
                            </button>
                        </div>
                    <?php else: ?>
                        <div class="table-responsive">
                            <table class="table table-hover align-middle">
                                <thead class="table-light">
                                    <tr>
                                        <th class="border-0">渠道名称</th>
                                        <th class="border-0">类型</th>
                                        <th class="border-0">邮箱</th>
                                        <th class="border-0 text-center">状态</th>
                                        <th class="border-0">创建时间</th>
                                        <th class="border-0 text-center">操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($channels as $channel): ?>
                                        <tr>
                                            <td>
                                                <div class="d-flex align-items-center">
                                                    <div>
                                                        <div class="fw-bold"><?php echo htmlspecialchars($channel['name'] ?: '未命名渠道'); ?></div>
                                                        <?php if (!empty($channel['description'])): ?>
                                                            <small class="text-muted"><?php echo htmlspecialchars($channel['description']); ?></small>
                                                        <?php endif; ?>
                                                    </div>
                                                </div>
                                            </td>
                                            <td>
                                                <?php
                                                $type_configs = [
                                                    'cloudflare' => ['label' => 'Cloudflare', 'class' => 'info', 'icon' => 'fab fa-cloudflare'],
                                                    'rainbow' => ['label' => '彩虹DNS', 'class' => 'warning', 'icon' => 'fas fa-rainbow'],
                                                    'dnspod' => ['label' => 'DNSPod', 'class' => 'success', 'icon' => 'fas fa-cloud'],
                                                    'powerdns' => ['label' => 'PowerDNS', 'class' => 'primary', 'icon' => 'fas fa-server']
                                                ];
                                                $config = $type_configs[$channel['type']];
                                                ?>
                                                <span class="badge bg-<?php echo $config['class']; ?> px-3 py-2">
                                                    <i class="<?php echo $config['icon']; ?> me-1"></i>
                                                    <?php echo $config['label']; ?>
                                                </span>
                                            </td>
                                            <td>
                                                <span class="text-muted"><?php echo htmlspecialchars($channel['email']); ?></span>
                                            </td>
                                            <td class="text-center">
                                                <form method="POST" class="d-inline">
                                                    <input type="hidden" name="channel_id" value="<?php echo $channel['id']; ?>">
                                                    <input type="hidden" name="channel_type" value="<?php echo $channel['type']; ?>">
                                                    <input type="hidden" name="new_status" value="<?php echo $channel['status'] ? 0 : 1; ?>">
                                                    <button type="submit" name="toggle_status" 
                                                            class="btn btn-sm <?php echo $channel['status'] ? 'btn-success' : 'btn-outline-secondary'; ?>" 
                                                            onclick="return confirm('确定要更改状态吗？')"
                                                            title="<?php echo $channel['status'] ? '点击禁用' : '点击启用'; ?>">
                                                        <i class="fas fa-<?php echo $channel['status'] ? 'check' : 'times'; ?>"></i>
                                                        <?php echo $channel['status'] ? '启用' : '禁用'; ?>
                                                    </button>
                                                </form>
                                            </td>
                                            <td>
                                                <small class="text-muted">
                                                    <?php echo date('Y-m-d H:i', strtotime($channel['created_at'])); ?>
                                                </small>
                                            </td>
                                            <td class="text-center">
                                                <div class="btn-group" role="group">
                                                    <button type="button" class="btn btn-sm btn-outline-primary" 
                                                            onclick="editChannel(<?php echo htmlspecialchars(json_encode($channel)); ?>)"
                                                            title="编辑渠道">
                                                        <i class="fas fa-edit"></i>
                                                    </button>
                                                    <form method="POST" class="d-inline" 
                                                          onsubmit="return confirm('确定要删除这个渠道吗？此操作不可恢复！')">
                                                        <input type="hidden" name="channel_id" value="<?php echo $channel['id']; ?>">
                                                        <input type="hidden" name="channel_type" value="<?php echo $channel['type']; ?>">
                                                        <button type="submit" name="delete_channel" 
                                                                class="btn btn-sm btn-outline-danger"
                                                                title="删除渠道">
                                                            <i class="fas fa-trash"></i>
                                                        </button>
                                                    </form>
                                                </div>
                                            </td>
                                        </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
        </main>
    </div>
</div>

<!-- 添加渠道模态框 -->
<div class="modal fade" id="addChannelModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">添加新渠道</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" id="addChannelForm" onsubmit="return validateChannelForm()">
                <div class="modal-body">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="channel_type" class="form-label">渠道类型 *</label>
                                <select class="form-select" id="channel_type" name="channel_type" required onchange="toggleFields()">
                                    <option value="">请选择渠道类型</option>
                                    <option value="cloudflare">Cloudflare</option>
                                    <option value="rainbow">彩虹DNS</option>
                                    <option value="dnspod">DNSPod</option>
                                    <option value="powerdns">PowerDNS</option>
                                </select>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="channel_name" class="form-label">渠道名称 *</label>
                                <input type="text" class="form-control" id="channel_name" name="channel_name" required>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6" id="email_field">
                            <div class="mb-3">
                                <label for="email" class="form-label">邮箱 *</label>
                                <input type="email" class="form-control" id="email" name="email">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="api_key" class="form-label">API密钥 *</label>
                                <input type="password" class="form-control" id="api_key" name="api_key" required>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Cloudflare和自定义API特有字段 -->
                    <div class="row" id="zone_id_row" style="display: none;">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="zone_id" class="form-label">Zone ID</label>
                                <input type="text" class="form-control" id="zone_id" name="zone_id">
                            </div>
                        </div>
                    </div>
                    
                    <!-- 彩虹DNS特有字段 -->
                    <div id="rainbow_fields" style="display: none;">
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                <label for="api_base_url" class="form-label">
                                    <i class="fas fa-exclamation-circle text-danger"></i>
                                    API基础URL <span class="text-danger">*</span>
                                </label>
                                <input type="url" class="form-control" id="api_base_url" name="api_base_url" 
                                       placeholder="https://6qu.cc" 
                                       style="border: 2px solid #ffc107;">
                                <div class="form-text text-warning">
                                    <strong>必填！</strong>请输入彩虹DNS服务的完整API基础URL地址，例如：https://6qu.cc
                                </div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                <label for="provider_uid" class="form-label">
                                    <i class="fas fa-exclamation-circle text-danger"></i>
                                    用户ID <span class="text-danger">*</span>
                                </label>
                                <input type="text" class="form-control" id="provider_uid" name="provider_uid" 
                                       placeholder="例如：1000" 
                                       style="border: 2px solid #ffc107;">
                                <div class="form-text text-warning">
                                    <strong>必填！</strong>请输入您的彩虹DNS用户ID（数字）"
                                </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- DNSPod特有字段 -->
                    <div id="dnspod_fields" style="display: none;">
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                    <label for="dnspod_secret_key" class="form-label">SecretKey <span class="text-danger">*</span></label>
                                    <input type="password" class="form-control" id="dnspod_secret_key" name="provider_uid" placeholder="请输入DNSPod SecretKey">
                                    <div class="form-text">请在腾讯云DNSPod控制台获取SecretKey</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- PowerDNS特有字段 -->
                    <div id="powerdns_fields" style="display: none;">
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                    <label for="powerdns_api_url" class="form-label">API URL <span class="text-danger">*</span></label>
                                    <input type="url" class="form-control" id="powerdns_api_url" name="api_base_url" placeholder="例如: http://powerdns.example.com:8081">
                                    <div class="form-text">请输入PowerDNS API服务器完整URL地址</div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                    <label for="powerdns_server_id" class="form-label">服务器ID (可选)</label>
                                    <input type="text" class="form-control" id="powerdns_server_id" name="provider_uid" placeholder="localhost" value="localhost">
                                    <div class="form-text">PowerDNS服务器标识符，通常为localhost</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="description" class="form-label">描述</label>
                        <textarea class="form-control" id="description" name="description" rows="3"></textarea>
                    </div>
                    
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="status" name="status" checked>
                        <label class="form-check-label" for="status">
                            启用此渠道
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <!--<button type="button" class="btn btn-info me-auto" onclick="testConnection()">-->
                    <!--    <i class="fas fa-plug"></i> 测试连接-->
                    <!--</button>-->
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="add_channel" class="btn btn-primary">添加渠道</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 编辑渠道模态框 -->
<div class="modal fade" id="editChannelModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">编辑渠道</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" id="editChannelForm">
                <div class="modal-body">
                    <input type="hidden" id="edit_channel_id" name="channel_id">
                    <input type="hidden" id="edit_channel_type" name="channel_type">
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div class="mb-3">
                                <label for="edit_channel_name" class="form-label">渠道名称 *</label>
                                <input type="text" class="form-control" id="edit_channel_name" name="channel_name" required>
                            </div>
                        </div>
                        <div class="col-md-6" id="edit_email_field">
                            <div class="mb-3">
                                <label for="edit_email" class="form-label">邮箱 *</label>
                                <input type="email" class="form-control" id="edit_email" name="email">
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="edit_api_key" class="form-label">API密钥</label>
                        <input type="password" class="form-control" id="edit_api_key" name="api_key" placeholder="不修改请留空">
                    </div>
                    
                    <div class="mb-3" id="edit_zone_id_field" style="display: none;">
                        <label for="edit_zone_id" class="form-label">Zone ID</label>
                        <input type="text" class="form-control" id="edit_zone_id" name="zone_id">
                    </div>
                    
                    <!-- 彩虹DNS编辑字段 -->
                    <div id="edit_rainbow_fields" style="display: none;">
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                    <label for="edit_api_base_url" class="form-label">API基础URL <span class="text-danger">*</span></label>
                                    <input type="url" class="form-control" id="edit_api_base_url" name="api_base_url" placeholder="例如: https://api.rainbow.com/dns">
                                    <div class="form-text">请输入彩虹DNS服务的完整API基础URL地址</div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                    <label for="edit_provider_uid" class="form-label">用户ID <span class="text-danger">*</span></label>
                                    <input type="text" class="form-control" id="edit_provider_uid" name="provider_uid" placeholder="请输入您的彩虹DNS用户ID">
                                    <div class="form-text">您可以在彩虹DNS控制面板的账户信息中找到用户ID</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- DNSPod编辑字段 -->
                    <div id="edit_dnspod_fields" style="display: none;">
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                    <label for="edit_dnspod_secret_key" class="form-label">SecretKey</label>
                                    <input type="password" class="form-control" id="edit_dnspod_secret_key" name="provider_uid" placeholder="不修改请留空">
                                    <div class="form-text">请在腾讯云DNSPod控制台获取SecretKey</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- PowerDNS编辑字段 -->
                    <div id="edit_powerdns_fields" style="display: none;">
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                    <label for="edit_powerdns_api_url" class="form-label">API URL</label>
                                    <input type="url" class="form-control" id="edit_powerdns_api_url" name="api_base_url" placeholder="例如: http://powerdns.example.com:8081">
                                    <div class="form-text">请输入PowerDNS API服务器完整URL地址</div>
                                </div>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-12">
                                <div class="mb-3">
                                    <label for="edit_powerdns_server_id" class="form-label">服务器ID</label>
                                    <input type="text" class="form-control" id="edit_powerdns_server_id" name="provider_uid" placeholder="localhost">
                                    <div class="form-text">PowerDNS服务器标识符，通常为localhost</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="edit_description" class="form-label">描述</label>
                        <textarea class="form-control" id="edit_description" name="description" rows="3"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="update_channel" class="btn btn-primary">更新渠道</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
// 禁用一个容器内的所有input/select/textarea
function disableFields(container) {
    if (!container) return;
    const inputs = container.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.disabled = true;
    });
}

// 启用一个容器内的所有input/select/textarea
function enableFields(container) {
    if (!container) return;
    const inputs = container.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.disabled = false;
    });
}

// 表单验证函数
function validateChannelForm() {
    const channelType = document.getElementById('channel_type').value;
    const apiBaseUrl = document.getElementById('api_base_url').value.trim();
    const providerUid = document.getElementById('provider_uid').value.trim();
    const apiKey = document.getElementById('api_key').value.trim();
    
    console.log('验证表单:', {channelType, apiBaseUrl, providerUid, apiKey});
    
    if (channelType === 'rainbow') {
        if (!apiBaseUrl) {
            alert('彩虹DNS需要填写API基础URL！\n例如：https://caihong.6qu.cc');
            document.getElementById('api_base_url').focus();
            return false;
        }
        if (!providerUid || providerUid === 'localhost') {
            alert('彩虹DNS需要填写用户ID！\n不能是"localhost"，应该是您的彩虹DNS用户ID，例如：1000');
            document.getElementById('provider_uid').focus();
            return false;
        }
        if (!apiKey) {
            alert('彩虹DNS需要填写API密钥！');
            document.getElementById('api_key').focus();
            return false;
        }
    }
    
    return true;
}

function toggleFields() {
    const channelType = document.getElementById('channel_type').value;
    const zoneIdRow = document.getElementById('zone_id_row');
    const rainbowFields = document.getElementById('rainbow_fields');
    const dnspodFields = document.getElementById('dnspod_fields');
    const powerdnsFields = document.getElementById('powerdns_fields');
    const emailField = document.getElementById('email_field');
    const emailInput = document.getElementById('email');
    const apiKeyLabel = document.querySelector('label[for="api_key"]');
    const apiBaseUrlInput = document.getElementById('api_base_url');
    const providerUidInput = document.getElementById('provider_uid');
    
    // 隐藏所有特殊字段，并禁用它们（防止提交）
    zoneIdRow.style.display = 'none';
    rainbowFields.style.display = 'none';
    dnspodFields.style.display = 'none';
    powerdnsFields.style.display = 'none';
    
    // 禁用所有隐藏字段，防止它们被提交
    disableFields(rainbowFields);
    disableFields(dnspodFields);
    disableFields(powerdnsFields);
    
    // 重置所有可选字段的required属性
    if (apiBaseUrlInput) apiBaseUrlInput.removeAttribute('required');
    if (providerUidInput) providerUidInput.removeAttribute('required');
    
    // 重置基础字段
    emailInput.setAttribute('required', 'required');
    emailField.style.display = 'block';
    apiKeyLabel.textContent = 'API密钥 *';
    
    if (channelType === 'cloudflare') {
        // Cloudflare需要邮箱和API密钥
        emailInput.setAttribute('required', 'required');
        emailField.style.display = 'block';
    } else if (channelType === 'rainbow') {
        // 彩虹DNS不需要邮箱，需要API基础URL和用户ID
        emailInput.removeAttribute('required');
        emailInput.value = '';  // 清空值避免验证
        emailField.style.display = 'none';
        rainbowFields.style.display = 'block';
        // 启用彩虹DNS字段
        enableFields(rainbowFields);
        // 设置彩虹DNS必填字段
        if (apiBaseUrlInput) {
            apiBaseUrlInput.setAttribute('required', 'required');
            apiBaseUrlInput.value = '';  // 清空以防有旧值
        }
        if (providerUidInput) {
            providerUidInput.setAttribute('required', 'required');
            providerUidInput.value = '';  // 清空以防有旧值
        }
    } else if (channelType === 'dnspod') {
        // DNSPod不需要邮箱，需要SecretId和SecretKey
        emailInput.removeAttribute('required');
        emailInput.value = '';  // 清空值避免验证
        emailField.style.display = 'none';
        dnspodFields.style.display = 'block';
        enableFields(dnspodFields);
        apiKeyLabel.textContent = 'SecretId *';
        // DNSPod的SecretKey通过provider_uid字段
        const dnspodSecretKey = document.getElementById('dnspod_secret_key');
        if (dnspodSecretKey) dnspodSecretKey.setAttribute('required', 'required');
    } else if (channelType === 'powerdns') {
        // PowerDNS不需要邮箱，需要API URL和API密钥
        emailInput.removeAttribute('required');
        emailInput.value = '';  // 清空值避免验证
        emailField.style.display = 'none';
        powerdnsFields.style.display = 'block';
        enableFields(powerdnsFields);
        // PowerDNS的API URL是必填的
        const powerdnsApiUrl = document.getElementById('powerdns_api_url');
        if (powerdnsApiUrl) powerdnsApiUrl.setAttribute('required', 'required');
    } else if (channelType === 'custom') {
        // 自定义API需要所有字段
        zoneIdRow.style.display = 'block';
        rainbowFields.style.display = 'block';
        emailInput.setAttribute('required', 'required');
        emailField.style.display = 'block';
    }
}

function editChannel(channel) {
    // 填充编辑表单
    document.getElementById('edit_channel_id').value = channel.id;
    document.getElementById('edit_channel_type').value = channel.type;
    document.getElementById('edit_channel_name').value = channel.name;
    document.getElementById('edit_email').value = channel.email || '';
    document.getElementById('edit_description').value = channel.description || '';
    
    // 根据渠道类型显示/隐藏字段
    const editZoneIdField = document.getElementById('edit_zone_id_field');
    const editRainbowFields = document.getElementById('edit_rainbow_fields');
    const editDnspodFields = document.getElementById('edit_dnspod_fields');
    const editPowerdnsFields = document.getElementById('edit_powerdns_fields');
    const editEmailField = document.getElementById('edit_email_field');
    const editEmailInput = document.getElementById('edit_email');
    const editApiKeyLabel = document.querySelector('label[for="edit_api_key"]');
    
    // 重置所有字段显示状态
    editZoneIdField.style.display = 'none';
    editRainbowFields.style.display = 'none';
    editDnspodFields.style.display = 'none';
    editPowerdnsFields.style.display = 'none';
    editEmailField.style.display = 'block';
    editEmailInput.setAttribute('required', 'required');
    editApiKeyLabel.textContent = 'API密钥';
    
    if (channel.type === 'cloudflare') {
        // Cloudflare需要邮箱
        editEmailField.style.display = 'block';
        editEmailInput.setAttribute('required', 'required');
    } else if (channel.type === 'rainbow') {
        // 彩虹DNS不需要邮箱
        editEmailField.style.display = 'none';
        editEmailInput.removeAttribute('required');
        editRainbowFields.style.display = 'block';
        document.getElementById('edit_api_base_url').value = channel.api_base_url || '';
        document.getElementById('edit_provider_uid').value = channel.provider_uid || '';
    } else if (channel.type === 'dnspod') {
        // DNSPod不需要邮箱
        editEmailField.style.display = 'none';
        editEmailInput.removeAttribute('required');
        editDnspodFields.style.display = 'block';
        editApiKeyLabel.textContent = 'SecretId';
        document.getElementById('edit_dnspod_secret_key').value = ''; // 不显示现有密钥
    } else if (channel.type === 'powerdns') {
        // PowerDNS不需要邮箱
        editEmailField.style.display = 'none';
        editEmailInput.removeAttribute('required');
        editPowerdnsFields.style.display = 'block';
        document.getElementById('edit_powerdns_api_url').value = channel.api_base_url || '';
        document.getElementById('edit_powerdns_server_id').value = channel.provider_uid || 'localhost';
    } else if (channel.type === 'custom') {
        // 自定义API需要所有字段
        editZoneIdField.style.display = 'block';
        editRainbowFields.style.display = 'block';
        editEmailField.style.display = 'block';
        editEmailInput.setAttribute('required', 'required');
        document.getElementById('edit_zone_id').value = channel.zone_id || '';
        document.getElementById('edit_api_base_url').value = channel.api_base_url || '';
        document.getElementById('edit_provider_uid').value = channel.provider_uid || '';
    }
    
    // 显示模态框
    new bootstrap.Modal(document.getElementById('editChannelModal')).show();
}

function testConnection() {
    const channelType = document.getElementById('channel_type').value;
    const apiKey = document.getElementById('api_key').value;
    const email = document.getElementById('email').value;
    const apiBaseUrl = document.getElementById('api_base_url').value;
    const providerUid = document.getElementById('provider_uid').value;
    
    if (!channelType) {
        alert('请先选择渠道类型');
        return;
    }
    
    if (!apiKey) {
        alert('请填写API密钥');
        return;
    }
    
    // 根据渠道类型验证必需字段
    if (channelType === 'cloudflare' || channelType === 'custom') {
        if (!email) {
            alert('Cloudflare和自定义API需要填写邮箱');
            return;
        }
    }
    
    if (channelType === 'rainbow') {
        if (!apiBaseUrl || !providerUid) {
            alert('彩虹DNS需要填写API基础URL和用户ID');
            return;
        }
    }
    
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 测试中...';
    btn.disabled = true;
    
    const formData = new FormData();
    formData.append('channel_type', channelType);
    formData.append('api_key', apiKey);
    formData.append('email', email);
    formData.append('api_base_url', apiBaseUrl);
    formData.append('provider_uid', providerUid);
    
    fetch('test_connection.php', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        btn.innerHTML = originalText;
        btn.disabled = false;
        
        if (data.success) {
            alert('✓ ' + data.message);
        } else {
            alert('✗ ' + data.message);
        }
    })
    .catch(error => {
        btn.innerHTML = originalText;
        btn.disabled = false;
        alert('测试连接时发生错误: ' + error.message);
    });
}
</script>

<style>
/* 卡片样式 */
.card {
    background-color: #ffffff !important;
    border: 1px solid #dee2e6 !important;
    border-radius: 0.5rem;
    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075) !important;
}

.card-header {
    background-color: #f8f9fa !important;
    border-bottom: 1px solid #dee2e6 !important;
}

.card-body {
    background-color: #ffffff !important;
}

/* 模态框样式 */
.modal-content {
    background-color: #ffffff !important;
    border: 1px solid #dee2e6;
    box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
    color: #212529 !important;
}

.modal-header {
    background-color: #ffffff !important;
    border-bottom: 1px solid #dee2e6 !important;
    color: #212529 !important;
}

.modal-footer {
    background-color: #ffffff !important;
    border-top: 1px solid #dee2e6 !important;
    color: #212529 !important;
}

.modal-title {
    color: #212529 !important;
}

/* 表格样式 */
.table {
    background-color: #ffffff !important;
}

.table thead th {
    background-color: #f8f9fa !important;
    border-color: #dee2e6 !important;
    color: #212529 !important;
    font-weight: 600;
    font-size: 0.875rem;
}

.table tbody tr {
    background-color: #f8f9fa !important;
}

.table tbody tr:hover {
    background-color: #e9ecef !important;
}

.table td {
    border-color: #dee2e6 !important;
}

/* 表单元素样式 */
.form-control, .form-select {
    background-color: #ffffff !important;
    border: 1px solid #ced4da !important;
    color: #212529 !important;
}

.form-control:focus, .form-select:focus {
    background-color: #ffffff !important;
    border-color: #0d6efd !important;
    box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25) !important;
    color: #212529 !important;
}

.form-control::placeholder {
    color: #6c757d !important;
}

.form-select option {
    background-color: #ffffff !important;
    color: #212529 !important;
}

/* 统计卡片文字保持黑色 - 白色背景上 */
/* 不要全局覆盖 .text-dark */

/* 按钮样式 */
.btn {
    /* 使用默认Bootstrap样式 */
}

/* 模态框按钮特殊样式 */
.modal-content .btn-primary {
    background-color: #0d6efd !important;
    border-color: #0d6efd !important;
    color: #ffffff !important;
}

.modal-content .btn-primary:hover {
    background-color: #0b5ed7 !important;
    border-color: #0a58ca !important;
}

.modal-content .btn-secondary {
    background-color: #6c757d !important;
    border-color: #6c757d !important;
    color: #ffffff !important;
}

.modal-content .btn-secondary:hover {
    background-color: #5c636a !important;
    border-color: #565e64 !important;
}

.modal-content .btn-info {
    background-color: #0dcaf0 !important;
    border-color: #0dcaf0 !important;
    color: #000000 !important;
}

.modal-content .btn-info:hover {
    background-color: #31d2f2 !important;
    border-color: #25cff2 !important;
}

/* 警告框样式 */
.alert {
    /* 使用默认Bootstrap样式 */
}

/* 其他样式保持 */
.btn-group .btn {
    border-radius: 0.375rem;
}

.btn-group .btn:not(:last-child) {
    margin-right: 0.25rem;
}

.badge {
    font-size: 0.75rem;
}

.table-responsive {
    border-radius: 0.375rem;
}

.btn-sm {
    padding: 0.25rem 0.75rem;
    font-size: 0.875rem;
}

/* 确保内容可读性 */
.card-body h5, .card-body .h5 {
    color: #212529 !important;
    font-weight: bold;
}

.small {
    color: #6c757d !important;
}

/* 边框装饰保持显眼 */
.border-primary {
    border-left: 4px solid #0d6efd !important;
}

.border-success {
    border-left: 4px solid #198754 !important;
}

.border-info {
    border-left: 4px solid #0dcaf0 !important;
}

.border-warning {
    border-left: 4px solid #ffc107 !important;
}

/* 页面主要内容区域 */
.main {
    /* 使用默认背景 */
}

/* 面包屑和标题区域 */
.border-bottom {
    border-color: #dee2e6 !important;
}

/* 图标颜色优化 */
.text-muted {
    color: #6c757d !important;
}

/* 表格无数据状态 */
.text-center {
    /* 使用默认颜色 */
}

/* 模态框body */
.modal-body {
    /* 使用默认背景 */
    color: #212529 !important;
}

/* 模态框内文本颜色 */
.modal-content label {
    color: #212529 !important;
}

.modal-content .form-label {
    color: #212529 !important;
    font-weight: 500;
}

.modal-content .form-check-label {
    color: #212529 !important;
}

.modal-content .text-muted {
    color: #6c757d !important;
}

/* 复选框样式优化 */
.form-check-input {
    /* 使用默认样式 */
}

.form-check-input:checked {
    background-color: #0d6efd !important;
    border-color: #0d6efd !important;
}

/* 必填标记颜色 */
.modal-content span[style*="color: red"] {
    color: #dc3545 !important;
}

/* 徽章样式 */
.bg-secondary {
    background-color: #6c757d !important;
}

.bg-success {
    background-color: #198754 !important;
}

.bg-danger {
    background-color: #dc3545 !important;
}
</style>

<?php include 'includes/footer.php'; ?>