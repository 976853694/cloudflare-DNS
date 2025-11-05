<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 处理修改DNS记录
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['edit_record'])) {
    $record_id = (int)getPost('record_id');
    $subdomain = trim(getPost('subdomain'));
    $type = getPost('type');
    $content = trim(getPost('content'));
    $remark = trim(getPost('remark'));
    $proxied = isset($_POST['proxied']) ? 1 : 0;
    
    $record = $db->querySingle("SELECT dr.*, d.* FROM dns_records dr JOIN domains d ON dr.domain_id = d.id WHERE dr.id = $record_id", true);
    if ($record) {
        try {
            require_once '../config/cloudflare.php';
            $cf = new CloudflareAPI($record['api_key'], $record['email']);
            
            // 更新Cloudflare DNS记录
            $cf->updateDNSRecord($record['zone_id'], $record['cloudflare_id'], [
                'type' => $type,
                'name' => $subdomain . '.' . $record['domain_name'],
                'content' => $content,
                'proxied' => (bool)$proxied
            ]);
            
            // 更新本地数据库
            $stmt = $db->prepare("UPDATE dns_records SET subdomain = ?, type = ?, content = ?, remark = ?, proxied = ? WHERE id = ?");
            $stmt->bindValue(1, $subdomain, SQLITE3_TEXT);
            $stmt->bindValue(2, $type, SQLITE3_TEXT);
            $stmt->bindValue(3, $content, SQLITE3_TEXT);
            $stmt->bindValue(4, $remark, SQLITE3_TEXT);
            $stmt->bindValue(5, $proxied, SQLITE3_INTEGER);
            $stmt->bindValue(6, $record_id, SQLITE3_INTEGER);
            $stmt->execute();
            
            logAction('admin', $_SESSION['admin_id'], 'edit_dns_record', "修改DNS记录ID: $record_id - {$subdomain}.{$record['domain_name']}");
            showSuccess('DNS记录修改成功！');
        } catch (Exception $e) {
            showError('修改失败: ' . $e->getMessage());
        }
    } else {
        showError('记录不存在！');
    }
    redirect('dns_records.php');
}

// 处理删除DNS记录
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete_record'])) {
    $record_id = (int)getPost('record_id');
    
    $record = $db->querySingle("SELECT * FROM dns_records WHERE id = $record_id", true);
    if ($record) {
        $db->exec("DELETE FROM dns_records WHERE id = $record_id");
        logAction('admin', $_SESSION['admin_id'], 'delete_dns_record', "删除DNS记录ID: $record_id");
        showSuccess('DNS记录删除成功！');
    } else {
        showError('记录不存在！');
    }
    redirect('dns_records.php');
}

// 获取筛选参数
$filter_type = isset($_GET['filter_type']) ? $_GET['filter_type'] : '';
$filter_domain = isset($_GET['filter_domain']) ? (int)$_GET['filter_domain'] : 0;
$filter_user = isset($_GET['filter_user']) ? (int)$_GET['filter_user'] : 0;
$filter_proxied = isset($_GET['filter_proxied']) ? $_GET['filter_proxied'] : '';
$filter_record_source = isset($_GET['filter_record_source']) ? $_GET['filter_record_source'] : '';
$filter_date_from = isset($_GET['filter_date_from']) ? $_GET['filter_date_from'] : '';
$filter_date_to = isset($_GET['filter_date_to']) ? $_GET['filter_date_to'] : '';

// 构建WHERE条件
$where_conditions = [];
$bind_params = [];

if (!empty($filter_type)) {
    $where_conditions[] = "dr.type = :type";
    $bind_params[':type'] = $filter_type;
}

if ($filter_domain > 0) {
    $where_conditions[] = "dr.domain_id = :domain_id";
    $bind_params[':domain_id'] = $filter_domain;
}

if ($filter_user > 0) {
    $where_conditions[] = "dr.user_id = :user_id";
    $bind_params[':user_id'] = $filter_user;
}

if ($filter_proxied !== '') {
    $where_conditions[] = "dr.proxied = :proxied";
    $bind_params[':proxied'] = (int)$filter_proxied;
}

if ($filter_record_source === 'system') {
    $where_conditions[] = "(dr.user_id IS NULL OR dr.is_system = 1)";
} elseif ($filter_record_source === 'user') {
    $where_conditions[] = "(dr.user_id IS NOT NULL AND (dr.is_system = 0 OR dr.is_system IS NULL))";
}

if (!empty($filter_date_from)) {
    $where_conditions[] = "date(dr.created_at) >= :date_from";
    $bind_params[':date_from'] = $filter_date_from;
}

if (!empty($filter_date_to)) {
    $where_conditions[] = "date(dr.created_at) <= :date_to";
    $bind_params[':date_to'] = $filter_date_to;
}

$where_sql = !empty($where_conditions) ? 'WHERE ' . implode(' AND ', $where_conditions) : '';

// 获取所有DNS记录（包括系统记录和用户记录）
$dns_records = [];
$sql = "
    SELECT dr.*, 
           CASE 
               WHEN dr.user_id IS NULL OR dr.is_system = 1 THEN '系统所属'
               ELSE COALESCE(u.username, '未知用户')
           END as username,
           d.domain_name,
           CASE 
               WHEN dr.user_id IS NULL OR dr.is_system = 1 THEN 1
               ELSE 0
           END as is_system_record
    FROM dns_records dr 
    LEFT JOIN users u ON dr.user_id = u.id AND dr.user_id IS NOT NULL AND (dr.is_system = 0 OR dr.is_system IS NULL)
    JOIN domains d ON dr.domain_id = d.id 
    $where_sql
    ORDER BY dr.is_system DESC, dr.created_at DESC
";

$stmt = $db->prepare($sql);
foreach ($bind_params as $param => $value) {
    $stmt->bindValue($param, $value);
}
$result = $stmt->execute();

while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $dns_records[] = $row;
}

// 获取域名列表用于筛选
$domains_list = [];
$domains_result = $db->query("SELECT id, domain_name FROM domains ORDER BY domain_name");
while ($domain = $domains_result->fetchArray(SQLITE3_ASSOC)) {
    $domains_list[] = $domain;
}

// 获取用户列表用于筛选
$users_list = [];
$users_result = $db->query("SELECT id, username FROM users ORDER BY username");
while ($user = $users_result->fetchArray(SQLITE3_ASSOC)) {
    $users_list[] = $user;
}

// 获取所有DNS记录类型（用于筛选）
$record_types = ['A', 'AAAA', 'CNAME', 'MX', 'NS', 'TXT', 'SRV', 'PTR', 'CAA'];

$page_title = 'DNS记录管理';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">DNS记录管理</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <button class="btn btn-primary me-2" type="button" data-bs-toggle="collapse" data-bs-target="#advancedFilter">
                        <i class="fas fa-filter me-1"></i>高级筛选
                    </button>
                    <div class="input-group">
                        <input type="text" class="form-control" placeholder="快速搜索..." id="searchInput" onkeyup="searchTable('searchInput', 'recordsTable')">
                        <span class="input-group-text"><i class="fas fa-search"></i></span>
                    </div>
                </div>
            </div>
            
            <!-- 高级筛选面板 -->
            <div class="collapse <?php echo (!empty($filter_type) || $filter_domain > 0 || $filter_user > 0 || $filter_proxied !== '' || $filter_record_source !== '' || !empty($filter_date_from) || !empty($filter_date_to)) ? 'show' : ''; ?>" id="advancedFilter">
                <div class="card shadow-sm mb-3">
                    <div class="card-header bg-light">
                        <h6 class="mb-0"><i class="fas fa-sliders-h me-2"></i>高级筛选条件</h6>
                    </div>
                    <div class="card-body">
                        <form method="GET" action="dns_records.php" id="filterForm">
                            <div class="row g-3">
                                <!-- 记录类型筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_type" class="form-label">记录类型</label>
                                    <select class="form-select" id="filter_type" name="filter_type">
                                        <option value="">全部类型</option>
                                        <?php foreach ($record_types as $type): ?>
                                            <option value="<?php echo $type; ?>" <?php echo $filter_type === $type ? 'selected' : ''; ?>>
                                                <?php echo $type; ?>
                                            </option>
                                        <?php endforeach; ?>
                                    </select>
                                </div>
                                
                                <!-- 域名筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_domain" class="form-label">域名</label>
                                    <select class="form-select" id="filter_domain" name="filter_domain">
                                        <option value="0">全部域名</option>
                                        <?php foreach ($domains_list as $domain): ?>
                                            <option value="<?php echo $domain['id']; ?>" <?php echo $filter_domain == $domain['id'] ? 'selected' : ''; ?>>
                                                <?php echo htmlspecialchars($domain['domain_name']); ?>
                                            </option>
                                        <?php endforeach; ?>
                                    </select>
                                </div>
                                
                                <!-- 用户筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_user" class="form-label">用户</label>
                                    <select class="form-select" id="filter_user" name="filter_user">
                                        <option value="0">全部用户</option>
                                        <?php foreach ($users_list as $user): ?>
                                            <option value="<?php echo $user['id']; ?>" <?php echo $filter_user == $user['id'] ? 'selected' : ''; ?>>
                                                <?php echo htmlspecialchars($user['username']); ?>
                                            </option>
                                        <?php endforeach; ?>
                                    </select>
                                </div>
                                
                                <!-- 代理状态筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_proxied" class="form-label">代理状态</label>
                                    <select class="form-select" id="filter_proxied" name="filter_proxied">
                                        <option value="">全部状态</option>
                                        <option value="1" <?php echo $filter_proxied === '1' ? 'selected' : ''; ?>>已代理</option>
                                        <option value="0" <?php echo $filter_proxied === '0' ? 'selected' : ''; ?>>仅DNS</option>
                                    </select>
                                </div>
                                
                                <!-- 记录来源筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_record_source" class="form-label">记录来源</label>
                                    <select class="form-select" id="filter_record_source" name="filter_record_source">
                                        <option value="">全部来源</option>
                                        <option value="system" <?php echo $filter_record_source === 'system' ? 'selected' : ''; ?>>系统记录</option>
                                        <option value="user" <?php echo $filter_record_source === 'user' ? 'selected' : ''; ?>>用户记录</option>
                                    </select>
                                </div>
                                
                                <!-- 创建日期起始 -->
                                <div class="col-md-3">
                                    <label for="filter_date_from" class="form-label">创建日期（起）</label>
                                    <input type="date" class="form-control" id="filter_date_from" name="filter_date_from" 
                                           value="<?php echo htmlspecialchars($filter_date_from); ?>">
                                </div>
                                
                                <!-- 创建日期结束 -->
                                <div class="col-md-3">
                                    <label for="filter_date_to" class="form-label">创建日期（止）</label>
                                    <input type="date" class="form-control" id="filter_date_to" name="filter_date_to" 
                                           value="<?php echo htmlspecialchars($filter_date_to); ?>">
                                </div>
                                
                                <!-- 按钮组 -->
                                <div class="col-md-3 d-flex align-items-end">
                                    <button type="submit" class="btn btn-primary me-2">
                                        <i class="fas fa-search me-1"></i>应用筛选
                                    </button>
                                    <a href="dns_records.php" class="btn btn-outline-secondary">
                                        <i class="fas fa-redo me-1"></i>重置
                                    </a>
                                </div>
                            </div>
                            
                            <!-- 当前筛选条件显示 -->
                            <?php 
                            $active_filters = [];
                            if (!empty($filter_type)) $active_filters[] = "类型: $filter_type";
                            if ($filter_domain > 0) {
                                foreach ($domains_list as $d) {
                                    if ($d['id'] == $filter_domain) {
                                        $active_filters[] = "域名: " . htmlspecialchars($d['domain_name']);
                                        break;
                                    }
                                }
                            }
                            if ($filter_user > 0) {
                                foreach ($users_list as $u) {
                                    if ($u['id'] == $filter_user) {
                                        $active_filters[] = "用户: " . htmlspecialchars($u['username']);
                                        break;
                                    }
                                }
                            }
                            if ($filter_proxied !== '') $active_filters[] = "代理: " . ($filter_proxied == '1' ? '已代理' : '仅DNS');
                            if ($filter_record_source === 'system') $active_filters[] = "来源: 系统记录";
                            if ($filter_record_source === 'user') $active_filters[] = "来源: 用户记录";
                            if (!empty($filter_date_from)) $active_filters[] = "起始: $filter_date_from";
                            if (!empty($filter_date_to)) $active_filters[] = "截止: $filter_date_to";
                            ?>
                            
                            <?php if (!empty($active_filters)): ?>
                            <div class="mt-3 pt-3 border-top">
                                <div class="d-flex align-items-center flex-wrap">
                                    <span class="text-muted me-2"><i class="fas fa-info-circle"></i> 当前筛选:</span>
                                    <?php foreach ($active_filters as $filter): ?>
                                        <span class="badge bg-primary me-2 mb-1"><?php echo $filter; ?></span>
                                    <?php endforeach; ?>
                                    <span class="text-muted ms-2">（共 <?php echo count($dns_records); ?> 条记录）</span>
                                </div>
                            </div>
                            <?php endif; ?>
                        </form>
                    </div>
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
            
            <!-- 记录类型说明 -->
            <div class="alert alert-info">
                <h6><i class="fas fa-info-circle me-2"></i>记录类型说明</h6>
                <div class="row">
                    <div class="col-md-6">
                        <p class="mb-1"><span class="badge bg-success"><i class="fas fa-user me-1"></i>用户记录</span> - 用户通过前台创建的DNS记录</p>
                        <small class="text-muted">• 可以编辑和删除 • 消耗用户积分 • 用户可管理</small>
                    </div>
                    <div class="col-md-6">
                        <p class="mb-1"><span class="badge bg-info"><i class="fas fa-server me-1"></i>系统记录</span> - 系统导入的DNS记录</p>
                        <small class="text-muted">• 只读，不可编辑 • 不消耗积分 • 管理员专属</small>
                    </div>
                </div>
            </div>
            
            <!-- DNS记录列表 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">所有DNS记录 
                        <small class="text-muted">(系统记录优先显示)</small>
                    </h6>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-bordered" id="recordsTable">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>用户</th>
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
                                // 构建完整域名
                                $full_domain = htmlspecialchars($record['subdomain']) . '.' . htmlspecialchars($record['domain_name']);
                                // 构建跳转URL（根据记录类型决定协议）
                                $protocol = in_array($record['type'], ['A', 'AAAA', 'CNAME']) ? 'https://' : '';
                                $jump_url = $protocol . $record['subdomain'] . '.' . $record['domain_name'];
                                ?>
                                <tr>
                                    <td><?php echo $record['id']; ?></td>
                                    <td>
                                        <?php if ($record['is_system_record']): ?>
                                            <span class="badge bg-info">
                                                <i class="fas fa-server me-1"></i>系统所属
                                            </span>
                                        <?php else: ?>
                                            <span class="badge bg-success">
                                                <i class="fas fa-user me-1"></i><?php echo htmlspecialchars($record['username']); ?>
                                            </span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if (in_array($record['type'], ['A', 'AAAA', 'CNAME'])): ?>
                                            <a href="<?php echo $jump_url; ?>" target="_blank" class="domain-link text-decoration-none" title="点击访问 <?php echo $full_domain; ?>，右键复制域名">
                                                <code class="text-primary"><?php echo $full_domain; ?></code>
                                                <i class="fas fa-external-link-alt ms-1 external-link-icon" style="font-size: 0.8em;"></i>
                                            </a>
                                        <?php else: ?>
                                            <span class="domain-link" title="右键复制域名">
                                                <code><?php echo $full_domain; ?></code>
                                            </span>
                                        <?php endif; ?>
                                    </td>
                                    <td><span class="badge bg-info"><?php echo $record['type']; ?></span></td>
                                    <td>
                                        <?php 
                                        $content = htmlspecialchars($record['content']);
                                        $truncated = mb_strlen($content) > 50 ? mb_substr($content, 0, 50) . '...' : $content;
                                        ?>
                                        <span title="<?php echo $content; ?>" style="cursor: help;">
                                            <?php echo $truncated; ?>
                                        </span>
                                    </td>
                                    <td>
                                        <?php if (!empty($record['remark'])): ?>
                                            <span class="text-muted" title="<?php echo htmlspecialchars($record['remark']); ?>">
                                                <i class="fas fa-comment-alt me-1 text-info"></i>
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
                                        <?php if (!$record['is_system_record']): ?>
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
                                        <?php else: ?>
                                        <span class="text-muted">
                                            <i class="fas fa-lock me-1"></i>系统记录
                                        </span>
                                        <?php endif; ?>
                                    </td>
                                </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<style>
/* 完整域名链接样式 */
.domain-link {
    transition: all 0.2s ease;
    border-radius: 4px;
    padding: 2px 4px;
}

.domain-link:hover {
    background-color: #f8f9fa;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.domain-link code {
    font-size: 0.9em;
    font-weight: 500;
}

.external-link-icon {
    opacity: 0.6;
    transition: opacity 0.2s ease;
}

.domain-link:hover .external-link-icon {
    opacity: 1;
}

/* 表格行悬停效果 */
#recordsTable tbody tr:hover {
    background-color: #f8f9fa;
}

/* 响应式表格优化 */
@media (max-width: 768px) {
    .domain-link code {
        font-size: 0.8em;
        word-break: break-all;
    }
}

/* 高级筛选面板样式 */
#advancedFilter {
    transition: all 0.3s ease;
}

#advancedFilter .card {
    border: 1px solid #dee2e6;
    border-radius: 8px;
}

#advancedFilter .card-header {
    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
    border-bottom: 1px solid #dee2e6;
    padding: 12px 20px;
}

#advancedFilter .form-label {
    font-weight: 500;
    font-size: 0.9rem;
    color: #495057;
    margin-bottom: 0.5rem;
}

#advancedFilter .form-select,
#advancedFilter .form-control {
    border-radius: 6px;
    border: 1px solid #ced4da;
    transition: all 0.2s ease;
}

#advancedFilter .form-select:focus,
#advancedFilter .form-control:focus {
    border-color: #0d6efd;
    box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.15);
}

#advancedFilter .badge {
    font-weight: 500;
    padding: 0.5em 0.8em;
    font-size: 0.85rem;
}

#advancedFilter .btn-primary {
    background: linear-gradient(135deg, #0d6efd 0%, #0a58ca 100%);
    border: none;
    transition: all 0.3s ease;
}

#advancedFilter .btn-primary:hover {
    background: linear-gradient(135deg, #0a58ca 0%, #084298 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(13, 110, 253, 0.3);
}

#advancedFilter .btn-outline-secondary {
    transition: all 0.3s ease;
}

#advancedFilter .btn-outline-secondary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(108, 117, 125, 0.2);
}

/* 筛选按钮动画 */
.btn[data-bs-toggle="collapse"] {
    position: relative;
    overflow: hidden;
}

.btn[data-bs-toggle="collapse"]::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.3);
    transform: translate(-50%, -50%);
    transition: width 0.6s, height 0.6s;
}

.btn[data-bs-toggle="collapse"]:active::after {
    width: 300px;
    height: 300px;
}

/* 当前筛选条件标签动画 */
#advancedFilter .badge {
    animation: fadeInScale 0.3s ease;
}

@keyframes fadeInScale {
    from {
        opacity: 0;
        transform: scale(0.8);
    }
    to {
        opacity: 1;
        transform: scale(1);
    }
}

/* 移动端优化 */
@media (max-width: 768px) {
    #advancedFilter .col-md-3 {
        margin-bottom: 1rem;
    }
    
    #advancedFilter .btn-toolbar {
        flex-direction: column;
    }
    
    #advancedFilter .btn-toolbar .btn {
        width: 100%;
        margin-bottom: 0.5rem;
    }
}
</style>

<script>
// 搜索功能
function searchTable(inputId, tableId) {
    const input = document.getElementById(inputId);
    const filter = input.value.toUpperCase();
    const table = document.getElementById(tableId);
    const tr = table.getElementsByTagName("tr");

    for (let i = 1; i < tr.length; i++) {
        let td = tr[i].getElementsByTagName("td");
        let found = false;
        
        for (let j = 0; j < td.length; j++) {
            if (td[j]) {
                let txtValue = td[j].textContent || td[j].innerText;
                if (txtValue.toUpperCase().indexOf(filter) > -1) {
                    found = true;
                    break;
                }
            }
        }
        
        tr[i].style.display = found ? "" : "none";
    }
}

// 确认删除
function confirmDelete(message) {
    return confirm(message);
}

// 复制域名到剪贴板
function copyDomain(domain) {
    navigator.clipboard.writeText(domain).then(function() {
        // 显示复制成功提示
        const toast = document.createElement('div');
        toast.className = 'toast align-items-center text-white bg-success border-0 position-fixed';
        toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999;';
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-check me-2"></i>域名已复制到剪贴板
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        document.body.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // 3秒后自动移除
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 3000);
    }).catch(function(err) {
        console.error('复制失败: ', err);
    });
}

// 为域名链接添加右键复制功能
document.addEventListener('DOMContentLoaded', function() {
    const domainLinks = document.querySelectorAll('.domain-link');
    domainLinks.forEach(function(link) {
        link.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            const domain = this.querySelector('code').textContent;
            copyDomain(domain);
        });
    });
});

// 修改DNS记录函数
function editRecord(record) {
    // 填充表单数据
    document.getElementById('edit_record_id').value = record.id;
    document.getElementById('edit_subdomain').value = record.subdomain;
    document.getElementById('edit_type').value = record.type;
    document.getElementById('edit_content').value = record.content;
    document.getElementById('edit_remark').value = record.remark || '';
    document.getElementById('edit_proxied').checked = record.proxied == 1;
    
    // 更新域名后缀显示
    document.getElementById('edit_domain_suffix').textContent = '.' + record.domain_name;
    
    // 更新内容占位符和帮助文本
    updateEditContentPlaceholder();
    
    // 显示模态框
    var modal = new bootstrap.Modal(document.getElementById('editRecordModal'));
    modal.show();
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
        proxiedSection.style.display = config.showProxied ? 'block' : 'none';
    } else {
        contentInput.placeholder = '';
        contentHelp.textContent = '请输入对应记录类型的值';
        proxiedSection.style.display = 'none';
    }
}
</script>

<!-- 修改DNS记录模态框 -->
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
                            <span class="input-group-text" id="edit_domain_suffix">.domain.com</span>
                        </div>
                        <div class="form-text">输入 @ 表示根域名</div>
                    </div>
                    <div class="mb-3">
                        <label for="edit_type" class="form-label">记录类型</label>
                        <select class="form-select" id="edit_type" name="type" required onchange="updateEditContentPlaceholder()">
                            <option value="A">A - IPv4地址</option>
                            <option value="AAAA">AAAA - IPv6地址</option>
                            <option value="CNAME">CNAME - 别名记录</option>
                            <option value="MX">MX - 邮件交换记录</option>
                            <option value="NS">NS - 域名服务器记录</option>
                            <option value="TXT">TXT - 文本记录</option>
                            <option value="SRV">SRV - 服务记录</option>
                            <option value="PTR">PTR - 反向解析记录</option>
                            <option value="CAA">CAA - 证书颁发机构授权记录</option>
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

<?php include 'includes/footer.php'; ?>