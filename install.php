<?php
/**
 * 系统安装页面
 */
session_start();

// 检查是否已经安装
if (file_exists('data/install.lock')) {
    // 显示安全警告页面
    ?>
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>安全警告 - 系统已安装</title>
        <link href="assets/css/bootstrap.min.css" rel="stylesheet">
        <link href="assets/css/fontawesome.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
            }
            .warning-container {
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                overflow: hidden;
                margin: 2rem auto;
                max-width: 600px;
            }
            .warning-header {
                background: linear-gradient(135deg, #dc3545 0%, #fd7e14 100%);
                color: white;
                padding: 2rem;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="warning-container">
                <div class="warning-header">
                    <h1><i class="fas fa-exclamation-triangle me-2"></i>安全警告</h1>
                    <p class="mb-0">系统已安装完成</p>
                </div>
                <div class="p-4">
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-shield-alt me-2"></i>重要安全提示</h5>
                        <p>检测到系统已经安装完成，但安装文件 <code>install.php</code> 仍然存在。</p>
                        <p class="mb-0">为了系统安全，请立即删除或重命名此文件！</p>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="fas fa-terminal me-2"></i>删除命令</h6>
                        </div>
                        <div class="card-body">
                            <p>在服务器上执行以下命令删除安装文件：</p>
                            <code class="d-block bg-dark text-light p-2 rounded">rm install.php</code>
                            <p class="mt-2 mb-0">或者将文件重命名：</p>
                            <code class="d-block bg-dark text-light p-2 rounded">mv install.php install.php.bak</code>
                        </div>
                    </div>
                    
                    <div class="text-center mt-4">
                        <a href="admin/login.php" class="btn btn-primary me-2">
                            <i class="fas fa-sign-in-alt me-2"></i>管理员登录
                        </a>
                        <a href="user/login.php" class="btn btn-outline-primary">
                            <i class="fas fa-users me-2"></i>用户登录
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    <?php
    exit;
}

$step = isset($_GET['step']) ? (int)$_GET['step'] : 1;
$error = '';
$success = '';

// 处理安装步骤
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    switch ($step) {
        case 1:
            // 环境检查完成，进入下一步
            header('Location: install.php?step=2');
            exit;
            
        case 2:
            // 数据库配置
            $db_path = 'data/cloudflare_dns.db';
            $data_dir = dirname($db_path);
            
            if (!is_dir($data_dir)) {
                if (!mkdir($data_dir, 0755, true)) {
                    $error = '无法创建数据目录，请检查权限';
                    break;
                }
            }
            
            if (!is_writable($data_dir)) {
                $error = '数据目录不可写，请检查权限';
                break;
            }
            
            try {
                // 创建数据库并设置优化参数，防止卡死
                $db = new SQLite3($db_path);
                $db->enableExceptions(true);
                
                // 设置较短的超时时间和优化参数
                $db->busyTimeout(5000); // 5秒超时
                $db->exec('PRAGMA journal_mode = WAL');
                $db->exec('PRAGMA synchronous = NORMAL');
                $db->exec('PRAGMA cache_size = -2000'); // 2MB cache
                $db->exec('PRAGMA temp_store = MEMORY');
                $db->exec('PRAGMA locking_mode = NORMAL');
                
                // 测试写入
                $db->exec("CREATE TABLE IF NOT EXISTS install_test (id INTEGER PRIMARY KEY)");
                $db->exec("DROP TABLE IF EXISTS install_test");
                
                $db->close();
                
                // 确保文件权限正确
                chmod($db_path, 0666);
                if (file_exists($db_path . '-wal')) {
                    chmod($db_path . '-wal', 0666);
                }
                if (file_exists($db_path . '-shm')) {
                    chmod($db_path . '-shm', 0666);
                }
                
                header('Location: install.php?step=3');
                exit;
            } catch (Exception $e) {
                $error = '数据库创建失败: ' . $e->getMessage();
            }
            break;
            
        case 3:
            // 管理员账户配置
            $admin_username = trim($_POST['admin_username'] ?? '');
            $admin_password = $_POST['admin_password'] ?? '';
            $admin_email = trim($_POST['admin_email'] ?? '');
            $confirm_password = $_POST['confirm_password'] ?? '';
            
            if (!$admin_username || !$admin_password) {
                $error = '请填写管理员用户名和密码';
            } elseif (strlen($admin_username) < 3) {
                $error = '用户名至少需要3个字符';
            } elseif (strlen($admin_password) < 6) {
                $error = '密码至少需要6个字符';
            } elseif ($admin_password !== $confirm_password) {
                $error = '两次输入的密码不一致';
            } elseif ($admin_email && !filter_var($admin_email, FILTER_VALIDATE_EMAIL)) {
                $error = '邮箱格式不正确';
            } else {
                $_SESSION['install_admin'] = [
                    'username' => $admin_username,
                    'password' => $admin_password,
                    'email' => $admin_email
                ];
                header('Location: install.php?step=4');
                exit;
            }
            break;
            
        case 4:
            // 系统配置
            $site_name = trim($_POST['site_name'] ?? '');
            $points_per_record = (int)($_POST['points_per_record'] ?? 1);
            $default_user_points = (int)($_POST['default_user_points'] ?? 100);
            $allow_registration = isset($_POST['allow_registration']) ? 1 : 0;
            
            if (!$site_name) {
                $error = '请填写网站名称';
            } elseif ($points_per_record < 1) {
                $error = '每条记录消耗积分必须大于0';
            } elseif ($default_user_points < 0) {
                $error = '新用户默认积分不能为负数';
            } else {
                $_SESSION['install_config'] = [
                    'site_name' => $site_name,
                    'points_per_record' => $points_per_record,
                    'default_user_points' => $default_user_points,
                    'allow_registration' => $allow_registration
                ];
                header('Location: install.php?step=5');
                exit;
            }
            break;
            
        case 5:
            // 执行安装
            try {
                // 设置较长的执行时间限制
                set_time_limit(300); // 5分钟
                
                require_once 'config/database.php';
                
                // 获取配置
                $admin_config = $_SESSION['install_admin'] ?? [];
                $system_config = $_SESSION['install_config'] ?? [];
                
                if (empty($admin_config) || empty($system_config)) {
                    throw new Exception('安装配置丢失，请重新开始安装');
                }
                
                // 初始化数据库（这会创建所有表）
                // 使用try-catch包装，避免初始化时卡死
                $max_retries = 3;
                $retry_count = 0;
                $db = null;
                
                while ($retry_count < $max_retries && $db === null) {
                    try {
                        $db = Database::getInstance()->getConnection();
                        break;
                    } catch (Exception $e) {
                        $retry_count++;
                        if ($retry_count >= $max_retries) {
                            throw new Exception('数据库初始化失败: ' . $e->getMessage() . '。请检查data目录权限或尝试手动删除cloudflare_dns.db及其相关文件(-wal, -shm)后重新安装');
                        }
                        // 等待一下再重试
                        sleep(1);
                        
                        // 尝试清理可能的锁文件
                        $db_path = __DIR__ . '/data/cloudflare_dns.db';
                        if (file_exists($db_path . '-shm')) {
                            @unlink($db_path . '-shm');
                        }
                    }
                }
                
                // 删除默认管理员（如果存在）
                $db->exec("DELETE FROM admins WHERE username = 'admin'");
                
                // 创建新管理员
                $hashed_password = password_hash($admin_config['password'], PASSWORD_DEFAULT);
                $stmt = $db->prepare("INSERT INTO admins (username, password, email) VALUES (?, ?, ?)");
                $stmt->bindValue(1, $admin_config['username'], SQLITE3_TEXT);
                $stmt->bindValue(2, $hashed_password, SQLITE3_TEXT);
                $stmt->bindValue(3, $admin_config['email'], SQLITE3_TEXT);
                $stmt->execute();
                
                // 更新系统设置
                $settings = [
                    'site_name' => $system_config['site_name'],
                    'points_per_record' => $system_config['points_per_record'],
                    'default_user_points' => $system_config['default_user_points'],
                    'allow_registration' => $system_config['allow_registration']
                ];
                
                foreach ($settings as $key => $value) {
                    $stmt = $db->prepare("UPDATE settings SET setting_value = ? WHERE setting_key = ?");
                    $stmt->bindValue(1, $value, SQLITE3_TEXT);
                    $stmt->bindValue(2, $key, SQLITE3_TEXT);
                    $stmt->execute();
                }
                
                // 自动导入邮件模板
                require_once 'includes/functions.php';
                importEmailTemplates($db);
                
                // 创建安装锁定文件
                file_put_contents('data/install.lock', date('Y-m-d H:i:s'));
                
                // 清除安装会话
                unset($_SESSION['install_admin']);
                unset($_SESSION['install_config']);
                
                header('Location: install.php?step=6');
                exit;
                
            } catch (Exception $e) {
                $error = '安装失败: ' . $e->getMessage();
            }
            break;
    }
}

// 环境检查
function checkEnvironment() {
    // 检查data目录权限
    $data_writable = false;
    if (!is_dir('data')) {
        $data_writable = @mkdir('data', 0755, true);
    } else {
        $data_writable = is_writable('data');
    }
    
    // 检查磁盘空间（至少需要10MB）
    $disk_space_ok = false;
    if (function_exists('disk_free_space')) {
        $free_space = @disk_free_space('.');
        $disk_space_ok = ($free_space === false || $free_space > 10 * 1024 * 1024);
    } else {
        $disk_space_ok = true; // 无法检测时假设足够
    }
    
    $checks = [
        'PHP版本 >= 7.0' => version_compare(PHP_VERSION, '7.0.0', '>='),
        'SQLite3扩展' => extension_loaded('sqlite3'),
        'cURL扩展' => extension_loaded('curl'),
        'OpenSSL扩展' => extension_loaded('openssl'),
        'data目录可写' => $data_writable,
        '磁盘空间充足 (>10MB)' => $disk_space_ok,
    ];
    return $checks;
}

$env_checks = checkEnvironment();
$env_ok = !in_array(false, $env_checks);
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>系统安装 - Cloudflare DNS管理系统</title>
    <link href="assets/css/bootstrap.min.css" rel="stylesheet">
    <link href="assets/css/fontawesome.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .install-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            margin: 2rem auto;
            max-width: 800px;
        }
        .install-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        .install-body {
            padding: 2rem;
        }
        .step-indicator {
            display: flex;
            justify-content: center;
            margin-bottom: 2rem;
        }
        .step {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 10px;
            font-weight: bold;
            position: relative;
        }
        .step.active {
            background: #667eea;
            color: white;
        }
        .step.completed {
            background: #28a745;
            color: white;
        }
        .step.pending {
            background: #e9ecef;
            color: #6c757d;
        }
        .step:not(:last-child)::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 100%;
            width: 20px;
            height: 2px;
            background: #e9ecef;
            transform: translateY(-50%);
        }
        .step.completed:not(:last-child)::after {
            background: #28a745;
        }
        .check-item {
            display: flex;
            align-items: center;
            padding: 0.5rem 0;
        }
        .check-item i {
            margin-right: 0.5rem;
            width: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="install-container">
            <div class="install-header">
                <h1><i class="fas fa-cloud me-2"></i>Cloudflare DNS管理系统</h1>
                <p class="mb-0">欢迎使用系统安装向导</p>
            </div>
            
            <div class="install-body">
                <!-- 步骤指示器 -->
                <div class="step-indicator">
                    <?php for ($i = 1; $i <= 6; $i++): ?>
                    <div class="step <?php 
                        if ($i < $step) echo 'completed';
                        elseif ($i == $step) echo 'active';
                        else echo 'pending';
                    ?>">
                        <?php if ($i < $step): ?>
                            <i class="fas fa-check"></i>
                        <?php else: ?>
                            <?php echo $i; ?>
                        <?php endif; ?>
                    </div>
                    <?php endfor; ?>
                </div>
                
                <!-- 错误提示 -->
                <?php if ($error): ?>
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i><?php echo htmlspecialchars($error); ?>
                </div>
                <?php endif; ?>
                
                <!-- 成功提示 -->
                <?php if ($success): ?>
                <div class="alert alert-success">
                    <i class="fas fa-check-circle me-2"></i><?php echo htmlspecialchars($success); ?>
                </div>
                <?php endif; ?>
                
                <?php if ($step == 1): ?>
                <!-- 步骤1: 环境检查 -->
                <div class="text-center mb-4">
                    <h3><i class="fas fa-server me-2"></i>环境检查</h3>
                    <p class="text-muted">检查服务器环境是否满足系统要求</p>
                </div>
                
                <div class="row justify-content-center">
                    <div class="col-md-8">
                        <?php foreach ($env_checks as $name => $status): ?>
                        <div class="check-item">
                            <i class="fas <?php echo $status ? 'fa-check-circle text-success' : 'fa-times-circle text-danger'; ?>"></i>
                            <span><?php echo $name; ?></span>
                        </div>
                        <?php endforeach; ?>
                        
                        <div class="mt-4 text-center">
                            <?php if ($env_ok): ?>
                            <form method="POST">
                                <button type="submit" class="btn btn-primary btn-lg">
                                    <i class="fas fa-arrow-right me-2"></i>下一步
                                </button>
                            </form>
                            <div class="mt-3">
                                <a href="install_diagnostic.php" class="btn btn-outline-info" target="_blank">
                                    <i class="fas fa-stethoscope me-2"></i>运行诊断工具
                                </a>
                            </div>
                            <?php else: ?>
                            <div class="alert alert-warning">
                                <i class="fas fa-exclamation-triangle me-2"></i>
                                请解决上述环境问题后刷新页面继续安装
                            </div>
                            <button type="button" class="btn btn-secondary me-2" onclick="location.reload()">
                                <i class="fas fa-redo me-2"></i>重新检查
                            </button>
                            <a href="install_diagnostic.php" class="btn btn-info" target="_blank">
                                <i class="fas fa-stethoscope me-2"></i>诊断工具
                            </a>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
                
                <?php elseif ($step == 2): ?>
                <!-- 步骤2: 数据库配置 -->
                <div class="text-center mb-4">
                    <h3><i class="fas fa-database me-2"></i>数据库配置</h3>
                    <p class="text-muted">配置SQLite数据库</p>
                </div>
                
                <div class="row justify-content-center">
                    <div class="col-md-6">
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            系统将使用SQLite数据库，数据将存储在 <code>data/cloudflare_dns.db</code> 文件中
                        </div>
                        
                        <form method="POST">
                            <div class="text-center">
                                <button type="submit" class="btn btn-primary btn-lg">
                                    <i class="fas fa-database me-2"></i>创建数据库
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
                
                <?php elseif ($step == 3): ?>
                <!-- 步骤3: 管理员账户 -->
                <div class="text-center mb-4">
                    <h3><i class="fas fa-user-shield me-2"></i>管理员账户</h3>
                    <p class="text-muted">创建系统管理员账户</p>
                </div>
                
                <div class="row justify-content-center">
                    <div class="col-md-6">
                        <form method="POST">
                            <div class="mb-3">
                                <label for="admin_username" class="form-label">管理员用户名</label>
                                <input type="text" class="form-control" id="admin_username" name="admin_username" 
                                       value="<?php echo htmlspecialchars($_POST['admin_username'] ?? ''); ?>" required>
                                <div class="form-text">至少3个字符</div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="admin_email" class="form-label">邮箱地址</label>
                                <input type="email" class="form-control" id="admin_email" name="admin_email" 
                                       value="<?php echo htmlspecialchars($_POST['admin_email'] ?? ''); ?>">
                                <div class="form-text">可选，用于找回密码</div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="admin_password" class="form-label">密码</label>
                                <input type="password" class="form-control" id="admin_password" name="admin_password" required>
                                <div class="form-text">至少6个字符</div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="confirm_password" class="form-label">确认密码</label>
                                <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
                            </div>
                            
                            <div class="text-center">
                                <button type="submit" class="btn btn-primary btn-lg">
                                    <i class="fas fa-arrow-right me-2"></i>下一步
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
                
                <?php elseif ($step == 4): ?>
                <!-- 步骤4: 系统配置 -->
                <div class="text-center mb-4">
                    <h3><i class="fas fa-cogs me-2"></i>系统配置</h3>
                    <p class="text-muted">配置系统基本参数</p>
                </div>
                
                <div class="row justify-content-center">
                    <div class="col-md-8">
                        <form method="POST">
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="site_name" class="form-label">网站名称</label>
                                        <input type="text" class="form-control" id="site_name" name="site_name" 
                                               value="<?php echo htmlspecialchars($_POST['site_name'] ?? 'Cloudflare DNS管理系统'); ?>" required>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <label for="points_per_record" class="form-label">每条记录消耗积分</label>
                                        <input type="number" class="form-control" id="points_per_record" name="points_per_record" 
                                               value="<?php echo (int)($_POST['points_per_record'] ?? 1); ?>" min="1" required>
                                    </div>
                                </div>
                                
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="default_user_points" class="form-label">新用户默认积分</label>
                                        <input type="number" class="form-control" id="default_user_points" name="default_user_points" 
                                               value="<?php echo (int)($_POST['default_user_points'] ?? 100); ?>" min="0" required>
                                    </div>
                                    
                                    <div class="mb-3">
                                        <div class="form-check">
                                            <input class="form-check-input" type="checkbox" id="allow_registration" name="allow_registration" 
                                                   <?php echo isset($_POST['allow_registration']) ? 'checked' : 'checked'; ?>>
                                            <label class="form-check-label" for="allow_registration">
                                                允许用户注册
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="text-center">
                                <button type="submit" class="btn btn-primary btn-lg">
                                    <i class="fas fa-arrow-right me-2"></i>下一步
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
                
                <?php elseif ($step == 5): ?>
                <!-- 步骤5: 执行安装 -->
                <div class="text-center mb-4">
                    <h3><i class="fas fa-download me-2"></i>执行安装</h3>
                    <p class="text-muted">正在安装系统，请稍候...</p>
                </div>
                
                <div class="row justify-content-center">
                    <div class="col-md-6">
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            系统正在初始化数据库并配置相关设置，请不要关闭浏览器。
                        </div>
                        
                        <!-- 安装进度提示 -->
                        <div id="installProgress" style="display:none;">
                            <div class="card">
                                <div class="card-body">
                                    <h6><i class="fas fa-spinner fa-spin me-2"></i>正在安装...</h6>
                                    <div class="progress mt-3">
                                        <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                             role="progressbar" style="width: 100%"></div>
                                    </div>
                                    <p class="mt-3 mb-0 text-muted small">
                                        <i class="fas fa-clock me-1"></i>此过程可能需要30秒到2分钟，请耐心等待...
                                    </p>
                                    <p class="mt-2 mb-0 text-muted small">
                                        <strong>提示：</strong>如果超过2分钟仍未完成，可能是服务器性能问题或权限问题。
                                        请检查data目录是否可写，或联系服务器管理员。
                                    </p>
                                </div>
                            </div>
                        </div>
                        
                        <form method="POST" id="installForm">
                            <div class="text-center">
                                <button type="submit" class="btn btn-success btn-lg" id="installBtn">
                                    <i class="fas fa-play me-2"></i>开始安装
                                </button>
                            </div>
                        </form>
                        
                        <script>
                            document.getElementById('installForm').addEventListener('submit', function() {
                                document.getElementById('installBtn').disabled = true;
                                document.getElementById('installProgress').style.display = 'block';
                            });
                        </script>
                    </div>
                </div>
                
                <?php elseif ($step == 6): ?>
                <!-- 步骤6: 安装完成 -->
                <div class="text-center mb-4">
                    <h3><i class="fas fa-check-circle text-success me-2"></i>安装完成</h3>
                    <p class="text-muted">系统安装成功！</p>
                </div>
                
                <div class="row justify-content-center">
                    <div class="col-md-8">
                        <div class="alert alert-success">
                            <h5><i class="fas fa-party-horn me-2"></i>恭喜！</h5>
                            <p>Cloudflare DNS管理系统已成功安装。您现在可以开始使用系统了。</p>
                        </div>
                        
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0"><i class="fas fa-info-circle me-2"></i>重要信息</h6>
                            </div>
                            <div class="card-body">
                                <ul class="mb-0">
                                    <li>管理员用户名: <strong><?php echo htmlspecialchars($_SESSION['install_admin']['username'] ?? ''); ?></strong></li>
                                    <li>请妥善保管管理员密码</li>
                                    <li>建议删除或重命名 <code>install.php</code> 文件以提高安全性</li>
                                    <li>首次使用前请在管理后台配置Cloudflare域名</li>
                                </ul>
                            </div>
                        </div>
                        
                        <div class="text-center mt-4">
                            <a href="admin/login.php" class="btn btn-primary btn-lg me-2">
                                <i class="fas fa-sign-in-alt me-2"></i>管理员登录
                            </a>
                            <a href="user/login.php" class="btn btn-outline-primary btn-lg">
                                <i class="fas fa-users me-2"></i>用户登录
                            </a>
                        </div>
                    </div>
                </div>
                <?php endif; ?>
            </div>
        </div>
    </div>
    
    <script src="assets/js/bootstrap.bundle.min.js"></script>
</body>
</html>