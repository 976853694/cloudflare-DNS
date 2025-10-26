<?php
session_start();

// 检查是否已安装
if (!file_exists('../data/install.lock')) {
    header('Location: ../install.php');
    exit;
}

require_once '../config/database.php';
require_once '../config/smtp.php';
require_once '../includes/functions.php';
require_once '../includes/captcha.php';

// 检查用户是否登录
checkUserLogin();

$messages = [];
$step = isset($_SESSION['email_change_step']) ? $_SESSION['email_change_step'] : 'request';

$db = Database::getInstance()->getConnection();
$user_id = $_SESSION['user_id'];

// 获取当前用户信息
$stmt = $db->prepare("SELECT * FROM users WHERE id = ?");
$stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
$result = $stmt->execute();
$user = $result->fetchArray(SQLITE3_ASSOC);

// 处理发送当前邮箱验证码
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['send_current_verification'])) {
    $password = getPost('password');
    $captcha_code = getPost('captcha_code');
    
    $captcha = new Captcha();
    
    if (!$password || !$captcha_code) {
        $messages['error'] = '请填写完整信息';
    } elseif (!$captcha->verify($captcha_code)) {
        $messages['error'] = '验证码错误或已过期';
    } elseif (!password_verify($password, $user['password'])) {
        $messages['error'] = '当前密码错误';
    } elseif (empty($user['email'])) {
        $messages['error'] = '您的账户未绑定邮箱，无法进行邮箱更换';
    } else {
        // 发送当前邮箱验证码
        try {
            // 启用输出缓冲，防止调试信息显示到页面
            ob_start();
            $emailService = new EmailService();
            $emailService->sendPasswordReset($user['email'], $user['username'], $user_id);
            ob_end_clean();
            $_SESSION['email_change_step'] = 'verify_current';
            $messages['success'] = '验证码已发送到当前邮箱，请查收';
            $step = 'verify_current';
        } catch (Exception $e) {
            ob_end_clean();
            $messages['error'] = '验证码发送失败：' . $e->getMessage();
            error_log("Email change current verification failed for user $user_id: " . $e->getMessage());
        }
    }
}

// 处理当前邮箱验证
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['verify_current_email'])) {
    $current_code = trim($_POST['current_code']);
    $new_email = getPost('new_email');
    
    if (empty($current_code) || empty($new_email)) {
        $messages['error'] = '请填写完整信息';
    } elseif (!isValidEmail($new_email)) {
        $messages['error'] = '请输入有效的邮箱地址';
    } elseif ($new_email === $user['email']) {
        $messages['error'] = '新邮箱不能与当前邮箱相同';
    } else {
        // 验证当前邮箱验证码
        $emailService = new EmailService();
        $verification = $emailService->verifyCode($user['email'], $current_code, 'password_reset');
        
        if ($verification['valid'] && $verification['user_id'] == $user_id) {
            // 检查新邮箱是否已被使用
            $exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE email = '$new_email' AND id != $user_id");
            if ($exists) {
                $messages['error'] = '该邮箱已被其他用户使用';
            } else {
                // 验证通过，发送新邮箱验证码
                ob_start();
                if ($emailService->sendEmailChangeVerification($new_email, $user['username'], $user_id)) {
                    ob_end_clean();
                    $_SESSION['new_email'] = $new_email;
                    $_SESSION['email_change_step'] = 'verify_new';
                    $messages['success'] = '验证码已发送到新邮箱，请查收';
                    $step = 'verify_new';
                } else {
                    ob_end_clean();
                    $messages['error'] = '验证邮件发送失败，请重试';
                }
            }
        } else {
            $messages['error'] = '当前邮箱验证码错误或已过期';
        }
    }
}

// 处理发送新邮箱验证码（原有功能保留但重命名）
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['send_verification'])) {
    // 这个功能现在不再直接使用，而是通过verify_current_email处理
    redirect('change_email.php');
}

// 处理新邮箱验证（最终步骤）
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['verify_new_email'])) {
    $new_code = trim($_POST['new_code']);
    
    if (empty($new_code)) {
        $messages['error'] = '请输入验证码';
    } else {
        $emailService = new EmailService();
        $verification = $emailService->verifyCode($_SESSION['new_email'], $new_code, 'email_change');
        
        if ($verification['valid'] && $verification['user_id'] == $user_id) {
            // 更新邮箱
            $old_email = $user['email'];
            $new_email = $_SESSION['new_email'];
            
            $stmt = $db->prepare("UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
            $stmt->bindValue(1, $new_email, SQLITE3_TEXT);
            $stmt->bindValue(2, $user_id, SQLITE3_INTEGER);
            
            if ($stmt->execute()) {
                // 更新session中的邮箱
                $_SESSION['user_email'] = $new_email;
                
                // 清除临时数据
                unset($_SESSION['new_email']);
                unset($_SESSION['email_change_step']);
                
                logAction('user', $user_id, 'change_email', "邮箱从 {$old_email} 更换为 {$new_email}");
                $messages['success'] = '邮箱更换成功！';
                $step = 'success';
                
                // 重新获取用户信息
                $stmt = $db->prepare("SELECT * FROM users WHERE id = ?");
                $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
                $result = $stmt->execute();
                $user = $result->fetchArray(SQLITE3_ASSOC);
            } else {
                $messages['error'] = '邮箱更换失败，请重试';
            }
        } else {
            $messages['error'] = '验证码错误或已过期';
        }
    }
}

$page_title = '更换邮箱';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">更换邮箱</h1>
            </div>
            
            <div class="row justify-content-center">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0">更换邮箱地址</h5>
                        </div>
                        <div class="card-body">
                            <!-- 消息提示 -->
                            <?php if (!empty($messages)): ?>
                                <?php foreach ($messages as $type => $message): ?>
                                    <div class="alert alert-<?php echo $type; ?> alert-dismissible fade show" role="alert">
                                        <?php echo htmlspecialchars($message); ?>
                                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                    </div>
                                <?php endforeach; ?>
                            <?php endif; ?>
                            
                            <div class="mb-3">
                                <label class="form-label">当前邮箱</label>
                                <input type="text" class="form-control" value="<?php echo htmlspecialchars($user['email'] ?? '未设置'); ?>" readonly>
                            </div>
                            
                            <?php if ($step === 'request'): ?>
                                <!-- 步骤1: 验证当前邮箱 -->
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    为了安全，我们需要先验证您当前的邮箱地址
                                </div>
                                <form method="POST">
                                    <div class="mb-3">
                                        <label for="password" class="form-label">当前密码</label>
                                        <input type="password" class="form-control" id="password" name="password" required placeholder="请输入当前密码">
                                        <div class="form-text">验证您的身份</div>
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
                                    <div class="d-grid">
                                        <button type="submit" name="send_current_verification" class="btn btn-primary">
                                            <i class="fas fa-paper-plane me-1"></i>发送验证码到当前邮箱
                                        </button>
                                    </div>
                                </form>
                                
                            <?php elseif ($step === 'verify_current'): ?>
                                <!-- 步骤2: 验证当前邮箱并输入新邮箱 -->
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    验证码已发送到: <strong><?php echo htmlspecialchars($user['email']); ?></strong>
                                </div>
                                <form method="POST">
                                    <div class="mb-3">
                                        <label for="current_code" class="form-label">当前邮箱验证码</label>
                                        <input type="text" class="form-control" id="current_code" name="current_code" 
                                               placeholder="请输入6位验证码" maxlength="6" required>
                                        <div class="form-text">请查收当前邮箱中的验证码</div>
                                    </div>
                                    <div class="mb-3">
                                        <label for="new_email" class="form-label">新邮箱地址</label>
                                        <input type="email" class="form-control" id="new_email" name="new_email" required placeholder="请输入新的邮箱地址">
                                        <div class="form-text">验证当前邮箱后，将向新邮箱发送验证码</div>
                                    </div>
                                    <div class="d-grid gap-2">
                                        <button type="submit" name="verify_current_email" class="btn btn-success">
                                            <i class="fas fa-check me-1"></i>验证并发送新邮箱验证码
                                        </button>
                                        <a href="change_email.php" class="btn btn-outline-secondary">
                                            <i class="fas fa-arrow-left me-1"></i>重新发送验证码
                                        </a>
                                    </div>
                                </form>
                                
                            <?php elseif ($step === 'verify_new'): ?>
                                <!-- 步骤3: 验证新邮箱 -->
                                <div class="alert alert-success">
                                    <i class="fas fa-check-circle me-2"></i>
                                    当前邮箱验证成功！验证码已发送到新邮箱: <strong><?php echo htmlspecialchars($_SESSION['new_email']); ?></strong>
                                </div>
                                
                                <form method="POST">
                                    <div class="mb-3">
                                        <label for="new_code" class="form-label">新邮箱验证码</label>
                                        <input type="text" class="form-control" id="new_code" name="new_code" 
                                               placeholder="请输入6位验证码" maxlength="6" required>
                                        <div class="form-text">请查收新邮箱中的验证码，验证码5分钟内有效</div>
                                    </div>
                                    <div class="d-grid gap-2">
                                        <button type="submit" name="verify_new_email" class="btn btn-success">
                                            <i class="fas fa-check me-1"></i>完成邮箱更换
                                        </button>
                                        <a href="change_email.php" class="btn btn-outline-secondary">
                                            <i class="fas fa-redo me-1"></i>重新开始验证
                                        </a>
                                    </div>
                                </form>
                                
                            <?php else: ?>
                                <!-- 步骤3: 更换成功 -->
                                <div class="text-center">
                                    <div class="mb-4">
                                        <i class="fas fa-check-circle text-success" style="font-size: 3rem;"></i>
                                    </div>
                                    <h5 class="text-success mb-3">邮箱更换成功！</h5>
                                    <p class="text-muted mb-4">
                                        您的邮箱已成功更换为: <br>
                                        <strong><?php echo htmlspecialchars($user['email']); ?></strong>
                                    </p>
                                    <a href="profile.php" class="btn btn-primary">
                                        <i class="fas fa-user me-1"></i>返回个人资料
                                    </a>
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
    // 刷新验证码
    function refreshCaptcha() {
        document.getElementById('captcha_img').src = '../captcha_image.php?t=' + new Date().getTime();
    }
    
    // 页面加载时初始化验证码
    document.addEventListener('DOMContentLoaded', function() {
        refreshCaptcha();
    });
</script>

<?php include 'includes/footer.php'; ?>