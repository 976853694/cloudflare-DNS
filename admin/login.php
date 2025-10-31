<?php
session_start();

// 检查是否已安装
if (!file_exists('../data/install.lock')) {
    header('Location: ../install.php');
    exit;
}

require_once '../config/database.php';
require_once '../includes/functions.php';
require_once '../includes/captcha.php';
require_once '../includes/security.php';

// 如果已经登录，重定向到仪表板
if (isset($_SESSION['admin_logged_in'])) {
    redirect('dashboard.php');
}

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = getPost('username');
    $password = getPost('password');
    $captcha_code = getPost('captcha_code');
    $admin_ip = $_SERVER['REMOTE_ADDR'] ?? '';
    
    $captcha = new Captcha();
    
    // 检查IP是否被锁定
    if (Security::isIpLocked($admin_ip, 'admin')) {
        $remaining_time = Security::getRemainingLockTime($admin_ip, 'admin');
        $error = '登录失败次数过多，IP已被锁定。请在 ' . Security::formatRemainingTime($remaining_time) . ' 后重试';
    } elseif (!$username || !$password || !$captcha_code) {
        $error = '请填写完整信息';
    } elseif (!$captcha->verify($captcha_code)) {
        $error = '验证码错误或已过期';
    } elseif ($username && $password) {
        $db = Database::getInstance()->getConnection();
        $stmt = $db->prepare("SELECT * FROM admins WHERE username = ?");
        $stmt->bindValue(1, $username, SQLITE3_TEXT);
        $result = $stmt->execute();
        $admin = $result->fetchArray(SQLITE3_ASSOC);
        
        if ($admin && password_verify($password, $admin['password'])) {
            // 登录成功，清除失败记录
            Security::clearFailedAttempts($admin_ip, 'admin');
            
            $_SESSION['admin_logged_in'] = true;
            $_SESSION['admin_id'] = $admin['id'];
            $_SESSION['admin_username'] = $admin['username'];
            
            logAction('admin', $admin['id'], 'login', '管理员登录');
            redirect('dashboard.php');
        } else {
            // 登录失败，记录失败尝试
            Security::recordFailedLogin($admin_ip, $username, 'admin');
            $error = '用户名或密码错误';
        }
    } else {
        $error = '请填写完整信息';
    }
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>管理员登录 - <?php echo getSetting('site_name', 'DNS管理系统'); ?></title>
    <link href="../assets/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #0d6efd 0%, #0056b3 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }
        .login-container {
            background: white;
            border-radius: 10px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        .login-header {
            background: linear-gradient(135deg, #0d6efd 0%, #0056b3 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        .login-body {
            padding: 2rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-6 col-lg-4">
                <div class="login-container">
                    <div class="login-header">
                        <h3 class="mb-0">管理员登录</h3>
                        <p class="mb-0 mt-2">DNS管理系统后台</p>
                    </div>
                    <div class="login-body">
                        <?php if ($error): ?>
                            <div class="alert alert-danger"><?php echo htmlspecialchars($error); ?></div>
                        <?php endif; ?>
                        
                        <form method="POST">
                            <div class="mb-3">
                                <label for="username" class="form-label">用户名</label>
                                <input type="text" class="form-control" id="username" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">密码</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <div class="mb-3">
                                <label for="captcha_code" class="form-label">验证码</label>
                                <div class="row">
                                    <div class="col-6">
                                        <input type="text" class="form-control" id="captcha_code" name="captcha_code" required placeholder="请输入验证码">
                                    </div>
                                    <div class="col-6">
                                        <img src="../captcha_image.php" alt="验证码" class="img-fluid border rounded" 
                                             id="admin_captcha_img" style="height: 38px; cursor: pointer;" 
                                             onclick="refreshCaptcha()" title="点击刷新验证码">
                                    </div>
                                </div>
                                <small class="form-text text-muted">点击图片可刷新验证码</small>
                            </div>
                            <div class="d-grid">
                                <button type="submit" class="btn btn-primary btn-lg">登录</button>
                            </div>
                        </form>
                        
                        <div class="text-center mt-3">
                            <small class="text-muted">
                                <a href="../user/" class="text-decoration-none">返回用户端</a>
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="../assets/js/bootstrap.bundle.min.js"></script>
    <script>
        // 刷新验证码
        function refreshCaptcha() {
            document.getElementById('admin_captcha_img').src = '../captcha_image.php?t=' + new Date().getTime();
        }
        
        // 页面加载时初始化验证码
        document.addEventListener('DOMContentLoaded', function() {
            refreshCaptcha();
        });
    </script>
</body>
</html>