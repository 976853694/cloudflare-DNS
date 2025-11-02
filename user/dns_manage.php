<?php
session_start();
require_once '../config/database.php';
require_once '../config/cloudflare.php';
require_once '../config/dns_manager.php';
require_once '../includes/functions.php';
require_once '../includes/user_groups.php';

checkUserLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 处理从主页传递的参数
$auto_prefix = isset($_GET['prefix']) ? trim($_GET['prefix']) : '';
$auto_domain_id = isset($_GET['domain_id']) ? intval($_GET['domain_id']) : 0;
$auto_fill_mode = !empty($auto_prefix) && $auto_domain_id > 0;

// 更新用户积分到session
$user_points = $db->querySingle("SELECT points FROM users WHERE id = {$_SESSION['user_id']}");
$_SESSION['user_points'] = $user_points;

// 获取用户组信息
$user_group = getUserGroup($_SESSION['user_id']);
$required_points = getRequiredPoints($_SESSION['user_id']);
$current_record_count = getUserCurrentRecordCount($_SESSION['user_id']);

// 获取用户可访问的域名（根据用户组权限）
$domains = getUserAccessibleDomains($_SESSION['user_id']);

// 处理域名选择
$selected_domain_id = $_SESSION['selected_domain_id'] ?? ($domains[0]['id'] ?? null);
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['select_domain'])) {
    $selected_domain_id = (int)getPost('domain_id');
    $_SESSION['selected_domain_id'] = $selected_domain_id;
    redirect('dashboard.php');
}

// 如果通过GET参数切换域名（但不是自动填充模式）
if (isset($_GET['domain_id']) && !$auto_fill_mode) {
    $selected_domain_id = (int)$_GET['domain_id'];
    $_SESSION['selected_domain_id'] = $selected_domain_id;
    redirect('dashboard.php');
}

// 如果是自动填充模式，直接设置选中的域名
if ($auto_fill_mode) {
    $selected_domain_id = $auto_domain_id;
    $_SESSION['selected_domain_id'] = $selected_domain_id;
}

// 获取当前域名配置
$current_domain = null;
foreach ($domains as $domain) {
    if ($domain['id'] == $selected_domain_id) {
        $current_domain = $domain;
        break;
    }
}

// 处理添加DNS记录
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_record'])) {
    $subdomain = getPost('subdomain');
    $type = getPost('type');
    $content = getPost('content');
    $proxied = getPost('proxied', 0);
    $remark = getPost('remark', '');
    $add_domain_id = getPost('add_domain_id'); // 从表单中获取选择的域名ID
    
    // 根据表单选择的域名ID获取域名信息
    $add_domain = null;
    foreach ($domains as $domain) {
        if ($domain['id'] == $add_domain_id) {
            $add_domain = $domain;
            break;
        }
    }
    
    if (!$add_domain) {
        showError('请选择一个有效的域名！');
    } elseif (!$subdomain || !$type || !$content) {
        showError('请填写完整信息！');
    } elseif (!isDNSTypeEnabled($type)) {
        showError('该DNS记录类型未启用！');
    } elseif (!checkUserDomainPermission($_SESSION['user_id'], $add_domain['id'])) {
        showError('您的用户组无权访问此域名！请联系管理员升级用户组。');
    } elseif (!checkUserRecordLimit($_SESSION['user_id'])) {
        $max = $user_group['max_records'];
        showError("您已达到用户组的最大记录数限制（{$max}条）！请联系管理员升级用户组。");
    } elseif ($user_points < $required_points) {
        showError("积分不足！需要 {$required_points} 积分，您当前有 {$user_points} 积分。");
    } elseif (isSubdomainBlocked($subdomain)) {
        showError("前缀 \"$subdomain\" 已被系统拦截，无法创建此子域名！");
    } else {
        try {
            // 使用统一的DNS管理器
            $dns_manager = new DNSManager($add_domain);
            $full_name = $subdomain === '@' ? $add_domain['domain_name'] : $subdomain . '.' . $add_domain['domain_name'];
            
            // 优先检查本地数据库中是否已存在该记录
            $stmt = $db->prepare("
                SELECT * FROM dns_records 
                WHERE domain_id = ? AND subdomain = ? AND status = 1
            ");
            $stmt->bindValue(1, $add_domain['id'], SQLITE3_INTEGER);
            $stmt->bindValue(2, $subdomain, SQLITE3_TEXT);
            $result = $stmt->execute();
            
            $local_records = [];
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $local_records[] = $row;
            }
            
            // 检查本地记录是否有冲突
            $conflict_found = false;
            $existing_record = null;
            
            foreach ($local_records as $record) {
                $record_type = strtoupper($record['type']);
                $target_type = strtoupper($type);
                
                // A、AAAA、CNAME记录之间会冲突
                $conflicting_types = ['A', 'AAAA', 'CNAME'];
                
                if (in_array($record_type, $conflicting_types) && in_array($target_type, $conflicting_types)) {
                    $conflict_found = true;
                    $existing_record = $record;
                    break;
                }
                
                // 完全相同的记录类型和内容
                if ($record_type === $target_type) {
                    if ($record['content'] === $content) {
                        throw new Exception("相同的DNS记录已存在！记录名称: {$full_name}, 类型: {$type}, 内容: {$content}");
                    } else {
                        $conflict_found = true;
                        $existing_record = $record;
                        break;
                    }
                }
            }
            
            if ($conflict_found) {
                $conflict_msg = "DNS记录冲突：域名 '{$full_name}' 已存在 {$existing_record['type']} 记录";
                $conflict_msg .= "（内容: {$existing_record['content']}）";
                $conflict_msg .= "。无法添加 {$type} 记录到相同名称。";
                $conflict_msg .= "建议：1) 使用不同的子域名前缀；2) 删除现有记录后重新添加；3) 使用编辑功能修改现有记录。";
                throw new Exception($conflict_msg);
            }
            
            // 如果本地没有冲突，再检查远程DNS提供商（可选，用于双重验证）
            // 这可以捕获直接在DNS提供商后台添加的记录
            try {
                $remote_records = $dns_manager->getDNSRecords($add_domain['zone_id']);
                foreach ($remote_records as $record) {
                    if (strtolower($record['name']) === strtolower($full_name)) {
                        $record_type = strtoupper($record['type']);
                        $target_type = strtoupper($type);
                        
                        // 检查是否是同一条记录（通过cloudflare_id对比）
                        $is_same_record = false;
                        if (isset($record['id'])) {
                            foreach ($local_records as $local_rec) {
                                if ($local_rec['cloudflare_id'] == $record['id']) {
                                    $is_same_record = true;
                                    break;
                                }
                            }
                        }
                        
                        // 如果不是已知的本地记录，则检查冲突
                        if (!$is_same_record) {
                            $conflicting_types = ['A', 'AAAA', 'CNAME'];
                            
                            if (in_array($record_type, $conflicting_types) && in_array($target_type, $conflicting_types)) {
                                $conflict_msg = "DNS记录冲突：域名 '{$full_name}' 在远程DNS提供商已存在 {$record_type} 记录";
                                $conflict_msg .= "（内容: {$record['content']}）";
                                $conflict_msg .= "。该记录可能是直接在DNS提供商后台添加的。请先删除该记录或使用不同的子域名。";
                                throw new Exception($conflict_msg);
                            }
                            
                            if ($record_type === $target_type && $record['content'] === $content) {
                                throw new Exception("相同的DNS记录已存在于远程DNS提供商！记录名称: {$full_name}, 类型: {$type}, 内容: {$content}");
                            }
                        }
                    }
                }
            } catch (Exception $e) {
                // 如果远程查询失败，记录日志但不阻止添加
                error_log("远程DNS记录查询失败: " . $e->getMessage());
            }
            
            // 某些记录类型不能启用代理
            $non_proxiable_types = ['NS', 'MX', 'TXT', 'SRV', 'CAA'];
            $final_proxied = in_array(strtoupper($type), $non_proxiable_types) ? false : (bool)$proxied;
            
            // 对于彩虹DNS，代理功能不可用
            if (isset($add_domain['provider_type']) && $add_domain['provider_type'] === 'rainbow') {
                $final_proxied = false;
            }
            
            // 对于彩虹DNS，需要使用子域名而不是完整域名
            if (isset($add_domain['provider_type']) && $add_domain['provider_type'] === 'rainbow') {
                $record_name = $subdomain; // 彩虹DNS使用子域名
            } else {
                $record_name = $full_name; // Cloudflare使用完整域名
            }
            
            $result = null;
            $synced_record_id = null;
            
            try {
                // 尝试创建DNS记录
                $result = $dns_manager->createDNSRecord($add_domain['zone_id'], $type, $record_name, $content, [
                    'proxied' => $final_proxied,
                    'remark' => $remark
                ]);
            } catch (Exception $create_error) {
                // 检查是否是"记录已存在"错误
                if (strpos($create_error->getMessage(), 'identical record already exists') !== false ||
                    strpos($create_error->getMessage(), 'already exists') !== false ||
                    strpos($create_error->getMessage(), '记录已存在') !== false) {
                    
                    // 尝试从DNS提供商找到这条已存在的记录
                    try {
                        $remote_records = $dns_manager->getDNSRecords($add_domain['zone_id']);
                        $found_record = null;
                        
                        foreach ($remote_records as $remote_record) {
                            $remote_name = $remote_record['name'] ?? '';
                            $remote_type = strtoupper($remote_record['type'] ?? '');
                            $remote_content = $remote_record['content'] ?? '';
                            $target_type = strtoupper($type);
                            
                            // 标准化记录名称以进行比较
                            $compare_name = ($add_domain['provider_type'] === 'rainbow') ? $subdomain : $full_name;
                            
                            // 匹配名称、类型和内容
                            if ($remote_name === $compare_name && 
                                $remote_type === $target_type && 
                                $remote_content === $content) {
                                $found_record = $remote_record;
                                break;
                            }
                        }
                        
                        if ($found_record) {
                            // 找到了已存在的记录，检查本地数据库是否已有记录
                            $existing_id = $found_record['id'] ?? $found_record['RecordId'] ?? null;
                            
                            if ($existing_id) {
                                // 检查本地数据库中是否已有此记录
                                $check_stmt = $db->prepare("SELECT * FROM dns_records WHERE cloudflare_id = ? AND domain_id = ?");
                                $check_stmt->bindValue(1, $existing_id, SQLITE3_TEXT);
                                $check_stmt->bindValue(2, $add_domain['id'], SQLITE3_INTEGER);
                                $check_result = $check_stmt->execute();
                                $local_existing = $check_result->fetchArray(SQLITE3_ASSOC);
                                
                                if ($local_existing) {
                                    // 本地已有此记录
                                    if ($local_existing['user_id'] == $_SESSION['user_id']) {
                                        throw new Exception("此DNS记录已存在于您的记录列表中！记录名称: {$full_name}, 类型: {$type}, 内容: {$content}");
                                    } else {
                                        throw new Exception("此DNS记录已被其他用户占用！记录名称: {$full_name}, 类型: {$type}");
                                    }
                                } else {
                                    // 远程有记录但本地没有，将其同步到本地数据库
                                    $synced_record_id = $existing_id;
                                    $result = $found_record; // 使用找到的记录
                                }
                            }
                        } else {
                            // 找不到匹配的记录，抛出原始错误
                            throw new Exception('DNS记录已存在，但无法在远程找到匹配的记录。请检查DNS提供商后台或稍后重试。');
                        }
                    } catch (Exception $sync_error) {
                        // 如果同步查找失败，抛出更友好的错误信息
                        if (strpos($sync_error->getMessage(), '已存在') !== false || 
                            strpos($sync_error->getMessage(), '已被') !== false) {
                            throw $sync_error; // 保留业务逻辑错误
                        } else {
                            throw new Exception('DNS记录已存在于远程服务器，但同步失败: ' . $sync_error->getMessage());
                        }
                    }
                } else {
                    // 其他类型的错误，直接抛出
                    throw $create_error;
                }
            }
            
            if (!$result) {
                throw new Exception('创建DNS记录失败，未获得有效响应');
            }
            
            // 保存到数据库
            $stmt = $db->prepare("INSERT INTO dns_records (user_id, domain_id, subdomain, type, content, proxied, cloudflare_id, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
            $stmt->bindValue(1, $_SESSION['user_id'], SQLITE3_INTEGER);
            $stmt->bindValue(2, $add_domain['id'], SQLITE3_INTEGER);
            $stmt->bindValue(3, $subdomain, SQLITE3_TEXT);
            $stmt->bindValue(4, $type, SQLITE3_TEXT);
            $stmt->bindValue(5, $content, SQLITE3_TEXT);
            $stmt->bindValue(6, $final_proxied ? 1 : 0, SQLITE3_INTEGER);
            // 使用同步的ID（如果存在），否则从结果中提取
            if ($synced_record_id) {
                $record_id = $synced_record_id;
            } else {
                // 对于彩虹DNS，使用RecordId；对于Cloudflare，使用id
                $record_id = isset($result['RecordId']) ? $result['RecordId'] : $result['id'];
            }
            $stmt->bindValue(7, $record_id, SQLITE3_TEXT);
            $stmt->bindValue(8, $remark, SQLITE3_TEXT);
            
            if ($stmt->execute()) {
                // 扣除积分（根据用户组策略）
                $points_cost = $required_points;
                if ($points_cost > 0) {
                    $db->exec("UPDATE users SET points = points - $points_cost WHERE id = {$_SESSION['user_id']}");
                    $_SESSION['user_points'] -= $points_cost;
                }
                
                logAction('user', $_SESSION['user_id'], 'add_dns_record', "添加DNS记录: $full_name ($type)");
                showSuccess('DNS记录添加成功！');
            } else {
                showError('记录保存失败！');
            }
        } catch (Exception $e) {
            showError('添加失败: ' . $e->getMessage());
        }
    }
    redirect('dns_manage.php');
}

// 处理修改DNS记录
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['edit_record'])) {
    $record_id = (int)getPost('record_id');
    $subdomain = trim(getPost('subdomain'));
    $type = getPost('type');
    $content = trim(getPost('content'));
    $remark = trim(getPost('remark'));
    $proxied = isset($_POST['proxied']) ? 1 : 0;
    
    $record = $db->querySingle("SELECT * FROM dns_records WHERE id = $record_id AND user_id = {$_SESSION['user_id']}", true);
    if ($record && $current_domain) {
        // 检查新的前缀是否被拦截（如果前缀发生了变化）
        if ($subdomain !== $record['subdomain'] && isSubdomainBlocked($subdomain)) {
            showError("前缀 \"$subdomain\" 已被系统拦截，无法修改为此子域名！");
            redirect('dns_manage.php');
        }
        
        try {
            // 使用统一的DNS管理器
            $dns_manager = new DNSManager($current_domain);
            $full_name = $subdomain === '@' ? $current_domain['domain_name'] : $subdomain . '.' . $current_domain['domain_name'];
            
            // 对于彩虹DNS，代理功能不可用
            if (isset($current_domain['provider_type']) && $current_domain['provider_type'] === 'rainbow') {
                $proxied = 0;
            }
            
            // 对于彩虹DNS，需要使用子域名而不是完整域名
            if (isset($current_domain['provider_type']) && $current_domain['provider_type'] === 'rainbow') {
                $record_name = $subdomain; // 彩虹DNS使用子域名
            } else {
                $record_name = $full_name; // Cloudflare使用完整域名
            }
            
            // 获取原始记录的完整域名
            $old_full_name = $record['subdomain'] === '@' ? $current_domain['domain_name'] : $record['subdomain'] . '.' . $current_domain['domain_name'];
            
            $update_success = false;
            $current_cloudflare_id = $record['cloudflare_id'];
            
            try {
                // 尝试更新DNS记录
                $dns_manager->updateDNSRecord($current_domain['zone_id'], $current_cloudflare_id, $type, $record_name, $content, [
                    'proxied' => (bool)$proxied,
                    'remark' => $remark
                ]);
                $update_success = true;
            } catch (Exception $update_error) {
                // 检查是否是"记录不存在"错误
                if (strpos($update_error->getMessage(), 'Record does not exist') !== false || 
                    strpos($update_error->getMessage(), 'does not exist') !== false ||
                    strpos($update_error->getMessage(), '记录不存在') !== false) {
                    
                    // 尝试从DNS提供商重新同步记录ID
                    try {
                        $remote_records = $dns_manager->getDNSRecords($current_domain['zone_id']);
                        $found_record = null;
                        
                        foreach ($remote_records as $remote_record) {
                            // 匹配记录名称和类型
                            $remote_name = $remote_record['name'] ?? '';
                            $remote_type = strtoupper($remote_record['type'] ?? '');
                            $local_type = strtoupper($record['type']);
                            
                            // 标准化记录名称以进行比较
                            if ($current_domain['provider_type'] === 'rainbow') {
                                // 彩虹DNS使用子域名
                                $compare_name = $record['subdomain'];
                            } else {
                                // Cloudflare使用完整域名
                                $compare_name = $old_full_name;
                            }
                            
                            if ($remote_name === $compare_name && $remote_type === $local_type) {
                                $found_record = $remote_record;
                                break;
                            }
                        }
                        
                        if ($found_record) {
                            // 找到匹配的记录，更新本地数据库中的cloudflare_id
                            $new_cloudflare_id = $found_record['id'] ?? $found_record['RecordId'] ?? null;
                            
                            if ($new_cloudflare_id) {
                                // 更新本地数据库中的cloudflare_id
                                $update_stmt = $db->prepare("UPDATE dns_records SET cloudflare_id = ? WHERE id = ?");
                                $update_stmt->bindValue(1, $new_cloudflare_id, SQLITE3_TEXT);
                                $update_stmt->bindValue(2, $record_id, SQLITE3_INTEGER);
                                $update_stmt->execute();
                                
                                // 使用新的ID重试更新
                                $dns_manager->updateDNSRecord($current_domain['zone_id'], $new_cloudflare_id, $type, $record_name, $content, [
                                    'proxied' => (bool)$proxied,
                                    'remark' => $remark
                                ]);
                                
                                $update_success = true;
                                $current_cloudflare_id = $new_cloudflare_id;
                            }
                        } else {
                            // 记录在DNS提供商中不存在，自动重新创建
                            // 某些记录类型不能启用代理
                            $non_proxiable_types = ['NS', 'MX', 'TXT', 'SRV', 'CAA'];
                            $final_proxied = in_array(strtoupper($type), $non_proxiable_types) ? false : (bool)$proxied;
                            
                            // 创建新记录
                            $create_result = $dns_manager->createDNSRecord($current_domain['zone_id'], $type, $record_name, $content, [
                                'proxied' => $final_proxied,
                                'remark' => $remark
                            ]);
                            
                            // 更新本地数据库中的cloudflare_id
                            $new_cloudflare_id = isset($create_result['RecordId']) ? $create_result['RecordId'] : $create_result['id'];
                            $update_success = true;
                            $current_cloudflare_id = $new_cloudflare_id;
                        }
                    } catch (Exception $sync_error) {
                        // 如果同步失败，抛出原始错误
                        throw new Exception('DNS记录同步失败: ' . $sync_error->getMessage());
                    }
                } else {
                    // 其他类型的错误，直接抛出
                    throw $update_error;
                }
            }
            
            if ($update_success) {
                // 更新本地数据库
                $stmt = $db->prepare("UPDATE dns_records SET subdomain = ?, type = ?, content = ?, remark = ?, proxied = ?, cloudflare_id = ? WHERE id = ?");
                $stmt->bindValue(1, $subdomain, SQLITE3_TEXT);
                $stmt->bindValue(2, $type, SQLITE3_TEXT);
                $stmt->bindValue(3, $content, SQLITE3_TEXT);
                $stmt->bindValue(4, $remark, SQLITE3_TEXT);
                $stmt->bindValue(5, $proxied, SQLITE3_INTEGER);
                $stmt->bindValue(6, $current_cloudflare_id, SQLITE3_TEXT);
                $stmt->bindValue(7, $record_id, SQLITE3_INTEGER);
                $stmt->execute();
                
                logAction('user', $_SESSION['user_id'], 'edit_dns_record', "修改DNS记录: {$subdomain}.{$current_domain['domain_name']}");
                showSuccess('DNS记录修改成功！');
            }
        } catch (Exception $e) {
            showError('修改失败: ' . $e->getMessage());
        }
    } else {
        showError('记录不存在或无权限修改！');
    }
    redirect('dns_manage.php');
}

// 处理删除DNS记录
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete_record'])) {
    $record_id = (int)getPost('record_id');
    
    $record = $db->querySingle("SELECT * FROM dns_records WHERE id = $record_id AND user_id = {$_SESSION['user_id']}", true);
    if ($record && $current_domain) {
        try {
            // 使用统一的DNS管理器
            $dns_manager = new DNSManager($current_domain);
            
            $delete_success = false;
            
            try {
                // 尝试删除DNS记录
                $dns_manager->deleteDNSRecord($current_domain['zone_id'], $record['cloudflare_id']);
                $delete_success = true;
            } catch (Exception $delete_error) {
                // 检查是否是"记录不存在"错误
                if (strpos($delete_error->getMessage(), 'Record does not exist') !== false || 
                    strpos($delete_error->getMessage(), 'does not exist') !== false ||
                    strpos($delete_error->getMessage(), '记录不存在') !== false) {
                    
                    // 记录在远程已经不存在了，直接删除本地记录即可
                    $delete_success = true;
                } else {
                    // 其他类型的错误，直接抛出
                    throw $delete_error;
                }
            }
            
            if ($delete_success) {
                $db->exec("DELETE FROM dns_records WHERE id = $record_id");
                
                logAction('user', $_SESSION['user_id'], 'delete_dns_record', "删除DNS记录: {$record['subdomain']}.{$current_domain['domain_name']}");
                showSuccess('DNS记录删除成功！');
            }
        } catch (Exception $e) {
            showError('删除失败: ' . $e->getMessage());
        }
    } else {
        showError('记录不存在或无权限删除！');
    }
    redirect('dns_manage.php');
}

// 获取用户的所有DNS记录（包含域名信息）
$dns_records = [];
$stmt = $db->prepare("
    SELECT dr.*, d.domain_name, d.provider_type 
    FROM dns_records dr 
    JOIN domains d ON dr.domain_id = d.id 
    WHERE dr.user_id = ? AND (dr.is_system = 0 OR dr.is_system IS NULL)
    ORDER BY dr.created_at DESC
");
$stmt->bindValue(1, $_SESSION['user_id'], SQLITE3_INTEGER);
$result = $stmt->execute();
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $dns_records[] = $row;
}

// 按域名分组记录
$records_by_domain = [];
foreach ($dns_records as $record) {
    $domain_id = $record['domain_id'];
    if (!isset($records_by_domain[$domain_id])) {
        $records_by_domain[$domain_id] = [
            'domain_name' => $record['domain_name'],
            'provider_type' => $record['provider_type'],
            'records' => []
        ];
    }
    $records_by_domain[$domain_id]['records'][] = $record;
}

// 获取启用的DNS记录类型
$enabled_dns_types = getEnabledDNSTypes();

// 公告仅在首页显示，此页面不需要获取公告
// $user_announcements = getUserAnnouncements($_SESSION['user_id']);

// 获取被拦截的前缀列表（用于前端验证）
$blocked_prefixes = getBlockedPrefixes();

$page_title = '用户面板';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="main-content">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3" style="border-bottom: 1px solid rgba(255, 255, 255, 0.2);">
                <div>
                    <h1 class="h2">
                        <i class="fas fa-cog me-2"></i>DNS记录管理
                    </h1>
                    <?php if ($auto_fill_mode && $current_domain): ?>
                    <p class="text-muted mb-0">
                        <i class="fas fa-magic me-1"></i>
                        准备添加解析：<strong><?php echo htmlspecialchars($auto_prefix . '.' . $current_domain['domain_name']); ?></strong>
                    </p>
                    <?php endif; ?>
                </div>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <?php if ($user_group): 
                        $badge_class = 'bg-secondary';
                        if ($user_group['group_name'] === 'vip') $badge_class = 'bg-info';
                        if ($user_group['group_name'] === 'svip') $badge_class = 'bg-warning text-dark';
                    ?>
                    <span class="badge <?php echo $badge_class; ?> fs-6 me-2" title="<?php echo htmlspecialchars($user_group['description']); ?>">
                        <i class="fas fa-user-tag me-1"></i><?php echo htmlspecialchars($user_group['display_name']); ?>
                    </span>
                    <?php endif; ?>
                    <span class="badge bg-primary fs-6 me-2">
                        <i class="fas fa-coins me-1"></i>积分: <?php echo $_SESSION['user_points']; ?>
                    </span>
                    <span class="badge bg-success fs-6 me-2">
                        <i class="fas fa-list me-1"></i>记录: <?php echo $current_record_count; ?><?php if ($user_group && $user_group['max_records'] != -1): ?>/<?php echo $user_group['max_records']; ?><?php endif; ?>
                    </span>
                    <?php if (!empty($domains)): ?>
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addRecordModal" 
                            <?php if ($auto_fill_mode): ?>onclick="autoFillForm()"<?php endif; ?>>
                        <i class="fas fa-plus me-1"></i>添加记录
                    </button>
                    <?php endif; ?>
                </div>
            </div>
            
            <!-- 消息提示 -->
            <?php if (isset($messages['success'])): ?>
                <div class="alert alert-success alert-dismissible fade show">
                    <?php echo htmlspecialchars($messages['success']); ?>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            <?php endif; ?>
            
            <?php if (isset($messages['error'])): ?>
                <div class="alert alert-danger alert-dismissible fade show">
                    <?php echo htmlspecialchars($messages['error']); ?>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            <?php endif; ?>
            
            <!-- 统计信息 -->
            <div class="row mb-4">
                <div class="col-xl-3 col-md-6 mb-3">
                    <div class="card border-left-primary shadow h-100 py-2">
                        <div class="card-body">
                            <div class="row no-gutters align-items-center">
                                <div class="col mr-2">
                                    <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">总记录数</div>
                                    <div class="h5 mb-0 font-weight-bold"><?php echo count($dns_records); ?></div>
                                </div>
                                <div class="col-auto">
                                    <i class="fas fa-list fa-2x text-gray-300"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-xl-3 col-md-6 mb-3">
                    <div class="card border-left-success shadow h-100 py-2">
                        <div class="card-body">
                            <div class="row no-gutters align-items-center">
                                <div class="col mr-2">
                                    <div class="text-xs font-weight-bold text-success text-uppercase mb-1">可用域名</div>
                                    <div class="h5 mb-0 font-weight-bold"><?php echo count($domains); ?></div>
                                </div>
                                <div class="col-auto">
                                    <i class="fas fa-globe fa-2x text-gray-300"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-xl-3 col-md-6 mb-3">
                    <div class="card border-left-info shadow h-100 py-2">
                        <div class="card-body">
                            <div class="row no-gutters align-items-center">
                                <div class="col mr-2">
                                    <div class="text-xs font-weight-bold text-info text-uppercase mb-1">当前积分</div>
                                    <div class="h5 mb-0 font-weight-bold"><?php echo $_SESSION['user_points']; ?></div>
                                </div>
                                <div class="col-auto">
                                    <i class="fas fa-coins fa-2x text-gray-300"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-xl-3 col-md-6 mb-3">
                    <div class="card border-left-warning shadow h-100 py-2">
                        <div class="card-body">
                            <div class="row no-gutters align-items-center">
                                <div class="col mr-2">
                                    <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">代理记录</div>
                                    <div class="h5 mb-0 font-weight-bold"><?php echo count(array_filter($dns_records, function($r) { return $r['proxied']; })); ?></div>
                                </div>
                                <div class="col-auto">
                                    <i class="fas fa-shield-alt fa-2x text-gray-300"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- DNS记录列表 - 按域名分组显示 -->
            <?php if (!empty($records_by_domain)): ?>
                <?php foreach ($records_by_domain as $domain_id => $domain_data): ?>
                <div class="card shadow mb-4">
                    <div class="card-header py-3 d-flex justify-content-between align-items-center">
                        <h6 class="m-0 font-weight-bold text-primary">
                            <i class="fas fa-globe me-2"></i><?php echo htmlspecialchars($domain_data['domain_name']); ?>
                            <span class="badge bg-secondary ms-2"><?php echo count($domain_data['records']); ?> 条记录</span>
                        </h6>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-bordered table-hover">
                                <thead>
                                    <tr>
                                        <th>子域名</th>
                                        <th>类型</th>
                                        <th>内容</th>
                                        <th>备注</th>
                                        <th>代理状态</th>
                                        <th>创建时间</th>
                                        <th>操作</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($domain_data['records'] as $record): ?>
                                    <tr>
                                        <td>
                                            <code><?php echo htmlspecialchars($record['subdomain']); ?></code>
                                        </td>
                                        <td>
                                            <span class="badge bg-info"><?php echo $record['type']; ?></span>
                                        </td>
                                        <td class="text-break"><?php echo htmlspecialchars($record['content']); ?></td>
                                        <td>
                                            <?php if (!empty($record['remark'])): ?>
                                                <span class="text-muted" title="<?php echo htmlspecialchars($record['remark']); ?>">
                                                    <i class="fas fa-comment-alt me-1"></i>
                                                    <?php echo htmlspecialchars(mb_strlen($record['remark']) > 20 ? mb_substr($record['remark'], 0, 20) . '...' : $record['remark']); ?>
                                                </span>
                                            <?php else: ?>
                                                <span class="text-muted">-</span>
                                            <?php endif; ?>
                                        </td>
                                        <td>
                                            <?php if ($record['proxied']): ?>
                                                <span class="badge bg-warning">已代理</span>
                                            <?php else: ?>
                                                <span class="badge bg-secondary">仅DNS</span>
                                            <?php endif; ?>
                                        </td>
                                        <td><?php echo formatTime($record['created_at']); ?></td>
                                        <td>
                                            <button type="button" class="btn btn-sm btn-primary me-1" 
                                                    onclick="editRecord(<?php echo htmlspecialchars(json_encode($record)); ?>)"
                                                    title="修改记录">
                                                <i class="fas fa-edit"></i>
                                            </button>
                                            <form method="POST" style="display: inline;">
                                                <input type="hidden" name="record_id" value="<?php echo $record['id']; ?>">
                                                <button type="submit" name="delete_record" class="btn btn-sm btn-danger" 
                                                        onclick="return confirmDelete('确定要删除这条DNS记录吗？')"
                                                        title="删除记录">
                                                    <i class="fas fa-trash"></i>
                                                </button>
                                            </form>
                                        </td>
                                    </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                <?php endforeach; ?>
            <?php else: ?>
                <div class="card shadow">
                    <div class="card-body text-center py-5">
                        <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                        <h5 class="text-muted">暂无DNS记录</h5>
                        <p class="text-muted">点击上方"添加记录"按钮创建您的第一条DNS记录</p>
                    </div>
                </div>
            <?php endif; ?>
            
            <?php if (empty($domains)): ?>
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle me-2"></i>
                系统暂无可用域名，请联系管理员添加域名配置。
            </div>
            <?php endif; ?>
            </div>
        </main>
    </div>
</div>

<!-- 添加DNS记录模态框 -->
<?php if (!empty($domains)): ?>
<div class="modal fade" id="addRecordModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">添加DNS记录</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <?php if ($user_group): ?>
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        您的用户组：<strong><?php echo htmlspecialchars($user_group['display_name']); ?></strong> | 
                        <?php if ($required_points > 0): ?>
                            添加一条DNS记录需要消耗 <strong><?php echo $required_points; ?></strong> 积分
                        <?php else: ?>
                            <strong class="text-success">免费添加</strong> DNS记录
                        <?php endif; ?>
                        <?php if ($user_group['max_records'] != -1): ?>
                            | 已用 <strong><?php echo $current_record_count; ?>/<?php echo $user_group['max_records']; ?></strong> 条
                        <?php else: ?>
                            | 已用 <strong><?php echo $current_record_count; ?></strong> 条（无限制）
                        <?php endif; ?>
                    </div>
                    <?php endif; ?>
                    <div class="mb-3">
                        <label for="add_domain_id" class="form-label">选择域名</label>
                        <select class="form-select" id="add_domain_id" name="add_domain_id" required onchange="updateDomainSuffix()">
                            <?php foreach ($domains as $domain): ?>
                                <option value="<?php echo $domain['id']; ?>" 
                                        data-domain-name="<?php echo htmlspecialchars($domain['domain_name']); ?>"
                                        data-provider-type="<?php echo htmlspecialchars($domain['provider_type'] ?? 'cloudflare'); ?>"
                                        data-proxied-default="<?php echo $domain['proxied_default'] ? '1' : '0'; ?>"
                                        <?php echo ($auto_fill_mode && $domain['id'] == $auto_domain_id) || (!$auto_fill_mode && $domain['id'] == $selected_domain_id) ? 'selected' : ''; ?>>
                                    <?php echo htmlspecialchars($domain['domain_name']); ?>
                                </option>
                            <?php endforeach; ?>
                        </select>
                        <div class="form-text">选择要添加DNS记录的域名</div>
                    </div>
                    <div class="mb-3">
                        <label for="subdomain" class="form-label">子域名</label>
                        <div class="input-group">
                            <input type="text" class="form-control" id="subdomain" name="subdomain" 
                                   placeholder="www" 
                                   value="<?php echo $auto_fill_mode ? htmlspecialchars($auto_prefix) : ''; ?>" 
                                   required oninput="checkAndUpdateConflict()">
                            <span class="input-group-text" id="domain-suffix">.<?php echo htmlspecialchars(($auto_fill_mode && $current_domain) ? $current_domain['domain_name'] : $domains[0]['domain_name']); ?></span>
                        </div>
                        <div class="form-text">输入 @ 表示根域名</div>
                        <div id="conflict-warning-add" style="display: none;"></div>
                        <?php if ($auto_fill_mode): ?>
                        <div class="alert alert-success mt-2">
                            <i class="fas fa-magic me-2"></i>已自动填入前缀：<strong><?php echo htmlspecialchars($auto_prefix); ?></strong>
                        </div>
                        <?php endif; ?>
                    </div>
                    <div class="mb-3">
                        <label for="type" class="form-label">记录类型</label>
                        <select class="form-select" id="type" name="type" required onchange="updateContentPlaceholder(); checkAndUpdateConflict();">
                            <?php if (empty($enabled_dns_types)): ?>
                                <option value="">暂无可用的记录类型</option>
                            <?php else: ?>
                                <?php foreach ($enabled_dns_types as $dns_type): ?>
                                    <option value="<?php echo $dns_type['type_name']; ?>">
                                        <?php echo htmlspecialchars($dns_type['type_name']); ?> - <?php echo htmlspecialchars($dns_type['description']); ?>
                                    </option>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </select>
                        <?php if (empty($enabled_dns_types)): ?>
                            <div class="form-text text-danger">
                                <i class="fas fa-exclamation-triangle me-1"></i>
                                管理员暂未启用任何DNS记录类型，请联系管理员。
                            </div>
                        <?php endif; ?>
                    </div>
                    <div class="mb-3">
                        <label for="content" class="form-label">记录值</label>
                        <input type="text" class="form-control" id="content" name="content" placeholder="192.168.1.1" required oninput="checkAndUpdateConflict()">
                        <div class="form-text" id="content-help">
                            请输入对应记录类型的值
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="remark" class="form-label">备注 <span class="text-muted">(可选)</span></label>
                        <input type="text" class="form-control" id="remark" name="remark" placeholder="例如：网站主页、API接口、邮件服务器等" maxlength="100">
                        <div class="form-text">添加备注可以帮助您区分不同解析记录的用途</div>
                    </div>
                    <div class="mb-3" id="proxied-section" style="display: <?php 
                        $first_domain = ($auto_fill_mode && $current_domain) ? $current_domain : $domains[0];
                        echo (isset($first_domain['provider_type']) && $first_domain['provider_type'] === 'rainbow') ? 'none' : 'block'; 
                    ?>;">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="proxied" name="proxied" value="1" 
                                   <?php echo $first_domain['proxied_default'] ? 'checked' : ''; ?>>
                            <label class="form-check-label" for="proxied">
                                启用Cloudflare代理
                            </label>
                        </div>
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            仅A、AAAA、CNAME记录支持代理功能。NS、MX、TXT、SRV等记录类型会自动禁用代理。
                        </div>
                    </div>
                    <div class="alert alert-info" id="rainbow-info-alert" style="display: <?php 
                        echo (isset($first_domain['provider_type']) && $first_domain['provider_type'] === 'rainbow') ? 'block' : 'none'; 
                    ?>;">
                        <i class="fas fa-info-circle me-2"></i>
                        彩虹DNS不支持代理功能，所有记录将直接解析。
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="add_record" class="btn btn-primary" <?php echo empty($enabled_dns_types) ? 'disabled' : ''; ?>>
                        添加记录
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
<?php endif; ?>

<!-- 修改DNS记录模态框 -->
<?php if (!empty($domains)): ?>
<div class="modal fade" id="editRecordModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">修改DNS记录</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <input type="hidden" id="edit_record_id" name="record_id">
                    <div class="mb-3">
                        <label for="edit_subdomain" class="form-label">子域名</label>
                        <div class="input-group">
                            <input type="text" class="form-control" id="edit_subdomain" name="subdomain" placeholder="www" required>
                            <span class="input-group-text" id="edit-domain-suffix"></span>
                        </div>
                        <div class="form-text">输入 @ 表示根域名</div>
                    </div>
                    <div class="mb-3">
                        <label for="edit_type" class="form-label">记录类型</label>
                        <select class="form-select" id="edit_type" name="type" required onchange="updateEditContentPlaceholder()">
                            <?php if (empty($enabled_dns_types)): ?>
                                <option value="">暂无可用的记录类型</option>
                            <?php else: ?>
                                <?php foreach ($enabled_dns_types as $dns_type): ?>
                                    <option value="<?php echo $dns_type['type_name']; ?>">
                                        <?php echo htmlspecialchars($dns_type['type_name']); ?> - <?php echo htmlspecialchars($dns_type['description']); ?>
                                    </option>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="edit_content" class="form-label">记录值</label>
                        <input type="text" class="form-control" id="edit_content" name="content" placeholder="192.168.1.1" required>
                        <div class="form-text" id="edit-content-help">
                            请输入对应记录类型的值
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="edit_remark" class="form-label">备注 <span class="text-muted">(可选)</span></label>
                        <input type="text" class="form-control" id="edit_remark" name="remark" placeholder="例如：网站主页、API接口、邮件服务器等" maxlength="100">
                        <div class="form-text">添加备注可以帮助您区分不同解析记录的用途</div>
                    </div>
                    <div class="mb-3" id="edit-proxied-section">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="edit_proxied" name="proxied" value="1">
                            <label class="form-check-label" for="edit_proxied">
                                启用Cloudflare代理
                            </label>
                        </div>
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            仅A、AAAA、CNAME记录支持代理功能
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="edit_record" class="btn btn-primary">
                        保存修改
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>
<?php endif; ?>

<script>
// 自动填充参数
const autoPrefix = '<?php echo addslashes($auto_prefix); ?>';
const autoFillMode = <?php echo $auto_fill_mode ? 'true' : 'false'; ?>;

function switchDomain(domainId) {
    if (domainId) {
        window.location.href = 'dashboard.php?domain_id=' + domainId;
    }
}

// 更新域名后缀显示
function updateDomainSuffix() {
    const selectElement = document.getElementById('add_domain_id');
    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const domainName = selectedOption.getAttribute('data-domain-name');
    const providerType = selectedOption.getAttribute('data-provider-type');
    const proxiedDefault = selectedOption.getAttribute('data-proxied-default');
    
    // 更新域名后缀显示
    const suffixElement = document.getElementById('domain-suffix');
    if (suffixElement) {
        suffixElement.textContent = '.' + domainName;
    }
    
    // 更新代理选项的显示和默认值
    const proxiedSection = document.getElementById('proxied-section');
    const proxiedCheckbox = document.getElementById('proxied');
    const rainbowInfoAlert = document.getElementById('rainbow-info-alert');
    
    if (providerType === 'rainbow') {
        // 彩虹DNS不支持代理
        if (proxiedSection) {
            proxiedSection.style.display = 'none';
        }
        if (rainbowInfoAlert) {
            rainbowInfoAlert.style.display = 'block';
        }
    } else {
        // Cloudflare支持代理
        if (proxiedSection) {
            proxiedSection.style.display = 'block';
        }
        if (rainbowInfoAlert) {
            rainbowInfoAlert.style.display = 'none';
        }
        // 设置默认值
        if (proxiedCheckbox) {
            proxiedCheckbox.checked = (proxiedDefault === '1');
        }
    }
    
    // 触发冲突检查
    checkAndUpdateConflict();
}

function autoFillForm() {
    if (autoFillMode && autoPrefix) {
        // 延迟执行，确保模态框已完全显示
        setTimeout(function() {
            document.getElementById('subdomain').value = autoPrefix;
            document.getElementById('subdomain').focus();
            
            // 添加高亮效果
            const subdomainField = document.getElementById('subdomain');
            subdomainField.style.backgroundColor = '#d4edda';
            subdomainField.style.borderColor = '#28a745';
            
            // 3秒后移除高亮
            setTimeout(function() {
                subdomainField.style.backgroundColor = '';
                subdomainField.style.borderColor = '';
            }, 3000);
            
            // 显示提示信息
            showAutoFillNotice();
        }, 300);
    }
}

function showAutoFillNotice() {
    // 创建提示元素
    const notice = document.createElement('div');
    notice.className = 'alert alert-success alert-dismissible fade show mt-3';
    notice.innerHTML = `
        <i class="fas fa-check-circle me-2"></i>
        <strong>自动填充完成！</strong> 前缀已填入，请选择记录类型和记录值。
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // 插入到表单顶部
    const modalBody = document.querySelector('#addRecordModal .modal-body');
    const firstChild = modalBody.firstElementChild.nextElementSibling;
    modalBody.insertBefore(notice, firstChild);
    
    // 5秒后自动移除
    setTimeout(function() {
        if (notice.parentNode) {
            notice.remove();
        }
    }, 5000);
}

// 页面加载时检查是否需要自动打开模态框
document.addEventListener('DOMContentLoaded', function() {
    if (autoFillMode) {
        // 自动打开添加记录模态框
        setTimeout(function() {
            const addModal = new bootstrap.Modal(document.getElementById('addRecordModal'));
            addModal.show();
            autoFillForm();
        }, 500);
    }
});

function updateContentPlaceholder() {
    const typeSelect = document.getElementById('type');
    const contentInput = document.getElementById('content');
    const contentHelp = document.getElementById('content-help');
    const proxiedSection = document.getElementById('proxied-section');
    
    const type = typeSelect.value;
    const isRainbowDNS = <?php echo (isset($current_domain['provider_type']) && $current_domain['provider_type'] === 'rainbow') ? 'true' : 'false'; ?>;
    
    // 定义记录类型的配置
    const typeConfigs = {
        'A': {
            placeholder: '192.168.1.1',
            help: '请输入IPv4地址',
            showProxied: true
        },
        'AAAA': {
            placeholder: '2001:db8::1',
            help: '请输入IPv6地址',
            showProxied: true
        },
        'CNAME': {
            placeholder: 'example.com',
            help: '请输入目标域名',
            showProxied: true
        },
        'MX': {
            placeholder: '10 mail.example.com',
            help: '请输入优先级和邮件服务器地址',
            showProxied: false
        },
        'NS': {
            placeholder: 'ns1.example.com',
            help: '请输入域名服务器地址',
            showProxied: false
        },
        'TXT': {
            placeholder: 'v=spf1 include:_spf.google.com ~all',
            help: '请输入文本内容',
            showProxied: false
        },
        'SRV': {
            placeholder: '10 5 443 target.example.com',
            help: '请输入优先级 权重 端口 目标',
            showProxied: false
        },
        'PTR': {
            placeholder: 'example.com',
            help: '请输入反向解析的域名',
            showProxied: false
        },
        'CAA': {
            placeholder: '0 issue "letsencrypt.org"',
            help: '请输入CAA记录值',
            showProxied: false
        }
    };
    
    const config = typeConfigs[type];
    if (config) {
        contentInput.placeholder = config.placeholder;
        contentHelp.textContent = config.help;
        // 对于彩虹DNS，隐藏代理选项
        if (proxiedSection) {
            proxiedSection.style.display = (config.showProxied && !isRainbowDNS) ? 'block' : 'none';
        }
    } else {
        contentInput.placeholder = '';
        contentHelp.textContent = '请输入对应记录类型的值';
        if (proxiedSection) {
            proxiedSection.style.display = 'none';
        }
    }
}

function updateEditContentPlaceholder() {
    const typeSelect = document.getElementById('edit_type');
    const contentInput = document.getElementById('edit_content');
    const contentHelp = document.getElementById('edit-content-help');
    const proxiedSection = document.getElementById('edit-proxied-section');
    
    const type = typeSelect.value;
    
    // 定义记录类型的配置
    const typeConfigs = {
        'A': {
            placeholder: '192.168.1.1',
            help: '请输入IPv4地址',
            showProxied: true
        },
        'AAAA': {
            placeholder: '2001:db8::1',
            help: '请输入IPv6地址',
            showProxied: true
        },
        'CNAME': {
            placeholder: 'example.com',
            help: '请输入目标域名',
            showProxied: true
        },
        'MX': {
            placeholder: '10 mail.example.com',
            help: '请输入优先级和邮件服务器地址',
            showProxied: false
        },
        'NS': {
            placeholder: 'ns1.example.com',
            help: '请输入域名服务器地址',
            showProxied: false
        },
        'TXT': {
            placeholder: 'v=spf1 include:_spf.google.com ~all',
            help: '请输入文本内容',
            showProxied: false
        },
        'SRV': {
            placeholder: '10 5 443 target.example.com',
            help: '请输入优先级 权重 端口 目标',
            showProxied: false
        },
        'PTR': {
            placeholder: 'example.com',
            help: '请输入反向解析的域名',
            showProxied: false
        },
        'CAA': {
            placeholder: '0 issue "letsencrypt.org"',
            help: '请输入CAA记录值',
            showProxied: false
        }
    };
    
    const config = typeConfigs[type];
    if (config) {
        contentInput.placeholder = config.placeholder;
        contentHelp.textContent = config.help;
        // 代理选项的显示/隐藏由 editRecord 函数控制，这里不做处理
    } else {
        contentInput.placeholder = '';
        contentHelp.textContent = '请输入对应记录类型的值';
    }
}

function editRecord(record) {
    // 填充表单数据
    document.getElementById('edit_record_id').value = record.id;
    document.getElementById('edit_subdomain').value = record.subdomain;
    document.getElementById('edit_type').value = record.type;
    document.getElementById('edit_content').value = record.content;
    document.getElementById('edit_remark').value = record.remark || '';
    document.getElementById('edit_proxied').checked = record.proxied == 1;
    
    // 更新域名后缀显示
    const editSuffixElement = document.getElementById('edit-domain-suffix');
    if (editSuffixElement && record.domain_name) {
        editSuffixElement.textContent = '.' + record.domain_name;
    }
    
    // 根据提供商类型显示/隐藏代理选项
    const editProxiedSection = document.getElementById('edit-proxied-section');
    if (editProxiedSection) {
        if (record.provider_type === 'rainbow') {
            editProxiedSection.style.display = 'none';
        } else {
            editProxiedSection.style.display = 'block';
        }
    }
    
    // 更新内容占位符和帮助文本
    updateEditContentPlaceholder();
    
    // 显示模态框
    var modal = new bootstrap.Modal(document.getElementById('editRecordModal'));
    modal.show();
}

function confirmDelete(message) {
    return confirm(message);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    updateContentPlaceholder();
    
    // 显示公告
    showAnnouncements();
    
    // 初始化前缀检查
    initPrefixValidation();
});

// 被拦截的前缀列表
const blockedPrefixes = <?php echo json_encode($blocked_prefixes); ?>;

// 初始化前缀验证
function initPrefixValidation() {
    const subdomainInput = document.getElementById('subdomain');
    const editSubdomainInput = document.getElementById('edit_subdomain');
    
    if (subdomainInput) {
        subdomainInput.addEventListener('input', function() {
            validateSubdomain(this, 'subdomain-warning');
        });
        subdomainInput.addEventListener('blur', function() {
            validateSubdomain(this, 'subdomain-warning');
        });
    }
    
    if (editSubdomainInput) {
        editSubdomainInput.addEventListener('input', function() {
            validateSubdomain(this, 'edit-subdomain-warning');
        });
        editSubdomainInput.addEventListener('blur', function() {
            validateSubdomain(this, 'edit-subdomain-warning');
        });
    }
}

// 验证子域名前缀
function validateSubdomain(input, warningId) {
    const subdomain = input.value.toLowerCase().trim();
    const warningElement = document.getElementById(warningId);
    
    // 移除现有的警告元素
    if (warningElement) {
        warningElement.remove();
    }
    
    // 检查是否为空
    if (!subdomain) {
        input.classList.remove('is-invalid', 'is-valid');
        return;
    }
    
    // 检查是否被拦截
    if (blockedPrefixes.includes(subdomain)) {
        input.classList.add('is-invalid');
        input.classList.remove('is-valid');
        
        // 添加警告提示
        const warning = document.createElement('div');
        warning.id = warningId;
        warning.className = 'invalid-feedback';
        warning.innerHTML = '<i class="fas fa-exclamation-triangle me-1"></i>此前缀已被系统拦截，无法使用！';
        input.parentNode.appendChild(warning);
        
        // 禁用提交按钮
        const submitBtn = input.closest('form').querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = true;
        }
    } else {
        input.classList.add('is-valid');
        input.classList.remove('is-invalid');
        
        // 启用提交按钮
        const submitBtn = input.closest('form').querySelector('button[type="submit"]');
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    }
}

// 显示公告弹窗
function showAnnouncements() {
    // 公告功能已移除，仅在首页显示
    const announcements = [];
    
    if (announcements.length > 0) {
        // 延迟1秒显示公告，让页面完全加载
        setTimeout(() => {
            showAnnouncementModal(announcements, 0);
        }, 1000);
    }
}

// 显示公告模态框
function showAnnouncementModal(announcements, index) {
    if (index >= announcements.length) {
        return; // 所有公告都显示完了
    }
    
    const announcement = announcements[index];
    
    // 设置模态框内容
    document.getElementById('announcementTitle').textContent = announcement.title;
    document.getElementById('announcementContent').innerHTML = announcement.content;
    document.getElementById('announcementTime').textContent = '发布时间：' + formatDateTime(announcement.created_at);
    
    // 设置公告类型样式
    const modal = document.getElementById('announcementModal');
    const header = modal.querySelector('.modal-header');
    
    // 移除之前的类型样式
    header.classList.remove('bg-info', 'bg-success', 'bg-warning', 'bg-danger');
    
    // 添加对应的类型样式
    switch (announcement.type) {
        case 'success':
            header.classList.add('bg-success');
            break;
        case 'warning':
            header.classList.add('bg-warning');
            break;
        case 'danger':
            header.classList.add('bg-danger');
            break;
        default:
            header.classList.add('bg-info');
    }
    
    // 显示模态框
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // 记录查看
    markAnnouncementAsViewed(announcement.id);
    
    // 当模态框关闭时，显示下一个公告
    modal.addEventListener('hidden.bs.modal', function() {
        setTimeout(() => {
            showAnnouncementModal(announcements, index + 1);
        }, 500);
    }, { once: true });
}

// 标记公告为已查看
function markAnnouncementAsViewed(announcementId) {
    fetch('mark_announcement_viewed.php', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            announcement_id: announcementId
        })
    }).catch(error => {
        console.error('标记公告查看状态失败:', error);
    });
}

// 格式化日期时间
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// DNS冲突检测功能
function checkDNSConflict(subdomain, type, content) {
    if (!subdomain || !type || !content) return { hasConflict: false };
    
    const domainName = '<?php echo addslashes($current_domain['domain_name'] ?? ''); ?>';
    const fullName = subdomain === '@' ? domainName : `${subdomain}.${domainName}`;
    const targetType = type.toUpperCase();
    const conflictingTypes = ['A', 'AAAA', 'CNAME'];
    
    // 获取现有记录（从页面表格中提取）
    const existingRecords = [];
    const tableRows = document.querySelectorAll('table tbody tr');
    
    tableRows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 3) {
            const recordName = cells[0].textContent.trim();
            const recordType = cells[1].textContent.trim().toUpperCase();
            const recordContent = cells[2].textContent.trim();
            
            existingRecords.push({
                name: recordName,
                type: recordType,
                content: recordContent
            });
        }
    });
    
    // 检查冲突
    for (const record of existingRecords) {
        if (record.name.toLowerCase() === fullName.toLowerCase()) {
            // 检查类型冲突
            if (conflictingTypes.includes(record.type) && conflictingTypes.includes(targetType)) {
                return {
                    hasConflict: true,
                    type: 'type_conflict',
                    existingRecord: record,
                    message: `域名 '${fullName}' 已存在 ${record.type} 记录，无法添加 ${targetType} 记录`
                };
            }
            
            // 检查完全相同的记录
            if (record.type === targetType) {
                if (record.content === content) {
                    return {
                        hasConflict: true,
                        type: 'exact_match',
                        existingRecord: record,
                        message: `完全相同的DNS记录已存在`
                    };
                } else {
                    return {
                        hasConflict: true,
                        type: 'same_type',
                        existingRecord: record,
                        message: `域名 '${fullName}' 已存在相同类型的 ${record.type} 记录`
                    };
                }
            }
        }
    }
    
    return { hasConflict: false };
}

// 显示冲突警告
function showConflictWarning(elementId, conflictResult) {
    const warningElement = document.getElementById(elementId);
    if (!warningElement) return;
    
    if (conflictResult.hasConflict) {
        warningElement.innerHTML = `
            <div class="alert alert-warning alert-sm mt-2">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>冲突警告：</strong>${conflictResult.message}<br>
                <small>现有记录：${conflictResult.existingRecord.type} → ${conflictResult.existingRecord.content}</small>
            </div>
        `;
        warningElement.style.display = 'block';
    } else {
        warningElement.style.display = 'none';
    }
}

// 检查并更新冲突状态
function checkAndUpdateConflict() {
    const subdomainInput = document.getElementById('subdomain');
    const typeSelect = document.getElementById('type');
    const contentInput = document.getElementById('content');
    const submitButton = document.querySelector('button[name="add_record"]');
    
    if (subdomainInput && typeSelect && contentInput && submitButton) {
        const subdomain = subdomainInput.value;
        const type = typeSelect.value;
        const content = contentInput.value;
        
        if (subdomain && type && content) {
            const conflictResult = checkDNSConflict(subdomain, type, content);
            showConflictWarning('conflict-warning-add', conflictResult);
            
            // 如果有冲突，禁用提交按钮
            if (conflictResult.hasConflict) {
                submitButton.disabled = true;
                submitButton.title = '存在DNS记录冲突，无法提交';
                submitButton.classList.add('btn-secondary');
                submitButton.classList.remove('btn-primary');
            } else {
                submitButton.disabled = false;
                submitButton.title = '';
                submitButton.classList.add('btn-primary');
                submitButton.classList.remove('btn-secondary');
            }
        } else {
            // 清除警告
            showConflictWarning('conflict-warning-add', { hasConflict: false });
            if (submitButton) {
                submitButton.disabled = false;
                submitButton.classList.add('btn-primary');
                submitButton.classList.remove('btn-secondary');
            }
        }
    }
}
</script>


<!-- 公告功能已移至首页 (dashboard.php)，此页面不再显示公告 -->

<?php include 'includes/footer.php'; ?>