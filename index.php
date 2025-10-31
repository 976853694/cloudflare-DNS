<?php
/**
 * 项目主页 - 现代化仪表盘风格
 * 前缀查询和DNS管理入口
 */

session_start();

// 检查是否已安装
if (!file_exists('data/install.lock')) {
    header("Location: install.php");
    exit;
}

// 获取系统设置
require_once 'config/database.php';
require_once 'includes/functions.php';

$db = Database::getInstance()->getConnection();
$site_name = getSetting('site_name', 'Cloudflare DNS管理系统');
$allow_registration = getSetting('allow_registration', 1);

// 检查用户登录状态
$is_logged_in = isset($_SESSION['user_logged_in']) && $_SESSION['user_logged_in'];
$user_info = null;
if ($is_logged_in) {
    $user_info = $db->querySingle("SELECT * FROM users WHERE id = {$_SESSION['user_id']}", true);
    $_SESSION['user_points'] = $user_info['points'];
}

// 处理前缀查询
$query_result = null;
$query_prefix = '';
$domain_results = [];
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['check_prefix'])) {
    $query_prefix = strtolower(trim($_POST['prefix']));
    if ($query_prefix) {
        // 检查前缀是否被禁用
        $stmt = $db->prepare("SELECT COUNT(*) FROM blocked_prefixes WHERE prefix = ? AND is_active = 1");
        $stmt->bindValue(1, $query_prefix, SQLITE3_TEXT);
        $result = $stmt->execute();
        $blocked = $result->fetchArray(SQLITE3_NUM)[0];
        
        if ($blocked) {
            $query_result = ['status' => 'blocked', 'message' => '该前缀已被管理员禁用'];
        } else {
            // 获取所有可用域名
            $domains_stmt = $db->prepare("SELECT id, domain_name FROM domains WHERE status = 1 ORDER BY domain_name");
            $domains_result = $domains_stmt->execute();
            
            while ($domain = $domains_result->fetchArray(SQLITE3_ASSOC)) {
                // 检查该前缀在此域名下是否已被使用
                $used_stmt = $db->prepare("SELECT COUNT(*) FROM dns_records WHERE subdomain = ? AND domain_id = ? AND status = 1");
                $used_stmt->bindValue(1, $query_prefix, SQLITE3_TEXT);
                $used_stmt->bindValue(2, $domain['id'], SQLITE3_INTEGER);
                $used_result = $used_stmt->execute();
                $is_used = $used_result->fetchArray(SQLITE3_NUM)[0] > 0;
                
                $domain_results[] = [
                    'domain' => $domain['domain_name'],
                    'domain_id' => $domain['id'],
                    'available' => !$is_used,
                    'full_domain' => $query_prefix . '.' . $domain['domain_name']
                ];
            }
            
            // 计算总体状态
            $available_count = count(array_filter($domain_results, function($d) { return $d['available']; }));
            $total_count = count($domain_results);
            
            if ($available_count == 0) {
                $query_result = ['status' => 'used', 'message' => '该前缀在所有域名下都已被使用'];
            } elseif ($available_count == $total_count) {
                $query_result = ['status' => 'available', 'message' => '该前缀在所有域名下都可用'];
            } else {
                $query_result = ['status' => 'partial', 'message' => "该前缀在 {$available_count}/{$total_count} 个域名下可用"];
            }
        }
    }
}

// 获取统计信息
$stats = [
    'total_users' => $db->querySingle("SELECT COUNT(*) FROM users"),
    'total_domains' => $db->querySingle("SELECT COUNT(*) FROM domains WHERE status = 1"),
    'total_records' => $db->querySingle("SELECT COUNT(*) FROM dns_records WHERE status = 1"),
    'active_today' => $db->querySingle("SELECT COUNT(DISTINCT user_id) FROM dns_records WHERE DATE(created_at) = DATE('now')")
];

// 获取所有域名及到期时间
$domains_with_expiration = [];
$domains_query = $db->query("SELECT domain_name, expiration_time FROM domains WHERE status = 1 ORDER BY expiration_time ASC, domain_name ASC");
while ($domain = $domains_query->fetchArray(SQLITE3_ASSOC)) {
    $domains_with_expiration[] = $domain;
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars($site_name); ?></title>
    <meta name="description" content="专业的Cloudflare DNS记录管理系统，支持多域名管理、积分系统、卡密充值等功能">
    <meta name="keywords" content="Cloudflare,DNS,域名管理,DNS记录,子域名分发">
    
    <!-- Bootstrap CSS -->
    <link href="assets/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link href="assets/css/fontawesome.min.css" rel="stylesheet">
    <!-- White Theme CSS -->
    <link href="assets/css/white-theme.css" rel="stylesheet">
    
    <style>
        body {
            background-color: #f8f9fa;
        }
        
        .hero-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 80px 0 60px;
            margin-bottom: 40px;
        }
        
        .hero-title {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 20px;
        }
        
        .hero-subtitle {
            font-size: 1.25rem;
            margin-bottom: 30px;
            opacity: 0.95;
        }
        
        .query-card {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        .domain-item {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border: 1px solid #dee2e6;
            transition: all 0.3s ease;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .domain-item:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }
        
        .domain-item.available {
            background-color: #d4edda;
            border-color: #28a745;
        }
        
        .domain-item.used {
            background-color: #f8d7da;
            border-color: #dc3545;
        }
        
        .result-message {
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .result-message.success {
            background-color: #d4edda;
            border: 1px solid #28a745;
            color: #155724;
        }
        
        .result-message.warning {
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            color: #856404;
        }
        
        .result-message.danger {
            background-color: #f8d7da;
            border: 1px solid #dc3545;
            color: #721c24;
        }
    </style>
</head>
<body>
    <!-- 导航栏 -->
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary shadow-sm">
        <div class="container">
            <a class="navbar-brand" href="index.php">
                <i class="fas fa-cloud me-2"></i><?php echo htmlspecialchars($site_name); ?>
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <?php if ($is_logged_in): ?>
                        <li class="nav-item">
                            <a class="nav-link" href="user/dashboard.php">
                                <i class="fas fa-tachometer-alt me-1"></i>仪表盘
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="user/records.php">
                                <i class="fas fa-list me-1"></i>我的记录
                            </a>
                        </li>
                        <li class="nav-item">
                            <a class="nav-link" href="user/logout.php">
                                <i class="fas fa-sign-out-alt me-1"></i>退出
                            </a>
                        </li>
                    <?php else: ?>
                        <li class="nav-item">
                            <a class="nav-link" href="user/login.php">
                                <i class="fas fa-sign-in-alt me-1"></i>登录
                            </a>
                        </li>
                        <?php if ($allow_registration): ?>
                        <li class="nav-item">
                            <a class="nav-link" href="user/register_verify.php">
                                <i class="fas fa-user-plus me-1"></i>注册
                            </a>
                        </li>
                        <?php endif; ?>
                    <?php endif; ?>
                </ul>
            </div>
        </div>
    </nav>

    <!-- 英雄区域 -->
    <section class="hero-section">
        <div class="container">
            <div class="row">
                <div class="col-lg-8 mx-auto text-center">
                    <h1 class="hero-title">
                        <i class="fas fa-server me-3"></i>DNS 管理系统
                    </h1>
                    <p class="hero-subtitle">
                        专业的 Cloudflare DNS 记录管理平台<br>
                        轻松管理您的域名解析，支持多域名、多记录类型
                    </p>
                </div>
            </div>
        </div>
    </section>

    <!-- 主要内容 -->
    <div class="container">
        <?php if ($is_logged_in && $user_info): ?>
        <!-- 用户状态卡片 -->
        <div class="card shadow-sm mb-4">
            <div class="card-body">
                <div class="row align-items-center">
                    <div class="col-md-8">
                        <h5 class="mb-2">
                            <i class="fas fa-user-circle me-2 text-primary"></i>
                            欢迎回来，<?php echo htmlspecialchars($user_info['username']); ?>！
                        </h5>
                        <p class="text-muted mb-0">
                            <i class="fas fa-coins me-1"></i>当前积分: <strong><?php echo $user_info['points']; ?></strong>
                        </p>
                    </div>
                    <div class="col-md-4 text-md-end mt-3 mt-md-0">
                        <a href="user/dashboard.php" class="btn btn-primary">
                            <i class="fas fa-tachometer-alt me-2"></i>进入仪表盘
                        </a>
                    </div>
                </div>
            </div>
        </div>
        <?php endif; ?>

        <!-- 前缀查询卡片 -->
        <div class="query-card">
            <h3 class="mb-4">
                <i class="fas fa-search me-2 text-primary"></i>前缀可用性查询
            </h3>
            <form method="POST" action="">
                <div class="row">
                    <div class="col-md-9 mb-3 mb-md-0">
                        <input type="text" name="prefix" class="form-control form-control-lg" 
                               placeholder="请输入要查询的子域名前缀（例如：blog, www, api）" 
                               value="<?php echo htmlspecialchars($query_prefix); ?>" required>
                        <small class="form-text text-muted">
                            <i class="fas fa-info-circle me-1"></i>只能使用小写字母、数字和连字符
                        </small>
                    </div>
                    <div class="col-md-3">
                        <button type="submit" name="check_prefix" class="btn btn-primary btn-lg w-100">
                            <i class="fas fa-search me-2"></i>查询
                        </button>
                    </div>
                </div>
            </form>

            <?php if ($query_result): ?>
            <!-- 查询结果 -->
            <div class="mt-4">
                <?php
                $alert_class = 'success';
                if ($query_result['status'] == 'used') $alert_class = 'warning';
                if ($query_result['status'] == 'blocked') $alert_class = 'danger';
                if ($query_result['status'] == 'partial') $alert_class = 'info';
                ?>
                <div class="alert alert-<?php echo $alert_class; ?>" role="alert">
                    <h5 class="alert-heading">
                        <?php if ($query_result['status'] == 'available'): ?>
                            <i class="fas fa-check-circle me-2"></i>前缀可用
                        <?php elseif ($query_result['status'] == 'partial'): ?>
                            <i class="fas fa-info-circle me-2"></i>部分可用
                        <?php elseif ($query_result['status'] == 'used'): ?>
                            <i class="fas fa-exclamation-triangle me-2"></i>前缀已被使用
                        <?php else: ?>
                            <i class="fas fa-ban me-2"></i>前缀被禁用
                        <?php endif; ?>
                    </h5>
                    <p class="mb-0"><?php echo htmlspecialchars($query_result['message']); ?></p>
                </div>

                <?php if (!empty($domain_results)): ?>
                <h5 class="mb-3">域名详情：</h5>
                <div style="max-height: 400px; overflow-y: auto;">
                    <?php foreach ($domain_results as $result): ?>
                    <div class="domain-item <?php echo $result['available'] ? 'available' : 'used'; ?>">
                        <div>
                            <strong><?php echo htmlspecialchars($result['full_domain']); ?></strong>
                            <span class="ms-3">
                                <?php if ($result['available']): ?>
                                    <span class="badge bg-success">
                                        <i class="fas fa-check me-1"></i>可用
                                    </span>
                                <?php else: ?>
                                    <span class="badge bg-danger">
                                        <i class="fas fa-times me-1"></i>已被使用
                                    </span>
                                <?php endif; ?>
                            </span>
                        </div>
                        <div>
                            <?php if ($result['available']): ?>
                                <?php if ($is_logged_in): ?>
                                    <a href="user/records.php?domain_id=<?php echo $result['domain_id']; ?>&subdomain=<?php echo urlencode($query_prefix); ?>" 
                                       class="btn btn-sm btn-success">
                                        <i class="fas fa-plus me-1"></i>添加记录
                                    </a>
                                <?php else: ?>
                                    <a href="user/login.php" class="btn btn-sm btn-primary">
                                        <i class="fas fa-sign-in-alt me-1"></i>登录后添加
                                    </a>
                                <?php endif; ?>
                            <?php endif; ?>
                        </div>
                    </div>
                    <?php endforeach; ?>
                </div>
                <?php endif; ?>
            </div>
            <?php endif; ?>
        </div>

        <!-- 系统统计 -->
        <div class="row mb-4">
            <div class="col-lg-3 col-md-6 mb-4">
                <div class="card border-left-primary shadow h-100 py-2">
                    <div class="card-body">
                        <div class="row no-gutters align-items-center">
                            <div class="col mr-2">
                                <div class="text-xs font-weight-bold text-primary text-uppercase mb-1">总用户数</div>
                                <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $stats['total_users']; ?></div>
                            </div>
                            <div class="col-auto">
                                <i class="fas fa-users fa-2x text-gray-300"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-3 col-md-6 mb-4">
                <div class="card border-left-success shadow h-100 py-2">
                    <div class="card-body">
                        <div class="row no-gutters align-items-center">
                            <div class="col mr-2">
                                <div class="text-xs font-weight-bold text-success text-uppercase mb-1">可用域名</div>
                                <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $stats['total_domains']; ?></div>
                            </div>
                            <div class="col-auto">
                                <i class="fas fa-globe fa-2x text-gray-300"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-3 col-md-6 mb-4">
                <div class="card border-left-info shadow h-100 py-2">
                    <div class="card-body">
                        <div class="row no-gutters align-items-center">
                            <div class="col mr-2">
                                <div class="text-xs font-weight-bold text-info text-uppercase mb-1">DNS记录数</div>
                                <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $stats['total_records']; ?></div>
                            </div>
                            <div class="col-auto">
                                <i class="fas fa-list fa-2x text-gray-300"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-lg-3 col-md-6 mb-4">
                <div class="card border-left-warning shadow h-100 py-2">
                    <div class="card-body">
                        <div class="row no-gutters align-items-center">
                            <div class="col mr-2">
                                <div class="text-xs font-weight-bold text-warning text-uppercase mb-1">今日活跃</div>
                                <div class="h5 mb-0 font-weight-bold text-gray-800"><?php echo $stats['active_today']; ?></div>
                            </div>
                            <div class="col-auto">
                                <i class="fas fa-chart-line fa-2x text-gray-300"></i>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 域名到期时间 -->
        <?php if (!empty($domains_with_expiration)): ?>
        <div class="card shadow-sm mb-4">
            <div class="card-header bg-white">
                <h5 class="mb-0">
                    <i class="fas fa-calendar-alt me-2 text-primary"></i>域名到期时间
                </h5>
            </div>
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>域名</th>
                                <th>到期时间</th>
                                <th>剩余天数</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($domains_with_expiration as $domain): ?>
                            <tr>
                                <td><strong><?php echo htmlspecialchars($domain['domain_name']); ?></strong></td>
                                <td><?php echo $domain['expiration_time'] ? date('Y-m-d', strtotime($domain['expiration_time'])) : '永久'; ?></td>
                                <td>
                                    <?php 
                                    if ($domain['expiration_time']) {
                                        $days_left = (strtotime($domain['expiration_time']) - time()) / 86400;
                                        if ($days_left < 30) {
                                            echo '<span class="badge bg-danger">' . round($days_left) . ' 天</span>';
                                        } elseif ($days_left < 90) {
                                            echo '<span class="badge bg-warning">' . round($days_left) . ' 天</span>';
                                        } else {
                                            echo '<span class="badge bg-success">' . round($days_left) . ' 天</span>';
                                        }
                                    } else {
                                        echo '<span class="badge bg-info">永久</span>';
                                    }
                                    ?>
                                </td>
                            </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        <?php endif; ?>
    </div>

    <!-- 页脚 -->
    <footer class="bg-white border-top mt-5 py-4">
        <div class="container text-center text-muted">
            <p class="mb-0">&copy; <?php echo date('Y'); ?> <?php echo htmlspecialchars($site_name); ?>. All rights reserved.</p>
        </div>
    </footer>

    <!-- Bootstrap JS -->
    <script src="assets/js/jquery.min.js"></script>
    <script src="assets/js/bootstrap.bundle.min.js"></script>
</body>
</html>
