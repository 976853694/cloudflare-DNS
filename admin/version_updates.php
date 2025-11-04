<?php
session_start();
require_once '../includes/init.php';
require_once '../config/database.php';

// 检查管理员权限
if (!isset($_SESSION['admin_logged_in']) || $_SESSION['admin_logged_in'] !== true) {
    header('Location: login.php');
    exit();
}

$db = Database::getInstance()->getConnection();

// 当前系统版本（在代码中维护）
define('CURRENT_VERSION', '2.2.3');

// 强制每次都重新获取远程信息，禁用缓存
function forceRefreshRemoteInfo() {
    // 清除可能的缓存
    if (function_exists('opcache_reset')) {
        opcache_reset();
    }
    
    // 添加随机参数防止缓存
    $timestamp = time();
    $url = 'https://gh-proxy.com/https://raw.githubusercontent.com/976853694/cloudflare-DNS/refs/heads/main/docs/g.json?' . $timestamp;
    
    $context = stream_context_create([
        'http' => [
            'timeout' => 15,
            'user_agent' => 'Mozilla/5.0 (compatible; Version Checker)',
            'header' => [
                'Cache-Control: no-cache',
                'Pragma: no-cache'
            ]
        ]
    ]);
    
    $content = @file_get_contents($url, false, $context);
    if ($content === false) {
        // 如果获取失败，返回默认结构，确保页面不出错
        return [
            'version' => '0.0.0', // 这样会强制显示有更新
            'announcements' => []
        ];
    }
    
    $data = json_decode($content, true);
    if ($data === null) {
        // JSON解析失败，返回默认结构
        return [
            'version' => '0.0.0',
            'announcements' => []
        ];
    }
    
    return $data;
}

// 获取远程版本信息（使用强制刷新）
function getRemoteVersionInfo() {
    return forceRefreshRemoteInfo();
}

// 获取当前版本
function getCurrentVersion() {
    return CURRENT_VERSION;
}

// 获取远程公告（每次都重新获取）
function getRemoteAnnouncements() {
    $remoteInfo = getRemoteVersionInfo();
    return $remoteInfo ? ($remoteInfo['announcements'] ?? []) : [];
}

// 比较版本号
function compareVersions($local, $remote) {
    return version_compare($local, $remote);
}


// 处理操作请求
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';
    
    if ($action === 'refresh_announcements') {
        $success_message = '公告已刷新！';
    } elseif ($action === 'check_update') {
        $success_message = '版本检查已完成！';
    }
}

// 获取版本和公告信息 - 每次页面加载都重新获取
echo "<!-- 正在获取最新版本和公告信息... -->\n";
$currentVersion = getCurrentVersion();
$remoteInfo = getRemoteVersionInfo();
$announcements = getRemoteAnnouncements();

// 调试信息
echo "<!-- 当前版本: $currentVersion -->\n";
echo "<!-- 远程版本: " . ($remoteInfo ? $remoteInfo['version'] : '获取失败') . " -->\n";
echo "<!-- 公告数量: " . count($announcements) . " -->\n";

include 'includes/header.php';
?>

<style>
.announcement-row {
    transition: all 0.3s ease;
}

.announcement-row:hover {
    background-color: #f8f9fa !important;
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.announcement-content {
    max-height: 400px;
    overflow-y: auto;
    padding: 15px;
    background-color: transparent;
    border-radius: 8px;
    border-left: 4px solid #007bff;
    color: #ffffff;
}

.announcement-content h1,
.announcement-content h2,
.announcement-content h3,
.announcement-content h4,
.announcement-content h5,
.announcement-content h6 {
    color: #ffffff;
    margin-top: 1rem;
    margin-bottom: 0.5rem;
}

.announcement-content p {
    margin-bottom: 1rem;
    line-height: 1.6;
    color: #ffffff;
}

.announcement-content ul,
.announcement-content ol {
    margin-bottom: 1rem;
    padding-left: 2rem;
    color: #ffffff;
}

.announcement-content li {
    color: #ffffff;
}

.announcement-content blockquote {
    border-left: 4px solid #dee2e6;
    padding-left: 1rem;
    margin: 1rem 0;
    font-style: italic;
    color: #e0e0e0;
}

.announcement-content code {
    background-color: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    padding: 0.2rem 0.4rem;
    border-radius: 0.25rem;
    font-size: 0.875em;
}

.announcement-content pre {
    background-color: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    padding: 1rem;
    border-radius: 0.5rem;
    overflow-x: auto;
}

/* 公告弹窗模态框样式 */
.modal-content {
    background-color: rgba(33, 37, 41, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

.modal-header {
    border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.modal-header .modal-title,
.modal-header .modal-title * {
    color: #ffffff !important;
}

.modal-body {
    color: #ffffff;
}

.modal-body small {
    color: #e0e0e0;
}

.modal-body .fw-bold {
    color: #ffffff;
}

.modal-footer {
    border-top: 1px solid rgba(255, 255, 255, 0.2);
}

/* 强制所有文本元素为白色 */
.announcement-content * {
    color: #ffffff !important;
}

.announcement-content a {
    color: #6fb3ff !important;
}

.announcement-content a:hover {
    color: #9fd3ff !important;
}
</style>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
    <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
        <h1 class="h2">版本更新与公告管理</h1>
    </div>

    <?php if (isset($success_message)): ?>
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            <?php echo htmlspecialchars($success_message); ?>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    <?php endif; ?>

    <?php if (isset($error_message)): ?>
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <?php echo htmlspecialchars($error_message); ?>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    <?php endif; ?>

    <!-- 版本检查区域 -->
    <div class="row mb-4">
        <div class="col-12">
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">
                        <i class="fas fa-code-branch me-2"></i>版本检查
                    </h5>
                    <button class="btn btn-outline-primary btn-sm" onclick="location.reload()">
                        <i class="fas fa-sync-alt me-1"></i>刷新检查
                    </button>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h6>当前版本</h6>
                            <p class="text-info fs-4">
                                <i class="fas fa-tag me-2"></i>
                                <?php echo htmlspecialchars($currentVersion); ?>
                            </p>
                        </div>
                        <div class="col-md-6">
                            <h6>最新版本</h6>
                            <p class="text-success fs-4">
                                <i class="fas fa-tag me-2"></i>
                                <?php echo $remoteInfo ? htmlspecialchars($remoteInfo['version']) : '获取中...'; ?>
                            </p>
                            <?php 
                            // 强制显示版本比较结果
                            if ($remoteInfo && $remoteInfo['version'] !== '0.0.0'): 
                                $comparison = compareVersions($currentVersion, $remoteInfo['version']);
                            else:
                                $comparison = -1; // 如果获取失败，默认显示需要检查
                            endif;
                            
                            if ($comparison < 0): 
                            ?>
                                <div class="alert alert-warning" id="updateAlert" style="display: block !important;">
                                    <h6><i class="fas fa-exclamation-triangle me-2"></i>
                                        <?php if ($remoteInfo && $remoteInfo['version'] !== '0.0.0'): ?>
                                            发现新版本！
                                        <?php else: ?>
                                            请检查版本更新！
                                        <?php endif; ?>
                                    </h6>
                                    <?php if ($remoteInfo && $remoteInfo['version'] !== '0.0.0'): ?>
                                        <p class="mb-2">
                                            当前版本：<strong><?php echo htmlspecialchars($currentVersion); ?></strong> → 
                                            最新版本：<strong><?php echo htmlspecialchars($remoteInfo['version']); ?></strong>
                                        </p>
                                        <p class="mb-2">有新版本可用，建议及时更新以获得最新功能和安全修复。</p>
                                    <?php else: ?>
                                        <p class="mb-2">无法获取远程版本信息，请检查网络连接或手动检查更新。</p>
                                    <?php endif; ?>
                                    <div class="d-flex gap-2">
                                        <a href="https://github.com/976853694/cloudflare-DNS" 
                                           target="_blank" class="btn btn-warning btn-sm">
                                            <i class="fas fa-download me-1"></i>前往更新
                                        </a>
                                        <button class="btn btn-outline-info btn-sm" onclick="checkUpdate()">
                                            <i class="fas fa-sync-alt me-1"></i>重新检查
                                        </button>
                                    </div>
                                </div>
                            <?php elseif ($comparison === 0): ?>
                                <div class="alert alert-success">
                                    <i class="fas fa-check-circle me-2"></i>您使用的是最新版本
                                </div>
                            <?php else: ?>
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>您使用的是开发版本
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 公告管理区域 -->
    <div class="row">
        <div class="col-12">
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h5 class="mb-0">
                        <i class="fas fa-bullhorn me-2"></i>公告管理
                    </h5>
                    <div>
                        <button class="btn btn-outline-success btn-sm" onclick="refreshAnnouncements()">
                            <i class="fas fa-sync-alt me-1"></i>刷新公告
                        </button>
                        <small class="text-muted ms-2">
                            <i class="fas fa-info-circle me-1"></i>公告实时从远程获取
                        </small>
                    </div>
                </div>
                <div class="card-body">
                    <?php if (!empty($announcements)): ?>
                        <div class="table-responsive">
                            <table class="table table-striped">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>标题</th>
                                        <th>内容预览</th>
                                        <th>日期</th>
                                        <th>优先级</th>
                                        <th>状态</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <?php foreach ($announcements as $announcement): ?>
                                        <tr class="announcement-row" style="cursor: pointer;" 
                                            onclick="showAnnouncementDetail(<?php echo htmlspecialchars(json_encode($announcement), ENT_QUOTES, 'UTF-8'); ?>)"
                                            title="点击查看详细内容">
                                            <td><?php echo htmlspecialchars($announcement['id']); ?></td>
                                            <td>
                                                <div class="d-flex align-items-center">
                                                    <i class="fas fa-file-text me-2 text-primary"></i>
                                                    <?php echo htmlspecialchars($announcement['title']); ?>
                                                </div>
                                            </td>
                                            <td>
                                                <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                                    <?php echo htmlspecialchars(strip_tags($announcement['content'])); ?>
                                                </div>
                                                <small class="text-muted">
                                                    <i class="fas fa-eye me-1"></i>点击查看完整内容
                                                </small>
                                            </td>
                                            <td><?php echo htmlspecialchars($announcement['date']); ?></td>
                                            <td>
                                                <?php
                                                $priorityClass = '';
                                                $priorityText = '';
                                                switch ($announcement['priority']) {
                                                    case 'high':
                                                        $priorityClass = 'badge bg-danger';
                                                        $priorityText = '高';
                                                        break;
                                                    case 'medium':
                                                        $priorityClass = 'badge bg-warning text-dark';
                                                        $priorityText = '中';
                                                        break;
                                                    case 'low':
                                                        $priorityClass = 'badge bg-success';
                                                        $priorityText = '低';
                                                        break;
                                                }
                                                ?>
                                                <span class="<?php echo $priorityClass; ?>"><?php echo $priorityText; ?></span>
                                            </td>
                                            <td>
                                                <span class="text-success">
                                                    <i class="fas fa-cloud me-1"></i>远程
                                                </span>
                                            </td>
                                        </tr>
                                    <?php endforeach; ?>
                                </tbody>
                            </table>
                        </div>
                    <?php else: ?>
                        <div class="text-center py-4">
                            <i class="fas fa-wifi fa-3x text-muted mb-3"></i>
                            <p class="text-muted">无法获取远程公告或暂无公告</p>
                            <button class="btn btn-outline-primary btn-sm" onclick="refreshAnnouncements()">
                                <i class="fas fa-retry me-1"></i>重试获取
                            </button>
                        </div>
                    <?php endif; ?>
                </div>
            </div>
        </div>
    </div>
</main>

    </div>
</div>

<!-- 公告详情模态框 -->
<div class="modal fade" id="announcementDetailModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title d-flex align-items-center">
                    <i class="fas fa-bullhorn me-2 text-primary"></i>
                    <span id="modalAnnouncementTitle">公告详情</span>
                    <span id="modalAnnouncementPriority" class="ms-2"></span>
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="mb-3">
                    <div class="row">
                        <div class="col-md-6">
                            <small class="text-muted">
                                <i class="fas fa-calendar me-1"></i>发布日期
                            </small>
                            <div id="modalAnnouncementDate" class="fw-bold"></div>
                        </div>
                        <div class="col-md-6">
                            <small class="text-muted">
                                <i class="fas fa-tag me-1"></i>公告编号
                            </small>
                            <div id="modalAnnouncementId" class="fw-bold"></div>
                        </div>
                    </div>
                </div>
                <hr>
                <div class="announcement-content">
                    <div id="modalAnnouncementContent"></div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                    <i class="fas fa-times me-1"></i>关闭
                </button>
            </div>
        </div>
    </div>
</div>



<script>
function refreshAnnouncements() {
    // 刷新页面来重新获取公告
    window.location.reload();
}

function checkUpdate() {
    // 刷新页面重新检查版本
    window.location.reload();
}

function showAnnouncementDetail(announcement) {
    // 设置标题
    document.getElementById('modalAnnouncementTitle').textContent = announcement.title;
    
    // 设置优先级徽章
    var priorityElement = document.getElementById('modalAnnouncementPriority');
    var priorityClass = '';
    var priorityText = '';
    
    switch (announcement.priority) {
        case 'high':
            priorityClass = 'badge bg-danger';
            priorityText = '高优先级';
            break;
        case 'medium':
            priorityClass = 'badge bg-warning text-dark';
            priorityText = '中优先级';
            break;
        case 'low':
            priorityClass = 'badge bg-success';
            priorityText = '低优先级';
            break;
    }
    
    priorityElement.className = priorityClass;
    priorityElement.textContent = priorityText;
    
    // 设置日期和ID
    document.getElementById('modalAnnouncementDate').textContent = announcement.date;
    document.getElementById('modalAnnouncementId').textContent = '#' + announcement.id;
    
    // 设置内容（支持HTML）
    document.getElementById('modalAnnouncementContent').innerHTML = announcement.content;
    
    // 显示模态框
    var modal = new bootstrap.Modal(document.getElementById('announcementDetailModal'));
    modal.show();
}

// 自动刷新页面（每10分钟）来获取最新公告和版本信息
setInterval(function() {
    console.log('自动刷新页面以获取最新信息...');
    window.location.reload();
}, 600000); // 10分钟

// 页面加载完成后显示信息
document.addEventListener('DOMContentLoaded', function() {
    console.log('版本更新页面已加载');
    console.log('当前版本: <?php echo $currentVersion; ?>');
    <?php if ($remoteInfo): ?>
    console.log('远程版本: <?php echo $remoteInfo["version"]; ?>');
    console.log('公告数量: <?php echo count($announcements); ?>');
    <?php endif; ?>
});
</script>

<?php include 'includes/footer.php'; ?>
