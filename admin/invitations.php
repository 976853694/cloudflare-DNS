<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 处理搜索和筛选
$search = getGet('search', '');
$status_filter = getGet('status', 'all');
$sort_by = getGet('sort', 'created_at');
$sort_order = getGet('order', 'DESC');

// 构建查询条件
$where_conditions = [];
$search_params = [];

if (!empty($search)) {
    $where_conditions[] = "(u1.username LIKE ? OR i.invitation_code LIKE ?)";
    $search_params[] = "%$search%";
    $search_params[] = "%$search%";
}

if ($status_filter === 'active') {
    $where_conditions[] = "i.is_active = 1";
} elseif ($status_filter === 'inactive') {
    $where_conditions[] = "i.is_active = 0";
} elseif ($status_filter === 'used') {
    $where_conditions[] = "i.use_count > 0";
} elseif ($status_filter === 'unused') {
    $where_conditions[] = "i.use_count = 0";
}

$where_clause = !empty($where_conditions) ? 'WHERE ' . implode(' AND ', $where_conditions) : '';

// 获取邀请记录
$invitations = [];
$query = "
    SELECT i.*, 
           u1.username as inviter_username,
           u1.email as inviter_email,
           u1.points as inviter_points,
           (SELECT COUNT(*) FROM invitation_uses WHERE invitation_id = i.id) as actual_use_count,
           (SELECT GROUP_CONCAT(u.username, ', ') FROM invitation_uses iu 
            JOIN users u ON iu.invitee_id = u.id 
            WHERE iu.invitation_id = i.id 
            ORDER BY iu.used_at DESC LIMIT 3) as recent_users,
           (SELECT COUNT(DISTINCT iu.invitee_id) FROM invitation_uses iu WHERE iu.invitation_id = i.id) as unique_users
    FROM invitations i 
    LEFT JOIN users u1 ON i.inviter_id = u1.id 
    $where_clause
    ORDER BY i.$sort_by $sort_order
";

$stmt = $db->prepare($query);
if (!empty($search_params)) {
    foreach ($search_params as $index => $param) {
        $stmt->bindValue($index + 1, $param, SQLITE3_TEXT);
    }
}
$result = $stmt->execute();
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $invitations[] = $row;
}

// 获取统计信息
$stats = [
    'total_users_with_codes' => $db->querySingle("SELECT COUNT(*) FROM invitations WHERE is_active = 1"),
    'total_uses' => $db->querySingle("SELECT COUNT(*) FROM invitation_uses"),
    'unique_invited_users' => $db->querySingle("SELECT COUNT(DISTINCT invitee_id) FROM invitation_uses"),
    'total_rewards_given' => $db->querySingle("SELECT SUM(total_rewards) FROM invitations") ?: 0,
    'active_inviters_30d' => $db->querySingle("SELECT COUNT(DISTINCT i.inviter_id) FROM invitations i JOIN invitation_uses iu ON i.id = iu.invitation_id WHERE iu.used_at >= date('now', '-30 days')"),
    'avg_uses_per_code' => $db->querySingle("SELECT AVG(use_count) FROM invitations WHERE use_count > 0") ?: 0,
    'top_inviter' => $db->querySingle("SELECT u.username FROM users u JOIN invitations i ON u.id = i.inviter_id ORDER BY i.total_rewards DESC LIMIT 1", true)
];

// 获取最近的邀请活动
$recent_activities = [];
$result = $db->query("
    SELECT iu.*, i.invitation_code, u1.username as inviter_name, u2.username as invitee_name
    FROM invitation_uses iu
    JOIN invitations i ON iu.invitation_id = i.id
    JOIN users u1 ON i.inviter_id = u1.id
    JOIN users u2 ON iu.invitee_id = u2.id
    ORDER BY iu.used_at DESC
    LIMIT 10
");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $recent_activities[] = $row;
}

$page_title = '邀请系统管理';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2"><i class="fas fa-user-friends me-2"></i>邀请系统管理</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <div class="btn-group me-2">
                        <button type="button" class="btn btn-outline-primary" onclick="exportData()">
                            <i class="fas fa-download me-2"></i>导出数据
                        </button>
                        <button type="button" class="btn btn-outline-info" onclick="refreshData()">
                            <i class="fas fa-sync-alt me-2"></i>刷新
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- 搜索和筛选栏 -->
            <div class="card shadow-sm mb-4">
                <div class="card-body">
                    <form method="GET" class="row g-3">
                        <div class="col-md-4">
                            <label for="search" class="form-label">搜索</label>
                            <div class="input-group">
                                <input type="text" class="form-control" id="search" name="search" 
                                       value="<?php echo htmlspecialchars($search); ?>" 
                                       placeholder="用户名或邀请码...">
                                <span class="input-group-text"><i class="fas fa-search"></i></span>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label for="status" class="form-label">状态筛选</label>
                            <select class="form-select" id="status" name="status">
                                <option value="all" <?php echo $status_filter === 'all' ? 'selected' : ''; ?>>全部状态</option>
                                <option value="active" <?php echo $status_filter === 'active' ? 'selected' : ''; ?>>活跃</option>
                                <option value="inactive" <?php echo $status_filter === 'inactive' ? 'selected' : ''; ?>>禁用</option>
                                <option value="used" <?php echo $status_filter === 'used' ? 'selected' : ''; ?>>已使用</option>
                                <option value="unused" <?php echo $status_filter === 'unused' ? 'selected' : ''; ?>>未使用</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label for="sort" class="form-label">排序方式</label>
                            <select class="form-select" id="sort" name="sort">
                                <option value="created_at" <?php echo $sort_by === 'created_at' ? 'selected' : ''; ?>>创建时间</option>
                                <option value="use_count" <?php echo $sort_by === 'use_count' ? 'selected' : ''; ?>>使用次数</option>
                                <option value="total_rewards" <?php echo $sort_by === 'total_rewards' ? 'selected' : ''; ?>>总奖励</option>
                                <option value="last_used_at" <?php echo $sort_by === 'last_used_at' ? 'selected' : ''; ?>>最后使用</option>
                            </select>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">&nbsp;</label>
                            <div class="d-grid">
                                <button type="submit" class="btn btn-primary">
                                    <i class="fas fa-filter me-1"></i>筛选
                                </button>
                            </div>
                        </div>
                    </form>
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
            
            <!-- 统计概览 -->
            <div class="row mb-4">
                <!-- 主要统计 -->
                <div class="col-lg-8">
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <div class="card bg-gradient-primary text-white shadow">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <div>
                                            <div class="text-white-75 small">拥有邀请码用户</div>
                                            <div class="h3 mb-0"><?php echo $stats['total_users_with_codes']; ?></div>
                                        </div>
                                        <div class="text-white-25">
                                            <i class="fas fa-ticket-alt fa-2x"></i>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-6 mb-3">
                            <div class="card bg-gradient-success text-white shadow">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <div>
                                            <div class="text-white-75 small">总使用次数</div>
                                            <div class="h3 mb-0"><?php echo $stats['total_uses']; ?></div>
                                        </div>
                                        <div class="text-white-25">
                                            <i class="fas fa-chart-line fa-2x"></i>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-6 mb-3">
                            <div class="card bg-gradient-warning text-white shadow">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <div>
                                            <div class="text-white-75 small">被邀请用户数</div>
                                            <div class="h3 mb-0"><?php echo $stats['unique_invited_users']; ?></div>
                                        </div>
                                        <div class="text-white-25">
                                            <i class="fas fa-users fa-2x"></i>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-6 mb-3">
                            <div class="card bg-gradient-info text-white shadow">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between align-items-center">
                                        <div>
                                            <div class="text-white-75 small">已发积分</div>
                                            <div class="h3 mb-0"><?php echo $stats['total_rewards_given']; ?></div>
                                        </div>
                                        <div class="text-white-25">
                                            <i class="fas fa-coins fa-2x"></i>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 详细统计 -->
                <div class="col-lg-4">
                    <div class="card shadow h-100">
                        <div class="card-header">
                            <h6 class="m-0 font-weight-bold text-primary">
                                <i class="fas fa-chart-pie me-2"></i>详细统计
                            </h6>
                        </div>
                        <div class="card-body">
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="text-muted small">30天活跃邀请人</span>
                                    <span class="font-weight-bold"><?php echo $stats['active_inviters_30d']; ?></span>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-primary" style="width: <?php echo $stats['total_users_with_codes'] > 0 ? ($stats['active_inviters_30d'] / $stats['total_users_with_codes'] * 100) : 0; ?>%"></div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="text-muted small">平均使用次数</span>
                                    <span class="font-weight-bold"><?php echo number_format($stats['avg_uses_per_code'], 1); ?></span>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-success" style="width: <?php echo min($stats['avg_uses_per_code'] * 10, 100); ?>%"></div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="text-muted small">转化率</span>
                                    <span class="font-weight-bold"><?php echo $stats['total_uses'] > 0 ? number_format(($stats['unique_invited_users'] / $stats['total_uses']) * 100, 1) : 0; ?>%</span>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-warning" style="width: <?php echo $stats['total_uses'] > 0 ? ($stats['unique_invited_users'] / $stats['total_uses']) * 100 : 0; ?>%"></div>
                                </div>
                            </div>
                            
                            <?php if ($stats['top_inviter']): ?>
                            <div class="text-center mt-3 pt-3 border-top">
                                <div class="text-muted small">顶级邀请人</div>
                                <div class="font-weight-bold text-success">
                                    <i class="fas fa-crown me-1"></i>
                                    <?php echo htmlspecialchars($stats['top_inviter']['username'] ?? '暂无'); ?>
                                </div>
                            </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 主要内容区域 -->
            <div class="row">
                <!-- 邀请记录列表 -->
                <div class="col-lg-8">
                    <div class="card shadow">
                        <div class="card-header d-flex justify-content-between align-items-center">
                            <h6 class="m-0 font-weight-bold text-primary">
                                <i class="fas fa-list me-2"></i>邀请记录
                                <span class="badge bg-primary ms-2"><?php echo count($invitations); ?></span>
                            </h6>
                            <div class="dropdown">
                                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
                                    <i class="fas fa-cog me-1"></i>操作
                                </button>
                                <ul class="dropdown-menu">
                                    <li><a class="dropdown-item" href="#" onclick="exportData()">
                                        <i class="fas fa-download me-2"></i>导出数据
                                    </a></li>
                                    <li><a class="dropdown-item" href="#" onclick="refreshData()">
                                        <i class="fas fa-sync-alt me-2"></i>刷新数据
                                    </a></li>
                                    <li><hr class="dropdown-divider"></li>
                                    <li><a class="dropdown-item" href="settings.php">
                                        <i class="fas fa-cog me-2"></i>邀请设置
                                    </a></li>
                                </ul>
                            </div>
                        </div>
                        <div class="card-body p-0">
                            <?php if (empty($invitations)): ?>
                                <div class="text-center py-5">
                                    <i class="fas fa-user-friends fa-3x text-muted mb-3"></i>
                                    <h5 class="text-muted">暂无邀请记录</h5>
                                    <p class="text-muted">当前筛选条件下没有找到邀请记录</p>
                                    <a href="invitations.php" class="btn btn-primary">
                                        <i class="fas fa-refresh me-2"></i>重置筛选
                                    </a>
                                </div>
                            <?php else: ?>
                                <div class="table-responsive">
                                    <table class="table table-hover mb-0" id="invitationsTable">
                                        <thead class="table-light">
                                            <tr>
                                                <th class="border-0">邀请人</th>
                                                <th class="border-0">邀请码</th>
                                                <th class="border-0">状态</th>
                                                <th class="border-0">使用情况</th>
                                                <th class="border-0">奖励</th>
                                                <th class="border-0">创建时间</th>
                                                <th class="border-0">操作</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <?php foreach ($invitations as $invitation): ?>
                                            <tr>
                                                <td>
                                                    <div class="d-flex align-items-center">
                                                        <div class="avatar-sm bg-primary rounded-circle d-flex align-items-center justify-content-center me-2">
                                                            <i class="fas fa-user text-white"></i>
                                                        </div>
                                                        <div>
                                                            <div class="fw-bold">
                                                                <a href="users.php?search=<?php echo urlencode($invitation['inviter_username']); ?>" 
                                                                   class="text-decoration-none">
                                                                    <?php echo htmlspecialchars($invitation['inviter_username']); ?>
                                                                </a>
                                                            </div>
                                                            <small class="text-muted">
                                                                <i class="fas fa-coins me-1"></i><?php echo $invitation['inviter_points']; ?> 积分
                                                            </small>
                                                        </div>
                                                    </div>
                                                </td>
                                                <td>
                                                    <div class="d-flex align-items-center">
                                                        <code class="invitation-code me-2"><?php echo htmlspecialchars($invitation['invitation_code']); ?></code>
                                                        <button class="btn btn-sm btn-outline-secondary" 
                                                                onclick="copyInvitationLink('<?php echo $invitation['invitation_code']; ?>')" 
                                                                title="复制邀请链接">
                                                            <i class="fas fa-copy"></i>
                                                        </button>
                                                    </div>
                                                </td>
                                                <td>
                                                    <?php if ($invitation['is_active']): ?>
                                                        <span class="badge bg-success">
                                                            <i class="fas fa-check-circle me-1"></i>活跃
                                                        </span>
                                                    <?php else: ?>
                                                        <span class="badge bg-secondary">
                                                            <i class="fas fa-times-circle me-1"></i>禁用
                                                        </span>
                                                    <?php endif; ?>
                                                </td>
                                                <td>
                                                    <div>
                                                        <span class="badge bg-info">
                                                            <i class="fas fa-chart-line me-1"></i>
                                                            <?php echo $invitation['use_count']; ?> 次使用
                                                        </span>
                                                    </div>
                                                    <?php if ($invitation['recent_users']): ?>
                                                    <small class="text-muted d-block mt-1">
                                                        <i class="fas fa-users me-1"></i>
                                                        <?php 
                                                        $users = explode(', ', $invitation['recent_users']);
                                                        echo htmlspecialchars(implode(', ', array_slice($users, 0, 2)));
                                                        if (count($users) > 2) echo '...';
                                                        ?>
                                                    </small>
                                                    <?php endif; ?>
                                                </td>
                                                <td>
                                                    <div class="text-success fw-bold">
                                                        <i class="fas fa-coins me-1"></i>
                                                        <?php echo $invitation['total_rewards']; ?>
                                                    </div>
                                                    <small class="text-muted">
                                                        单次: <?php echo $invitation['reward_points']; ?>
                                                    </small>
                                                </td>
                                                <td>
                                                    <div><?php echo formatTime($invitation['created_at']); ?></div>
                                                    <?php if ($invitation['last_used_at']): ?>
                                                    <small class="text-muted">
                                                        最后使用: <?php echo formatTime($invitation['last_used_at']); ?>
                                                    </small>
                                                    <?php endif; ?>
                                                </td>
                                                <td>
                                                    <div class="btn-group" role="group">
                                                        <button class="btn btn-sm btn-outline-info" 
                                                                onclick="viewInvitationDetails('<?php echo $invitation['invitation_code']; ?>', <?php echo $invitation['id']; ?>)" 
                                                                title="查看详情">
                                                            <i class="fas fa-eye"></i>
                                                        </button>
                                                        <button class="btn btn-sm btn-outline-primary" 
                                                                onclick="copyInvitationLink('<?php echo $invitation['invitation_code']; ?>')" 
                                                                title="复制链接">
                                                            <i class="fas fa-share-alt"></i>
                                                        </button>
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
                </div>
                
                <!-- 最近活动 -->
                <div class="col-lg-4">
                    <div class="card shadow">
                        <div class="card-header">
                            <h6 class="m-0 font-weight-bold text-success">
                                <i class="fas fa-clock me-2"></i>最近邀请活动
                            </h6>
                        </div>
                        <div class="card-body">
                            <?php if (empty($recent_activities)): ?>
                                <div class="text-center py-3">
                                    <i class="fas fa-history fa-2x text-muted mb-2"></i>
                                    <p class="text-muted small">暂无最近活动</p>
                                </div>
                            <?php else: ?>
                                <div class="timeline">
                                    <?php foreach ($recent_activities as $activity): ?>
                                    <div class="timeline-item">
                                        <div class="timeline-marker bg-success"></div>
                                        <div class="timeline-content">
                                            <div class="d-flex justify-content-between align-items-start">
                                                <div class="flex-grow-1">
                                                    <div class="fw-bold small">
                                                        <?php echo htmlspecialchars($activity['invitee_name']); ?>
                                                    </div>
                                                    <div class="text-muted small">
                                                        使用了 <?php echo htmlspecialchars($activity['inviter_name']); ?> 的邀请码
                                                    </div>
                                                    <div class="text-success small">
                                                        <i class="fas fa-coins me-1"></i>
                                                        +<?php echo $activity['reward_points']; ?> 积分
                                                    </div>
                                                </div>
                                                <small class="text-muted">
                                                    <?php echo formatTime($activity['used_at']); ?>
                                                </small>
                                            </div>
                                        </div>
                                    </div>
                                    <?php endforeach; ?>
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<script>
// 导出数据
function exportData() {
    const currentUrl = new URL(window.location);
    currentUrl.searchParams.set('export', '1');
    window.open(currentUrl.toString(), '_blank');
    showToast('数据导出已开始', 'info');
}

// 刷新数据
function refreshData() {
    window.location.reload();
}

// 复制邀请链接
function copyInvitationLink(code) {
    const baseUrl = window.location.origin + window.location.pathname.replace('/admin/invitations.php', '');
    const inviteUrl = baseUrl + '/user/login.php?invite=' + code;
    
    copyToClipboard(inviteUrl, '邀请链接已复制到剪贴板');
}

// 通用复制函数
function copyToClipboard(text, successMessage) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(function() {
            showToast(successMessage, 'success');
        }).catch(function(err) {
            fallbackCopy(text, successMessage);
        });
    } else {
        fallbackCopy(text, successMessage);
    }
}

// 降级复制方案
function fallbackCopy(text, successMessage) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showToast(successMessage, 'success');
    } catch (err) {
        showToast('复制失败，请手动复制', 'error');
    }
    
    document.body.removeChild(textArea);
}

// 查看邀请详情
function viewInvitationDetails(code, invitationId) {
    // 创建详情模态框
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'invitationDetailsModal';
    modal.innerHTML = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">
                        <i class="fas fa-info-circle me-2"></i>邀请码详情 - ${code}
                    </h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div class="text-center">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">加载中...</span>
                        </div>
                        <p class="mt-2">正在加载详细信息...</p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    <button type="button" class="btn btn-primary" onclick="copyInvitationLink('${code}')">
                        <i class="fas fa-copy me-2"></i>复制邀请链接
                    </button>
                    <button type="button" class="btn btn-info" onclick="viewInvitationHistory(${invitationId})">
                        <i class="fas fa-history me-2"></i>查看历史
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
    
    // 从API获取详情数据
    fetch(`api/invitation_details.php?id=${invitationId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            const modalBody = modal.querySelector('.modal-body');
            const invitation = data.invitation;
            const stats = data.statistics;
            const history = data.usage_history;
            
            const baseUrl = window.location.origin + window.location.pathname.replace('/admin/invitations.php', '');
            const inviteUrl = baseUrl + '/user/login.php?invite=' + code;
            
            modalBody.innerHTML = `
                <div class="row">
                    <div class="col-md-6">
                        <h6 class="text-primary mb-3">
                            <i class="fas fa-ticket-alt me-2"></i>邀请码信息
                        </h6>
                        <div class="card bg-light">
                            <div class="card-body">
                                <div class="mb-3">
                                    <label class="form-label fw-bold">邀请人</label>
                                    <div class="text-success fw-bold">
                                        <i class="fas fa-user me-1"></i>${invitation.inviter_username}
                                        <span class="badge bg-info ms-2">${invitation.inviter_points} 积分</span>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label fw-bold">邀请码</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control" value="${code}" readonly>
                                        <button class="btn btn-outline-secondary" onclick="copyToClipboard('${code}', '邀请码已复制')" title="复制邀请码">
                                            <i class="fas fa-copy"></i>
                                        </button>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label fw-bold">邀请链接</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control" value="${inviteUrl}" readonly>
                                        <button class="btn btn-outline-primary" onclick="copyInvitationLink('${code}')" title="复制邀请链接">
                                            <i class="fas fa-link"></i>
                                        </button>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label fw-bold">状态</label>
                                    <div>
                                        ${invitation.is_active ? 
                                            '<span class="badge bg-success"><i class="fas fa-check-circle me-1"></i>活跃</span>' : 
                                            '<span class="badge bg-secondary"><i class="fas fa-times-circle me-1"></i>禁用</span>'
                                        }
                                    </div>
                                </div>
                                <div class="mb-0">
                                    <label class="form-label fw-bold">创建时间</label>
                                    <div class="text-muted">${invitation.created_at}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <h6 class="text-success mb-3">
                            <i class="fas fa-chart-bar me-2"></i>使用统计
                        </h6>
                        <div class="card bg-light">
                            <div class="card-body">
                                <div class="row text-center mb-3">
                                    <div class="col-4">
                                        <h4 class="text-primary mb-1">${stats.total_uses}</h4>
                                        <small class="text-muted">总使用次数</small>
                                    </div>
                                    <div class="col-4">
                                        <h4 class="text-info mb-1">${stats.unique_users}</h4>
                                        <small class="text-muted">邀请用户数</small>
                                    </div>
                                    <div class="col-4">
                                        <h4 class="text-success mb-1">${stats.total_rewards}</h4>
                                        <small class="text-muted">获得积分</small>
                                    </div>
                                </div>
                                ${stats.last_used_at ? `
                                    <div class="mb-2">
                                        <small class="text-muted">
                                            <i class="fas fa-clock me-1"></i>最后使用：${stats.last_used_at}
                                        </small>
                                    </div>
                                ` : ''}
                                ${stats.first_used_at ? `
                                    <div class="mb-0">
                                        <small class="text-muted">
                                            <i class="fas fa-history me-1"></i>首次使用：${stats.first_used_at}
                                        </small>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                        
                        <div class="mt-3">
                            <h6 class="text-info mb-3">
                                <i class="fas fa-cog me-2"></i>管理操作
                            </h6>
                            <div class="d-grid gap-2">
                                <button class="btn btn-outline-warning" onclick="toggleInvitationStatus(${invitationId})">
                                    <i class="fas fa-toggle-on me-2"></i>切换状态
                                </button>
                                <button class="btn btn-outline-info" onclick="viewInvitationHistory(${invitationId})">
                                    <i class="fas fa-history me-2"></i>查看完整历史
                                </button>
                                <button class="btn btn-outline-success" onclick="copyInvitationLink('${code}')">
                                    <i class="fas fa-share-alt me-2"></i>分享链接
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
                
                ${history.length > 0 ? `
                    <hr class="my-4">
                    <h6 class="text-warning mb-3">
                        <i class="fas fa-history me-2"></i>最近使用记录
                    </h6>
                    <div class="table-responsive">
                        <table class="table table-sm">
                            <thead>
                                <tr>
                                    <th>用户</th>
                                    <th>使用时间</th>
                                    <th>奖励积分</th>
                                    <th>IP地址</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${history.slice(0, 10).map(record => `
                                    <tr>
                                        <td><i class="fas fa-user me-1"></i>${record.invitee_username}</td>
                                        <td>${record.used_at}</td>
                                        <td><span class="badge bg-success">+${record.reward_points}</span></td>
                                        <td><small class="text-muted">${record.ip_address}</small></td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                        ${history.length > 10 ? `
                            <div class="text-center">
                                <button class="btn btn-sm btn-outline-primary" onclick="viewInvitationHistory(${invitationId})">
                                    查看全部 ${history.length} 条记录
                                </button>
                            </div>
                        ` : ''}
                    </div>
                ` : '<div class="alert alert-info mt-4"><i class="fas fa-info-circle me-2"></i>暂无使用记录</div>'}
            `;
        })
        .catch(error => {
            const modalBody = modal.querySelector('.modal-body');
            modalBody.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    加载失败：${error.message}
                </div>
            `;
        });
    
    // 模态框关闭时移除
    modal.addEventListener('hidden.bs.modal', function() {
        document.body.removeChild(modal);
    });
}

// 切换邀请码状态
function toggleInvitationStatus(invitationId) {
    if (confirm('确定要切换此邀请码的状态吗？')) {
        // 这里可以添加AJAX请求来切换状态
        showToast('状态切换功能待实现', 'info');
    }
}

// 查看邀请历史
function viewInvitationHistory(invitationId) {
    window.open(`invitation_history.php?id=${invitationId}`, '_blank');
}

// 显示提示
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0 position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999;';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-${type === 'success' ? 'check' : type === 'error' ? 'times' : 'info'} me-2"></i>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    document.body.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
}

// 页面加载完成后的初始化
document.addEventListener('DOMContentLoaded', function() {
    // 自动刷新功能
    setInterval(function() {
        const lastActivity = document.querySelector('.timeline-item');
        if (lastActivity) {
            // 可以添加自动刷新最近活动的逻辑
        }
    }, 30000); // 30秒检查一次
});
</script>

<style>
/* 渐变背景卡片 */
.bg-gradient-primary {
    background: linear-gradient(135deg, #0d6efd 0%, #0056b3 100%);
}

.bg-gradient-success {
    background: linear-gradient(135deg, #198754 0%, #0d5132 100%);
}

.bg-gradient-warning {
    background: linear-gradient(135deg, #ffc107 0%, #d39e00 100%);
}

.bg-gradient-info {
    background: linear-gradient(135deg, #0dcaf0 0%, #087990 100%);
}

/* 头像样式 */
.avatar-sm {
    width: 32px;
    height: 32px;
    font-size: 0.875rem;
}

/* 邀请码样式 */
.invitation-code {
    background-color: #f8f9fa;
    padding: 4px 8px;
    border-radius: 6px;
    font-family: 'Courier New', monospace;
    font-weight: bold;
    color: #495057;
    border: 1px solid #dee2e6;
    transition: all 0.2s ease;
    font-size: 0.875rem;
}

.invitation-code:hover {
    background-color: #e9ecef;
    border-color: #007bff;
    cursor: pointer;
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,123,255,0.15);
}

/* 时间线样式 */
.timeline {
    position: relative;
    padding-left: 20px;
}

.timeline-item {
    position: relative;
    margin-bottom: 20px;
    padding-left: 20px;
}

.timeline-item:not(:last-child)::before {
    content: '';
    position: absolute;
    left: -12px;
    top: 20px;
    bottom: -20px;
    width: 2px;
    background-color: #e9ecef;
}

.timeline-marker {
    position: absolute;
    left: -16px;
    top: 4px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: 2px solid #fff;
    box-shadow: 0 0 0 2px #e9ecef;
}

.timeline-content {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 12px;
    border-left: 3px solid #28a745;
}

/* 表格样式增强 */
.table-hover tbody tr:hover {
    background-color: rgba(0,123,255,0.05);
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
}

/* 按钮组样式 */
.btn-group .btn {
    transition: all 0.2s ease;
}

.btn-group .btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* 卡片阴影增强 */
.card.shadow {
    box-shadow: 0 0.15rem 1.75rem 0 rgba(58, 59, 69, 0.15) !important;
    transition: all 0.3s ease;
}

.card.shadow:hover {
    box-shadow: 0 0.25rem 2rem 0 rgba(58, 59, 69, 0.2) !important;
    transform: translateY(-2px);
}

/* 进度条动画 */
.progress-bar {
    transition: width 0.6s ease;
}

/* 徽章样式增强 */
.badge {
    font-size: 0.75rem;
    padding: 0.375rem 0.75rem;
    border-radius: 0.375rem;
}

/* 搜索筛选卡片 */
.card-body .form-label {
    font-weight: 600;
    color: #5a5c69;
    margin-bottom: 0.5rem;
}

.form-select, .form-control {
    border-radius: 0.375rem;
    border: 1px solid #d1d3e2;
    transition: all 0.15s ease-in-out;
}

.form-select:focus, .form-control:focus {
    border-color: #bac8f3;
    box-shadow: 0 0 0 0.2rem rgba(78, 115, 223, 0.25);
}

/* 统计卡片文字颜色 - 使用白色以保持在渐变背景上的可读性 */
.text-white-75 {
    color: rgba(255, 255, 255, 0.95) !important;
}

.text-white-25 {
    color: rgba(255, 255, 255, 0.75) !important;
}

/* 响应式优化 */
@media (max-width: 768px) {
    .timeline {
        padding-left: 15px;
    }
    
    .timeline-item {
        padding-left: 15px;
    }
    
    .timeline-marker {
        left: -12px;
    }
    
    .avatar-sm {
        width: 28px;
        height: 28px;
        font-size: 0.75rem;
    }
    
    .invitation-code {
        font-size: 0.75rem;
        padding: 3px 6px;
    }
    
    .btn-group .btn {
        padding: 0.25rem 0.5rem;
        font-size: 0.875rem;
    }
}

/* 加载动画 */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

.card {
    animation: fadeIn 0.5s ease-out;
}

/* 空状态样式 */
.text-center.py-5 {
    padding: 3rem 1rem !important;
}

.text-center.py-5 i {
    opacity: 0.5;
}

/* 下拉菜单样式 */
.dropdown-menu {
    border: none;
    box-shadow: 0 0.15rem 1.75rem 0 rgba(58, 59, 69, 0.15);
    border-radius: 0.375rem;
}

.dropdown-item {
    padding: 0.5rem 1rem;
    transition: all 0.15s ease-in-out;
}

.dropdown-item:hover {
    background-color: #f8f9fa;
    transform: translateX(5px);
}

/* 模态框样式增强 */
.modal-content {
    border: none;
    border-radius: 0.5rem;
    box-shadow: 0 0.5rem 2rem 0 rgba(58, 59, 69, 0.3);
}

.modal-header {
    border-bottom: 1px solid #e3e6f0;
    border-radius: 0.5rem 0.5rem 0 0;
}

.modal-footer {
    border-top: 1px solid #e3e6f0;
    border-radius: 0 0 0.5rem 0.5rem;
}
</style>

<?php include 'includes/footer.php'; ?>