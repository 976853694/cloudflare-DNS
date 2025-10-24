<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 处理批量添加前缀
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['add_prefixes'])) {
    $prefixes_text = trim(getPost('prefixes_text'));
    $description = trim(getPost('description'));
    
    if (!empty($prefixes_text)) {
        $prefixes = array_filter(array_map('trim', explode("\n", $prefixes_text)));
        $added_count = 0;
        $skipped_count = 0;
        
        foreach ($prefixes as $prefix) {
            // 验证前缀格式（允许字母、数字、连字符、星号*和@符号）
            if (!preg_match('/^[a-zA-Z0-9\-\*@]+$/', $prefix)) {
                continue;
            }
            
            // 检查是否已存在
            $existing = $db->querySingle("SELECT COUNT(*) FROM blocked_prefixes WHERE prefix = '$prefix'");
            if ($existing > 0) {
                $skipped_count++;
                continue;
            }
            
            // 添加新前缀
            $stmt = $db->prepare("INSERT INTO blocked_prefixes (prefix, description) VALUES (?, ?)");
            $stmt->bindValue(1, strtolower($prefix), SQLITE3_TEXT);
            $stmt->bindValue(2, $description, SQLITE3_TEXT);
            $stmt->execute();
            $added_count++;
        }
        
        logAction('admin', $_SESSION['admin_id'], 'add_blocked_prefixes', "添加了 $added_count 个拦截前缀");
        
        if ($added_count > 0) {
            showSuccess("成功添加 $added_count 个前缀" . ($skipped_count > 0 ? "，跳过 $skipped_count 个重复前缀" : ""));
        } else {
            showError('没有添加任何前缀，请检查格式或是否重复');
        }
    } else {
        showError('前缀列表不能为空！');
    }
    redirect('blocked_prefixes.php');
}

// 处理删除前缀
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['delete_prefix'])) {
    $id = (int)getPost('prefix_id');
    
    $prefix = $db->querySingle("SELECT prefix FROM blocked_prefixes WHERE id = $id", true);
    if ($prefix) {
        $db->exec("DELETE FROM blocked_prefixes WHERE id = $id");
        logAction('admin', $_SESSION['admin_id'], 'delete_blocked_prefix', "删除拦截前缀: {$prefix['prefix']}");
        showSuccess('前缀删除成功！');
    } else {
        showError('前缀不存在！');
    }
    redirect('blocked_prefixes.php');
}

// 处理切换状态
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['toggle_status'])) {
    $id = (int)getPost('prefix_id');
    
    $prefix = $db->querySingle("SELECT * FROM blocked_prefixes WHERE id = $id", true);
    if ($prefix) {
        $new_status = $prefix['is_active'] ? 0 : 1;
        $db->exec("UPDATE blocked_prefixes SET is_active = $new_status, updated_at = CURRENT_TIMESTAMP WHERE id = $id");
        
        $status_text = $new_status ? '启用' : '禁用';
        logAction('admin', $_SESSION['admin_id'], 'toggle_blocked_prefix', "{$status_text}拦截前缀: {$prefix['prefix']}");
        showSuccess("前缀{$status_text}成功！");
    }
    redirect('blocked_prefixes.php');
}

// 处理编辑前缀
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['edit_prefix'])) {
    $id = (int)getPost('prefix_id');
    $prefix = trim(strtolower(getPost('prefix')));
    $description = trim(getPost('description'));
    $is_active = isset($_POST['is_active']) ? 1 : 0;
    
    if (!empty($prefix) && preg_match('/^[a-zA-Z0-9\-\*@]+$/', $prefix)) {
        // 检查是否与其他前缀重复
        $existing = $db->querySingle("SELECT COUNT(*) FROM blocked_prefixes WHERE prefix = '$prefix' AND id != $id");
        if ($existing == 0) {
            $stmt = $db->prepare("UPDATE blocked_prefixes SET prefix = ?, description = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
            $stmt->bindValue(1, $prefix, SQLITE3_TEXT);
            $stmt->bindValue(2, $description, SQLITE3_TEXT);
            $stmt->bindValue(3, $is_active, SQLITE3_INTEGER);
            $stmt->bindValue(4, $id, SQLITE3_INTEGER);
            $stmt->execute();
            
            logAction('admin', $_SESSION['admin_id'], 'edit_blocked_prefix', "修改拦截前缀ID: $id");
            showSuccess('前缀修改成功！');
        } else {
            showError('该前缀已存在！');
        }
    } else {
        showError('前缀格式不正确！只允许字母、数字、连字符、星号(*)和@符号');
    }
    redirect('blocked_prefixes.php');
}

// 获取所有拦截前缀
$blocked_prefixes = [];
$result = $db->query("SELECT * FROM blocked_prefixes ORDER BY prefix ASC");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $blocked_prefixes[] = $row;
}

$page_title = 'DNS前缀拦截管理';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">DNS前缀拦截管理</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addPrefixesModal">
                        <i class="fas fa-plus me-1"></i>添加拦截前缀
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
            
            <!-- 功能说明 -->
            <div class="alert alert-info">
                <h6><i class="fas fa-info-circle me-2"></i>功能说明</h6>
                <p class="mb-2">DNS前缀拦截功能可以防止用户创建特定的子域名，保护重要的系统域名。</p>
                <ul class="mb-0">
                    <li>用户尝试添加被拦截的前缀时会收到错误提示</li>
                    <li>前缀匹配不区分大小写</li>
                    <li>只有启用状态的前缀才会生效</li>
                    <li>支持批量添加，每行一个前缀</li>
                    <li><strong>支持星号(*)拦截泛解析</strong>，添加 * 可以阻止用户创建泛解析记录</li>
                    <li><strong>支持@符号拦截根域名</strong>，添加 @ 可以阻止用户对根域名进行解析操作</li>
                </ul>
            </div>
            
            <!-- 拦截前缀列表 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">
                        拦截前缀列表 
                        <span class="badge bg-secondary ms-2"><?php echo count($blocked_prefixes); ?> 个</span>
                    </h6>
                </div>
                <div class="card-body">
                    <?php if (!empty($blocked_prefixes)): ?>
                    <div class="table-responsive">
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>前缀</th>
                                    <th>描述</th>
                                    <th>状态</th>
                                    <th>创建时间</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($blocked_prefixes as $prefix): ?>
                                <tr>
                                    <td><?php echo $prefix['id']; ?></td>
                                    <td>
                                        <code class="text-danger"><?php echo htmlspecialchars($prefix['prefix']); ?></code>
                                    </td>
                                    <td>
                                        <?php if (!empty($prefix['description'])): ?>
                                            <?php echo htmlspecialchars($prefix['description']); ?>
                                        <?php else: ?>
                                            <span class="text-muted">-</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if ($prefix['is_active']): ?>
                                            <span class="badge bg-success">启用</span>
                                        <?php else: ?>
                                            <span class="badge bg-secondary">禁用</span>
                                        <?php endif; ?>
                                    </td>
                                    <td><?php echo formatTime($prefix['created_at']); ?></td>
                                    <td>
                                        <button type="button" class="btn btn-sm btn-primary me-1" 
                                                onclick="editPrefix(<?php echo htmlspecialchars(json_encode($prefix)); ?>)"
                                                title="编辑前缀">
                                            <i class="fas fa-edit"></i>
                                        </button>
                                        <form method="POST" style="display: inline;" class="me-1">
                                            <input type="hidden" name="prefix_id" value="<?php echo $prefix['id']; ?>">
                                            <button type="submit" name="toggle_status" 
                                                    class="btn btn-sm <?php echo $prefix['is_active'] ? 'btn-warning' : 'btn-success'; ?>"
                                                    title="<?php echo $prefix['is_active'] ? '禁用' : '启用'; ?>前缀">
                                                <i class="fas <?php echo $prefix['is_active'] ? 'fa-pause' : 'fa-play'; ?>"></i>
                                            </button>
                                        </form>
                                        <form method="POST" style="display: inline;">
                                            <input type="hidden" name="prefix_id" value="<?php echo $prefix['id']; ?>">
                                            <button type="submit" name="delete_prefix" class="btn btn-sm btn-danger" 
                                                    onclick="return confirmDelete('确定要删除前缀 &quot;<?php echo htmlspecialchars($prefix['prefix']); ?>&quot; 吗？')"
                                                    title="删除前缀">
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
                        <i class="fas fa-shield-alt fa-3x text-muted mb-3"></i>
                        <p class="text-muted">暂无拦截前缀</p>
                        <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addPrefixesModal">
                            <i class="fas fa-plus me-1"></i>添加第一个拦截前缀
                        </button>
                    </div>
                    <?php endif; ?>
                </div>
            </div>
        </main>
    </div>
</div>

<!-- 添加拦截前缀模态框 -->
<div class="modal fade" id="addPrefixesModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">添加拦截前缀</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="prefixes_text" class="form-label">前缀列表</label>
                        <textarea class="form-control" id="prefixes_text" name="prefixes_text" rows="8" required placeholder="admin&#10;api&#10;mail&#10;ftp&#10;www&#10;*&#10;@&#10;test"></textarea>
                        <div class="form-text">
                            <i class="fas fa-info-circle me-1"></i>
                            每行输入一个前缀，允许字母、数字、连字符、星号(*)用于拦截泛解析、@符号代表根域名，系统会自动转换为小写
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="description" class="form-label">描述 <span class="text-muted">(可选)</span></label>
                        <input type="text" class="form-control" id="description" name="description" placeholder="例如：系统保留前缀" maxlength="100">
                        <div class="form-text">为这批前缀添加统一描述，方便管理</div>
                    </div>
                    <div class="alert alert-warning">
                        <h6><i class="fas fa-exclamation-triangle me-2"></i>注意事项</h6>
                        <ul class="mb-0">
                            <li>前缀将立即生效，用户无法创建对应的子域名</li>
                            <li>重复的前缀会被自动跳过</li>
                            <li>格式不正确的前缀会被忽略</li>
                        </ul>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="add_prefixes" class="btn btn-primary">添加前缀</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 编辑前缀模态框 -->
<div class="modal fade" id="editPrefixModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">编辑拦截前缀</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <input type="hidden" id="edit_prefix_id" name="prefix_id">
                    <div class="mb-3">
                        <label for="edit_prefix" class="form-label">前缀</label>
                        <input type="text" class="form-control" id="edit_prefix" name="prefix" required pattern="[a-zA-Z0-9\-\*@]+" maxlength="50">
                        <div class="form-text">允许字母、数字、连字符、星号(*用于泛解析拦截)和@符号(根域名)</div>
                    </div>
                    <div class="mb-3">
                        <label for="edit_description" class="form-label">描述 <span class="text-muted">(可选)</span></label>
                        <input type="text" class="form-control" id="edit_description" name="description" maxlength="100">
                    </div>
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" id="edit_is_active" name="is_active" value="1">
                            <label class="form-check-label" for="edit_is_active">
                                启用此前缀拦截
                            </label>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="edit_prefix" class="btn btn-primary">保存修改</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
function editPrefix(prefix) {
    document.getElementById('edit_prefix_id').value = prefix.id;
    document.getElementById('edit_prefix').value = prefix.prefix;
    document.getElementById('edit_description').value = prefix.description || '';
    document.getElementById('edit_is_active').checked = prefix.is_active == 1;
    
    var modal = new bootstrap.Modal(document.getElementById('editPrefixModal'));
    modal.show();
}

function confirmDelete(message) {
    return confirm(message);
}
</script>

<?php include 'includes/footer.php'; ?>