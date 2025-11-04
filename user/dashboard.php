<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';
require_once '../includes/user_groups.php';

checkUserLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 更新用户积分到session
$user_points = $db->querySingle("SELECT points FROM users WHERE id = {$_SESSION['user_id']}");
$_SESSION['user_points'] = $user_points;

// 获取用户信息
$user_info = $db->querySingle("SELECT * FROM users WHERE id = {$_SESSION['user_id']}", true);

// 获取用户组信息
$user_group = getUserGroup($_SESSION['user_id']);
$required_points = getRequiredPoints($_SESSION['user_id']);
$current_record_count = getUserCurrentRecordCount($_SESSION['user_id']);

// 获取用户可访问的域名
$domains = getUserAccessibleDomains($_SESSION['user_id']);
$domain_count = count($domains);

// 获取用户的DNS记录统计
$dns_records = [];
$stmt = $db->prepare("
    SELECT dr.*, d.domain_name 
    FROM dns_records dr 
    JOIN domains d ON dr.domain_id = d.id 
    WHERE dr.user_id = ? AND (dr.is_system = 0 OR dr.is_system IS NULL)
    ORDER BY dr.created_at DESC
    LIMIT 10
");
$stmt->bindValue(1, $_SESSION['user_id'], SQLITE3_INTEGER);
$result = $stmt->execute();
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $dns_records[] = $row;
}

// 统计各类型记录数量
$record_stats = [
    'total' => $current_record_count,
    'A' => 0,
    'AAAA' => 0,
    'CNAME' => 0,
    'MX' => 0,
    'TXT' => 0,
    'other' => 0,
    'proxied' => 0
];

$all_records_stmt = $db->prepare("
    SELECT type, proxied FROM dns_records 
    WHERE user_id = ? AND (is_system = 0 OR is_system IS NULL) AND status = 1
");
$all_records_stmt->bindValue(1, $_SESSION['user_id'], SQLITE3_INTEGER);
$all_records_result = $all_records_stmt->execute();
while ($row = $all_records_result->fetchArray(SQLITE3_ASSOC)) {
    if (isset($record_stats[$row['type']])) {
        $record_stats[$row['type']]++;
    } else {
        $record_stats['other']++;
    }
    if ($row['proxied']) {
        $record_stats['proxied']++;
    }
}

// 获取邀请统计（如果启用了邀请功能）
$invitation_stats = null;
if (getSetting('invitation_enabled', '1')) {
    $invitation_stats = $db->querySingle("
        SELECT 
            (SELECT COUNT(*) FROM invitation_uses WHERE invitation_id IN 
                (SELECT id FROM invitations WHERE inviter_id = {$_SESSION['user_id']})) as use_count,
            (SELECT COALESCE(SUM(reward_points), 0) FROM invitation_uses WHERE invitation_id IN 
                (SELECT id FROM invitations WHERE inviter_id = {$_SESSION['user_id']})) as total_rewards,
            (SELECT invitation_code FROM invitations WHERE inviter_id = {$_SESSION['user_id']} LIMIT 1) as code
    ", true);
}

// 获取最近的操作日志
$recent_logs = [];
$logs_stmt = $db->prepare("
    SELECT * FROM action_logs 
    WHERE user_type = 'user' AND user_id = ? 
    ORDER BY created_at DESC 
    LIMIT 8
");
$logs_stmt->bindValue(1, $_SESSION['user_id'], SQLITE3_INTEGER);
$logs_result = $logs_stmt->execute();
while ($row = $logs_result->fetchArray(SQLITE3_ASSOC)) {
    $recent_logs[] = $row;
}

// 获取用户需要显示的公告
$user_announcements = getUserAnnouncements($_SESSION['user_id']);

$page_title = '用户仪表盘';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="main-content">
                <!-- 页面标题 -->
                <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3" style="border-bottom: 1px solid #e0e0e0;">
                    <div>
                        <h1 class="h2">
                            <i class="fas fa-tachometer-alt me-2"></i>用户仪表盘
                        </h1>
                        <p class="text-muted mb-0">欢迎回来，<?php echo htmlspecialchars($user_info['username']); ?>！</p>
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
                    </div>
                </div>
                
                <!-- 消息提示 -->
                <?php if (!empty($messages)): ?>
                    <?php foreach ($messages as $type => $message): ?>
                        <div class="alert alert-<?php echo $type === 'error' ? 'danger' : $type; ?> alert-dismissible fade show">
                            <?php echo $message; ?>
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        </div>
                    <?php endforeach; ?>
                <?php endif; ?>
                
                <!-- 公告通知（页面顶部提示条，仅用于 auto_close_seconds = 0 的公告） -->
                <?php if (!empty($user_announcements)): ?>
                    <?php foreach ($user_announcements as $announcement): ?>
                        <?php if (empty($announcement['auto_close_seconds']) || $announcement['auto_close_seconds'] == 0): ?>
                        <div class="alert alert-<?php echo $announcement['type']; ?> alert-dismissible fade show">
                            <h5 class="alert-heading">
                                <i class="fas fa-bullhorn me-2"></i><?php echo htmlspecialchars($announcement['title']); ?>
                            </h5>
                            <p class="mb-0"><?php echo nl2br(htmlspecialchars($announcement['content'])); ?></p>
                            <small class="text-muted">
                                发布时间: <?php echo formatTime($announcement['created_at']); ?>
                            </small>
                            <button type="button" class="btn-close" 
                                    data-bs-dismiss="alert" 
                                    onclick="markAnnouncementAsViewed(<?php echo $announcement['id']; ?>)"></button>
                        </div>
                        <?php endif; ?>
                    <?php endforeach; ?>
                <?php endif; ?>
                
                <!-- 统计卡片 -->
                <div class="row mb-4">
                    <!-- 积分统计 -->
                    <div class="col-xl-3 col-md-6 mb-4">
                        <div class="card border-left-primary shadow h-100 py-2">
                            <div class="card-body">
                                <div class="row no-gutters align-items-center">
                                    <div class="col mr-2">
                                        <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">当前积分</div>
                                        <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $user_points; ?></div>
                                    </div>
                                    <div class="col-auto">
                                        <i class="fas fa-coins fa-2x text-gray-300"></i>
                                    </div>
                                </div>
                                <div class="mt-2">
                                    <small class="text-muted">
                                        <?php if ($required_points > 0): ?>
                                            每条记录消耗 <?php echo $required_points; ?> 积分
                                        <?php else: ?>
                                            免费添加记录
                                        <?php endif; ?>
                                    </small>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- DNS记录统计 -->
                    <div class="col-xl-3 col-md-6 mb-4">
                        <div class="card border-left-success shadow h-100 py-2">
                            <div class="card-body">
                                <div class="row no-gutters align-items-center">
                                    <div class="col mr-2">
                                        <div class="text-xs font-weight-bold text-success text-uppercase mb-1">DNS记录</div>
                                        <div class="h5 mb-0 font-weight-bold text-gray-800">
                                            <?php echo $current_record_count; ?>
                                            <?php if ($user_group && $user_group['max_records'] != -1): ?>
                                                / <?php echo $user_group['max_records']; ?>
                                            <?php endif; ?>
                                        </div>
                                    </div>
                                    <div class="col-auto">
                                        <i class="fas fa-list fa-2x text-gray-300"></i>
                                    </div>
                                </div>
                                <div class="mt-2">
                                    <small class="text-muted">
                                        <?php if ($user_group && $user_group['max_records'] != -1): ?>
                                            剩余 <?php echo max(0, $user_group['max_records'] - $current_record_count); ?> 条
                                        <?php else: ?>
                                            无限制
                                        <?php endif; ?>
                                    </small>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 域名统计 -->
                    <div class="col-xl-3 col-md-6 mb-4">
                        <div class="card border-left-info shadow h-100 py-2">
                            <div class="card-body">
                                <div class="row no-gutters align-items-center">
                                    <div class="col mr-2">
                                        <div class="text-xs font-weight-bold text-info text-uppercase mb-1">可用域名</div>
                                        <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $domain_count; ?></div>
                                    </div>
                                    <div class="col-auto">
                                        <i class="fas fa-globe fa-2x text-gray-300"></i>
                                    </div>
                                </div>
                                <div class="mt-2">
                                    <small class="text-muted">已授权访问的域名</small>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 代理记录统计 -->
                    <div class="col-xl-3 col-md-6 mb-4">
                        <div class="card border-left-warning shadow h-100 py-2">
                            <div class="card-body">
                                <div class="row no-gutters align-items-center">
                                    <div class="col mr-2">
                                        <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">代理记录</div>
                                        <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $record_stats['proxied']; ?></div>
                                    </div>
                                    <div class="col-auto">
                                        <i class="fas fa-shield-alt fa-2x text-gray-300"></i>
                                    </div>
                                </div>
                                <div class="mt-2">
                                    <small class="text-muted">启用Cloudflare代理</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 快捷操作 -->
                <div class="row mb-4">
                    <div class="col-lg-12">
                        <div class="card shadow">
                            <div class="card-header">
                                <h6 class="m-0 font-weight-bold text-primary">
                                    <i class="fas fa-bolt me-2"></i>快捷操作
                                </h6>
                            </div>
                            <div class="card-body">
                                <div class="row text-center">
                                    <div class="col-md-3 mb-3">
                                        <a href="dns_manage.php" class="btn btn-outline-primary btn-lg w-100">
                                            <i class="fas fa-plus fa-2x mb-2"></i>
                                            <div>添加DNS记录</div>
                                        </a>
                                    </div>
                                    <div class="col-md-3 mb-3">
                                        <a href="dns_manage.php" class="btn btn-outline-success btn-lg w-100">
                                            <i class="fas fa-list fa-2x mb-2"></i>
                                            <div>我的记录</div>
                                        </a>
                                    </div>
                                    <div class="col-md-3 mb-3">
                                        <a href="recharge.php" class="btn btn-outline-warning btn-lg w-100">
                                            <i class="fas fa-credit-card fa-2x mb-2"></i>
                                            <div>积分充值</div>
                                        </a>
                                    </div>
                                    <?php if (getSetting('invitation_enabled', '1')): ?>
                                    <div class="col-md-3 mb-3">
                                        <a href="invitations.php" class="btn btn-outline-info btn-lg w-100">
                                            <i class="fas fa-user-friends fa-2x mb-2"></i>
                                            <div>邀请好友</div>
                                        </a>
                                    </div>
                                    <?php endif; ?>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <!-- 记录类型分布 -->
                    <div class="col-lg-6 mb-4">
                        <div class="card shadow">
                            <div class="card-header">
                                <h6 class="m-0 font-weight-bold text-primary">
                                    <i class="fas fa-chart-pie me-2"></i>记录类型分布
                                </h6>
                            </div>
                            <div class="card-body">
                                <div class="table-responsive">
                                    <table class="table table-bordered">
                                        <thead>
                                            <tr>
                                                <th>类型</th>
                                                <th>数量</th>
                                                <th>占比</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <?php 
                                            $types = ['A', 'AAAA', 'CNAME', 'MX', 'TXT'];
                                            foreach ($types as $type): 
                                                $count = $record_stats[$type];
                                                $percentage = $record_stats['total'] > 0 ? round(($count / $record_stats['total']) * 100, 1) : 0;
                                            ?>
                                            <tr>
                                                <td><span class="badge bg-info"><?php echo $type; ?></span></td>
                                                <td><?php echo $count; ?></td>
                                                <td>
                                                    <div class="progress" style="height: 20px;">
                                                        <div class="progress-bar" role="progressbar" 
                                                             style="width: <?php echo $percentage; ?>%" 
                                                             aria-valuenow="<?php echo $percentage; ?>" 
                                                             aria-valuemin="0" aria-valuemax="100">
                                                            <?php echo $percentage; ?>%
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <?php endforeach; ?>
                                            <?php if ($record_stats['other'] > 0): ?>
                                            <tr>
                                                <td><span class="badge bg-secondary">其他</span></td>
                                                <td><?php echo $record_stats['other']; ?></td>
                                                <td>
                                                    <?php 
                                                    $percentage = $record_stats['total'] > 0 ? round(($record_stats['other'] / $record_stats['total']) * 100, 1) : 0;
                                                    ?>
                                                    <div class="progress" style="height: 20px;">
                                                        <div class="progress-bar bg-secondary" role="progressbar" 
                                                             style="width: <?php echo $percentage; ?>%" 
                                                             aria-valuenow="<?php echo $percentage; ?>" 
                                                             aria-valuemin="0" aria-valuemax="100">
                                                            <?php echo $percentage; ?>%
                                                        </div>
                                                    </div>
                                                </td>
                                            </tr>
                                            <?php endif; ?>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 最近记录 -->
                    <div class="col-lg-6 mb-4">
                        <div class="card shadow">
                            <div class="card-header">
                                <h6 class="m-0 font-weight-bold text-primary">
                                    <i class="fas fa-clock me-2"></i>最近添加的记录
                                </h6>
                            </div>
                            <div class="card-body">
                                <?php if (!empty($dns_records)): ?>
                                <div class="table-responsive">
                                    <table class="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>域名</th>
                                                <th>类型</th>
                                                <th>时间</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <?php foreach (array_slice($dns_records, 0, 5) as $record): ?>
                                            <tr>
                                                <td>
                                                    <small>
                                                        <?php 
                                                        $full_domain = $record['subdomain'] === '@' ? 
                                                            $record['domain_name'] : 
                                                            $record['subdomain'] . '.' . $record['domain_name'];
                                                        echo htmlspecialchars($full_domain); 
                                                        ?>
                                                    </small>
                                                </td>
                                                <td><span class="badge bg-info"><?php echo $record['type']; ?></span></td>
                                                <td><small><?php echo formatTime($record['created_at']); ?></small></td>
                                            </tr>
                                            <?php endforeach; ?>
                                        </tbody>
                                    </table>
                                </div>
                                <div class="text-center mt-3">
                                    <a href="records.php" class="btn btn-sm btn-outline-primary">
                                        查看全部记录 <i class="fas fa-arrow-right ms-1"></i>
                                    </a>
                                </div>
                                <?php else: ?>
                                <div class="text-center py-4">
                                    <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                                    <p class="text-muted">暂无DNS记录</p>
                                    <a href="records.php" class="btn btn-primary">
                                        <i class="fas fa-plus me-1"></i>添加第一条记录
                                    </a>
                                </div>
                                <?php endif; ?>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- 邀请统计和最近活动 -->
                <div class="row">
                    <?php if ($invitation_stats && getSetting('invitation_enabled', '1')): ?>
                    <!-- 邀请统计 -->
                    <div class="col-lg-6 mb-4">
                        <div class="card shadow">
                            <div class="card-header">
                                <h6 class="m-0 font-weight-bold text-primary">
                                    <i class="fas fa-user-friends me-2"></i>邀请统计
                                </h6>
                            </div>
                            <div class="card-body">
                                <div class="row text-center mb-3">
                                    <div class="col-6">
                                        <h3 class="text-primary"><?php echo $invitation_stats['use_count']; ?></h3>
                                        <p class="text-muted mb-0">成功邀请</p>
                                    </div>
                                    <div class="col-6">
                                        <h3 class="text-success"><?php echo $invitation_stats['total_rewards']; ?></h3>
                                        <p class="text-muted mb-0">获得积分</p>
                                    </div>
                                </div>
                                <?php if ($invitation_stats['code']): ?>
                                <div class="alert alert-info mb-0">
                                    <strong>我的邀请码：</strong>
                                    <code class="ms-2"><?php echo htmlspecialchars($invitation_stats['code']); ?></code>
                                    <button class="btn btn-sm btn-outline-primary ms-2" 
                                            onclick="copyToClipboard('<?php echo htmlspecialchars($invitation_stats['code']); ?>')">
                                        <i class="fas fa-copy"></i> 复制
                                    </button>
                                </div>
                                <div class="text-center mt-3">
                                    <a href="invitations.php" class="btn btn-sm btn-outline-primary">
                                        查看详情 <i class="fas fa-arrow-right ms-1"></i>
                                    </a>
                                </div>
                                <?php endif; ?>
                            </div>
                        </div>
                    </div>
                    <?php endif; ?>
                    
                    <!-- 最近活动 -->
                    <div class="col-lg-<?php echo ($invitation_stats && getSetting('invitation_enabled', '1')) ? '6' : '12'; ?> mb-4">
                        <div class="card shadow">
                            <div class="card-header">
                                <h6 class="m-0 font-weight-bold text-primary">
                                    <i class="fas fa-history me-2"></i>最近活动
                                </h6>
                            </div>
                            <div class="card-body" style="max-height: 400px; overflow-y: auto;">
                                <?php if (!empty($recent_logs)): ?>
                                <ul class="list-group list-group-flush">
                                    <?php foreach ($recent_logs as $log): ?>
                                    <li class="list-group-item px-0">
                                        <div class="d-flex justify-content-between align-items-start">
                                            <div>
                                                <i class="fas fa-circle text-primary me-2" style="font-size: 0.5rem;"></i>
                                                <strong><?php echo htmlspecialchars($log['action']); ?></strong>
                                                <?php if (!empty($log['details'])): ?>
                                                <br>
                                                <small class="text-muted ms-3"><?php echo htmlspecialchars($log['details']); ?></small>
                                                <?php endif; ?>
                                            </div>
                                            <small class="text-muted"><?php echo formatTime($log['created_at']); ?></small>
                                        </div>
                                    </li>
                                    <?php endforeach; ?>
                                </ul>
                                <?php else: ?>
                                <div class="text-center py-4">
                                    <i class="fas fa-info-circle fa-2x text-muted mb-3"></i>
                                    <p class="text-muted">暂无活动记录</p>
                                </div>
                                <?php endif; ?>
                            </div>
                        </div>
                    </div>
                </div>
                
            </div>
        </main>
    </div>
</div>

<!-- 强制阅读公告模态框 -->
<?php if (!empty($user_announcements)): ?>
    <?php foreach ($user_announcements as $announcement): ?>
        <?php if (!empty($announcement['auto_close_seconds']) && $announcement['auto_close_seconds'] > 0): ?>
        <div class="modal fade" id="announcement-modal-<?php echo $announcement['id']; ?>" 
             data-bs-backdrop="static" 
             data-bs-keyboard="false" 
             tabindex="-1" 
             data-announcement-id="<?php echo $announcement['id']; ?>"
             data-auto-close-seconds="<?php echo $announcement['auto_close_seconds']; ?>">
            <div class="modal-dialog modal-dialog-centered modal-lg">
                <div class="modal-content border-<?php echo $announcement['type']; ?>" style="border-width: 3px;">
                    <div class="modal-header bg-<?php echo $announcement['type']; ?> text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-bullhorn me-2"></i><?php echo htmlspecialchars($announcement['title']); ?>
                        </h5>
                    </div>
                    <div class="modal-body">
                        <div class="p-3 mb-3" style="background-color: rgba(var(--bs-<?php echo $announcement['type']; ?>-rgb), 0.1); border-left: 4px solid var(--bs-<?php echo $announcement['type']; ?>);">
                            <div style="font-size: 1.1rem; line-height: 1.6;">
                                <?php echo nl2br(htmlspecialchars($announcement['content'])); ?>
                            </div>
                        </div>
                        <div class="text-muted small">
                            <i class="fas fa-clock me-1"></i>发布时间: <?php echo formatTime($announcement['created_at']); ?>
                        </div>
                    </div>
                    <div class="modal-footer d-flex justify-content-between align-items-center">
                        <div id="countdown-modal-<?php echo $announcement['id']; ?>" class="text-warning fw-bold">
                            <i class="fas fa-lock me-1"></i>还需等待 <strong><?php echo $announcement['auto_close_seconds']; ?></strong> 秒后才能关闭
                        </div>
                        <button type="button" 
                                class="btn btn-primary" 
                                id="close-modal-btn-<?php echo $announcement['id']; ?>"
                                data-bs-dismiss="modal"
                                onclick="markAnnouncementAsViewed(<?php echo $announcement['id']; ?>)"
                                disabled
                                style="min-width: 120px;">
                            <i class="fas fa-check me-1"></i>我已阅读
                        </button>
                    </div>
                </div>
            </div>
        </div>
        <?php endif; ?>
    <?php endforeach; ?>
<?php endif; ?>

<script>
function markAnnouncementAsViewed(announcementId) {
    fetch('mark_announcement_viewed.php', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: 'announcement_id=' + announcementId
    });
}

// 处理强制阅读公告模态框
document.addEventListener('DOMContentLoaded', function() {
    // 查找所有需要强制阅读的公告模态框
    const modals = document.querySelectorAll('[data-auto-close-seconds]');
    
    modals.forEach(function(modalElement, index) {
        const autoCloseSeconds = parseInt(modalElement.getAttribute('data-auto-close-seconds'));
        const announcementId = modalElement.getAttribute('data-announcement-id');
        
        if (autoCloseSeconds > 0) {
            // 延迟显示模态框，避免多个模态框同时弹出
            setTimeout(function() {
                const modal = new bootstrap.Modal(modalElement);
                modal.show();
                
                // 启动倒计时
                let remainingSeconds = autoCloseSeconds;
                const countdownElement = document.getElementById('countdown-modal-' + announcementId);
                const closeButton = document.getElementById('close-modal-btn-' + announcementId);
                
                const countdownInterval = setInterval(function() {
                    remainingSeconds--;
                    
                    if (countdownElement) {
                        countdownElement.innerHTML = '<i class="fas fa-lock me-1"></i>还需等待 <strong>' + remainingSeconds + '</strong> 秒后才能关闭';
                    }
                    
                    if (remainingSeconds <= 0) {
                        clearInterval(countdownInterval);
                        
                        // 启用关闭按钮
                        if (closeButton) {
                            closeButton.disabled = false;
                            closeButton.classList.remove('btn-secondary');
                            closeButton.classList.add('btn-success');
                        }
                        
                        // 更新提示信息
                        if (countdownElement) {
                            countdownElement.innerHTML = '<i class="fas fa-check-circle me-1 text-success"></i>您现在可以关闭此公告了';
                        }
                    }
                }, 1000);
            }, index * 500); // 每个模态框间隔0.5秒显示，避免堆叠
        }
    });
});
</script>

<?php include 'includes/footer.php'; ?>
