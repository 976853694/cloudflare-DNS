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
if (isset($_SESSION['user_logged_in'])) {
    redirect('dashboard.php');
}

$error = '';
$success = '';

// 获取URL中的邀请码
$invite_code = getGet('invite');


// 处理注册
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['register'])) {
    $username = getPost('username');
    $password = getPost('password');
    $confirm_password = getPost('confirm_password');
    $email = getPost('email');
    $captcha_code = getPost('captcha_code');
    $invitation_code = getPost('invitation_code');
    
    $captcha = new Captcha();
    
    if (!$username || !$password || !$email || !$captcha_code) {
        $error = '请填写完整信息';
    } elseif (!$captcha->verify($captcha_code)) {
        $error = '验证码错误或已过期';
    } elseif (strlen($password) < 6) {
        $error = '密码至少需要6个字符';
    } elseif ($password !== $confirm_password) {
        $error = '两次输入的密码不一致';
    } elseif (!isValidEmail($email)) {
        $error = '请输入有效的邮箱地址';
    } else {
        // 检查注册是否开放
        if (!getSetting('allow_registration', 1)) {
            $error = '系统暂时关闭注册功能';
        } else {
            $db = Database::getInstance()->getConnection();
            
            // 检查用户名是否已存在
            $exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE username = '$username'");
            if ($exists) {
                $error = '用户名已存在';
            } else {
                // 检查邮箱是否已存在
                $email_exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE email = '$email'");
                if ($email_exists) {
                    $error = '该邮箱已被注册';
                } else {
                    $hashed_password = password_hash($password, PASSWORD_DEFAULT);
                    $default_points = getSetting('default_user_points', 100);
                    $invitee_bonus = 0;
                    $invitation_id = null;
                    
                    // 处理邀请码
                    if (!empty($invitation_code)) {
                        $invitation = $db->querySingle("SELECT * FROM invitations WHERE invitation_code = '$invitation_code' AND is_active = 1", true);
                        if ($invitation) {
                            // 检查该用户是否已经使用过此邀请码
                            $already_used = $db->querySingle("SELECT COUNT(*) FROM invitation_uses iu 
                                JOIN users u ON iu.invitee_id = u.id 
                                WHERE iu.invitation_id = {$invitation['id']} AND u.username = '$username'");
                            
                            if (!$already_used) {
                                $invitee_bonus = (int)getSetting('invitee_bonus_points', '5');
                                $invitation_id = $invitation['id'];
                            }
                        }
                    }
                    
                    $total_points = $default_points + $invitee_bonus;
                    
                    // 新用户默认分配到默认组（ID=1）
                    $stmt = $db->prepare("INSERT INTO users (username, password, email, points, group_id) VALUES (?, ?, ?, ?, 1)");
                    $stmt->bindValue(1, $username, SQLITE3_TEXT);
                    $stmt->bindValue(2, $hashed_password, SQLITE3_TEXT);
                    $stmt->bindValue(3, $email, SQLITE3_TEXT);
                    $stmt->bindValue(4, $total_points, SQLITE3_INTEGER);
                    
                    if ($stmt->execute()) {
                        $user_id = $db->lastInsertRowID();
                        
                        // 自动为新用户生成邀请码
                        do {
                            $new_invitation_code = 'INV' . strtoupper(substr(md5(uniqid(rand(), true)), 0, 8));
                            $exists = $db->querySingle("SELECT COUNT(*) FROM invitations WHERE invitation_code = '$new_invitation_code'");
                        } while ($exists > 0);
                        
                        $current_reward_points = (int)getSetting('invitation_reward_points', '10');
                        $stmt_inv = $db->prepare("INSERT INTO invitations (inviter_id, invitation_code, reward_points) VALUES (?, ?, ?)");
                        $stmt_inv->bindValue(1, $user_id, SQLITE3_INTEGER);
                        $stmt_inv->bindValue(2, $new_invitation_code, SQLITE3_TEXT);
                        $stmt_inv->bindValue(3, $current_reward_points, SQLITE3_INTEGER);
                        $stmt_inv->execute();
                        
                        // 处理邀请奖励
                        if ($invitation_id) {
                            // 记录邀请使用
                            $reward_points = $invitation['reward_points'];
                            $stmt = $db->prepare("INSERT INTO invitation_uses (invitation_id, invitee_id, reward_points) VALUES (?, ?, ?)");
                            $stmt->bindValue(1, $invitation_id, SQLITE3_INTEGER);
                            $stmt->bindValue(2, $user_id, SQLITE3_INTEGER);
                            $stmt->bindValue(3, $reward_points, SQLITE3_INTEGER);
                            $stmt->execute();
                            
                            // 更新邀请记录统计
                            $db->exec("UPDATE invitations SET 
                                use_count = use_count + 1, 
                                total_rewards = total_rewards + $reward_points,
                                last_used_at = CURRENT_TIMESTAMP 
                                WHERE id = $invitation_id");
                            
                            // 给邀请人奖励积分
                            $inviter_id = $invitation['inviter_id'];
                            $db->exec("UPDATE users SET points = points + $reward_points WHERE id = $inviter_id");
                            
                            logAction('user', $user_id, 'register_with_invitation', "通过邀请码注册: $invitation_code");
                            logAction('user', $inviter_id, 'invitation_reward', "邀请奖励: +$reward_points 积分");
                            
                            $success = "注册成功！您获得了 $invitee_bonus 积分邀请奖励，请登录";
                        } else {
                            logAction('user', $user_id, 'register', '用户注册');
                            $success = '注册成功！请登录';
                        }
                    } else {
                        $error = '注册失败，请重试';
                    }
                }
            }
        }
    }
}

// 处理登录
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['login'])) {
    $username = getPost('username');
    $password = getPost('password');
    $captcha_code = getPost('captcha_code');
    $user_ip = $_SERVER['REMOTE_ADDR'] ?? '';
    
    $captcha = new Captcha();
    
    // 检查IP是否被锁定
    if (Security::isIpLocked($user_ip, 'user')) {
        $remaining_time = Security::getRemainingLockTime($user_ip, 'user');
        $error = '登录失败次数过多，IP已被锁定。请在 ' . Security::formatRemainingTime($remaining_time) . ' 后重试';
    } elseif (!$username || !$password || !$captcha_code) {
        $error = '请填写完整信息';
    } elseif (!$captcha->verify($captcha_code)) {
        $error = '验证码错误或已过期';
    } elseif ($username && $password) {
        $db = Database::getInstance()->getConnection();
        $stmt = $db->prepare("SELECT * FROM users WHERE username = ? AND status = 1");
        $stmt->bindValue(1, $username, SQLITE3_TEXT);
        $result = $stmt->execute();
        $user = $result->fetchArray(SQLITE3_ASSOC);
        
        if ($user && password_verify($password, $user['password'])) {
            // 登录成功，清除失败记录
            Security::clearFailedAttempts($user_ip, 'user');
            
            $_SESSION['user_logged_in'] = true;
            $_SESSION['user_id'] = $user['id'];
            $_SESSION['username'] = $user['username'];
            $_SESSION['user_email'] = $user['email'];
            $_SESSION['user_points'] = $user['points'];
            
            logAction('user', $user['id'], 'login', '用户登录');
            redirect('dashboard.php');
        } else {
            // 登录失败，记录失败尝试
            Security::recordFailedLogin($user_ip, $username, 'user');
            $error = '用户名或密码错误，或账户已被禁用';
        }
    } else {
        $error = '用户名或密码错误，或账户已被禁用';
    }
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>用户登录 - <?php echo getSetting('site_name', 'DNS管理系统'); ?></title>
    <link href="../assets/css/bootstrap.min.css" rel="stylesheet">
    <link href="../assets/css/fontawesome.min.css" rel="stylesheet">
    <link href="../assets/css/white-auth.css" rel="stylesheet">
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-8 col-lg-6">
                <div class="auth-container">
                    <div class="auth-header">
                        <h3 class="mb-0"><?php echo getSetting('site_name', 'DNS管理系统'); ?></h3>
                        <p class="mb-0 mt-2">Cloudflare DNS管理平台</p>
                    </div>
                    <div class="auth-body">
                        <!-- 登录标题 -->
                        <div class="text-center mb-4">
                            <h4 class="text-primary mb-3">
                                <i class="fas fa-sign-in-alt me-2"></i>用户登录
                            </h4>
                            
                            <!-- 快速注册和找回密码链接 -->
                            <div class="quick-links mb-3">
                                <?php if (getSetting('allow_registration', 1)): ?>
                                <a href="register_verify.php" class="btn btn-outline-primary me-2">
                                    <i class="fas fa-user-plus me-1"></i>新用户注册
                                </a>
                                <?php endif; ?>
                                <a href="forgot_password.php" class="btn btn-outline-secondary">
                                    <i class="fas fa-key me-1"></i>忘记密码
                                </a>
                            </div>
                        </div>
                        
                        <!-- GitHub OAuth 登录 -->
                        <?php 
                        if (getSetting('github_oauth_enabled', 0)): 
                            require_once '../config/github_oauth.php';
                            try {
                                $github = new GitHubOAuth();
                                if ($github->isConfigured()) {
                                    $github_auth_url = $github->getAuthUrl();
                        ?>
                        <div class="mb-4">
                            <a href="<?php echo htmlspecialchars($github_auth_url); ?>" class="btn btn-dark w-100">
                                <i class="fab fa-github me-2"></i>使用 GitHub 登录
                            </a>
                            <div class="divider mt-3">
                                <span>或使用账号登录</span>
                            </div>
                        </div>
                        <?php 
                                }
                            } catch (Exception $e) {
                                // 静默处理配置错误
                            }
                        endif; 
                        ?>
                        
                        <!-- 消息提示 -->
                        <?php if ($error): ?>
                            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                                <i class="fas fa-exclamation-circle me-2"></i><?php echo htmlspecialchars($error); ?>
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        <?php endif; ?>
                        
                        <?php if ($success): ?>
                            <div class="alert alert-success alert-dismissible fade show" role="alert">
                                <i class="fas fa-check-circle me-2"></i><?php echo htmlspecialchars($success); ?>
                                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                            </div>
                        <?php endif; ?>
                        
                        <!-- 登录表单 -->
                        <form method="POST">
                            <div class="mb-3">
                                <label for="login_username" class="form-label">
                                    <i class="fas fa-user me-1"></i>用户名
                                </label>
                                <input type="text" class="form-control" id="login_username" name="username" 
                                       placeholder="请输入用户名" required autofocus>
                            </div>
                            <div class="mb-3">
                                <label for="login_password" class="form-label">
                                    <i class="fas fa-lock me-1"></i>密码
                                </label>
                                <input type="password" class="form-control" id="login_password" name="password" 
                                       placeholder="请输入密码" required>
                            </div>
                            <div class="mb-3">
                                <label for="login_captcha" class="form-label">
                                    <i class="fas fa-shield-alt me-1"></i>验证码
                                </label>
                                <div class="row g-2">
                                    <div class="col-7">
                                        <input type="text" class="form-control" id="login_captcha" name="captcha_code" 
                                               placeholder="请输入验证码" required>
                                    </div>
                                    <div class="col-5">
                                        <img src="../captcha_image.php" alt="验证码" class="img-fluid border captcha-img" 
                                             id="login_captcha_img" 
                                             onclick="refreshCaptcha('login_captcha_img')" 
                                             title="点击刷新验证码">
                                    </div>
                                </div>
                                <small class="form-text text-muted">
                                    <i class="fas fa-info-circle me-1"></i>点击图片可刷新验证码
                                </small>
                            </div>
                            <div class="d-grid mt-4">
                                <button type="submit" name="login" class="btn btn-primary btn-lg">
                                    <i class="fas fa-sign-in-alt me-2"></i>登录
                                </button>
                            </div>
                        </form>
                        
                        <!-- 底部链接 -->
                        <div class="text-center mt-4">
                            <small class="text-muted">
                                <a href="../admin/login.php" class="text-decoration-none">
                                    <i class="fas fa-user-shield me-1"></i>管理员入口
                                </a>
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
        function refreshCaptcha(imgId) {
            document.getElementById(imgId).src = '../captcha_image.php?t=' + new Date().getTime();
        }
        
        // 页面加载时初始化验证码
        document.addEventListener('DOMContentLoaded', function() {
            refreshCaptcha('login_captcha_img');
        });
    </script>
</body>
</html>