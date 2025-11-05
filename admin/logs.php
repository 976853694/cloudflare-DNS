<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 确保日志表存在
$db->exec("CREATE TABLE IF NOT EXISTS action_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_type TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)");

// 处理清空日志
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['clear_logs'])) {
    $clear_type = $_POST['clear_type'] ?? 'all';
    
    try {
        if ($clear_type === 'all') {
            // 清空所有日志
            $db->exec("DELETE FROM action_logs");
            logAction('admin', $_SESSION['admin_id'], 'clear_all_logs', '清空所有操作日志');
            showSuccess('已清空所有操作日志');
        } elseif ($clear_type === 'old') {
            // 清空30天前的日志
            $db->exec("DELETE FROM action_logs WHERE created_at < datetime('now', '-30 days')");
            logAction('admin', $_SESSION['admin_id'], 'clear_old_logs', '清空30天前的操作日志');
            showSuccess('已清空30天前的操作日志');
        }
        redirect('logs.php');
    } catch (Exception $e) {
        showError('清空日志失败: ' . $e->getMessage());
    }
}

// 获取筛选参数
$filter_user_type = isset($_GET['filter_user_type']) ? $_GET['filter_user_type'] : '';
$filter_action = isset($_GET['filter_action']) ? $_GET['filter_action'] : '';
$filter_user_id = isset($_GET['filter_user_id']) ? (int)$_GET['filter_user_id'] : 0;
$filter_date_from = isset($_GET['filter_date_from']) ? $_GET['filter_date_from'] : '';
$filter_date_to = isset($_GET['filter_date_to']) ? $_GET['filter_date_to'] : '';
$filter_ip = isset($_GET['filter_ip']) ? trim($_GET['filter_ip']) : '';
$limit = isset($_GET['limit']) ? (int)$_GET['limit'] : 100;

// 构建WHERE条件
$where_conditions = [];
$bind_params = [];

if (!empty($filter_user_type)) {
    $where_conditions[] = "user_type = :user_type";
    $bind_params[':user_type'] = $filter_user_type;
}

if (!empty($filter_action)) {
    $where_conditions[] = "action LIKE :action";
    $bind_params[':action'] = '%' . $filter_action . '%';
}

if ($filter_user_id > 0) {
    $where_conditions[] = "user_id = :user_id";
    $bind_params[':user_id'] = $filter_user_id;
}

if (!empty($filter_date_from)) {
    $where_conditions[] = "date(created_at) >= :date_from";
    $bind_params[':date_from'] = $filter_date_from;
}

if (!empty($filter_date_to)) {
    $where_conditions[] = "date(created_at) <= :date_to";
    $bind_params[':date_to'] = $filter_date_to;
}

if (!empty($filter_ip)) {
    $where_conditions[] = "ip_address LIKE :ip_address";
    $bind_params[':ip_address'] = '%' . $filter_ip . '%';
}

$where_sql = !empty($where_conditions) ? 'WHERE ' . implode(' AND ', $where_conditions) : '';

// 获取操作日志
$logs = [];
$sql = "SELECT * FROM action_logs $where_sql ORDER BY created_at DESC LIMIT ?";
$stmt = $db->prepare($sql);
foreach ($bind_params as $param => $value) {
    $stmt->bindValue($param, $value);
}
$stmt->bindValue(count($bind_params) + 1, $limit, SQLITE3_INTEGER);
$result = $stmt->execute();

if ($result) {
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $logs[] = $row;
    }
}

// 获取总日志数
$total_logs = $db->querySingle("SELECT COUNT(*) FROM action_logs");

// 获取所有操作类型（用于筛选）
$action_types = [];
$action_result = $db->query("SELECT DISTINCT action FROM action_logs ORDER BY action");
if ($action_result) {
    while ($row = $action_result->fetchArray(SQLITE3_ASSOC)) {
        $action_types[] = $row['action'];
    }
}

$page_title = '操作日志';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">操作日志</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <button class="btn btn-primary me-2" type="button" data-bs-toggle="collapse" data-bs-target="#advancedFilter">
                        <i class="fas fa-filter me-1"></i>高级筛选
                    </button>
                    <button class="btn btn-danger me-2" type="button" data-bs-toggle="modal" data-bs-target="#clearLogsModal">
                        <i class="fas fa-trash me-1"></i>清空日志
                    </button>
                    <div class="input-group">
                        <input type="text" class="form-control" placeholder="快速搜索..." id="searchInput" onkeyup="searchTable('searchInput', 'logsTable')">
                        <span class="input-group-text"><i class="fas fa-search"></i></span>
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
            
            <!-- 高级筛选面板 -->
            <div class="collapse <?php echo (!empty($filter_user_type) || !empty($filter_action) || $filter_user_id > 0 || !empty($filter_date_from) || !empty($filter_date_to) || !empty($filter_ip) || $limit != 100) ? 'show' : ''; ?>" id="advancedFilter">
                <div class="card shadow-sm mb-3">
                    <div class="card-header bg-light">
                        <h6 class="mb-0"><i class="fas fa-sliders-h me-2"></i>高级筛选条件</h6>
                    </div>
                    <div class="card-body">
                        <form method="GET" action="logs.php" id="filterForm">
                            <div class="row g-3">
                                <!-- 用户类型筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_user_type" class="form-label">用户类型</label>
                                    <select class="form-select" id="filter_user_type" name="filter_user_type">
                                        <option value="">全部类型</option>
                                        <option value="admin" <?php echo $filter_user_type === 'admin' ? 'selected' : ''; ?>>管理员</option>
                                        <option value="user" <?php echo $filter_user_type === 'user' ? 'selected' : ''; ?>>用户</option>
                                    </select>
                                </div>
                                
                                <!-- 操作类型筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_action" class="form-label">操作类型</label>
                                    <select class="form-select" id="filter_action" name="filter_action">
                                        <option value="">全部操作</option>
                                        <?php foreach ($action_types as $action): ?>
                                            <option value="<?php echo htmlspecialchars($action); ?>" <?php echo $filter_action === $action ? 'selected' : ''; ?>>
                                                <?php echo htmlspecialchars($action); ?>
                                            </option>
                                        <?php endforeach; ?>
                                    </select>
                                </div>
                                
                                <!-- 用户ID筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_user_id" class="form-label">用户ID</label>
                                    <input type="number" class="form-control" id="filter_user_id" name="filter_user_id" 
                                           value="<?php echo $filter_user_id > 0 ? $filter_user_id : ''; ?>" placeholder="输入用户ID" min="0">
                                </div>
                                
                                <!-- IP地址筛选 -->
                                <div class="col-md-3">
                                    <label for="filter_ip" class="form-label">IP地址</label>
                                    <input type="text" class="form-control" id="filter_ip" name="filter_ip" 
                                           value="<?php echo htmlspecialchars($filter_ip); ?>" placeholder="输入IP地址">
                                </div>
                                
                                <!-- 日期起始 -->
                                <div class="col-md-3">
                                    <label for="filter_date_from" class="form-label">开始日期</label>
                                    <input type="date" class="form-control" id="filter_date_from" name="filter_date_from" 
                                           value="<?php echo htmlspecialchars($filter_date_from); ?>">
                                </div>
                                
                                <!-- 日期结束 -->
                                <div class="col-md-3">
                                    <label for="filter_date_to" class="form-label">结束日期</label>
                                    <input type="date" class="form-control" id="filter_date_to" name="filter_date_to" 
                                           value="<?php echo htmlspecialchars($filter_date_to); ?>">
                                </div>
                                
                                <!-- 显示数量 -->
                                <div class="col-md-3">
                                    <label for="limit" class="form-label">显示数量</label>
                                    <select class="form-select" id="limit" name="limit">
                                        <option value="50" <?php echo $limit == 50 ? 'selected' : ''; ?>>50条</option>
                                        <option value="100" <?php echo $limit == 100 ? 'selected' : ''; ?>>100条</option>
                                        <option value="200" <?php echo $limit == 200 ? 'selected' : ''; ?>>200条</option>
                                        <option value="500" <?php echo $limit == 500 ? 'selected' : ''; ?>>500条</option>
                                        <option value="1000" <?php echo $limit == 1000 ? 'selected' : ''; ?>>1000条</option>
                                    </select>
                                </div>
                                
                                <!-- 按钮组 -->
                                <div class="col-md-3 d-flex align-items-end">
                                    <button type="submit" class="btn btn-primary me-2">
                                        <i class="fas fa-search me-1"></i>应用筛选
                                    </button>
                                    <a href="logs.php" class="btn btn-outline-secondary">
                                        <i class="fas fa-redo me-1"></i>重置
                                    </a>
                                </div>
                            </div>
                            
                            <!-- 当前筛选条件显示 -->
                            <?php 
                            $active_filters = [];
                            if (!empty($filter_user_type)) $active_filters[] = "类型: " . ($filter_user_type === 'admin' ? '管理员' : '用户');
                            if (!empty($filter_action)) $active_filters[] = "操作: " . htmlspecialchars($filter_action);
                            if ($filter_user_id > 0) $active_filters[] = "用户ID: $filter_user_id";
                            if (!empty($filter_ip)) $active_filters[] = "IP: " . htmlspecialchars($filter_ip);
                            if (!empty($filter_date_from)) $active_filters[] = "起始: $filter_date_from";
                            if (!empty($filter_date_to)) $active_filters[] = "截止: $filter_date_to";
                            if ($limit != 100) $active_filters[] = "显示: {$limit}条";
                            ?>
                            
                            <?php if (!empty($active_filters)): ?>
                            <div class="mt-3 pt-3 border-top">
                                <div class="d-flex align-items-center flex-wrap">
                                    <span class="text-muted me-2"><i class="fas fa-info-circle"></i> 当前筛选:</span>
                                    <?php foreach ($active_filters as $filter): ?>
                                        <span class="badge bg-primary me-2 mb-1"><?php echo $filter; ?></span>
                                    <?php endforeach; ?>
                                    <span class="text-muted ms-2">（共 <?php echo count($logs); ?> 条记录 / 总计 <?php echo $total_logs; ?> 条）</span>
                                </div>
                            </div>
                            <?php endif; ?>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="card shadow">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="m-0 font-weight-bold text-primary">
                        操作日志记录 
                        <small class="text-muted">(显示 <?php echo count($logs); ?> 条 / 总计 <?php echo $total_logs; ?> 条)</small>
                    </h6>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-bordered table-sm" id="logsTable">
                            <thead>
                                <tr>
                                    <th>时间</th>
                                    <th>用户类型</th>
                                    <th>用户ID</th>
                                    <th>操作</th>
                                    <th>详情</th>
                                    <th>IP地址</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($logs as $log): ?>
                                <tr>
                                    <td><?php echo formatTime($log['created_at']); ?></td>
                                    <td>
                                        <span class="badge bg-<?php echo $log['user_type'] === 'admin' ? 'danger' : 'primary'; ?>">
                                            <?php echo $log['user_type'] === 'admin' ? '管理员' : '用户'; ?>
                                        </span>
                                    </td>
                                    <td><?php echo $log['user_id']; ?></td>
                                    <td><?php echo htmlspecialchars($log['action']); ?></td>
                                    <td><?php echo htmlspecialchars($log['details']); ?></td>
                                    <td><code><?php echo htmlspecialchars($log['ip_address']); ?></code></td>
                                </tr>
                                <?php endforeach; ?>
                                <?php if (empty($logs)): ?>
                                <tr>
                                    <td colspan="6" class="text-center text-muted">暂无操作日志</td>
                                </tr>
                                <?php endif; ?>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<!-- 清空日志模态框 -->
<div class="modal fade" id="clearLogsModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header bg-danger text-white">
                <h5 class="modal-title"><i class="fas fa-exclamation-triangle me-2"></i>清空操作日志</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST" onsubmit="return confirmClearLogs()">
                <div class="modal-body">
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        <strong>警告：</strong>此操作不可恢复，请谨慎选择！
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">选择清空范围：</label>
                        <div class="form-check">
                            <input class="form-check-input" type="radio" name="clear_type" id="clearOld" value="old" checked>
                            <label class="form-check-label" for="clearOld">
                                <i class="fas fa-history me-1"></i>清空30天前的日志
                                <small class="text-muted d-block">保留最近30天的日志记录</small>
                            </label>
                        </div>
                        <div class="form-check mt-2">
                            <input class="form-check-input" type="radio" name="clear_type" id="clearAll" value="all">
                            <label class="form-check-label" for="clearAll">
                                <i class="fas fa-trash-alt me-1"></i>清空所有日志
                                <small class="text-muted d-block text-danger">删除全部 <?php echo $total_logs; ?> 条日志记录</small>
                            </label>
                        </div>
                    </div>
                    
                    <div class="alert alert-info mb-0">
                        <i class="fas fa-info-circle me-2"></i>
                        <small>清空日志操作本身也会被记录到操作日志中</small>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                        <i class="fas fa-times me-1"></i>取消
                    </button>
                    <button type="submit" name="clear_logs" class="btn btn-danger">
                        <i class="fas fa-trash me-1"></i>确认清空
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<style>
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

/* 清空日志按钮样式 */
.btn-danger {
    transition: all 0.3s ease;
}

.btn-danger:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(220, 53, 69, 0.3);
}

/* 表格样式优化 */
#logsTable tbody tr:hover {
    background-color: #f8f9fa;
}

#logsTable .badge {
    font-size: 0.85rem;
}

/* 移动端优化 */
@media (max-width: 768px) {
    #advancedFilter .col-md-3 {
        margin-bottom: 1rem;
    }
    
    .btn-toolbar {
        flex-direction: column;
        align-items: stretch !important;
    }
    
    .btn-toolbar .btn,
    .btn-toolbar .input-group {
        width: 100%;
        margin: 0.25rem 0 !important;
    }
}
</style>

<script>
function searchTable(inputId, tableId) {
    const input = document.getElementById(inputId);
    const filter = input.value.toUpperCase();
    const table = document.getElementById(tableId);
    const tr = table.getElementsByTagName("tr");

    for (let i = 1; i < tr.length; i++) {
        const td = tr[i].getElementsByTagName("td");
        let found = false;
        
        for (let j = 0; j < td.length; j++) {
            if (td[j]) {
                const txtValue = td[j].textContent || td[j].innerText;
                if (txtValue.toUpperCase().indexOf(filter) > -1) {
                    found = true;
                    break;
                }
            }
        }
        
        tr[i].style.display = found ? "" : "none";
    }
}

function confirmClearLogs() {
    const clearType = document.querySelector('input[name="clear_type"]:checked').value;
    
    if (clearType === 'all') {
        return confirm('确定要清空所有操作日志吗？\n\n此操作不可恢复！');
    } else {
        return confirm('确定要清空30天前的操作日志吗？\n\n此操作不可恢复！');
    }
}
</script>

<?php include 'includes/footer.php'; ?>