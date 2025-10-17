<?php
/**
 * 用户注册验证页面
 */
session_start();
require_once '../config/database.php';
require_once '../config/smtp.php';
require_once '../includes/functions.php';

$messages = [];
$step = isset($_GET['step']) ? $_GET['step'] : 'email';

// 处理发送验证码
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['send_code'])) {
    $email = trim($_POST['email']);
    $username = trim($_POST['username']);
    
    if (empty($email) || empty($username)) {
        $messages['error'] = '邮箱和用户名不能为空';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $messages['error'] = '邮箱格式不正确';
    } else {
        // 检查用户名和邮箱是否已注册
        $db = Database::getInstance()->getConnection();
        $username_exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE username = '$username'");
        $email_exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE email = '$email'");
        
        if ($username_exists > 0) {
            $messages['error'] = '该用户名已被注册，请更换用户名';
        } elseif ($email_exists > 0) {
            $messages['error'] = '该邮箱已被注册';
        } else {
            // 发送验证码
            try {
                $emailService = new EmailService();
                $emailService->sendRegistrationVerification($email, $username);
                $_SESSION['registration_email'] = $email;
                $_SESSION['registration_username'] = $username;
                $messages['success'] = '验证码已发送到您的邮箱，请查收';
                $step = 'verify';
            } catch (Exception $e) {
                $messages['error'] = '验证码发送失败：' . $e->getMessage();
                error_log("Registration verification failed for $email: " . $e->getMessage());
            }
        }
    }
}

// 处理验证码验证
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['verify_code'])) {
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
        $verification = $emailService->verifyCode($_SESSION['registration_email'], $code, 'registration');
        
        if ($verification['valid']) {
            // 再次检查用户名和邮箱是否已存在（避免并发注册）
            $db = Database::getInstance()->getConnection();
            
            $username_exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE username = '{$_SESSION['registration_username']}'");
            $email_exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE email = '{$_SESSION['registration_email']}'");
            
            if ($username_exists > 0) {
                $messages['error'] = '该用户名已被注册，请重新选择';
            } elseif ($email_exists > 0) {
                $messages['error'] = '该邮箱已被注册';
            } else {
                // 创建用户账户
                $hashed_password = password_hash($password, PASSWORD_DEFAULT);
                
                $stmt = $db->prepare("INSERT INTO users (username, email, password, credits, created_at) VALUES (?, ?, ?, 100, datetime('now'))");
                $stmt->bindValue(1, $_SESSION['registration_username'], SQLITE3_TEXT);
                $stmt->bindValue(2, $_SESSION['registration_email'], SQLITE3_TEXT);
                $stmt->bindValue(3, $hashed_password, SQLITE3_TEXT);
                
                if ($stmt->execute()) {
                // 清除会话数据
                unset($_SESSION['registration_email']);
                unset($_SESSION['registration_username']);
                
                    $messages['success'] = '注册成功！您已获得100积分，请登录您的账户';
                    $step = 'success';
                } else {
                    $messages['error'] = '注册失败，请重试';
                }
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
    <title>用户注册 - <?php echo getSetting('site_name', 'DNS管理系统'); ?></title>
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
        .register-card {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
            max-width: 550px;
            margin: 0 auto;
        }
        .register-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        .register-header h3 {
            font-size: 1.8rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        .step-indicator {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 1.5rem;
            border-bottom: 3px solid rgba(255, 255, 255, 0.2);
        }
        .step-container {
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
        }
        .step {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
            z-index: 2;
        }
        .step-circle {
            width: 45px;
            height: 45px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 1.2rem;
            transition: all 0.3s;
            border: 3px solid transparent;
        }
        .step.active .step-circle {
            background: white;
            color: #667eea;
            border-color: white;
            box-shadow: 0 4px 15px rgba(255, 255, 255, 0.4);
            transform: scale(1.1);
        }
        .step.completed .step-circle {
            background: #28a745;
            border-color: #28a745;
        }
        .step-label {
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.75rem;
            margin-top: 0.5rem;
            font-weight: 500;
        }
        .step.active .step-label {
            color: white;
            font-weight: 600;
        }
        .step-line {
            position: absolute;
            top: 22px;
            height: 3px;
            background: rgba(255, 255, 255, 0.3);
            z-index: 1;
        }
        .step-line.line-1 {
            left: calc(33.33% + 22px);
            width: calc(33.33% - 44px);
        }
        .step-line.line-2 {
            left: calc(66.66% + 22px);
            width: calc(33.33% - 44px);
        }
        .step-line.completed {
            background: #28a745;
        }
        .register-body {
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
            .register-body {
                padding: 1.5rem 1rem;
            }
            .register-header {
                padding: 1.5rem 1rem;
            }
            .step-indicator {
                padding: 1rem;
            }
            .step-circle {
                width: 35px;
                height: 35px;
                font-size: 1rem;
            }
            .step-label {
                font-size: 0.7rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-8 col-lg-7">
                <div class="register-card">
                    <!-- 步骤指示器 -->
                    <div class="step-indicator">
                        <div class="step-container">
                            <div class="step <?php echo ($step === 'email') ? 'active' : (in_array($step, ['verify', 'success']) ? 'completed' : ''); ?>" style="width: 33.33%;">
                                <div class="step-circle">
                                    <?php if (in_array($step, ['verify', 'success'])): ?>
                                        <i class="fas fa-check"></i>
                                    <?php else: ?>
                                        1
                                    <?php endif; ?>
                                </div>
                                <div class="step-label">填写信息</div>
                            </div>
                            
                            <div class="step <?php echo ($step === 'verify') ? 'active' : ($step === 'success' ? 'completed' : ''); ?>" style="width: 33.33%;">
                                <div class="step-circle">
                                    <?php if ($step === 'success'): ?>
                                        <i class="fas fa-check"></i>
                                    <?php else: ?>
                                        2
                                    <?php endif; ?>
                                </div>
                                <div class="step-label">验证邮箱</div>
                            </div>
                            
                            <div class="step <?php echo ($step === 'success') ? 'active' : ''; ?>" style="width: 33.33%;">
                                <div class="step-circle">3</div>
                                <div class="step-label">完成注册</div>
                            </div>
                            
                            <div class="step-line line-1 <?php echo in_array($step, ['verify', 'success']) ? 'completed' : ''; ?>"></div>
                            <div class="step-line line-2 <?php echo $step === 'success' ? 'completed' : ''; ?>"></div>
                        </div>
                    </div>
                    
                    <div class="register-body">
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
                                <h4 class="text-primary mb-2">
                                    <i class="fas fa-user-plus me-2"></i>创建新账户
                                </h4>
                                <p class="text-muted">请填写您的注册信息</p>
                            </div>
                            
                            <form method="POST">
                                <div class="mb-3">
                                    <label for="username" class="form-label">
                                        <i class="fas fa-user me-1"></i>用户名
                                    </label>
                                    <input type="text" class="form-control" id="username" name="username" 
                                           value="<?php echo isset($_POST['username']) ? htmlspecialchars($_POST['username']) : ''; ?>" 
                                           placeholder="请输入用户名" required autofocus>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="email" class="form-label">
                                        <i class="fas fa-envelope me-1"></i>邮箱地址
                                    </label>
                                    <input type="email" class="form-control" id="email" name="email" 
                                           value="<?php echo isset($_POST['email']) ? htmlspecialchars($_POST['email']) : ''; ?>" 
                                           placeholder="请输入邮箱地址" required>
                                    <div class="form-text">
                                        <i class="fas fa-info-circle me-1"></i>我们将向此邮箱发送验证码
                                    </div>
                                </div>
                                
                                <div class="d-grid mt-4">
                                    <button type="submit" name="send_code" class="btn btn-primary btn-lg">
                                        <i class="fas fa-paper-plane me-2"></i>发送验证码
                                    </button>
                                </div>
                            </form>
                            
                        <?php elseif ($step === 'verify'): ?>
                            <!-- 步骤2: 验证邮箱 -->
                            <div class="text-center mb-4">
                                <h4 class="text-primary mb-2">
                                    <i class="fas fa-envelope-open-text me-2"></i>验证邮箱
                                </h4>
                                <p class="text-muted">请查收验证码并设置密码</p>
                            </div>
                            
                            <div class="alert alert-info mb-4">
                                <i class="fas fa-info-circle me-2"></i>
                                验证码已发送到: <strong><?php echo htmlspecialchars($_SESSION['registration_email']); ?></strong>
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
                                        <i class="fas fa-lock me-1"></i>设置密码
                                    </label>
                                    <input type="password" class="form-control" id="password" name="password" 
                                           placeholder="至少6位字符" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="confirm_password" class="form-label">
                                        <i class="fas fa-lock me-1"></i>确认密码
                                    </label>
                                    <input type="password" class="form-control" id="confirm_password" name="confirm_password" 
                                           placeholder="再次输入密码" required>
                                </div>
                                
                                <div class="d-grid mt-4">
                                    <button type="submit" name="verify_code" class="btn btn-success btn-lg">
                                        <i class="fas fa-check me-2"></i>完成注册
                                    </button>
                                </div>
                            </form>
                            
                            <div class="text-center mt-3">
                                <a href="?step=email" class="btn btn-link">
                                    <i class="fas fa-arrow-left me-1"></i>重新发送验证码
                                </a>
                            </div>
                            
                        <?php else: ?>
                            <!-- 步骤3: 注册成功 -->
                            <div class="text-center">
                                <div class="success-icon">
                                    <i class="fas fa-check"></i>
                                </div>
                                <h4 class="text-success mb-3">注册成功！</h4>
                                <p class="text-muted mb-4">
                                    恭喜您成功注册 <?php echo getSetting('site_name', 'DNS管理系统'); ?>！<br>
                                    您已获得 <strong class="text-success">100积分</strong> 的新用户奖励。
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
                                已有账户？ <a href="login.php" class="text-decoration-none fw-bold">立即登录</a>
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