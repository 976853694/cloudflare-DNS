<?php
session_start();

// 检查是否已安装
if (!file_exists('../data/install.lock')) {
    header('Location: ../install.php');
    exit;
}

require_once '../config/database.php';
require_once '../config/github_oauth.php';
require_once '../includes/functions.php';

// OAuth功能已集成到数据库升级系统中

$error = '';

try {
    // 检查是否启用GitHub OAuth
    if (!getSetting('github_oauth_enabled', 0)) {
        throw new Exception('GitHub OAuth登录未启用');
    }
    
    $github = new GitHubOAuth();
    
    // 检查OAuth配置
    if (!$github->isConfigured()) {
        throw new Exception('GitHub OAuth配置不完整，请联系管理员');
    }
    
    // 获取授权码和state参数
    $code = getGet('code');
    $state = getGet('state');
    $error_param = getGet('error');
    
    // 检查是否有错误
    if ($error_param) {
        $error_description = getGet('error_description', '用户取消授权');
        throw new Exception('GitHub授权失败: ' . $error_description);
    }
    
    // 检查必要参数
    if (!$code || !$state) {
        throw new Exception('缺少必要的授权参数');
    }
    
    // 验证state参数
    if (!$github->verifyState($state)) {
        throw new Exception('无效的state参数，可能存在CSRF攻击');
    }
    
    // 清除state参数
    unset($_SESSION['github_oauth_state']);
    
    // 获取访问令牌
    $access_token = $github->getAccessToken($code);
    
    // 获取用户信息
    $github_user = $github->getUserInfo($access_token);
    
    // 检查必要的用户信息
    if (!isset($github_user['id']) || !isset($github_user['login'])) {
        throw new Exception('无法获取GitHub用户信息');
    }
    
    $github_id = $github_user['id'];
    $github_username = $github_user['login'];
    $email = $github_user['email'] ?? '';
    $avatar_url = $github_user['avatar_url'] ?? '';
    $display_name = $github_user['name'] ?? $github_username;
    
    $db = Database::getInstance()->getConnection();
    
    // 检查是否是已登录用户要绑定GitHub账户
    if (isset($_SESSION['user_logged_in']) && isset($_SESSION['user_id'])) {
        // 用户已登录，这是绑定操作
        $current_user_id = $_SESSION['user_id'];
        
        // 检查当前用户是否已经绑定了GitHub
        $current_user = $db->querySingle("SELECT * FROM users WHERE id = $current_user_id", true);
        if (!empty($current_user['github_id'])) {
            throw new Exception('您的账户已经绑定了GitHub账户，请先解绑后再重新绑定');
        }
        
        // 检查这个GitHub账户是否已被其他用户绑定
        $stmt = $db->prepare("SELECT * FROM users WHERE github_id = ? AND oauth_provider = 'github'");
        $stmt->bindValue(1, $github_id, SQLITE3_TEXT);
        $result = $stmt->execute();
        $existing_github_user = $result->fetchArray(SQLITE3_ASSOC);
        
        if ($existing_github_user) {
            throw new Exception('该GitHub账户已被其他用户绑定');
        }
        
        // 计算GitHub账户注册天数并检查是否符合奖励条件
        $account_age_days = $github->getAccountAgeDays($github_user);
        $min_days = getSetting('github_min_account_days', 30);
        $github_bonus_points = getSetting('github_bonus_points', 200);
        $default_points = getSetting('default_user_points', 100);
        
        // 检查用户是否已经获得过GitHub绑定奖励
        $bonus_received = $db->querySingle("SELECT github_bonus_received FROM users WHERE id = $current_user_id");
        
        // 计算奖励积分：GitHub奖励积分 - 默认积分
        $bonus_points = 0;
        $bonus_message = '';
        
        if ($bonus_received) {
            $bonus_message = "（您已经获得过GitHub绑定奖励，不能重复获得）";
        } elseif ($account_age_days >= $min_days) {
            $bonus_points = $github_bonus_points - $default_points;
            if ($bonus_points > 0) {
                // 给用户增加奖励积分并标记已获得奖励
                $stmt_points = $db->prepare("UPDATE users SET points = points + ?, github_bonus_received = 1 WHERE id = ?");
                $stmt_points->bindValue(1, $bonus_points, SQLITE3_INTEGER);
                $stmt_points->bindValue(2, $current_user_id, SQLITE3_INTEGER);
                $stmt_points->execute();
                
                // 更新会话中的积分
                $_SESSION['user_points'] = $current_user['points'] + $bonus_points;
                
                $bonus_message = "，并获得{$bonus_points}积分奖励（GitHub账户{$account_age_days}天）";
            }
        } else {
            $bonus_message = "（GitHub账户{$account_age_days}天，未达到{$min_days}天要求，暂无积分奖励）";
        }
        
        // 绑定GitHub账户到当前用户
        $stmt = $db->prepare("UPDATE users SET github_id = ?, github_username = ?, avatar_url = ?, oauth_provider = 'github', updated_at = CURRENT_TIMESTAMP WHERE id = ?");
        $stmt->bindValue(1, $github_id, SQLITE3_TEXT);
        $stmt->bindValue(2, $github_username, SQLITE3_TEXT);
        $stmt->bindValue(3, $avatar_url, SQLITE3_TEXT);
        $stmt->bindValue(4, $current_user_id, SQLITE3_INTEGER);
        
        if ($stmt->execute()) {
            // 更新会话信息
            $_SESSION['github_username'] = $github_username;
            $_SESSION['avatar_url'] = $avatar_url;
            
            // 记录详细的绑定日志
            $github_created_at = $github_user['created_at'] ?? '未知';
            $log_details = "绑定GitHub账户: {$github_username}, 账户年龄: {$account_age_days}天, 创建时间: {$github_created_at}";
            if ($bonus_points > 0) {
                $log_details .= ", 获得奖励积分: {$bonus_points}";
            }
            logAction('user', $current_user_id, 'bind_github', $log_details);
            
            // 重定向到个人设置页面并显示成功消息
            showSuccess("GitHub账户绑定成功！{$bonus_message}");
            redirect('profile.php');
        } else {
            throw new Exception('绑定GitHub账户失败，请重试');
        }
    }
    
    // 检查是否已存在GitHub用户
    $stmt = $db->prepare("SELECT * FROM users WHERE github_id = ? AND oauth_provider = 'github'");
    $stmt->bindValue(1, $github_id, SQLITE3_TEXT);
    $result = $stmt->execute();
    $existing_user = $result->fetchArray(SQLITE3_ASSOC);
    
    if ($existing_user) {
        // 用户已存在，直接登录
        if ($existing_user['status'] != 1) {
            throw new Exception('您的账户已被禁用，请联系管理员');
        }
        
        // 更新用户信息
        $stmt = $db->prepare("UPDATE users SET github_username = ?, avatar_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?");
        $stmt->bindValue(1, $github_username, SQLITE3_TEXT);
        $stmt->bindValue(2, $avatar_url, SQLITE3_TEXT);
        $stmt->bindValue(3, $existing_user['id'], SQLITE3_INTEGER);
        $stmt->execute();
        
        // 设置登录会话
        $_SESSION['user_logged_in'] = true;
        $_SESSION['user_id'] = $existing_user['id'];
        $_SESSION['username'] = $existing_user['username'];
        $_SESSION['user_email'] = $existing_user['email'];
        $_SESSION['user_points'] = $existing_user['points'];
        $_SESSION['github_username'] = $github_username;
        $_SESSION['avatar_url'] = $avatar_url;
        
        logAction('user', $existing_user['id'], 'github_login', 'GitHub OAuth登录');
        redirect('dashboard.php');
        
    } else {
        // 检查是否允许自动注册
        if (!getSetting('github_auto_register', 1)) {
            throw new Exception('系统不允许GitHub用户自动注册，请使用普通方式注册');
        }
        
        // 检查邮箱是否已被其他用户使用
        if (!empty($email)) {
            $email_exists = $db->querySingle("SELECT COUNT(*) FROM users WHERE email = '$email'");
            if ($email_exists) {
                throw new Exception('该邮箱已被其他用户注册，请联系管理员处理账户关联');
            }
        }
        
        // 生成唯一用户名
        $username = $github_username;
        $counter = 1;
        while ($db->querySingle("SELECT COUNT(*) FROM users WHERE username = '$username'")) {
            $username = $github_username . '_' . $counter;
            $counter++;
        }
        
        // 计算GitHub账户注册天数并分配积分
        $account_age_days = $github->getAccountAgeDays($github_user);
        $assigned_points = $github->calculatePointsByAge($account_age_days);
        
        // 记录GitHub账户信息用于日志
        $github_created_at = $github_user['created_at'] ?? '未知';
        $min_days = getSetting('github_min_account_days', 30);
        
        $stmt = $db->prepare("INSERT INTO users (username, password, email, points, github_id, github_username, avatar_url, oauth_provider, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)");
        $stmt->bindValue(1, $username, SQLITE3_TEXT);
        $stmt->bindValue(2, '', SQLITE3_TEXT); // GitHub用户不需要密码
        $stmt->bindValue(3, $email, SQLITE3_TEXT);
        $stmt->bindValue(4, $assigned_points, SQLITE3_INTEGER);
        $stmt->bindValue(5, $github_id, SQLITE3_TEXT);
        $stmt->bindValue(6, $github_username, SQLITE3_TEXT);
        $stmt->bindValue(7, $avatar_url, SQLITE3_TEXT);
        $stmt->bindValue(8, 'github', SQLITE3_TEXT);
        $stmt->bindValue(9, 1, SQLITE3_INTEGER);
        
        if ($stmt->execute()) {
            $user_id = $db->lastInsertRowID();
            
            // 设置登录会话
            $_SESSION['user_logged_in'] = true;
            $_SESSION['user_id'] = $user_id;
            $_SESSION['username'] = $username;
            $_SESSION['user_email'] = $email;
            $_SESSION['user_points'] = $assigned_points;
            $_SESSION['github_username'] = $github_username;
            $_SESSION['avatar_url'] = $avatar_url;
            
            // 记录详细的注册日志
            $points_reason = $account_age_days >= $min_days ? "奖励积分(账户{$account_age_days}天)" : "默认积分(账户{$account_age_days}天)";
            logAction('user', $user_id, 'github_register', "GitHub OAuth注册并登录 - {$points_reason}, 获得{$assigned_points}积分, GitHub创建时间: {$github_created_at}");
            
            // 显示欢迎消息
            $welcome_message = "欢迎使用GitHub登录！您的账户已自动创建，获得了 {$assigned_points} 积分";
            if ($account_age_days >= $min_days) {
                $welcome_message .= "（GitHub账户{$account_age_days}天，获得奖励积分）";
            } else {
                $welcome_message .= "（GitHub账户{$account_age_days}天，获得默认积分）";
            }
            showSuccess($welcome_message);
            redirect('dashboard.php');
        } else {
            throw new Exception('创建用户失败，请重试');
        }
    }
    
} catch (Exception $e) {
    $error = $e->getMessage();
    logAction('system', 0, 'github_oauth_error', $error . ' - IP: ' . ($_SERVER['REMOTE_ADDR'] ?? ''));
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub登录处理 - <?php echo getSetting('site_name', 'DNS管理系统'); ?></title>
    <link href="../assets/css/bootstrap.min.css" rel="stylesheet">
    <link href="../assets/css/fontawesome.min.css" rel="stylesheet">
    <link href="../assets/css/white-auth.css" rel="stylesheet">
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="callback-container">
                    <?php if ($error): ?>
                        <div class="text-danger mb-4">
                            <i class="fab fa-github fa-3x mb-3"></i>
                            <h4>GitHub登录失败</h4>
                            <p class="text-muted"><?php echo htmlspecialchars($error); ?></p>
                            <a href="login.php" class="btn btn-primary">
                                <i class="fas fa-arrow-left me-1"></i>返回登录页面
                            </a>
                        </div>
                    <?php else: ?>
                        <div class="text-success mb-4">
                            <i class="fas fa-spinner fa-spin fa-3x mb-3"></i>
                            <h4>正在处理GitHub登录...</h4>
                            <p class="text-muted">请稍候，正在为您登录系统</p>
                        </div>
                        <script>
                            // 如果没有错误但也没有重定向，3秒后自动跳转
                            setTimeout(function() {
                                window.location.href = 'dashboard.php';
                            }, 3000);
                        </script>
                    <?php endif; ?>
                </div>
            </div>
        </div>
    </div>
    
    <script src="../assets/js/bootstrap.bundle.min.js"></script>
</body>
</html>