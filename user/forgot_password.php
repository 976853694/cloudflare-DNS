<?php
/**
 * 忘记密码页面
 */
session_start();
require_once '../config/database.php';
require_once '../config/smtp.php';
require_once '../includes/functions.php';

$messages = [];
$step = isset($_GET['step']) ? $_GET['step'] : 'email';

// 处理发送重置邮件
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['send_reset'])) {
    $email = trim($_POST['email']);
    
    if (empty($email)) {
        $messages['error'] = '邮箱地址不能为空';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $messages['error'] = '邮箱格式不正确';
    } else {
        // 检查邮箱是否存在
        $db = Database::getInstance()->getConnection();
        $user = $db->querySingle("SELECT id, username FROM users WHERE email = '$email'", true);
        
        if (!$user) {
            $messages['error'] = '该邮箱未注册';
        } else {
            // 发送重置邮件
            try {
                $emailService = new EmailService();
                $emailService->sendPasswordReset($email, $user['username'], $user['id']);
                $_SESSION['reset_email'] = $email;
                $_SESSION['reset_user_id'] = $user['id'];
                $messages['success'] = '密码重置邮件已发送，请查收';
                $step = 'verify';
            } catch (Exception $e) {
                $messages['error'] = '邮件发送失败：' . $e->getMessage();
                error_log("Password reset failed for $email: " . $e->getMessage());
            }
        }
    }
}

// 处理密码重置
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['reset_password'])) {
    $code = trim($_POST['code']);
    $password = trim($_POST['password']);
    $confirm_password = trim($_POST['confirm_password']);
    
    if (empty($code) || empty($password) || empty($confirm_password)) {
        $messages['error'] = '所有字段都必须填写';
    } elseif ($password !== $confirm_password) {
        $messages['error'] = '两次输入的密码不一致';
    } elseif (strlen($password) < 6) {
        $messages['error'] = '密码长度至少6位';
    } else {
        $emailService = new EmailService();
        $verification = $emailService->verifyCode($_SESSION['reset_email'], $code, 'password_reset');
        
        if ($verification['valid']) {
            // 更新密码
            $db = Database::getInstance()->getConnection();
            $hashed_password = password_hash($password, PASSWORD_DEFAULT);
            
            $stmt = $db->prepare("UPDATE users SET password = ? WHERE id = ?");
            $stmt->bindValue(1, $hashed_password, SQLITE3_TEXT);
            $stmt->bindValue(2, $_SESSION['reset_user_id'], SQLITE3_INTEGER);
            
            if ($stmt->execute()) {
                // 发送密码修改通知
                $user = $db->querySingle("SELECT username FROM users WHERE id = {$_SESSION['reset_user_id']}", true);
                $emailService->sendPasswordChangeNotification($_SESSION['reset_email'], $user['username']);
                
                // 清除会话数据
                unset($_SESSION['reset_email']);
                unset($_SESSION['reset_user_id']);
                
                $messages['success'] = '密码重置成功！请使用新密码登录';
                $step = 'success';
            } else {
                $messages['error'] = '密码重置失败，请重试';
            }
        } else {
            $messages['error'] = '验证码错误或已过期';
        }
    }
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>找回密码 - <?php echo getSetting('site_name', 'DNS管理系统'); ?></title>
    <link href="../assets/css/bootstrap.min.css" rel="stylesheet">
    <link href="../assets/css/fontawesome.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            padding: 20px 0;
        }
        .reset-card {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
            max-width: 500px;
            margin: 0 auto;
        }
        .reset-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        .reset-header h3 {
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .reset-body {
            padding: 2.5rem 2rem;
        }
        .form-control {
            padding: 0.75rem;
            border-radius: 8px;
            border: 1px solid #dee2e6;
            transition: all 0.3s;
        }
        .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            padding: 0.75rem;
            font-size: 1.1rem;
            font-weight: 500;
            border-radius: 8px;
            transition: all 0.3s;
        }
        .btn-primary:hover {
            background: linear-gradient(135deg, #5568d3 0%, #63408b 100%);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        .btn-success {
            border-radius: 8px;
            padding: 0.75rem;
            font-size: 1.1rem;
            font-weight: 500;
            transition: all 0.3s;
        }
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(40, 167, 69, 0.4);
        }
        .btn-link {
            color: #667eea;
            text-decoration: none;
            transition: all 0.3s;
        }
        .btn-link:hover {
            color: #5568d3;
            text-decoration: underline;
        }
        .alert {
            border-radius: 8px;
            border: none;
        }
        .icon-container {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.5rem;
        }
        .icon-container i {
            font-size: 3rem;
            color: white;
        }
        .success-icon {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.5rem;
            animation: successPulse 1.5s ease-in-out infinite;
        }
        .success-icon i {
            font-size: 3rem;
            color: white;
        }
        @keyframes successPulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(40, 167, 69, 0.4); }
            50% { transform: scale(1.05); box-shadow: 0 0 0 20px rgba(40, 167, 69, 0); }
        }
        @media (max-width: 576px) {
            .reset-body {
                padding: 1.5rem 1rem;
            }
            .reset-header {
                padding: 1.5rem 1rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-7 col-lg-6">
                <div class="reset-card">
                    <?php if ($step !== 'success'): ?>
                    <div class="reset-header">
                        <h3 class="mb-0"><?php echo getSetting('site_name', 'DNS管理系统'); ?></h3>
                        <p class="mb-0 mt-2">密码找回服务</p>
                    </div>
                    <?php endif; ?>
                    
                    <div class="reset-body">
                        <!-- 消息提示 -->
                        <?php if (!empty($messages)): ?>
                            <?php foreach ($messages as $type => $message): ?>
                                <div class="alert alert-<?php echo $type; ?> alert-dismissible fade show" role="alert">
                                    <i class="fas fa-<?php echo $type === 'error' ? 'exclamation-circle' : 'check-circle'; ?> me-2"></i>
                                    <?php echo htmlspecialchars($message); ?>
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            <?php endforeach; ?>
                        <?php endif; ?>
                        
                        <?php if ($step === 'email'): ?>
                            <!-- 步骤1: 输入邮箱 -->
                            <div class="text-center mb-4">
                                <div class="icon-container">
                                    <i class="fas fa-key"></i>
                                </div>
                                <h4 class="text-primary mb-2">找回密码</h4>
                                <p class="text-muted">请输入您注册时使用的邮箱地址</p>
                            </div>
                            
                            <form method="POST">
                                <div class="mb-3">
                                    <label for="email" class="form-label">
                                        <i class="fas fa-envelope me-1"></i>邮箱地址
                                    </label>
                                    <input type="email" class="form-control" id="email" name="email" 
                                           value="<?php echo isset($_POST['email']) ? htmlspecialchars($_POST['email']) : ''; ?>" 
                                           placeholder="your@email.com" required autofocus>
                                    <div class="form-text">
                                        <i class="fas fa-info-circle me-1"></i>我们将向此邮箱发送验证码
                                    </div>
                                </div>
                                
                                <div class="d-grid mt-4">
                                    <button type="submit" name="send_reset" class="btn btn-primary btn-lg">
                                        <i class="fas fa-paper-plane me-2"></i>发送验证码
                                    </button>
                                </div>
                            </form>
                            
                        <?php elseif ($step === 'verify'): ?>
                            <!-- 步骤2: 验证并重置密码 -->
                            <div class="text-center mb-4">
                                <div class="icon-container">
                                    <i class="fas fa-shield-alt"></i>
                                </div>
                                <h4 class="text-primary mb-2">重置密码</h4>
                                <p class="text-muted">请输入验证码并设置新密码</p>
                            </div>
                            
                            <div class="alert alert-info mb-4">
                                <i class="fas fa-info-circle me-2"></i>
                                验证码已发送到: <strong><?php echo htmlspecialchars($_SESSION['reset_email']); ?></strong>
                            </div>
                            
                            <form method="POST">
                                <div class="mb-3">
                                    <label for="code" class="form-label">
                                        <i class="fas fa-key me-1"></i>验证码
                                    </label>
                                    <input type="text" class="form-control" id="code" name="code" 
                                           placeholder="请输入6位验证码" maxlength="6" required autofocus>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="password" class="form-label">
                                        <i class="fas fa-lock me-1"></i>新密码
                                    </label>
                                    <input type="password" class="form-control" id="password" name="password" 
                                           placeholder="至少6位字符" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="confirm_password" class="form-label">
                                        <i class="fas fa-lock me-1"></i>确认新密码
                                    </label>
                                    <input type="password" class="form-control" id="confirm_password" name="confirm_password" 
                                           placeholder="再次输入新密码" required>
                                </div>
                                
                                <div class="d-grid mt-4">
                                    <button type="submit" name="reset_password" class="btn btn-success btn-lg">
                                        <i class="fas fa-check me-2"></i>重置密码
                                    </button>
                                </div>
                            </form>
                            
                            <div class="text-center mt-3">
                                <a href="?step=email" class="btn btn-link">
                                    <i class="fas fa-arrow-left me-1"></i>重新发送验证码
                                </a>
                            </div>
                            
                        <?php else: ?>
                            <!-- 步骤3: 重置成功 -->
                            <div class="text-center">
                                <div class="success-icon">
                                    <i class="fas fa-check"></i>
                                </div>
                                <h4 class="text-success mb-3">密码重置成功！</h4>
                                <p class="text-muted mb-4">
                                    您的密码已成功重置<br>
                                    请使用新密码登录您的账户
                                </p>
                                <div class="d-grid">
                                    <a href="login.php" class="btn btn-primary btn-lg">
                                        <i class="fas fa-sign-in-alt me-2"></i>立即登录
                                    </a>
                                </div>
                            </div>
                        <?php endif; ?>
                        
                        <div class="text-center mt-4 pt-3 border-top">
                            <small class="text-muted">
                                <?php if ($step !== 'success'): ?>
                                记起密码了？ <a href="login.php" class="text-decoration-none fw-bold">立即登录</a>
                                <?php if ($step === 'email'): ?>
                                 | <a href="register_verify.php" class="text-decoration-none fw-bold">注册账户</a>
                                <?php endif; ?>
                                <?php endif; ?>
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="../assets/js/bootstrap.bundle.min.js"></script>
</body>
</html>