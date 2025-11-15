<?php
session_start();
require_once '../config/database.php';
require_once '../config/cloudflare.php';
require_once '../config/dns_manager.php';
require_once '../includes/functions.php';
require_once '../includes/user_groups.php';
require_once '../includes/security.php';

checkUserLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 更新用户积分到session
$user_points = $db->querySingle("SELECT points FROM users WHERE id = {$_SESSION['user_id']}");
$_SESSION['user_points'] = $user_points;

// 获取用户组信息
$user_group = getUserGroup($_SESSION['user_id']);
$required_points = getRequiredPoints($_SESSION['user_id']);
$current_record_count = getUserCurrentRecordCount($_SESSION['user_id']);

// 获取用户可访问的域名（根据用户组权限）
$domains = getUserAccessibleDomains($_SESSION['user_id']);

// 获取启用的DNS记录类型
$enabled_dns_types = [];
$result = $db->query("SELECT * FROM dns_record_types WHERE enabled = 1 ORDER BY type_name");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $enabled_dns_types[] = $row;
}

// 处理添加DNS记录
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_record'])) {
    // CSRF令牌验证
    $csrf_token = getPost('csrf_token', '');
    if (!Security::validateCSRFToken($csrf_token)) {
        showError('安全验证失败，请刷新页面后重试！');
        redirect('records.php');
    }
    
    // 操作频率限制检查（60秒内最多添加10条记录）
    $rateLimit = Security::checkOperationRateLimit($_SESSION['user_id'], 'add_dns_record', 10, 60);
    if (!$rateLimit['allowed']) {
        showError($rateLimit['message']);
        redirect('records.php');
    }
    
    $domain_id = (int)getPost('domain_id');
    $subdomain = getPost('subdomain');
    $type = getPost('type');
    $content = getPost('content');
    $proxied = getPost('proxied', 0);
    $remark = getPost('remark', '');
    
    // 获取选中的域名
    $selected_domain = null;
    foreach ($domains as $domain) {
        if ($domain['id'] == $domain_id) {
            $selected_domain = $domain;
            break;
        }
    }
    
    if (!$selected_domain) {
        showError('请选择一个有效的域名！');
    } elseif (!$subdomain || !$type || !$content) {
        showError('请填写完整信息！');
    } elseif (!isDNSTypeEnabled($type)) {
        showError('该DNS记录类型未启用！');
    } elseif (!checkUserDomainPermission($_SESSION['user_id'], $selected_domain['id'])) {
        showError('您的用户组无权访问此域名！请联系管理员升级用户组。');
    } elseif (!checkUserRecordLimit($_SESSION['user_id'])) {
        $max = $user_group['max_records'];
        showError("您已达到用户组的最大记录数限制（{$max}条）！请联系管理员升级用户组。");
    } elseif ($user_points < $required_points) {
        showError("积分不足！需要 {$required_points} 积分，您当前有 {$user_points} 积分。");
    } elseif (isSubdomainBlocked($subdomain)) {
        showError("前缀 \"$subdomain\" 已被系统拦截，无法创建此子域名！");
    } else {
        // 检查子域名前缀长度限制
        $groupManager = new UserGroupManager($db);
        $prefixCheck = $groupManager->checkPrefixLengthRestriction($_SESSION['user_id'], $subdomain);
        if (!$prefixCheck['allowed']) {
            showError($prefixCheck['message']);
            redirect('records.php');
        }
        
        // 验证DNS记录内容格式
        $contentValidation = validateDNSRecordContent($type, $content);
        if (!$contentValidation['valid']) {
            showError($contentValidation['message']);
            redirect('records.php');
        }
        
        try {
            // 使用统一的DNS管理器
            $dns_manager = new DNSManager($selected_domain);
            $full_name = $subdomain === '@' ? $selected_domain['domain_name'] : $subdomain . '.' . $selected_domain['domain_name'];
            
            // 检查子域名是否已被当前域名下的其他用户注册（同域名检查）
            $stmt = $db->prepare("
                SELECT dr.*, d.domain_name, dr.user_id as record_user_id
                FROM dns_records dr
                JOIN domains d ON dr.domain_id = d.id
                WHERE dr.subdomain = ? AND dr.domain_id = ? AND dr.status = 1
            ");
            $stmt->bindValue(1, $subdomain, SQLITE3_TEXT);
            $stmt->bindValue(2, $selected_domain['id'], SQLITE3_INTEGER);
            $result = $stmt->execute();
            
            $existing_records_in_domain = [];
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $existing_records_in_domain[] = $row;
            }
            
            // 检查前缀占用情况
            foreach ($existing_records_in_domain as $existing_record) {
                // 如果是NS记录
                if (strtoupper($type) === 'NS') {
                    // NS记录：只检查是否被其他用户占用
                    if ($existing_record['record_user_id'] != $_SESSION['user_id']) {
                        showError("子域名 \"{$subdomain}.{$selected_domain['domain_name']}\" 已被其他用户注册，无法添加NS记录！");
                        redirect('records.php');
                    }
                    // NS记录允许同一用户添加多条
                } else {
                    // 其他记录类型：该前缀已被占用（无论是自己还是别人）
                    // 只有当现有记录也是NS记录时才允许
                    if (strtoupper($existing_record['type']) !== 'NS') {
                        if ($existing_record['record_user_id'] == $_SESSION['user_id']) {
                            showError("子域名 \"{$subdomain}.{$selected_domain['domain_name']}\" 已被您占用，每个前缀只能创建一条非NS记录！");
                        } else {
                            showError("子域名 \"{$subdomain}.{$selected_domain['domain_name']}\" 已被其他用户注册，无法创建此记录！");
                        }
                        redirect('records.php');
                    }
                }
            }
            
            // 获取当前域名下的记录用于冲突检测
            $stmt = $db->prepare("
                SELECT * FROM dns_records 
                WHERE domain_id = ? AND subdomain = ? AND status = 1
            ");
            $stmt->bindValue(1, $selected_domain['id'], SQLITE3_INTEGER);
            $stmt->bindValue(2, $subdomain, SQLITE3_TEXT);
            $result = $stmt->execute();
            
            $local_records = [];
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $local_records[] = $row;
            }
            
            // 检查DNS冲突
            $conflict_result = checkLocalDNSConflict($local_records, $type, $content);
            
            if ($conflict_result['hasConflict']) {
                showError($conflict_result['message']);
            } else {
                // 添加DNS记录到服务商
                $remote_result = $dns_manager->addRecord($subdomain, $type, $content, $proxied);
                
                if ($remote_result['success']) {
                    // 保存到本地数据库
                    $stmt = $db->prepare("
                        INSERT INTO dns_records (
                            domain_id, user_id, subdomain, type, content, 
                            proxied, ttl, remark, remote_id, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ");
                    $stmt->bindValue(1, $selected_domain['id'], SQLITE3_INTEGER);
                    $stmt->bindValue(2, $_SESSION['user_id'], SQLITE3_INTEGER);
                    $stmt->bindValue(3, $subdomain, SQLITE3_TEXT);
                    $stmt->bindValue(4, $type, SQLITE3_TEXT);
                    $stmt->bindValue(5, $content, SQLITE3_TEXT);
                    $stmt->bindValue(6, $proxied ? 1 : 0, SQLITE3_INTEGER);
                    $stmt->bindValue(7, $remote_result['ttl'] ?? 1, SQLITE3_INTEGER);
                    $stmt->bindValue(8, $remark, SQLITE3_TEXT);
                    $stmt->bindValue(9, $remote_result['remote_id'] ?? '', SQLITE3_TEXT);
                    
                    if ($stmt->execute()) {
                        // 扣除积分
                        if ($required_points > 0) {
                            $db->exec("UPDATE users SET points = points - {$required_points} WHERE id = {$_SESSION['user_id']}");
                            $_SESSION['user_points'] -= $required_points;
                        }
                        
                        // 记录操作日志（用于频率限制追踪）
                        Security::logOperation($_SESSION['user_id'], 'add_dns_record');
                        
                        logAction('user', $_SESSION['user_id'], 'add_dns_record', "添加DNS记录: {$full_name} ({$type})");
                        showSuccess("DNS记录添加成功！完整域名：{$full_name}");
                        redirect('records.php');
                    } else {
                        showError('保存到数据库失败！');
                    }
                } else {
                    showError('添加DNS记录失败：' . $remote_result['message']);
                }
            }
        } catch (Exception $e) {
            logAction('user', $_SESSION['user_id'], 'add_dns_record_error', $e->getMessage());
            showError('添加DNS记录时发生错误：' . $e->getMessage());
        }
    }
}

// 获取用户的所有DNS记录（包含域名信息，排除系统同步的记录）
$dns_records = [];
$stmt = $db->prepare("
    SELECT dr.*, d.domain_name 
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

// 统计信息
$stats = [
    'total_records' => count($dns_records),
    'a_records' => count(array_filter($dns_records, function($r) { return $r['type'] === 'A'; })),
    'cname_records' => count(array_filter($dns_records, function($r) { return $r['type'] === 'CNAME'; })),
    'proxied_records' => count(array_filter($dns_records, function($r) { return $r['proxied']; }))
];

$page_title = '我的记录';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="main-content">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3" style="border-bottom: 1px solid #e0e0e0;">
                <h1 class="h2">我的DNS记录</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addRecordModal">
                        <i class="fas fa-plus me-1"></i>添加记录
                    </button>
                </div>
            </div>
            
            <?php if (!empty($messages)): ?>
                <?php foreach ($messages as $type => $message): ?>
                    <div class="alert alert-<?php echo $type === 'error' ? 'danger' : $type; ?> alert-dismissible fade show">
                        <?php echo $message; ?>
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                <?php endforeach; ?>
            <?php endif; ?>
            
            <!-- 统计卡片 -->
            <div class="row mb-4">
                <div class="col-xl-3 col-md-6 mb-4">
                    <div class="card border-left-primary shadow h-100 py-2">
                        <div class="card-body">
                            <div class="row no-gutters align-items-center">
                                <div class="col mr-2">
                                    <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">总记录数</div>
                                    <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $stats['total_records']; ?></div>
                                </div>
                                <div class="col-auto">
                                    <i class="fas fa-list fa-2x text-gray-300"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-xl-3 col-md-6 mb-4">
                    <div class="card border-left-success shadow h-100 py-2">
                        <div class="card-body">
                            <div class="row no-gutters align-items-center">
                                <div class="col mr-2">
                                    <div class="text-xs font-weight-bold text-success text-uppercase mb-1">A记录</div>
                                    <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $stats['a_records']; ?></div>
                                </div>
                                <div class="col-auto">
                                    <i class="fas fa-server fa-2x text-gray-300"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-xl-3 col-md-6 mb-4">
                    <div class="card border-left-info shadow h-100 py-2">
                        <div class="card-body">
                            <div class="row no-gutters align-items-center">
                                <div class="col mr-2">
                                    <div class="text-xs font-weight-bold text-info text-uppercase mb-1">CNAME记录</div>
                                    <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $stats['cname_records']; ?></div>
                                </div>
                                <div class="col-auto">
                                    <i class="fas fa-link fa-2x text-gray-300"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-xl-3 col-md-6 mb-4">
                    <div class="card border-left-warning shadow h-100 py-2">
                        <div class="card-body">
                            <div class="row no-gutters align-items-center">
                                <div class="col mr-2">
                                    <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">已代理</div>
                                    <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $stats['proxied_records']; ?></div>
                                </div>
                                <div class="col-auto">
                                    <i class="fas fa-shield-alt fa-2x text-gray-300"></i>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 记录列表 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">DNS记录列表</h6>
                </div>
                <div class="card-body">
                    <?php if (!empty($dns_records)): ?>
                    <div class="table-responsive">
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>域名</th>
                                    <th>子域名</th>
                                    <th>完整域名</th>
                                    <th>类型</th>
                                    <th>内容</th>
                                    <th>备注</th>
                                    <th>代理状态</th>
                                    <th>创建时间</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($dns_records as $record): ?>
                                <?php 
                                $full_domain = $record['subdomain'] === '@' ? 
                                    $record['domain_name'] : 
                                    $record['subdomain'] . '.' . $record['domain_name'];
                                ?>
                                <tr>
                                    <td>
                                        <strong><?php echo htmlspecialchars($record['domain_name']); ?></strong>
                                    </td>
                                    <td>
                                        <code><?php echo htmlspecialchars($record['subdomain']); ?></code>
                                    </td>
                                    <td>
                                        <span class="text-primary" style="cursor: pointer;" 
                                              onclick="copyToClipboard('<?php echo htmlspecialchars($full_domain); ?>')"
                                              title="点击复制">
                                            <?php echo htmlspecialchars($full_domain); ?>
                                            <i class="fas fa-copy ms-1"></i>
                                        </span>
                                    </td>
                                    <td>
                                        <span class="badge bg-info"><?php echo $record['type']; ?></span>
                                    </td>
                                    <td>
                                        <?php 
                                        $content = htmlspecialchars($record['content']);
                                        $truncated = mb_strlen($content) > 50 ? mb_substr($content, 0, 50) . '...' : $content;
                                        ?>
                                        <span style="cursor: pointer;" 
                                              onclick="copyToClipboard('<?php echo $content; ?>')"
                                              title="完整内容: <?php echo $content; ?> (点击复制)">
                                            <?php echo $truncated; ?>
                                        </span>
                                    </td>
                                    <td>
                                        <?php if (!empty($record['remark'])): ?>
                                            <span class="text-muted" title="<?php echo htmlspecialchars($record['remark']); ?>">
                                                <i class="fas fa-comment-alt me-1 text-info"></i>
                                                <?php echo htmlspecialchars(mb_strlen($record['remark']) > 15 ? mb_substr($record['remark'], 0, 15) . '...' : $record['remark']); ?>
                                            </span>
                                        <?php else: ?>
                                            <span class="text-muted">-</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if ($record['proxied']): ?>
                                            <span class="badge bg-warning">
                                                <i class="fas fa-shield-alt me-1"></i>已代理
                                            </span>
                                        <?php else: ?>
                                            <span class="badge bg-secondary">
                                                <i class="fas fa-globe me-1"></i>仅DNS
                                            </span>
                                        <?php endif; ?>
                                    </td>
                                    <td><?php echo formatTime($record['created_at']); ?></td>
                                    <td>
                                        <a href="dashboard.php" class="btn btn-sm btn-outline-primary" title="管理记录">
                                            <i class="fas fa-edit"></i>
                                        </a>
                                    </td>
                                </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>
                    <?php else: ?>
                    <div class="text-center py-5">
                        <i class="fas fa-inbox fa-4x text-muted mb-3"></i>
                        <h5 class="text-muted">暂无DNS记录</h5>
                        <p class="text-muted">您还没有添加任何DNS记录</p>
                        <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addRecordModal">
                            <i class="fas fa-plus me-1"></i>添加第一条记录
                        </button>
                    </div>
                    <?php endif; ?>
                </div>
            </div>
            </div>
        </main>
    </div>
</div>

<!-- 添加DNS记录模态框 -->
<div class="modal fade" id="addRecordModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">添加DNS记录</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <input type="hidden" name="csrf_token" value="<?php echo Security::generateCSRFToken(); ?>">
                <div class="modal-body">
                    <?php if ($user_group): ?>
                    <div class="alert alert-info mb-3" role="alert" style="border-left: 4px solid #0dcaf0;">
                        <div class="d-flex align-items-start">
                            <i class="fas fa-info-circle me-2 mt-1" style="font-size: 1.2em;"></i>
                            <div class="flex-grow-1">
                                <strong>用户组信息</strong><br>
                                <div class="mt-2">
                                    <span class="badge bg-primary me-2"><?php echo htmlspecialchars($user_group['display_name']); ?></span>
                                    <?php if ($required_points > 0): ?>
                                        <span class="badge bg-warning text-dark me-2">
                                            <i class="fas fa-coins me-1"></i>消耗 <?php echo $required_points; ?> 积分/条
                                        </span>
                                    <?php else: ?>
                                        <span class="badge bg-success me-2">
                                            <i class="fas fa-gift me-1"></i>免费添加
                                        </span>
                                    <?php endif; ?>
                                    <?php if ($user_group['max_records'] != -1): ?>
                                        <span class="badge bg-secondary">
                                            <i class="fas fa-list me-1"></i>已用 <?php echo $current_record_count; ?>/<?php echo $user_group['max_records']; ?> 条
                                        </span>
                                    <?php else: ?>
                                        <span class="badge bg-secondary">
                                            <i class="fas fa-infinity me-1"></i>已用 <?php echo $current_record_count; ?> 条
                                        </span>
                                    <?php endif; ?>
                                </div>
                            </div>
                        </div>
                    </div>
                    <?php endif; ?>
                    
                    <div class="mb-3">
                        <label for="domain_id" class="form-label">选择域名</label>
                        <select class="form-select" id="domain_id" name="domain_id" required onchange="updateDomainDisplay()">
                            <?php if (empty($domains)): ?>
                                <option value="">暂无可用域名</option>
                            <?php else: ?>
                                <?php foreach ($domains as $domain): ?>
                                    <option value="<?php echo $domain['id']; ?>" 
                                            data-domain="<?php echo htmlspecialchars($domain['domain_name']); ?>"
                                            data-provider="<?php echo htmlspecialchars($domain['provider_type'] ?? 'cloudflare'); ?>">
                                        <?php echo htmlspecialchars($domain['domain_name']); ?>
                                    </option>
                                <?php endforeach; ?>
                            <?php endif; ?>
                        </select>
                        <?php if (empty($domains)): ?>
                            <div class="form-text text-danger">
                                <i class="fas fa-exclamation-triangle me-1"></i>
                                暂无可用域名，请联系管理员。
                            </div>
                        <?php endif; ?>
                    </div>
                    
                    <div class="mb-3">
                        <label for="subdomain" class="form-label">子域名</label>
                        <div class="input-group">
                            <input type="text" class="form-control" id="subdomain" name="subdomain" 
                                   placeholder="www" required>
                            <span class="input-group-text" id="domain-display">
                                <?php echo !empty($domains) ? '.' . htmlspecialchars($domains[0]['domain_name']) : ''; ?>
                            </span>
                        </div>
                        <div class="form-text">输入 @ 表示根域名</div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="type" class="form-label">记录类型</label>
                        <select class="form-select" id="type" name="type" required onchange="updateContentPlaceholder()">
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
                        <input type="text" class="form-control" id="content" name="content" placeholder="192.168.1.1" required>
                        <div class="form-text" id="content-help">
                            请输入对应记录类型的值
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label for="remark" class="form-label">备注 <span class="text-muted">(可选)</span></label>
                        <input type="text" class="form-control" id="remark" name="remark" placeholder="例如：网站主页、API接口、邮件服务器等" maxlength="100">
                        <div class="form-text">添加备注可以帮助您区分不同解析记录的用途</div>
                    </div>
                    
                    <div class="mb-3" id="proxied-section">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="proxied" name="proxied" value="1">
                            <label class="form-check-label" for="proxied">
                                启用Cloudflare代理
                            </label>
                        </div>
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            仅A、AAAA、CNAME记录支持代理功能。NS、MX、TXT、SRV等记录类型会自动禁用代理。
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="add_record" class="btn btn-primary" <?php echo (empty($enabled_dns_types) || empty($domains)) ? 'disabled' : ''; ?>>
                        添加记录
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
// 更新域名显示
function updateDomainDisplay() {
    const domainSelect = document.getElementById('domain_id');
    const domainDisplay = document.getElementById('domain-display');
    const proxiedSection = document.getElementById('proxied-section');
    
    if (domainSelect && domainDisplay) {
        const selectedOption = domainSelect.options[domainSelect.selectedIndex];
        const domainName = selectedOption.getAttribute('data-domain');
        const providerType = selectedOption.getAttribute('data-provider');
        
        domainDisplay.textContent = '.' + domainName;
        
        // 根据服务商类型显示/隐藏代理选项
        if (providerType === 'rainbow') {
            proxiedSection.style.display = 'none';
        } else {
            proxiedSection.style.display = 'block';
        }
    }
}

// 更新内容占位符
function updateContentPlaceholder() {
    const typeSelect = document.getElementById('type');
    const contentInput = document.getElementById('content');
    const contentHelp = document.getElementById('content-help');
    const proxiedCheckbox = document.getElementById('proxied');
    
    if (!typeSelect || !contentInput || !contentHelp) return;
    
    const type = typeSelect.value;
    const placeholders = {
        'A': { placeholder: '192.168.1.1', help: '请输入IPv4地址', proxyable: true },
        'AAAA': { placeholder: '2001:0db8::1', help: '请输入IPv6地址', proxyable: true },
        'CNAME': { placeholder: 'example.com', help: '请输入目标域名', proxyable: true },
        'MX': { placeholder: 'mail.example.com', help: '请输入邮件服务器地址', proxyable: false },
        'TXT': { placeholder: '"v=spf1 include:example.com ~all"', help: '请输入文本内容', proxyable: false },
        'NS': { placeholder: 'ns1.example.com', help: '请输入名称服务器', proxyable: false },
        'SRV': { placeholder: '10 60 5060 sipserver.example.com', help: '格式: priority weight port target', proxyable: false },
        'CAA': { placeholder: '0 issue "letsencrypt.org"', help: '格式: flags tag value', proxyable: false }
    };
    
    const config = placeholders[type] || { placeholder: '', help: '请输入对应记录类型的值', proxyable: false };
    contentInput.placeholder = config.placeholder;
    contentHelp.textContent = config.help;
    
    // 根据记录类型启用/禁用代理选项
    if (proxiedCheckbox) {
        if (!config.proxyable) {
            proxiedCheckbox.checked = false;
            proxiedCheckbox.disabled = true;
        } else {
            proxiedCheckbox.disabled = false;
        }
    }
}

// 页面加载时初始化
document.addEventListener('DOMContentLoaded', function() {
    updateDomainDisplay();
    updateContentPlaceholder();
});
</script>

<?php include 'includes/footer.php'; ?>