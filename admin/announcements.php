<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 处理添加公告
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_announcement'])) {
    $title = trim(getPost('title'));
    $content = trim(getPost('content'));
    $type = getPost('type');
    $show_frequency = getPost('show_frequency');
    $interval_hours = (int)getPost('interval_hours');
    $is_active = isset($_POST['is_active']) ? 1 : 0;
    $target_user_ids = trim(getPost('target_user_ids', ''));
    $auto_close_seconds = (int)getPost('auto_close_seconds', 0);
    
    if (!empty($title) && !empty($content)) {
        $stmt = $db->prepare("INSERT INTO announcements (title, content, type, show_frequency, interval_hours, is_active, target_user_ids, auto_close_seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?)");
        $stmt->bindValue(1, $title, SQLITE3_TEXT);
        $stmt->bindValue(2, $content, SQLITE3_TEXT);
        $stmt->bindValue(3, $type, SQLITE3_TEXT);
        $stmt->bindValue(4, $show_frequency, SQLITE3_TEXT);
        $stmt->bindValue(5, $interval_hours, SQLITE3_INTEGER);
        $stmt->bindValue(6, $is_active, SQLITE3_INTEGER);
        $stmt->bindValue(7, $target_user_ids ? $target_user_ids : null, SQLITE3_TEXT);
        $stmt->bindValue(8, $auto_close_seconds, SQLITE3_INTEGER);
        $stmt->execute();
        
        logAction('admin', $_SESSION['admin_id'], 'add_announcement', "添加公告: $title");
        showSuccess('公告添加成功！');
    } else {
        showError('标题和内容不能为空！');
    }
    redirect('announcements.php');
}

// 处理修改公告
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['edit_announcement'])) {
    $id = (int)getPost('announcement_id');
    $title = trim(getPost('title'));
    $content = trim(getPost('content'));
    $type = getPost('type');
    $show_frequency = getPost('show_frequency');
    $interval_hours = (int)getPost('interval_hours');
    $is_active = isset($_POST['is_active']) ? 1 : 0;
    $target_user_ids = trim(getPost('target_user_ids', ''));
    $auto_close_seconds = (int)getPost('auto_close_seconds', 0);
    
    if (!empty($title) && !empty($content)) {
        $stmt = $db->prepare("UPDATE announcements SET title = ?, content = ?, type = ?, show_frequency = ?, interval_hours = ?, is_active = ?, target_user_ids = ?, auto_close_seconds = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
        $stmt->bindValue(1, $title, SQLITE3_TEXT);
        $stmt->bindValue(2, $content, SQLITE3_TEXT);
        $stmt->bindValue(3, $type, SQLITE3_TEXT);
        $stmt->bindValue(4, $show_frequency, SQLITE3_TEXT);
        $stmt->bindValue(5, $interval_hours, SQLITE3_INTEGER);
        $stmt->bindValue(6, $is_active, SQLITE3_INTEGER);
        $stmt->bindValue(7, $target_user_ids ? $target_user_ids : null, SQLITE3_TEXT);
        $stmt->bindValue(8, $auto_close_seconds, SQLITE3_INTEGER);
        $stmt->bindValue(9, $id, SQLITE3_INTEGER);
        $stmt->execute();
        
        logAction('admin', $_SESSION['admin_id'], 'edit_announcement', "修改公告ID: $id");
        showSuccess('公告修改成功！');
    } else {
        showError('标题和内容不能为空！');
    }
    redirect('announcements.php');
}

// 处理删除公告
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete_announcement'])) {
    $id = (int)getPost('announcement_id');
    
    $announcement = $db->querySingle("SELECT title FROM announcements WHERE id = $id", true);
    if ($announcement) {
        try {
            // 开始事务
            $db->exec("BEGIN TRANSACTION");
            
            // 先删除关联的用户查看记录，再删除公告
            $db->exec("DELETE FROM user_announcement_views WHERE announcement_id = $id");
            $db->exec("DELETE FROM announcements WHERE id = $id");
            
            // 提交事务
            $db->exec("COMMIT");
            
            logAction('admin', $_SESSION['admin_id'], 'delete_announcement', "删除公告: {$announcement['title']}");
            showSuccess('公告删除成功！');
        } catch (Exception $e) {
            // 回滚事务
            $db->exec("ROLLBACK");
            error_log("Delete announcement failed: " . $e->getMessage());
            showError('公告删除失败：' . $e->getMessage());
        }
    } else {
        showError('公告不存在！');
    }
    redirect('announcements.php');
}

// 处理切换状态
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['toggle_status'])) {
    $id = (int)getPost('announcement_id');
    
    $announcement = $db->querySingle("SELECT * FROM announcements WHERE id = $id", true);
    if ($announcement) {
        $new_status = $announcement['is_active'] ? 0 : 1;
        $db->exec("UPDATE announcements SET is_active = $new_status WHERE id = $id");
        
        $status_text = $new_status ? '启用' : '禁用';
        logAction('admin', $_SESSION['admin_id'], 'toggle_announcement', "{$status_text}公告: {$announcement['title']}");
        showSuccess("公告{$status_text}成功！");
    }
    redirect('announcements.php');
}

// 获取所有公告
$announcements = [];
$result = $db->query("SELECT * FROM announcements ORDER BY created_at DESC");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $announcements[] = $row;
}

$page_title = '公告管理';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">公告管理</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addAnnouncementModal">
                        <i class="fas fa-plus me-1"></i>添加公告
                    </button>
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
            
            <!-- 公告列表 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">公告列表</h6>
                </div>
                <div class="card-body">
                    <?php if (!empty($announcements)): ?>
                    <div class="table-responsive">
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>标题</th>
                                    <th>类型</th>
                                    <th>显示频率</th>
                                    <th>目标用户</th>
                                    <th>延迟关闭</th>
                                    <th>状态</th>
                                    <th>创建时间</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($announcements as $announcement): ?>
                                <tr>
                                    <td><?php echo $announcement['id']; ?></td>
                                    <td>
                                        <strong><?php echo htmlspecialchars($announcement['title']); ?></strong>
                                        <br>
                                        <small class="text-muted">
                                            <?php echo htmlspecialchars(mb_substr($announcement['content'], 0, 50)) . (mb_strlen($announcement['content']) > 50 ? '...' : ''); ?>
                                        </small>
                                    </td>
                                    <td>
                                        <?php
                                        $type_badges = [
                                            'info' => 'bg-info',
                                            'success' => 'bg-success',
                                            'warning' => 'bg-warning',
                                            'danger' => 'bg-danger'
                                        ];
                                        $type_names = [
                                            'info' => '信息',
                                            'success' => '成功',
                                            'warning' => '警告',
                                            'danger' => '重要'
                                        ];
                                        ?>
                                        <span class="badge <?php echo $type_badges[$announcement['type']] ?? 'bg-secondary'; ?>">
                                            <?php echo $type_names[$announcement['type']] ?? $announcement['type']; ?>
                                        </span>
                                    </td>
                                    <td>
                                        <?php
                                        $frequency_names = [
                                            'once' => '仅一次',
                                            'daily' => '每日',
                                            'login' => '每次登录',
                                            'interval' => "每{$announcement['interval_hours']}小时"
                                        ];
                                        echo $frequency_names[$announcement['show_frequency']] ?? $announcement['show_frequency'];
                                        ?>
                                    </td>
                                    <td>
                                        <?php if (!empty($announcement['target_user_ids'])): ?>
                                            <span class="badge bg-primary" title="用户ID: <?php echo htmlspecialchars($announcement['target_user_ids']); ?>">
                                                <i class="fas fa-user me-1"></i>指定用户
                                            </span>
                                        <?php else: ?>
                                            <span class="badge bg-secondary">全部用户</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if ($announcement['auto_close_seconds'] > 0): ?>
                                            <span class="badge bg-warning text-dark"><?php echo $announcement['auto_close_seconds']; ?>秒后可关闭</span>
                                        <?php else: ?>
                                            <span class="badge bg-success">立即可关闭</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if ($announcement['is_active']): ?>
                                            <span class="badge bg-success">启用</span>
                                        <?php else: ?>
                                            <span class="badge bg-secondary">禁用</span>
                                        <?php endif; ?>
                                    </td>
                                    <td><?php echo formatTime($announcement['created_at']); ?></td>
                                    <td>
                                        <button type="button" class="btn btn-sm btn-primary me-1" 
                                                onclick="editAnnouncement(<?php echo htmlspecialchars(json_encode($announcement)); ?>)"
                                                title="编辑公告">
                                            <i class="fas fa-edit"></i>
                                        </button>
                                        <form method="POST" style="display: inline;" class="me-1">
                                            <input type="hidden" name="announcement_id" value="<?php echo $announcement['id']; ?>">
                                            <button type="submit" name="toggle_status" 
                                                    class="btn btn-sm <?php echo $announcement['is_active'] ? 'btn-warning' : 'btn-success'; ?>"
                                                    title="<?php echo $announcement['is_active'] ? '禁用' : '启用'; ?>公告">
                                                <i class="fas <?php echo $announcement['is_active'] ? 'fa-pause' : 'fa-play'; ?>"></i>
                                            </button>
                                        </form>
                                        <form method="POST" style="display: inline;">
                                            <input type="hidden" name="announcement_id" value="<?php echo $announcement['id']; ?>">
                                            <button type="submit" name="delete_announcement" class="btn btn-sm btn-danger" 
                                                    onclick="return confirmDelete('确定要删除这条公告吗？')"
                                                    title="删除公告">
                                                <i class="fas fa-trash"></i>
                                            </button>
                                        </form>
                                    </td>
                                </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>
                    <?php else: ?>
                    <div class="text-center py-4">
                        <i class="fas fa-bullhorn fa-3x text-muted mb-3"></i>
                        <p class="text-muted">暂无公告</p>
                        <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addAnnouncementModal">
                            <i class="fas fa-plus me-1"></i>添加第一条公告
                        </button>
                    </div>
                    <?php endif; ?>
                </div>
            </div>
        </main>
    </div>
</div>

<!-- 添加公告模态框 -->
<div class="modal fade" id="addAnnouncementModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">添加公告</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="title" class="form-label">公告标题</label>
                        <input type="text" class="form-control" id="title" name="title" required maxlength="100">
                    </div>
                    <div class="mb-3">
                        <label for="content" class="form-label">公告内容</label>
                        <textarea class="form-control" id="content" name="content" rows="5" required></textarea>
                        <div class="form-text">支持HTML标签，如 &lt;br&gt;、&lt;strong&gt;、&lt;a&gt; 等</div>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <label for="type" class="form-label">公告类型</label>
                            <select class="form-select" id="type" name="type" required>
                                <option value="info">信息</option>
                                <option value="success">成功</option>
                                <option value="warning">警告</option>
                                <option value="danger">重要</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label for="show_frequency" class="form-label">显示频率</label>
                            <select class="form-select" id="show_frequency" name="show_frequency" required onchange="toggleIntervalInput()">
                                <option value="once">仅显示一次</option>
                                <option value="login">每次登录显示</option>
                                <option value="daily">每日显示一次</option>
                                <option value="interval">自定义间隔</option>
                            </select>
                        </div>
                    </div>
                    <div class="mb-3 mt-3" id="interval_section" style="display: none;">
                        <label for="interval_hours" class="form-label">显示间隔（小时）</label>
                        <input type="number" class="form-control" id="interval_hours" name="interval_hours" value="24" min="1" max="8760">
                        <div class="form-text">设置公告显示的时间间隔，单位为小时</div>
                    </div>
                    <div class="mb-3">
                        <label for="target_user_ids" class="form-label">目标用户ID <span class="text-muted">(可选)</span></label>
                        <input type="text" class="form-control" id="target_user_ids" name="target_user_ids" placeholder="例如：1,2,3">
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            留空表示向所有用户显示；填写用户ID（多个ID用英文逗号分隔）表示仅向指定用户显示
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="auto_close_seconds" class="form-label">延迟关闭时间（秒） <span class="text-muted">(可选)</span></label>
                        <input type="number" class="form-control" id="auto_close_seconds" name="auto_close_seconds" value="0" min="0" max="3600">
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            设置为0表示可以立即手动关闭；设置大于0的数值表示公告将在指定秒数后才能手动关闭（强制用户阅读）
                        </div>
                    </div>
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="is_active" name="is_active" value="1" checked>
                            <label class="form-check-label" for="is_active">
                                立即启用此公告
                            </label>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="add_announcement" class="btn btn-primary">添加公告</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 编辑公告模态框 -->
<div class="modal fade" id="editAnnouncementModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">编辑公告</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <input type="hidden" id="edit_announcement_id" name="announcement_id">
                    <div class="mb-3">
                        <label for="edit_title" class="form-label">公告标题</label>
                        <input type="text" class="form-control" id="edit_title" name="title" required maxlength="100">
                    </div>
                    <div class="mb-3">
                        <label for="edit_content" class="form-label">公告内容</label>
                        <textarea class="form-control" id="edit_content" name="content" rows="5" required></textarea>
                        <div class="form-text">支持HTML标签，如 &lt;br&gt;、&lt;strong&gt;、&lt;a&gt; 等</div>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <label for="edit_type" class="form-label">公告类型</label>
                            <select class="form-select" id="edit_type" name="type" required>
                                <option value="info">信息</option>
                                <option value="success">成功</option>
                                <option value="warning">警告</option>
                                <option value="danger">重要</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label for="edit_show_frequency" class="form-label">显示频率</label>
                            <select class="form-select" id="edit_show_frequency" name="show_frequency" required onchange="toggleEditIntervalInput()">
                                <option value="once">仅显示一次</option>
                                <option value="login">每次登录显示</option>
                                <option value="daily">每日显示一次</option>
                                <option value="interval">自定义间隔</option>
                            </select>
                        </div>
                    </div>
                    <div class="mb-3 mt-3" id="edit_interval_section" style="display: none;">
                        <label for="edit_interval_hours" class="form-label">显示间隔（小时）</label>
                        <input type="number" class="form-control" id="edit_interval_hours" name="interval_hours" value="24" min="1" max="8760">
                        <div class="form-text">设置公告显示的时间间隔，单位为小时</div>
                    </div>
                    <div class="mb-3">
                        <label for="edit_target_user_ids" class="form-label">目标用户ID <span class="text-muted">(可选)</span></label>
                        <input type="text" class="form-control" id="edit_target_user_ids" name="target_user_ids" placeholder="例如：1,2,3">
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            留空表示向所有用户显示；填写用户ID（多个ID用英文逗号分隔）表示仅向指定用户显示
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="edit_auto_close_seconds" class="form-label">延迟关闭时间（秒） <span class="text-muted">(可选)</span></label>
                        <input type="number" class="form-control" id="edit_auto_close_seconds" name="auto_close_seconds" value="0" min="0" max="3600">
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            设置为0表示可以立即手动关闭；设置大于0的数值表示公告将在指定秒数后才能手动关闭（强制用户阅读）
                        </div>
                    </div>
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="edit_is_active" name="is_active" value="1">
                            <label class="form-check-label" for="edit_is_active">
                                启用此公告
                            </label>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="edit_announcement" class="btn btn-primary">保存修改</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
function toggleIntervalInput() {
    const frequency = document.getElementById('show_frequency').value;
    const intervalSection = document.getElementById('interval_section');
    intervalSection.style.display = frequency === 'interval' ? 'block' : 'none';
}

function toggleEditIntervalInput() {
    const frequency = document.getElementById('edit_show_frequency').value;
    const intervalSection = document.getElementById('edit_interval_section');
    intervalSection.style.display = frequency === 'interval' ? 'block' : 'none';
}

function editAnnouncement(announcement) {
    document.getElementById('edit_announcement_id').value = announcement.id;
    document.getElementById('edit_title').value = announcement.title;
    document.getElementById('edit_content').value = announcement.content;
    document.getElementById('edit_type').value = announcement.type;
    document.getElementById('edit_show_frequency').value = announcement.show_frequency;
    document.getElementById('edit_interval_hours').value = announcement.interval_hours;
    document.getElementById('edit_target_user_ids').value = announcement.target_user_ids || '';
    document.getElementById('edit_auto_close_seconds').value = announcement.auto_close_seconds || 0;
    document.getElementById('edit_is_active').checked = announcement.is_active == 1;
    
    toggleEditIntervalInput();
    
    var modal = new bootstrap.Modal(document.getElementById('editAnnouncementModal'));
    modal.show();
}

function confirmDelete(message) {
    return confirm(message);
}
</script>

<?php include 'includes/footer.php'; ?>