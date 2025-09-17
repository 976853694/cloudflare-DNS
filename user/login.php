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
require_once '../includes/captcha_mail.php';

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
    $email_verify_code = getPost('email_verify_code');
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
    } elseif ((getSetting('mail_verify_enabled', '0') == '1') && !$email_verify_code) {
        $error = '邮箱验证码错误';
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

                    // 邮箱验证是否开启
                    if (getSetting('mail_verify_enabled', '0') == '1') {
                        // 邮箱验证
                        $check_code = new captcha_mail();
                        $status = $check_code->checkCode($email_verify_code, $email);
                        if (!($status == 0)) {
                            switch ($status) {
                                case -1: {
                                        echo "<script>alert('验证码已过期');</script>";
                                        $error = '验证码已过期';
                                        break;
                                    }
                                case 1: {
                                        echo "<script>alert('验证码错误');</script>";
                                        $error = '验证码错误';
                                        break;
                                    }
                                case -2: {
                                        echo "<script>alert('服务器出错，请联系管理员');</script>";
                                        $error = '服务器出错，请联系管理员';
                                        break;
                                    }
                            }
                        }
                    }

                    if (!empty($error)) {
                        // 显示错误但不继续注册
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

                        $stmt = $db->prepare("INSERT INTO users (username, password, email, points) VALUES (?, ?, ?, ?)");
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
    <style>
        body {
            background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }

        .auth-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }

        .auth-header {
            background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }

        .auth-body {
            padding: 2rem;
        }

        .nav-tabs .nav-link {
            border: none;
            color: #6c757d;
        }

        .nav-tabs .nav-link.active {
            background: none;
            border-bottom: 2px solid #0984e3;
            color: #0984e3;
        }
    </style>
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
                        <!-- 标签页导航 -->
                        <ul class="nav nav-tabs mb-4" id="authTabs" role="tablist">
                            <li class="nav-item" role="presentation">
                                <button class="nav-link active" id="login-tab" data-bs-toggle="tab" data-bs-target="#login" type="button" role="tab">
                                    <i class="fas fa-sign-in-alt me-1"></i>登录
                                </button>
                            </li>
                            <?php if (getSetting('allow_registration', 1)): ?>
                                <li class="nav-item" role="presentation">
                                    <button class="nav-link" id="register-tab" data-bs-toggle="tab" data-bs-target="#register" type="button" role="tab">
                                        <i class="fas fa-user-plus me-1"></i>注册
                                    </button>
                                </li>
                            <?php endif; ?>
                        </ul>

                        <!-- GitHub OAuth 登录 -->
                        <?php
                        require_once '../config/migrate_oauth.php';
                        migrateOAuthSupport(); // 确保数据库已更新

                        if (getSetting('github_oauth_enabled', 0)):
                            require_once '../config/github_oauth.php';
                            try {
                                $github = new GitHubOAuth();
                                if ($github->isConfigured()) {
                                    $github_auth_url = $github->getAuthUrl();
                        ?>
                                    <div class="text-center mb-4">
                                        <div class="d-flex align-items-center mb-3">
                                            <hr class="flex-grow-1">
                                            <span class="px-3 text-muted small">或使用第三方登录</span>
                                            <hr class="flex-grow-1">
                                        </div>
                                        <a href="<?php echo htmlspecialchars($github_auth_url); ?>" class="btn btn-dark btn-lg w-100">
                                            <i class="fab fa-github me-2"></i>使用 GitHub 登录
                                        </a>
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
                            <div class="alert alert-danger"><?php echo htmlspecialchars($error); ?></div>
                        <?php endif; ?>

                        <?php if ($success): ?>
                            <div class="alert alert-success"><?php echo htmlspecialchars($success); ?></div>
                        <?php endif; ?>

                        <!-- 标签页内容 -->
                        <div class="tab-content" id="authTabsContent">
                            <!-- 登录表单 -->
                            <div class="tab-pane fade show active" id="login" role="tabpanel">
                                <form method="POST">
                                    <div class="mb-3">
                                        <label for="login_username" class="form-label">用户名</label>
                                        <input type="text" class="form-control" id="login_username" name="username" required>
                                    </div>
                                    <div class="mb-3">
                                        <label for="login_password" class="form-label">密码</label>
                                        <input type="password" class="form-control" id="login_password" name="password" required>
                                    </div>
                                    <div class="mb-3">
                                        <label for="login_captcha" class="form-label">验证码</label>
                                        <div class="row">
                                            <div class="col-6">
                                                <input type="text" class="form-control" id="login_captcha" name="captcha_code" required placeholder="请输入验证码">
                                            </div>
                                            <div class="col-6">
                                                <img src="../captcha_image.php" alt="验证码" class="img-fluid border rounded"
                                                    id="login_captcha_img" style="height: 38px; cursor: pointer;"
                                                    onclick="refreshCaptcha('login_captcha_img')" title="点击刷新验证码">
                                            </div>
                                        </div>
                                        <small class="form-text text-muted">点击图片可刷新验证码</small>
                                    </div>
                                    <div class="d-grid">
                                        <button type="submit" name="login" class="btn btn-primary btn-lg">
                                            <i class="fas fa-sign-in-alt me-1"></i>登录
                                        </button>
                                    </div>
                                </form>
                            </div>

                            <!-- 注册表单 -->
                            <?php if (getSetting('allow_registration', 1)): ?>
                                <div class="tab-pane fade" id="register" role="tabpanel">
                                    <form method="POST">
                                        <div class="mb-3">
                                            <label for="reg_username" class="form-label">用户名</label>
                                            <input type="text" class="form-control" id="reg_username" name="username" required>
                                        </div>
                                        <div class="mb-3">
                                            <label for="reg_email" class="form-label">邮箱</label>
                                            <input type="email" class="form-control" id="reg_email" name="email" required>
                                        </div>

                                        <!-- 邮箱验证 BY Senvinn -->
                                        <?php if (getSetting('mail_verify_enabled', '0') == '1') : ?>
                                            <div class="mb-3">
                                                <label for="reg_email_verify" class="form-label">邮箱验证码</label>
                                                <div class="row g-2">
                                                    <div class="col-8">
                                                        <input type="text" class="form-control" id="email_verify_code" name="email_verify_code">
                                                    </div>
                                                    <div class="col-4">
                                                        <button type="button" onclick="sendEmailVerify()" name="send_email_verifycode" id="send_email_verifycode" class="btn btn-primary w-100">
                                                            <i class="fas fa-paper-plane"></i>发送验证码
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        <?php endif; ?>

                                        <div class="mb-3">
                                            <label for="reg_password" class="form-label">密码</label>
                                            <input type="password" class="form-control" id="reg_password" name="password" required>
                                            <div class="form-text">密码至少6个字符</div>
                                        </div>
                                        <div class="mb-3">
                                            <label for="confirm_password" class="form-label">确认密码</label>
                                            <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
                                        </div>
                                        <div class="mb-3">
                                            <label for="invitation_code" class="form-label">邀请码 <span class="text-muted">(可选)</span></label>
                                            <input type="text" class="form-control" id="invitation_code" name="invitation_code"
                                                value="<?php echo htmlspecialchars($invite_code ?? ''); ?>"
                                                placeholder="请输入邀请码，可获得额外积分">
                                            <div class="form-text">
                                                <i class="fas fa-gift me-1 text-success"></i>
                                                使用邀请码注册可额外获得 <strong><?php echo getSetting('invitee_bonus_points', '5'); ?></strong> 积分
                                            </div>
                                        </div>
                                        <div class="mb-3">
                                            <label for="reg_captcha" class="form-label">验证码</label>
                                            <div class="row">
                                                <div class="col-6">
                                                    <input type="text" class="form-control" id="reg_captcha" name="captcha_code" required placeholder="请输入验证码">
                                                </div>
                                                <div class="col-6">
                                                    <img src="../captcha_image.php" alt="验证码" class="img-fluid border rounded"
                                                        id="reg_captcha_img" style="height: 38px; cursor: pointer;"
                                                        onclick="refreshCaptcha('reg_captcha_img')" title="点击刷新验证码">
                                                </div>
                                            </div>
                                            <small class="form-text text-muted">点击图片可刷新验证码</small>
                                        </div>
                                        <div class="d-grid">
                                            <button type="submit" name="register" class="btn btn-success btn-lg">
                                                <i class="fas fa-user-plus me-1"></i>注册
                                            </button>
                                        </div>
                                    </form>
                                </div>
                            <?php endif; ?>
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
            refreshCaptcha('reg_captcha_img');
        });

        // 切换标签页时刷新验证码
        document.getElementById('login-tab').addEventListener('click', function() {
            setTimeout(function() {
                refreshCaptcha('login_captcha_img');
            }, 100);
        });

        document.getElementById('register-tab').addEventListener('click', function() {
            setTimeout(function() {
                refreshCaptcha('reg_captcha_img');
            }, 100);
        });

        // 邮箱验证 BY Senvinn
        <?php if (getSetting('mail_verify_enabled', '0') == '1') : ?>
            async function sendEmailVerify() {
                const formData = new FormData();
                const email = document.getElementById('reg_email').value;
                const button = document.getElementById('send_email_verifycode');
                formData.append('email', email);
                formData.append('send_email_verifycode', '1');

                await fetch('../includes/captcha_mail.php', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => res = response.json())
                    .then(res => {
                        alert(res.msg);
                        if (res.code == '0') {
                            button.disabled = true;
                            let i = 60;
                            let timer = setInterval(() => {
                                i--;
                                button.textContent = `重新发送：${i}秒`;
                                if (i === 0) {
                                    clearInterval(timer);
                                    button.textContent = `重发验证码`;
                                    button.disabled = 0;
                                }
                            }, 1000);
                        }
                    })
                    .catch(error => console.error(error));

            }
        <?php endif; ?>
    </script>

</body>

</html>