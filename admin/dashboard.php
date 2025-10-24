<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();

// 获取基础统计数据
$stats = [
    'total_users' => $db->querySingle("SELECT COUNT(*) FROM users"),
    'total_domains' => $db->querySingle("SELECT COUNT(*) FROM domains"),
    'total_records' => $db->querySingle("SELECT COUNT(*) FROM dns_records"),
    'active_users' => $db->querySingle("SELECT COUNT(*) FROM users WHERE status = 1"),
    'inactive_users' => $db->querySingle("SELECT COUNT(*) FROM users WHERE status = 0"),
    'today_records' => $db->querySingle("SELECT COUNT(*) FROM dns_records WHERE date(created_at) = date('now')"),
    'this_week_users' => $db->querySingle("SELECT COUNT(*) FROM users WHERE created_at >= date('now', '-7 days')"),
    'total_points' => $db->querySingle("SELECT SUM(points) FROM users") ?: 0
];

// 获取邀请统计（如果启用）
if (getSetting('invitation_enabled', '1')) {
    // 检查invitations表是否存在以及字段结构
    $invitations_exists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='invitations'");
    if ($invitations_exists) {
        $stats['total_invitations'] = $db->querySingle("SELECT COUNT(*) FROM invitations");
        
        // 检查used_by字段是否存在
        $columns = [];
        $result = $db->query("PRAGMA table_info(invitations)");
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $columns[] = $row['name'];
        }
        
        if (in_array('used_by', $columns)) {
            $stats['used_invitations'] = $db->querySingle("SELECT COUNT(*) FROM invitations WHERE used_by IS NOT NULL");
        } else {
            // 如果没有used_by字段，可能使用其他字段来判断是否已使用
            $stats['used_invitations'] = $db->querySingle("SELECT COUNT(*) FROM invitations WHERE last_used_at IS NOT NULL");
        }
        
        if (in_array('is_active', $columns)) {
            $stats['active_invitations'] = $db->querySingle("SELECT COUNT(*) FROM invitations WHERE is_active = 1");
        } else {
            $stats['active_invitations'] = $stats['total_invitations'] - $stats['used_invitations'];
        }
    } else {
        $stats['total_invitations'] = 0;
        $stats['used_invitations'] = 0;
        $stats['active_invitations'] = 0;
    }
} else {
    $stats['total_invitations'] = 0;
    $stats['used_invitations'] = 0;
    $stats['active_invitations'] = 0;
}

// 获取卡密统计
$card_keys_exists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='card_keys'");
if ($card_keys_exists) {
    $stats['total_card_keys'] = $db->querySingle("SELECT COUNT(*) FROM card_keys");
    
    // 检查used_by字段是否存在
    $card_columns = [];
    $result = $db->query("PRAGMA table_info(card_keys)");
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $card_columns[] = $row['name'];
    }
    
    if (in_array('used_by', $card_columns)) {
        $stats['used_card_keys'] = $db->querySingle("SELECT COUNT(*) FROM card_keys WHERE used_by IS NOT NULL");
    } elseif (in_array('used_count', $card_columns)) {
        $stats['used_card_keys'] = $db->querySingle("SELECT COUNT(*) FROM card_keys WHERE used_count > 0");
    } elseif (in_array('status', $card_columns)) {
        $stats['used_card_keys'] = $db->querySingle("SELECT COUNT(*) FROM card_keys WHERE status = 'used'");
    } else {
        $stats['used_card_keys'] = 0;
    }
} else {
    $stats['total_card_keys'] = 0;
    $stats['used_card_keys'] = 0;
}

// 获取域名利用率统计
if ($stats['total_domains'] > 0) {
    $stats['domain_utilization'] = $db->querySingle("SELECT COUNT(DISTINCT domain_id) FROM dns_records") / $stats['total_domains'] * 100;
} else {
    $stats['domain_utilization'] = 0;
}

// 获取最近7天的用户注册趋势
$weekly_registrations = [];
$max_count = 0;
for ($i = 6; $i >= 0; $i--) {
    $date = date('Y-m-d', strtotime("-$i days"));
    $count = $db->querySingle("SELECT COUNT(*) FROM users WHERE date(created_at) = '$date'");
    $weekly_registrations[] = ['date' => $date, 'count' => $count];
    if ($count > $max_count) {
        $max_count = $count;
    }
}

// 获取最近的用户
$recent_users = [];
$result = $db->query("SELECT * FROM users ORDER BY created_at DESC LIMIT 5");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $recent_users[] = $row;
}

// 获取最近的DNS记录
$recent_records = [];
$result = $db->query("
    SELECT dr.*, u.username, d.domain_name 
    FROM dns_records dr 
    JOIN users u ON dr.user_id = u.id 
    JOIN domains d ON dr.domain_id = d.id 
    ORDER BY dr.created_at DESC 
    LIMIT 10
");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $recent_records[] = $row;
}

include 'includes/header.php';
?>

<!-- 自定义样式 -->
<link rel="stylesheet" href="../assets/css/dashboard-custom.css">

<style>
/* 内联样式用于特定的仪表板效果 */
.trend-chart {
    height: 100px;
    display: flex;
    align-items: end;
    justify-content: space-between;
    padding: 10px 0;
}

.trend-bar {
    flex: 1;
    margin: 0 2px;
    background: linear-gradient(to top, #667eea, #764ba2);
    border-radius: 3px 3px 0 0;
    transition: all 0.3s ease;
    cursor: pointer;
    position: relative;
}

.trend-bar:hover::after {
    content: attr(data-count);
    position: absolute;
    top: -25px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.8);
    color: white;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 12px;
    white-space: nowrap;
}

.stats-number {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-weight: 700;
}

.pulse-animation {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
}
</style>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="main-content">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3" style="border-bottom: 1px solid rgba(255, 255, 255, 0.2);">
                <h1 class="h2">仪表板</h1>
                <div class="text-muted small">
                    <i class="fas fa-clock me-1"></i>
                    <span id="current-time"></span>
                </div>
            </div>
            
            <?php 
            // 检查数据完整性并显示提示
            $missing_features = [];
            if (!$db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='invitations'")) {
                $missing_features[] = '邀请系统';
            }
            if (!$db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='card_keys'")) {
                $missing_features[] = '卡密系统';
            }
            
            if (!empty($missing_features)): 
            ?>
            <div class="alert alert-info alert-dismissible fade show">
                <i class="fas fa-info-circle me-2"></i>
                <strong>系统提示</strong><br>
                检测到以下功能模块尚未初始化：<?php echo implode('、', $missing_features); ?>。部分统计数据可能显示为0，这是正常现象。
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
            <?php endif; ?>
            
            <?php 
            // 检查是否需要迁移邀请系统
            $columns = [];
            $result = $db->query("PRAGMA table_info(invitations)");
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $columns[] = $row['name'];
            }
            $needs_migration = !in_array('is_active', $columns);
            if ($needs_migration): 
            ?>
            <div class="alert alert-warning alert-dismissible fade show">
                <i class="fas fa-exclamation-triangle me-2"></i>
                <strong>系统升级提醒</strong><br>
                检测到邀请系统可以升级为永久邀请码功能，升级后邀请码将永不过期且可重复使用。
                <div class="mt-2">
                    <a href="migrate_invitations.php" class="btn btn-warning btn-sm">
                        <i class="fas fa-rocket me-1"></i>立即升级
                    </a>
                    <button type="button" class="btn btn-outline-secondary btn-sm ms-2" data-bs-dismiss="alert">
                        稍后提醒
                    </button>
                </div>
            </div>
            <?php endif; ?>
            
            <?php 
            // 检查邀请奖励积分是否需要更新
            if (getSetting('invitation_enabled', '1') && in_array('is_active', $columns)) {
                $current_reward_points = (int)getSetting('invitation_reward_points', '10');
                $outdated_invitations = $db->querySingle("SELECT COUNT(*) FROM invitations WHERE is_active = 1 AND reward_points != $current_reward_points");
                if ($outdated_invitations > 0): 
            ?>
            <div class="alert alert-info alert-dismissible fade show">
                <i class="fas fa-info-circle me-2"></i>
                <strong>邀请奖励更新提醒</strong><br>
                检测到有 <strong><?php echo $outdated_invitations; ?></strong> 个邀请码的奖励积分与当前设置不一致，建议进行批量更新以保持数据一致性。
                <div class="mt-2">
                    <a href="update_invitation_rewards.php" class="btn btn-info btn-sm">
                        <i class="fas fa-sync-alt me-1"></i>立即更新
                    </a>
                    <a href="invitations.php" class="btn btn-outline-info btn-sm ms-2">
                        <i class="fas fa-eye me-1"></i>查看详情
                    </a>
                    <button type="button" class="btn btn-outline-secondary btn-sm ms-2" data-bs-dismiss="alert">
                        稍后处理
                    </button>
                </div>
            </div>
            <?php endif; } ?>
            
            <!-- 核心统计概览 -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card shadow-sm border-0">
                        <div class="card-header bg-gradient-primary text-white" style="background: transparent !important;">
                            <h5 class="mb-0"><i class="fas fa-chart-line me-2"></i>系统概览</h5>
                        </div>
                        <div class="card-body p-0">
                            <div class="row g-0">
                                <!-- 用户统计 -->
                                <div class="col-lg-3 col-md-6">
                                    <div class="p-4 border-end">
                                        <div class="d-flex align-items-center">
                                            <div class="flex-shrink-0">
                                                <div class="bg-primary bg-opacity-10 rounded-circle p-3">
                                                    <i class="fas fa-users text-primary fa-lg"></i>
                                                </div>
                                            </div>
                                            <div class="flex-grow-1 ms-3">
                                                <div class="text-muted small">总用户数</div>
                                                <div class="h4 mb-0 fw-bold stats-number" data-target="<?php echo $stats['total_users']; ?>"><?php echo number_format($stats['total_users']); ?></div>
                                                <div class="small text-success">
                                                    <i class="fas fa-arrow-up me-1"></i>本周新增 <?php echo $stats['this_week_users']; ?>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- 域名统计 -->
                                <div class="col-lg-3 col-md-6">
                                    <div class="p-4 border-end">
                                        <div class="d-flex align-items-center">
                                            <div class="flex-shrink-0">
                                                <div class="bg-success bg-opacity-10 rounded-circle p-3">
                                                    <i class="fas fa-globe text-success fa-lg"></i>
                                                </div>
                                            </div>
                                            <div class="flex-grow-1 ms-3">
                                                <div class="text-muted small">域名数量</div>
                                                <div class="h4 mb-0 fw-bold stats-number" data-target="<?php echo $stats['total_domains']; ?>"><?php echo number_format($stats['total_domains']); ?></div>
                                                <div class="small text-info">
                                                    <i class="fas fa-percentage me-1"></i>利用率 <?php echo number_format($stats['domain_utilization'], 1); ?>%
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- DNS记录统计 -->
                                <div class="col-lg-3 col-md-6">
                                    <div class="p-4 border-end">
                                        <div class="d-flex align-items-center">
                                            <div class="flex-shrink-0">
                                                <div class="bg-info bg-opacity-10 rounded-circle p-3">
                                                    <i class="fas fa-list text-info fa-lg"></i>
                                                </div>
                                            </div>
                                            <div class="flex-grow-1 ms-3">
                                                <div class="text-muted small">DNS记录</div>
                                                <div class="h4 mb-0 fw-bold stats-number" data-target="<?php echo $stats['total_records']; ?>"><?php echo number_format($stats['total_records']); ?></div>
                                                <div class="small text-warning">
                                                    <i class="fas fa-clock me-1"></i>今日新增 <?php echo $stats['today_records']; ?>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- 积分统计 -->
                                <div class="col-lg-3 col-md-6">
                                    <div class="p-4">
                                        <div class="d-flex align-items-center">
                                            <div class="flex-shrink-0">
                                                <div class="bg-warning bg-opacity-10 rounded-circle p-3">
                                                    <i class="fas fa-coins text-warning fa-lg"></i>
                                                </div>
                                            </div>
                                            <div class="flex-grow-1 ms-3">
                                                <div class="text-muted small">总积分</div>
                                                <div class="h4 mb-0 fw-bold stats-number" data-target="<?php echo $stats['total_points']; ?>"><?php echo number_format($stats['total_points']); ?></div>
                                                <div class="small text-primary">
                                                    <i class="fas fa-user-check me-1"></i>活跃 <?php echo $stats['active_users']; ?> / <?php echo $stats['total_users']; ?>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 详细统计卡片 -->
            <div class="row mb-4">
                <!-- 邀请系统统计 -->
                <?php if (getSetting('invitation_enabled', '1')): ?>
                <div class="col-xl-4 col-md-6 mb-4">
                    <div class="card h-100 shadow-sm border-0">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="card-title text-muted mb-0">邀请系统</h6>
                                <i class="fas fa-user-friends text-primary"></i>
                            </div>
                            <div class="row text-center">
                                <div class="col-4">
                                    <div class="h5 mb-0 text-primary"><?php echo isset($stats['total_invitations']) ? $stats['total_invitations'] : 0; ?></div>
                                    <small class="text-muted">总邀请码</small>
                                </div>
                                <div class="col-4">
                                    <div class="h5 mb-0 text-success"><?php echo isset($stats['used_invitations']) ? $stats['used_invitations'] : 0; ?></div>
                                    <small class="text-muted">已使用</small>
                                </div>
                                <div class="col-4">
                                    <div class="h5 mb-0 text-info"><?php echo isset($stats['active_invitations']) ? $stats['active_invitations'] : 0; ?></div>
                                    <small class="text-muted">有效码</small>
                                </div>
                            </div>
                            <div class="progress mt-3" style="height: 6px;">
                                <?php 
                                $total_inv = isset($stats['total_invitations']) ? $stats['total_invitations'] : 0;
                                $used_inv = isset($stats['used_invitations']) ? $stats['used_invitations'] : 0;
                                $usage_rate = $total_inv > 0 ? ($used_inv / $total_inv * 100) : 0;
                                ?>
                                <div class="progress-bar bg-success" style="width: <?php echo $usage_rate; ?>%"></div>
                            </div>
                            <small class="text-muted">使用率: <?php echo number_format($usage_rate, 1); ?>%</small>
                        </div>
                    </div>
                </div>
                <?php endif; ?>
                
                <!-- 卡密系统统计 -->
                <div class="col-xl-4 col-md-6 mb-4">
                    <div class="card h-100 shadow-sm border-0">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="card-title text-muted mb-0">卡密系统</h6>
                                <i class="fas fa-credit-card text-success"></i>
                            </div>
                            <div class="row text-center">
                                <div class="col-6">
                                    <div class="h5 mb-0 text-primary"><?php echo isset($stats['total_card_keys']) ? $stats['total_card_keys'] : 0; ?></div>
                                    <small class="text-muted">总卡密</small>
                                </div>
                                <div class="col-6">
                                    <div class="h5 mb-0 text-success"><?php echo isset($stats['used_card_keys']) ? $stats['used_card_keys'] : 0; ?></div>
                                    <small class="text-muted">已使用</small>
                                </div>
                            </div>
                            <div class="progress mt-3" style="height: 6px;">
                                <?php 
                                $total_cards = isset($stats['total_card_keys']) ? $stats['total_card_keys'] : 0;
                                $used_cards = isset($stats['used_card_keys']) ? $stats['used_card_keys'] : 0;
                                $card_usage_rate = $total_cards > 0 ? ($used_cards / $total_cards * 100) : 0;
                                ?>
                                <div class="progress-bar bg-success" style="width: <?php echo $card_usage_rate; ?>%"></div>
                            </div>
                            <small class="text-muted">使用率: <?php echo number_format($card_usage_rate, 1); ?>%</small>
                        </div>
                    </div>
                </div>
                
                <!-- 用户状态统计 -->
                <div class="col-xl-4 col-md-6 mb-4">
                    <div class="card h-100 shadow-sm border-0">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6 class="card-title text-muted mb-0">用户状态</h6>
                                <i class="fas fa-user-check text-warning"></i>
                            </div>
                            <div class="row text-center">
                                <div class="col-6">
                                    <div class="h5 mb-0 text-success"><?php echo $stats['active_users']; ?></div>
                                    <small class="text-muted">活跃用户</small>
                                </div>
                                <div class="col-6">
                                    <div class="h5 mb-0 text-danger"><?php echo $stats['inactive_users']; ?></div>
                                    <small class="text-muted">禁用用户</small>
                                </div>
                            </div>
                            <div class="progress mt-3" style="height: 6px;">
                                <div class="progress-bar bg-success" style="width: <?php echo $stats['total_users'] > 0 ? ($stats['active_users'] / $stats['total_users'] * 100) : 0; ?>%"></div>
                            </div>
                            <small class="text-muted">活跃率: <?php echo $stats['total_users'] > 0 ? number_format($stats['active_users'] / $stats['total_users'] * 100, 1) : 0; ?>%</small>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 用户注册趋势图 -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card shadow-sm border-0">
                        <div class="card-header" style="background: transparent !important;">
                            <h6 class="mb-0"><i class="fas fa-chart-area me-2"></i>最近7天用户注册趋势</h6>
                        </div>
                        <div class="card-body">
                            <div class="trend-chart">
                                <?php foreach ($weekly_registrations as $day): 
                                    // 计算柱状图高度，确保不超过容器高度（90px为最大高度，留10px间距）
                                    $bar_height = $max_count > 0 ? ($day['count'] / $max_count) * 90 : 0;
                                    // 设置最小高度为5px，方便显示0值
                                    $bar_height = max(5, $bar_height);
                                ?>
                                <div class="trend-bar" 
                                     style="height: <?php echo $bar_height; ?>px;" 
                                     data-count="<?php echo $day['count']; ?> 人"
                                     data-date="<?php echo date('m月d日', strtotime($day['date'])); ?>">
                                </div>
                                <?php endforeach; ?>
                            </div>
                            <div class="d-flex justify-content-between mt-2">
                                <?php foreach ($weekly_registrations as $day): ?>
                                <small class="text-muted text-center flex-fill"><?php echo date('m/d', strtotime($day['date'])); ?></small>
                                <?php endforeach; ?>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <!-- 最近用户 -->
                <div class="col-lg-6 mb-4">
                    <div class="card shadow-sm border-0 h-100">
                        <div class="card-header d-flex justify-content-between align-items-center" style="background: transparent !important;">
                            <h6 class="mb-0"><i class="fas fa-user-plus me-2"></i>最近注册用户</h6>
                            <a href="users.php" class="btn btn-sm btn-outline-primary">查看全部</a>
                        </div>
                        <div class="card-body p-0">
                            <?php if (empty($recent_users)): ?>
                            <div class="text-center py-4 text-muted">
                                <i class="fas fa-users fa-2x mb-2"></i>
                                <p class="mb-0">暂无用户数据</p>
                            </div>
                            <?php else: ?>
                            <div class="list-group list-group-flush">
                                <?php foreach ($recent_users as $user): ?>
                                <div class="list-group-item border-0">
                                    <div class="d-flex align-items-center">
                                        <div class="flex-shrink-0">
                                            <div class="bg-primary bg-opacity-10 rounded-circle p-2">
                                                <i class="fas fa-user text-primary"></i>
                                            </div>
                                        </div>
                                        <div class="flex-grow-1 ms-3">
                                            <div class="fw-bold"><?php echo htmlspecialchars($user['username']); ?></div>
                                            <small class="text-muted"><?php echo formatTime($user['created_at']); ?></small>
                                        </div>
                                        <div class="flex-shrink-0">
                                            <span class="badge bg-<?php echo $user['status'] ? 'success' : 'danger'; ?>">
                                                <?php echo $user['status'] ? '活跃' : '禁用'; ?>
                                            </span>
                                            <div class="small text-muted mt-1"><?php echo $user['points']; ?> 积分</div>
                                        </div>
                                    </div>
                                </div>
                                <?php endforeach; ?>
                            </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
                
                <!-- 最近DNS记录 -->
                <div class="col-lg-6 mb-4">
                    <div class="card shadow-sm border-0 h-100">
                        <div class="card-header d-flex justify-content-between align-items-center" style="background: transparent !important;">
                            <h6 class="mb-0"><i class="fas fa-dns me-2"></i>最近DNS记录</h6>
                            <a href="dns_records.php" class="btn btn-sm btn-outline-primary">查看全部</a>
                        </div>
                        <div class="card-body p-0">
                            <?php if (empty($recent_records)): ?>
                            <div class="text-center py-4 text-muted">
                                <i class="fas fa-list fa-2x mb-2"></i>
                                <p class="mb-0">暂无DNS记录</p>
                            </div>
                            <?php else: ?>
                            <div class="list-group list-group-flush">
                                <?php foreach (array_slice($recent_records, 0, 5) as $record): ?>
                                <div class="list-group-item border-0">
                                    <div class="d-flex align-items-center">
                                        <div class="flex-shrink-0">
                                            <div class="bg-info bg-opacity-10 rounded-circle p-2">
                                                <i class="fas fa-globe text-info"></i>
                                            </div>
                                        </div>
                                        <div class="flex-grow-1 ms-3">
                                            <div class="fw-bold"><?php echo htmlspecialchars($record['subdomain']); ?>.<?php echo htmlspecialchars($record['domain_name']); ?></div>
                                            <small class="text-muted">
                                                by <?php echo htmlspecialchars($record['username']); ?> • 
                                                <?php echo formatTime($record['created_at']); ?>
                                            </small>
                                        </div>
                                        <div class="flex-shrink-0">
                                            <span class="badge bg-primary"><?php echo $record['type']; ?></span>
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
            
            <!-- 快速操作面板 -->
            <div class="row mb-4">
                <div class="col-12">
                    <div class="card shadow-sm border-0">
                        <div class="card-header" style="background: transparent !important;">
                            <h6 class="mb-0"><i class="fas fa-bolt me-2"></i>快速操作</h6>
                        </div>
                        <div class="card-body">
                            <div class="row g-3">
                                <div class="col-md-3">
                                    <a href="users.php" class="btn btn-outline-primary w-100">
                                        <i class="fas fa-users me-2"></i>管理用户
                                    </a>
                                </div>
                                <div class="col-md-3">
                                    <a href="domains.php" class="btn btn-outline-success w-100">
                                        <i class="fas fa-globe me-2"></i>管理域名
                                    </a>
                                </div>
                                <div class="col-md-3">
                                </div>
                                <div class="col-md-3">
                                    <a href="card_keys.php" class="btn btn-outline-secondary w-100">
                                        <i class="fas fa-credit-card me-2"></i>生成卡密
                                    </a>
                                </div>
                            </div>
                            <div class="row g-3 mt-2">
                                <div class="col-md-3">
                                    <a href="settings.php" class="btn btn-outline-warning w-100">
                                        <i class="fas fa-cog me-2"></i>系统设置
                                    </a>
                                </div>
                                <div class="col-md-3">
                                    <a href="dns_records.php" class="btn btn-outline-dark w-100">
                                        <i class="fas fa-list me-2"></i>DNS记录
                                    </a>
                                </div>
                                <div class="col-md-3">
                                    <a href="logs.php" class="btn btn-outline-secondary w-100">
                                        <i class="fas fa-history me-2"></i>操作日志
                                    </a>
                                </div>
                                <div class="col-md-3">
                                    <a href="announcements.php" class="btn btn-outline-primary w-100">
                                        <i class="fas fa-bullhorn me-2"></i>公告管理
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            </div>
        </main>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // 数字动画效果
    function animateNumbers() {
        const statsNumbers = document.querySelectorAll('.stats-number');
        
        statsNumbers.forEach(element => {
            const target = parseInt(element.getAttribute('data-target'));
            const duration = 2000; // 2秒动画
            const step = target / (duration / 16); // 60fps
            let current = 0;
            
            const timer = setInterval(() => {
                current += step;
                if (current >= target) {
                    current = target;
                    clearInterval(timer);
                }
                element.textContent = Math.floor(current).toLocaleString();
            }, 16);
        });
    }
    
    // 进度条动画
    function animateProgressBars() {
        const progressBars = document.querySelectorAll('.progress-bar');
        progressBars.forEach(bar => {
            const width = bar.style.width;
            bar.style.width = '0%';
            setTimeout(() => {
                bar.style.width = width;
            }, 500);
        });
    }
    
    // 趋势图交互
    function setupTrendChart() {
        const trendBars = document.querySelectorAll('.trend-bar');
        trendBars.forEach(bar => {
            bar.addEventListener('mouseenter', function() {
                this.style.transform = 'scaleY(1.1)';
                this.style.filter = 'brightness(1.2)';
            });
            
            bar.addEventListener('mouseleave', function() {
                this.style.transform = 'scaleY(1)';
                this.style.filter = 'brightness(1)';
            });
        });
    }
    
    // 卡片悬停效果
    function setupCardHover() {
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            card.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-5px)';
            });
            
            card.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
            });
        });
    }
    
    // 快速操作按钮效果
    function setupQuickActions() {
        const quickBtns = document.querySelectorAll('.btn-outline-primary, .btn-outline-success, .btn-outline-info, .btn-outline-warning');
        quickBtns.forEach(btn => {
            btn.classList.add('quick-action-btn');
        });
    }
    
    // 实时时间更新
    function updateTime() {
        const now = new Date();
        const timeString = now.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        // 如果页面有时间显示元素，更新它
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            timeElement.textContent = timeString;
        }
    }
    
    // 添加脉冲动画到重要数字
    function addPulseToImportantStats() {
        const importantStats = document.querySelectorAll('.stats-number');
        importantStats.forEach((stat, index) => {
            setTimeout(() => {
                stat.classList.add('pulse-animation');
                setTimeout(() => {
                    stat.classList.remove('pulse-animation');
                }, 2000);
            }, index * 200);
        });
    }
    
    // 初始化所有效果
    setTimeout(animateNumbers, 300);
    setTimeout(animateProgressBars, 800);
    setupTrendChart();
    setupCardHover();
    setupQuickActions();
    addPulseToImportantStats();
    
    // 每秒更新时间
    setInterval(updateTime, 1000);
    updateTime();
    
    // 页面加载完成提示
    console.log('🎉 仪表板已加载完成！');
    
    // 添加键盘快捷键
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case '1':
                    e.preventDefault();
                    window.location.href = 'users.php';
                    break;
                case '2':
                    e.preventDefault();
                    window.location.href = 'domains.php';
                    break;
                case '3':
                    e.preventDefault();
                    window.location.href = 'card_keys.php';
                    break;
                case '4':
                    e.preventDefault();
                    window.location.href = 'settings.php';
                    break;
            }
        }
    });
});

// 添加工具提示
document.addEventListener('DOMContentLoaded', function() {
    // 为趋势图添加工具提示
    const trendBars = document.querySelectorAll('.trend-bar');
    trendBars.forEach(bar => {
        bar.title = `${bar.getAttribute('data-date')}: ${bar.getAttribute('data-count')}`;
    });
});
</script>

<?php include 'includes/footer.php'; ?>