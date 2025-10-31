<?php
session_start();
require_once '../config/database.php';
require_once '../config/github_oauth.php';
require_once '../config/smtp.php';
require_once '../includes/functions.php';
require_once '../includes/captcha.php';
require_once '../includes/user_groups.php';

checkUserLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 获取用户组信息
$user_group = getUserGroup($_SESSION['user_id']);
$required_points = getRequiredPoints($_SESSION['user_id']);
$current_record_count = getUserCurrentRecordCount($_SESSION['user_id']);

// 处理发送密码修改验证码
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['send_password_code'])) {
    $current_password = getPost('current_password');
    $captcha_code = getPost('captcha_code');
    
    $captcha = new Captcha();
    
    if (!$current_password || !$captcha_code) {
        showError('请填写完整信息');
    } elseif (!$captcha->verify($captcha_code)) {
        showError('验证码错误或已过期');
    } else {
        // 验证当前密码
        $user = $db->querySingle("SELECT * FROM users WHERE id = {$_SESSION['user_id']}", true);
        if (!password_verify($current_password, $user['password'])) {
            showError('当前密码错误');
        } elseif (empty($user['email'])) {
            showError('您的账户未绑定邮箱，无法发送验证码');
        } else {
            // 发送密码修改验证码
            try {
                // 启用输出缓冲，防止调试信息显示到页面
                ob_start();
                $emailService = new EmailService();
                $emailService->sendPasswordReset($user['email'], $user['username'], $user['id']);
                ob_end_clean();
                
                $_SESSION['password_change_step'] = 'verify';
                showSuccess('验证码已发送到您的邮箱，请查收');
            } catch (Exception $e) {
                ob_end_clean();
                showError('验证码发送失败：' . $e->getMessage());
                error_log("Password change verification failed for user {$user['id']}: " . $e->getMessage());
            }
        }
    }
    redirect('profile.php');
}

// 处理密码修改（需要验证码）
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['change_password'])) {
    $verification_code = getPost('verification_code');
    $new_password = getPost('new_password');
    $confirm_password = getPost('confirm_password');
    
    if (!$verification_code || !$new_password || !$confirm_password) {
        showError('请填写完整信息');
    } elseif (strlen($new_password) < 6) {
        showError('新密码至少需要6个字符');
    } elseif ($new_password !== $confirm_password) {
        showError('两次输入的新密码不一致');
    } else {
        // 获取用户信息
        $user = $db->querySingle("SELECT * FROM users WHERE id = {$_SESSION['user_id']}", true);
        
        // 验证邮箱验证码
        try {
            $emailService = new EmailService();
            $verification = $emailService->verifyCode($user['email'], $verification_code, 'password_reset');
            
            if ($verification['valid'] && $verification['user_id'] == $_SESSION['user_id']) {
                // 更新密码
                $hashed_password = password_hash($new_password, PASSWORD_DEFAULT);
                $stmt = $db->prepare("UPDATE users SET password = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
                $stmt->bindValue(1, $hashed_password, SQLITE3_TEXT);
                $stmt->bindValue(2, $_SESSION['user_id'], SQLITE3_INTEGER);
                
                if ($stmt->execute()) {
                    logAction('user', $_SESSION['user_id'], 'change_password', '用户修改密码');
                    
                    // 发送密码修改通知邮件
                    try {
                        $emailService->sendPasswordChangeNotification($user['email'], $user['username']);
                        showSuccess('密码修改成功！已发送通知邮件到您的邮箱');
                    } catch (Exception $e) {
                        showSuccess('密码修改成功！但邮件通知发送失败');
                        error_log("Password change email failed: " . $e->getMessage());
                    }
                    
                    // 清除验证步骤
                    unset($_SESSION['password_change_step']);
                } else {
                    showError('密码修改失败');
                }
            } else {
                showError('验证码错误或已过期');
            }
        } catch (Exception $e) {
            showError('验证失败：' . $e->getMessage());
        }
    }
    redirect('profile.php');
}

// 邮箱修改重定向到专用页面
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_email'])) {
    redirect('change_email.php');
}

// 处理GitHub解绑
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['unbind_github'])) {
    // 检查用户是否确实绑定了GitHub
    $user_github = $db->querySingle("SELECT github_id, github_username FROM users WHERE id = {$_SESSION['user_id']}", true);
    
    if (empty($user_github['github_id'])) {
        showError('您尚未绑定GitHub账户！');
        redirect('profile.php');
    }
    
    $stmt = $db->prepare("UPDATE users SET github_id = NULL, github_username = NULL, avatar_url = NULL, oauth_provider = NULL WHERE id = ?");
    $stmt->bindValue(1, $_SESSION['user_id'], SQLITE3_INTEGER);
    
    if ($stmt->execute()) {
        logAction('user', $_SESSION['user_id'], 'unbind_github', "用户解绑GitHub账户: {$user_github['github_username']}");
        showSuccess('GitHub账户解绑成功！');
    } else {
        showError('GitHub账户解绑失败！');
    }
    redirect('profile.php');
}

// 获取用户信息
$user = $db->querySingle("SELECT * FROM users WHERE id = {$_SESSION['user_id']}", true);

// 检查GitHub OAuth是否启用
$github_oauth_enabled = getSetting('github_oauth_enabled', 0);
$github = null;
if ($github_oauth_enabled) {
    try {
        $github = new GitHubOAuth();
    } catch (Exception $e) {
        // GitHub OAuth配置有问题，忽略
    }
}

$page_title = '个人设置';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="main-content">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3" style="border-bottom: 1px solid #e0e0e0;">
                <h1 class="h2">个人设置</h1>
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
            
            <div class="row">
                <!-- 基本信息 -->
                <div class="col-lg-6 mb-4">
                    <div class="card shadow">
                        <div class="card-header">
                            <h6 class="m-0 font-weight-bold text-primary">基本信息</h6>
                        </div>
                        <div class="card-body">
                            <form method="POST">
                                <div class="mb-3">
                                    <label for="username" class="form-label">用户名</label>
                                    <input type="text" class="form-control" id="username" value="<?php echo htmlspecialchars($user['username']); ?>" readonly>
                                    <div class="form-text">用户名不可修改</div>
                                </div>
                                <div class="mb-3">
                                    <label for="email" class="form-label">邮箱地址</label>
                                    <input type="email" class="form-control" id="email" name="email" value="<?php echo htmlspecialchars($user['email'] ?? ''); ?>" required>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">当前积分</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control" value="<?php echo $user['points']; ?>" readonly>
                                        <span class="input-group-text">分</span>
                                    </div>
                                </div>
                                <?php if ($user_group): ?>
                                <div class="mb-3">
                                    <label class="form-label">用户组</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control" value="<?php echo htmlspecialchars($user_group['display_name']); ?>" readonly>
                                        <span class="input-group-text">
                                            <?php if ($user_group['group_name'] === 'default'): ?>
                                                <i class="fas fa-user text-secondary"></i>
                                            <?php elseif ($user_group['group_name'] === 'vip'): ?>
                                                <i class="fas fa-crown text-info"></i>
                                            <?php elseif ($user_group['group_name'] === 'svip'): ?>
                                                <i class="fas fa-gem text-warning"></i>
                                            <?php endif; ?>
                                        </span>
                                    </div>
                                    <div class="form-text"><?php echo htmlspecialchars($user_group['description']); ?></div>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">组权限</label>
                                    <div class="list-group">
                                        <div class="list-group-item d-flex justify-content-between align-items-center">
                                            <span><i class="fas fa-coins text-primary me-2"></i>每条记录积分</span>
                                            <span class="badge bg-primary"><?php echo $required_points; ?> 分</span>
                                        </div>
                                        <div class="list-group-item d-flex justify-content-between align-items-center">
                                            <span><i class="fas fa-list text-success me-2"></i>DNS记录限制</span>
                                            <span class="badge bg-success">
                                                <?php if ($user_group['max_records'] == -1): ?>
                                                    无限制
                                                <?php else: ?>
                                                    <?php echo $current_record_count; ?> / <?php echo $user_group['max_records']; ?> 条
                                                <?php endif; ?>
                                            </span>
                                        </div>
                                        <div class="list-group-item d-flex justify-content-between align-items-center">
                                            <span><i class="fas fa-globe text-info me-2"></i>域名访问权限</span>
                                            <span class="badge bg-info">
                                                <?php if ($user_group['can_access_all_domains']): ?>
                                                    所有域名
                                                <?php else: ?>
                                                    <?php
                                                    $accessible_domains = getUserAccessibleDomains($_SESSION['user_id']);
                                                    echo count($accessible_domains) . ' 个域名';
                                                    ?>
                                                <?php endif; ?>
                                            </span>
                                        </div>
                                    </div>
                                </div>
                                <?php endif; ?>
                                <div class="mb-3">
                                    <label class="form-label">注册时间</label>
                                    <input type="text" class="form-control" value="<?php echo formatTime($user['created_at']); ?>" readonly>
                                </div>
                                <a href="change_email.php" class="btn btn-primary">
                                    <i class="fas fa-edit me-1"></i>更换邮箱
                                </a>
                            </form>
                        </div>
                    </div>
                </div>
                
                <!-- 密码修改 -->
                <div class="col-lg-6 mb-4">
                    <div class="card shadow">
                        <div class="card-header">
                            <h6 class="m-0 font-weight-bold text-primary">修改密码</h6>
                        </div>
                        <div class="card-body">
                            <?php if (!isset($_SESSION['password_change_step']) || $_SESSION['password_change_step'] !== 'verify'): ?>
                                <!-- 步骤1: 验证身份并发送验证码 -->
                                <form method="POST">
                                    <div class="mb-3">
                                        <label for="current_password" class="form-label">当前密码</label>
                                        <input type="password" class="form-control" id="current_password" name="current_password" required>
                                        <div class="form-text">请输入当前密码以验证身份</div>
                                    </div>
                                    <div class="mb-3">
                                        <label for="captcha_code" class="form-label">图形验证码</label>
                                        <div class="row">
                                            <div class="col-6">
                                                <input type="text" class="form-control" id="captcha_code" name="captcha_code" required placeholder="请输入验证码">
                                            </div>
                                            <div class="col-6">
                                                <img src="../captcha_image.php" alt="验证码" class="img-fluid border rounded" 
                                                     id="captcha_img" style="height: 38px; cursor: pointer;" 
                                                     onclick="refreshCaptcha()" title="点击刷新验证码">
                                            </div>
                                        </div>
                                        <small class="form-text text-muted">点击图片可刷新验证码</small>
                                    </div>
                                    <button type="submit" name="send_password_code" class="btn btn-primary">
                                        <i class="fas fa-paper-plane me-1"></i>发送邮箱验证码
                                    </button>
                                </form>
                            <?php else: ?>
                                <!-- 步骤2: 输入验证码并修改密码 -->
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    验证码已发送到您的邮箱，请查收并输入验证码
                                </div>
                                <form method="POST">
                                    <div class="mb-3">
                                        <label for="verification_code" class="form-label">邮箱验证码</label>
                                        <input type="text" class="form-control" id="verification_code" name="verification_code" 
                                               placeholder="请输入6位验证码" maxlength="6" required>
                                        <div class="form-text">验证码5分钟内有效</div>
                                    </div>
                                    <div class="mb-3">
                                        <label for="new_password" class="form-label">新密码</label>
                                        <input type="password" class="form-control" id="new_password" name="new_password" required>
                                        <div class="form-text">密码长度至少6个字符</div>
                                    </div>
                                    <div class="mb-3">
                                        <label for="confirm_password" class="form-label">确认新密码</label>
                                        <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
                                    </div>
                                    <div class="d-grid gap-2">
                                        <button type="submit" name="change_password" class="btn btn-success">
                                            <i class="fas fa-check me-1"></i>确认修改密码
                                        </button>
                                        <a href="profile.php" class="btn btn-outline-secondary">
                                            <i class="fas fa-arrow-left me-1"></i>重新发送验证码
                                        </a>
                                    </div>
                                </form>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- GitHub绑定 -->
            <?php if ($github_oauth_enabled && $github && $github->isConfigured()): ?>
            <div class="col-lg-12 mb-4">
                <div class="card shadow">
                    <div class="card-header">
                        <h6 class="m-0 font-weight-bold text-primary">
                            <i class="fab fa-github me-2"></i>GitHub账户绑定
                        </h6>
                    </div>
                    <div class="card-body">
                        <?php if (!empty($user['github_id']) && $user['oauth_provider'] === 'github'): ?>
                            <!-- 已绑定GitHub -->
                            <div class="d-flex align-items-center mb-3">
                                <?php if (!empty($user['avatar_url'])): ?>
                                    <img src="<?php echo htmlspecialchars($user['avatar_url']); ?>" 
                                         alt="GitHub头像" class="rounded-circle me-3" width="50" height="50">
                                <?php endif; ?>
                                <div>
                                    <h6 class="mb-1">
                                        <i class="fas fa-check-circle text-success me-1"></i>
                                        已绑定GitHub账户
                                    </h6>
                                    <p class="text-muted mb-0">
                                        GitHub用户名: <strong><?php echo htmlspecialchars($user['github_username'] ?? '未知'); ?></strong>
                                    </p>
                                    <small class="text-muted">
                                        GitHub ID: <?php echo htmlspecialchars($user['github_id']); ?>
                                    </small>
                                </div>
                            </div>
                            <div class="alert alert-info">
                                <i class="fas fa-info-circle me-1"></i>
                                您的账户已与GitHub绑定，可以使用GitHub账户快速登录。
                            </div>
                            <form method="POST" onsubmit="return confirm('确定要解绑GitHub账户吗？解绑后将无法使用GitHub登录。');">
                                <button type="submit" name="unbind_github" class="btn btn-outline-danger">
                                    <i class="fab fa-github me-1"></i>解绑GitHub账户
                                </button>
                            </form>
                        <?php else: ?>
                            <!-- 未绑定GitHub -->
                            <div class="text-center py-3">
                                <i class="fab fa-github fa-3x text-muted mb-3"></i>
                                <h6>未绑定GitHub账户</h6>
                                <p class="text-muted mb-3">
                                    绑定GitHub账户后，您可以使用GitHub账户快速登录，无需记住密码。
                                </p>
                                <div class="alert alert-warning">
                                    <i class="fas fa-exclamation-triangle me-1"></i>
                                    <strong>注意：</strong>绑定GitHub账户时，请确保您的GitHub邮箱与当前账户邮箱一致，或者GitHub账户有已验证的邮箱。
                                </div>
                                <a href="<?php echo htmlspecialchars($github->getAuthUrl()); ?>" class="btn btn-dark">
                                    <i class="fab fa-github me-1"></i>绑定GitHub账户
                                </a>
                            </div>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
            <?php endif; ?>
            </div>
            
            <!-- 使用统计 -->
            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">使用统计</h6>
                </div>
                <div class="card-body">
                    <?php
                    $stats = $db->querySingle("
                        SELECT 
                            COUNT(*) as total_records,
                            COUNT(CASE WHEN type = 'A' THEN 1 END) as a_records,
                            COUNT(CASE WHEN type = 'CNAME' THEN 1 END) as cname_records,
                            COUNT(CASE WHEN proxied = 1 THEN 1 END) as proxied_records,
                            MIN(created_at) as first_record,
                            MAX(created_at) as last_record
                        FROM dns_records 
                        WHERE user_id = {$_SESSION['user_id']}
                    ", true);
                    ?>
                    <div class="row">
                        <div class="col-md-3 text-center">
                            <h4 class="text-primary"><?php echo $stats['total_records'] ?? 0; ?></h4>
                            <p class="text-muted">总DNS记录</p>
                        </div>
                        <div class="col-md-3 text-center">
                            <h4 class="text-success"><?php echo $stats['a_records'] ?? 0; ?></h4>
                            <p class="text-muted">A记录</p>
                        </div>
                        <div class="col-md-3 text-center">
                            <h4 class="text-info"><?php echo $stats['cname_records'] ?? 0; ?></h4>
                            <p class="text-muted">CNAME记录</p>
                        </div>
                        <div class="col-md-3 text-center">
                            <h4 class="text-warning"><?php echo $stats['proxied_records'] ?? 0; ?></h4>
                            <p class="text-muted">已代理记录</p>
                        </div>
                    </div>
                    
                    <?php if ($stats['first_record']): ?>
                    <hr>
                    <div class="row">
                        <div class="col-md-6">
                            <strong>首次添加记录：</strong>
                            <span class="text-muted"><?php echo formatTime($stats['first_record']); ?></span>
                        </div>
                        <div class="col-md-6">
                            <strong>最近添加记录：</strong>
                            <span class="text-muted"><?php echo formatTime($stats['last_record']); ?></span>
                        </div>
                    </div>
                    <?php endif; ?>
                </div>
            </div>
            </div>
        </main>
    </div>
</div>

<script>
// 刷新验证码
function refreshCaptcha() {
    const captchaImg = document.getElementById('captcha_img');
    if (captchaImg) {
        captchaImg.src = '../captcha_image.php?' + Math.random();
    }
}

// 清除密码修改步骤（当用户点击重新发送验证码时）
<?php if (isset($_GET['reset']) && $_GET['reset'] === 'password'): ?>
    <?php unset($_SESSION['password_change_step']); ?>
    window.location.href = 'profile.php';
<?php endif; ?>
</script>
<?php include 'includes/footer.php'; ?>