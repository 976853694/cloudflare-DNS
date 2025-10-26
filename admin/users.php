<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';
require_once '../includes/user_groups.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$action = getGet('action', 'list');
$messages = getMessages();
$groupManager = new UserGroupManager($db);

// 处理积分操作（充值/扣除）
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['points_action'])) {
    $user_id = (int)getPost('user_id');
    $points = (int)getPost('points');
    $action_type = getPost('action_type'); // 'add' 或 'subtract'
    
    if ($user_id && $points > 0 && in_array($action_type, ['add', 'subtract'])) {
        // 获取用户信息
        $user = $db->querySingle("SELECT username, points FROM users WHERE id = $user_id", true);
        
        if ($user) {
            if ($action_type === 'subtract' && $user['points'] < $points) {
                showError('用户当前积分不足，无法扣除！');
            } else {
                $operator = $action_type === 'add' ? '+' : '-';
                $stmt = $db->prepare("UPDATE users SET points = points $operator ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
                $stmt->bindValue(1, $points, SQLITE3_INTEGER);
                $stmt->bindValue(2, $user_id, SQLITE3_INTEGER);
                
                if ($stmt->execute()) {
                    $action_text = $action_type === 'add' ? '充值' : '扣除';
                    logAction('admin', $_SESSION['admin_id'], 'modify_points', "为用户 {$user['username']} {$action_text} $points 积分");
                    showSuccess("成功为用户{$action_text} $points 积分！");
                } else {
                    showError('积分操作失败！');
                }
            }
        } else {
            showError('用户不存在！');
        }
    } else {
        showError('请填写正确的参数！');
    }
    redirect('users.php');
}

// 处理修改用户信息
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['edit_user'])) {
    $user_id = (int)getPost('user_id');
    $username = trim(getPost('username'));
    $email = trim(getPost('email'));
    $points = (int)getPost('points');
    
    if ($user_id && $username) {
        // 检查用户名是否已存在（排除当前用户）
        $existing = $db->querySingle("SELECT id FROM users WHERE username = '$username' AND id != $user_id");
        if ($existing) {
            showError('用户名已存在！');
        } else {
            $stmt = $db->prepare("UPDATE users SET username = ?, email = ?, points = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
            $stmt->bindValue(1, $username, SQLITE3_TEXT);
            $stmt->bindValue(2, $email, SQLITE3_TEXT);
            $stmt->bindValue(3, $points, SQLITE3_INTEGER);
            $stmt->bindValue(4, $user_id, SQLITE3_INTEGER);
            
            if ($stmt->execute()) {
                logAction('admin', $_SESSION['admin_id'], 'edit_user', "修改用户信息: $username");
                showSuccess('用户信息修改成功！');
            } else {
                showError('修改失败！');
            }
        }
    } else {
        showError('请填写完整信息！');
    }
    redirect('users.php');
}

// 处理修改用户密码
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['change_password'])) {
    $user_id = (int)getPost('user_id');
    $new_password = trim(getPost('new_password'));
    $confirm_password = trim(getPost('confirm_password'));
    
    if ($user_id && $new_password) {
        if (strlen($new_password) < 6) {
            showError('密码长度不能少于6位！');
        } elseif ($new_password !== $confirm_password) {
            showError('两次输入的密码不一致！');
        } else {
            $hashed_password = password_hash($new_password, PASSWORD_DEFAULT);
            $stmt = $db->prepare("UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
            $stmt->bindValue(1, $hashed_password, SQLITE3_TEXT);
            $stmt->bindValue(2, $user_id, SQLITE3_INTEGER);
            
            if ($stmt->execute()) {
                $username = $db->querySingle("SELECT username FROM users WHERE id = $user_id");
                logAction('admin', $_SESSION['admin_id'], 'change_user_password', "修改用户密码: $username");
                showSuccess('用户密码修改成功！');
            } else {
                showError('密码修改失败！');
            }
        }
    } else {
        showError('请填写完整信息！');
    }
    redirect('users.php');
}

// 处理修改用户组
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['change_user_group'])) {
    $user_id = (int)getPost('user_id');
    $new_group_id = (int)getPost('group_id');
    
    if ($user_id && $new_group_id) {
        $user = $db->querySingle("SELECT username FROM users WHERE id = $user_id", true);
        $group = $groupManager->getGroupById($new_group_id);
        
        if ($user && $group) {
            if ($groupManager->changeUserGroup($user_id, $new_group_id, $_SESSION['admin_id'])) {
                logAction('admin', $_SESSION['admin_id'], 'change_user_group', 
                    "将用户 {$user['username']} 的组修改为 {$group['display_name']}");
                showSuccess("用户组修改成功！现在属于 {$group['display_name']}");
            } else {
                showError('用户组修改失败！');
            }
        } else {
            showError('用户或用户组不存在！');
        }
    } else {
        showError('请填写完整信息！');
    }
    redirect('users.php');
}

// 处理删除用户
if ($action === 'delete' && getGet('id')) {
    $id = (int)getGet('id');
    $user = $db->querySingle("SELECT username FROM users WHERE id = $id", true);
    
    if ($user) {
        // 检查用户是否有DNS记录
        $record_count = $db->querySingle("SELECT COUNT(*) FROM dns_records WHERE user_id = $id");
        
        if ($record_count > 0) {
            showError('该用户还有DNS记录，请先删除相关记录！');
        } else {
            try {
                // 开始事务
                $db->exec("BEGIN TRANSACTION");
                
                // 删除用户相关数据（按照外键依赖顺序）
                $db->exec("DELETE FROM card_key_usage WHERE user_id = $id");
                $db->exec("DELETE FROM login_attempts WHERE ip_address IN (SELECT DISTINCT ip_address FROM action_logs WHERE user_type = 'user' AND user_id = $id)");
                $db->exec("DELETE FROM action_logs WHERE user_type = 'user' AND user_id = $id");
                
                // 删除邀请相关记录
                $db->exec("DELETE FROM invitation_uses WHERE invitee_id = $id");
                $db->exec("DELETE FROM invitations WHERE inviter_id = $id");
                
                // 删除用户公告查看记录
                $db->exec("DELETE FROM user_announcement_views WHERE user_id = $id");
                
                // 删除邮箱验证记录
                $db->exec("DELETE FROM email_verifications WHERE email IN (SELECT email FROM users WHERE id = $id)");
                
                // 最后删除用户
                $db->exec("DELETE FROM users WHERE id = $id");
                
                // 提交事务
                $db->exec("COMMIT");
                
                logAction('admin', $_SESSION['admin_id'], 'delete_user', "删除用户: {$user['username']}");
                showSuccess('用户删除成功！');
            } catch (Exception $e) {
                // 回滚事务
                $db->exec("ROLLBACK");
                showError('删除用户失败: ' . $e->getMessage());
            }
        }
    } else {
        showError('用户不存在！');
    }
    redirect('users.php');
}

// 处理用户状态切换
if ($action === 'toggle_status' && getGet('id')) {
    $id = (int)getGet('id');
    $user = $db->querySingle("SELECT username, status FROM users WHERE id = $id", true);
    
    if ($user) {
        $new_status = $user['status'] ? 0 : 1;
        $status_text = $new_status ? '启用' : '禁用';
        
        $stmt = $db->prepare("UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
        $stmt->bindValue(1, $new_status, SQLITE3_INTEGER);
        $stmt->bindValue(2, $id, SQLITE3_INTEGER);
        
        if ($stmt->execute()) {
            logAction('admin', $_SESSION['admin_id'], 'toggle_user_status', "{$status_text}用户: {$user['username']}");
            showSuccess("用户状态已更新为：$status_text");
        } else {
            showError('状态更新失败！');
        }
    } else {
        showError('用户不存在！');
    }
    redirect('users.php');
}

// 处理撤销GitHub绑定
if ($action === 'revoke_github' && getGet('id')) {
    $id = (int)getGet('id');
    $user = $db->querySingle("SELECT username, github_username FROM users WHERE id = $id", true);
    
    if ($user) {
        if (!empty($user['github_username'])) {
            $stmt = $db->prepare("UPDATE users SET github_id = NULL, github_username = NULL, avatar_url = NULL, oauth_provider = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
            $stmt->bindValue(1, $id, SQLITE3_INTEGER);
            
            if ($stmt->execute()) {
                logAction('admin', $_SESSION['admin_id'], 'revoke_github', "撤销用户GitHub绑定: {$user['username']} (GitHub: {$user['github_username']})");
                showSuccess("已撤销用户 {$user['username']} 的GitHub绑定");
            } else {
                showError('撤销GitHub绑定失败！');
            }
        } else {
            showError('该用户未绑定GitHub账户！');
        }
    } else {
        showError('用户不存在！');
    }
    redirect('users.php');
}

// 获取用户列表
$users = [];
$result = $db->query("
    SELECT u.*, 
           COUNT(dr.id) as record_count,
           MAX(dr.created_at) as last_record_time
    FROM users u 
    LEFT JOIN dns_records dr ON u.id = dr.user_id 
    GROUP BY u.id 
    ORDER BY u.created_at DESC
");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $users[] = $row;
}

$page_title = '用户管理';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="main-content">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3" style="border-bottom: 1px solid rgba(255, 255, 255, 0.2);">
                <h1 class="h2">用户管理</h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <div class="input-group">
                        <input type="text" class="form-control" placeholder="搜索用户..." id="searchInput" onkeyup="searchTable('searchInput', 'usersTable')">
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
            
            <!-- 用户列表 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">用户列表</h6>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-bordered" id="usersTable">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>用户名</th>
                                    <th>邮箱</th>
                                    <th>用户组</th>
                                    <th>注册方式</th>
                                    <th>积分</th>
                                    <th>DNS记录数</th>
                                    <th>最后活动</th>
                                    <th>状态</th>
                                    <th>注册时间</th>
                                    <th>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                <?php foreach ($users as $user): ?>
                                <tr>
                                    <td><?php echo $user['id']; ?></td>
                                    <td>
                                        <strong><?php echo htmlspecialchars($user['username']); ?></strong>
                                        <?php if (!empty($user['github_username'])): ?>
                                            <br><small class="text-muted">
                                                <i class="fab fa-github"></i> <?php echo htmlspecialchars($user['github_username']); ?>
                                            </small>
                                        <?php endif; ?>
                                    </td>
                                    <td><?php echo htmlspecialchars($user['email'] ?? '未设置'); ?></td>
                                    <td>
                                        <?php 
                                        $user_group = $groupManager->getUserGroup($user['id']);
                                        if ($user_group):
                                            $badge_class = 'bg-secondary';
                                            if ($user_group['group_name'] === 'vip') $badge_class = 'bg-info';
                                            if ($user_group['group_name'] === 'svip') $badge_class = 'bg-warning text-dark';
                                        ?>
                                            <span class="badge <?php echo $badge_class; ?>" title="<?php echo htmlspecialchars($user_group['description']); ?>">
                                                <i class="fas fa-user-tag"></i> <?php echo htmlspecialchars($user_group['display_name']); ?>
                                            </span>
                                        <?php else: ?>
                                            <span class="badge bg-secondary">未分组</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if (!empty($user['oauth_provider']) && $user['oauth_provider'] === 'github'): ?>
                                            <span class="badge bg-dark">
                                                <i class="fab fa-github"></i> GitHub
                                            </span>
                                        <?php else: ?>
                                            <span class="badge bg-secondary">
                                                <i class="fas fa-user"></i> 普通注册
                                            </span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <span class="badge bg-primary"><?php echo $user['points']; ?></span>
                                    </td>
                                    <td><?php echo $user['record_count']; ?></td>
                                    <td>
                                        <?php if ($user['last_record_time']): ?>
                                            <?php echo formatTime($user['last_record_time']); ?>
                                        <?php else: ?>
                                            <span class="text-muted">无记录</span>
                                        <?php endif; ?>
                                    </td>
                                    <td>
                                        <?php if ($user['status']): ?>
                                            <span class="badge bg-success">正常</span>
                                        <?php else: ?>
                                            <span class="badge bg-danger">禁用</span>
                                        <?php endif; ?>
                                    </td>
                                    <td><?php echo formatTime($user['created_at']); ?></td>
                                    <td>
                                        <div class="btn-group" role="group">
                                            <button type="button" class="btn btn-sm btn-success" 
                                                    onclick="showPointsModal(<?php echo $user['id']; ?>, '<?php echo htmlspecialchars($user['username']); ?>', <?php echo $user['points']; ?>)"
                                                    title="管理积分">
                                                <i class="fas fa-coins"></i>
                                            </button>
                                            <button type="button" class="btn btn-sm btn-primary" 
                                                    onclick="showEditModal(<?php echo $user['id']; ?>, '<?php echo htmlspecialchars($user['username']); ?>', '<?php echo htmlspecialchars($user['email'] ?? ''); ?>', <?php echo $user['points']; ?>)"
                                                    title="编辑用户">
                                                <i class="fas fa-edit"></i>
                                            </button>
                                            <button type="button" class="btn btn-sm btn-secondary" 
                                                    onclick="showPasswordModal(<?php echo $user['id']; ?>, '<?php echo htmlspecialchars($user['username']); ?>')"
                                                    title="修改密码">
                                                <i class="fas fa-key"></i>
                                            </button>
                                            <button type="button" class="btn btn-sm btn-info" 
                                                    onclick="showGroupModal(<?php echo $user['id']; ?>, '<?php echo htmlspecialchars($user['username']); ?>', <?php echo $user_group ? $user_group['id'] : 1; ?>)"
                                                    title="修改用户组">
                                                <i class="fas fa-users-cog"></i>
                                            </button>
                                            <?php if (!empty($user['github_username'])): ?>
                                            <a href="?action=revoke_github&id=<?php echo $user['id']; ?>" 
                                               class="btn btn-sm btn-outline-dark"
                                               onclick="return confirm('确定要撤销用户 <?php echo htmlspecialchars($user['username']); ?> 的GitHub绑定吗？撤销后该用户将无法使用GitHub登录。')"
                                               title="撤销GitHub绑定">
                                                <i class="fab fa-github"></i>
                                            </a>
                                            <?php endif; ?>
                                            <a href="?action=toggle_status&id=<?php echo $user['id']; ?>" 
                                               class="btn btn-sm <?php echo $user['status'] ? 'btn-warning' : 'btn-info'; ?>"
                                               title="<?php echo $user['status'] ? '禁用用户' : '启用用户'; ?>">
                                                <i class="fas <?php echo $user['status'] ? 'fa-ban' : 'fa-check'; ?>"></i>
                                            </a>
                                            <a href="?action=delete&id=<?php echo $user['id']; ?>" 
                                               class="btn btn-sm btn-danger"
                                               onclick="return confirm('确定要删除用户 <?php echo htmlspecialchars($user['username']); ?> 吗？此操作不可恢复！')"
                                               title="删除用户">
                                                <i class="fas fa-trash"></i>
                                            </a>
                                        </div>
                                    </td>
                                </tr>
                                <?php endforeach; ?>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            </div>
        </main>
    </div>
</div>

<!-- 积分管理模态框 -->
<div class="modal fade" id="pointsModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">积分管理</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="mb-3">
                        <label class="form-label">用户</label>
                        <input type="text" class="form-control" id="points_username" readonly>
                        <input type="hidden" id="points_user_id" name="user_id">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">当前积分</label>
                        <input type="text" class="form-control" id="current_points" readonly>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">操作类型</label>
                        <select class="form-select" name="action_type" required>
                            <option value="">请选择操作</option>
                            <option value="add">充值积分</option>
                            <option value="subtract">扣除积分</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="points" class="form-label">积分数量</label>
                        <input type="number" class="form-control" id="points" name="points" min="1" required>
                        <div class="form-text">输入要操作的积分数量</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="points_action" class="btn btn-primary">确认操作</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 编辑用户模态框 -->
<div class="modal fade" id="editModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">编辑用户</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <input type="hidden" id="edit_user_id" name="user_id">
                    <div class="mb-3">
                        <label for="edit_username" class="form-label">用户名</label>
                        <input type="text" class="form-control" id="edit_username" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label for="edit_email" class="form-label">邮箱</label>
                        <input type="email" class="form-control" id="edit_email" name="email">
                        <div class="form-text">可选，用于找回密码等功能</div>
                    </div>
                    <div class="mb-3">
                        <label for="edit_points" class="form-label">积分</label>
                        <input type="number" class="form-control" id="edit_points" name="points" min="0" required>
                        <div class="form-text">直接设置用户的积分数量</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="edit_user" class="btn btn-primary">保存修改</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 修改密码模态框 -->
<div class="modal fade" id="passwordModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">修改用户密码</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <input type="hidden" id="password_user_id" name="user_id">
                    <div class="mb-3">
                        <label class="form-label">用户</label>
                        <input type="text" class="form-control" id="password_username" readonly>
                    </div>
                    <div class="mb-3">
                        <label for="new_password" class="form-label">新密码</label>
                        <input type="password" class="form-control" id="new_password" name="new_password" minlength="6" required>
                        <div class="form-text">密码长度至少6位</div>
                    </div>
                    <div class="mb-3">
                        <label for="confirm_password" class="form-label">确认密码</label>
                        <input type="password" class="form-control" id="confirm_password" name="confirm_password" minlength="6" required>
                        <div class="form-text">请再次输入新密码</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="change_password" class="btn btn-warning">修改密码</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 修改用户组模态框 -->
<div class="modal fade" id="groupModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">修改用户组</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <input type="hidden" id="group_user_id" name="user_id">
                    <div class="mb-3">
                        <label class="form-label">用户</label>
                        <input type="text" class="form-control" id="group_username" readonly>
                    </div>
                    <div class="mb-3">
                        <label for="group_id" class="form-label">用户组</label>
                        <select class="form-select" id="group_id" name="group_id" required>
                            <?php
                            $all_groups = $groupManager->getAllGroups(true);
                            foreach ($all_groups as $g):
                            ?>
                                <option value="<?php echo $g['id']; ?>">
                                    <?php echo htmlspecialchars($g['display_name']); ?> 
                                    (<?php echo $g['points_per_record']; ?>积分/条, 
                                    <?php echo $g['max_records'] == -1 ? '无限制' : $g['max_records'] . '条'; ?>)
                                </option>
                            <?php endforeach; ?>
                        </select>
                        <div class="form-text">选择新的用户组</div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="change_user_group" class="btn btn-primary">确认修改</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
function showPointsModal(userId, username, currentPoints) {
    document.getElementById('points_user_id').value = userId;
    document.getElementById('points_username').value = username;
    document.getElementById('current_points').value = currentPoints + ' 积分';
    document.getElementById('points').value = '';
    document.querySelector('select[name="action_type"]').value = '';
    new bootstrap.Modal(document.getElementById('pointsModal')).show();
}

function showEditModal(userId, username, email, points) {
    document.getElementById('edit_user_id').value = userId;
    document.getElementById('edit_username').value = username;
    document.getElementById('edit_email').value = email;
    document.getElementById('edit_points').value = points;
    new bootstrap.Modal(document.getElementById('editModal')).show();
}

function showPasswordModal(userId, username) {
    document.getElementById('password_user_id').value = userId;
    document.getElementById('password_username').value = username;
    document.getElementById('new_password').value = '';
    document.getElementById('confirm_password').value = '';
    new bootstrap.Modal(document.getElementById('passwordModal')).show();
}

function showGroupModal(userId, username, currentGroupId) {
    document.getElementById('group_user_id').value = userId;
    document.getElementById('group_username').value = username;
    document.getElementById('group_id').value = currentGroupId;
    new bootstrap.Modal(document.getElementById('groupModal')).show();
}
</script>

<?php include 'includes/footer.php'; ?>