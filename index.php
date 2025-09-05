<?php
/**
 * 项目主页 - 科技风格
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
$user_points = $is_logged_in ? $_SESSION['user_points'] : 0;

// 处理前缀查询
$query_result = null;
$query_prefix = '';
$domain_results = [];
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['check_prefix'])) {
    $query_prefix = trim($_POST['prefix']);
    if ($query_prefix) {
        // 检查前缀是否被禁用
        $stmt = $db->prepare("SELECT COUNT(*) FROM blocked_prefixes WHERE prefix = ? AND is_active = 1");
        $stmt->execute([$query_prefix]);
        $blocked = $stmt->fetchColumn();
        
        if ($blocked) {
            $query_result = ['status' => 'blocked', 'message' => '该前缀已被管理员禁用'];
        } else {
            // 获取所有可用域名
            $domains_stmt = $db->query("SELECT id, domain_name FROM domains WHERE status = 1 ORDER BY domain_name");
            
            while ($domain = $domains_stmt->fetch(PDO::FETCH_ASSOC)) {
                // 检查该前缀在此域名下是否已被使用
                $used_stmt = $db->prepare("SELECT COUNT(*) FROM dns_records WHERE subdomain = ? AND domain_id = ? AND status = 1");
                $used_stmt->execute([$query_prefix, $domain['id']]);
                $is_used = $used_stmt->fetchColumn() > 0;
                
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
    'total_users' => $db->query("SELECT COUNT(*) FROM users")->fetchColumn(),
    'total_domains' => $db->query("SELECT COUNT(*) FROM domains WHERE status = 1")->fetchColumn(),
    'total_records' => $db->query("SELECT COUNT(*) FROM dns_records WHERE status = 1")->fetchColumn(),
    'active_today' => $db->query("SELECT COUNT(DISTINCT user_id) FROM dns_records WHERE DATE(created_at) = CURDATE()")->fetchColumn()
];
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars($site_name); ?></title>
    <meta name="description" content="专业的Cloudflare DNS记录管理系统，支持多域名管理、积分系统、卡密充值等功能">
    <meta name="keywords" content="Cloudflare,DNS,域名管理,DNS记录,子域名分发">
    
    <link href="assets/css/bootstrap.min.css" rel="stylesheet">
    <link href="assets/css/fontawesome.min.css" rel="stylesheet">
    
    <style>
        :root {
            --primary-color: #00d4ff;
            --secondary-color: #0099cc;
            --accent-color: #ff6b6b;
            --dark-bg: #0a0e27;
            --darker-bg: #050816;
            --card-bg: rgba(255, 255, 255, 0.05);
            --text-primary: #ffffff;
            --text-secondary: #b8c5d6;
            --glow-color: rgba(0, 212, 255, 0.3);
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', 'Segoe UI', sans-serif;
            background: var(--dark-bg);
            color: var(--text-primary);
            overflow-x: hidden;
        }
        
        /* 动态背景 */
        .bg-animation {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            background: linear-gradient(45deg, var(--dark-bg), var(--darker-bg));
        }
        
        .bg-animation::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: 
                radial-gradient(circle at 20% 80%, rgba(0, 212, 255, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(255, 107, 107, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(0, 153, 204, 0.05) 0%, transparent 50%);
            animation: float 20s ease-in-out infinite;
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(180deg); }
        }
        
        /* 导航栏 */
        .navbar {
            background: rgba(10, 14, 39, 0.9) !important;
            backdrop-filter: blur(20px);
            border-bottom: 1px solid rgba(0, 212, 255, 0.2);
            padding: 1rem 0;
        }
        
        .navbar-brand {
            font-weight: 700;
            font-size: 1.5rem;
            color: var(--primary-color) !important;
            text-shadow: 0 0 10px var(--glow-color);
        }
        
        .navbar-nav .nav-link {
            color: var(--text-secondary) !important;
            font-weight: 500;
            margin: 0 0.5rem;
            transition: all 0.3s ease;
            position: relative;
        }
        
        .navbar-nav .nav-link:hover {
            color: var(--primary-color) !important;
            text-shadow: 0 0 5px var(--glow-color);
        }
        
        .navbar-nav .nav-link::after {
            content: '';
            position: absolute;
            bottom: -5px;
            left: 0;
            width: 0;
            height: 2px;
            background: var(--primary-color);
            transition: width 0.3s ease;
        }
        
        .navbar-nav .nav-link:hover::after {
            width: 100%;
        }
        
        /* 英雄区域 */
        .hero-section {
            min-height: 100vh;
            display: flex;
            align-items: center;
            position: relative;
            padding: 6rem 0 2rem 0;
        }
        
        .hero-content {
            position: relative;
            z-index: 2;
        }
        
        .hero-title {
            font-size: clamp(2.5rem, 5vw, 4rem);
            font-weight: 800;
            margin-bottom: 1.5rem;
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1.2;
        }
        
        .hero-subtitle {
            font-size: 1.25rem;
            color: var(--text-secondary);
            margin-bottom: 2rem;
            line-height: 1.6;
        }
        
        /* 卡片通用样式 */
        .card-modern {
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(0, 212, 255, 0.15);
            border-radius: 24px;
            padding: 2rem;
            box-shadow: 
                0 8px 32px rgba(0, 0, 0, 0.3),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }
        
        .card-modern::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--primary-color), transparent);
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .card-modern:hover {
            transform: translateY(-8px);
            box-shadow: 
                0 20px 60px rgba(0, 0, 0, 0.4),
                0 0 40px rgba(0, 212, 255, 0.1),
                inset 0 1px 0 rgba(255, 255, 255, 0.2);
            border-color: rgba(0, 212, 255, 0.4);
        }
        
        .card-modern:hover::before {
            opacity: 1;
        }
        
        /* 查询卡片 */
        .query-card {
            margin: 2rem 0;
        }
        
        .query-form {
            display: flex;
            gap: 1rem;
            align-items: end;
        }
        
        .form-control {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(0, 212, 255, 0.3);
            border-radius: 10px;
            color: var(--text-primary);
            padding: 0.75rem 1rem;
            font-size: 1.1rem;
            transition: all 0.3s ease;
        }
        
        .form-control:focus {
            background: rgba(255, 255, 255, 0.15);
            border-color: var(--primary-color);
            box-shadow: 0 0 20px var(--glow-color);
            color: var(--text-primary);
        }
        
        .form-control::placeholder {
            color: var(--text-secondary);
        }
        
        /* 按钮样式 */
        .btn-primary {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            border: none;
            border-radius: 10px;
            padding: 0.75rem 2rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 212, 255, 0.4);
        }
        
        .btn-primary::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.5s ease;
        }
        
        .btn-primary:hover::before {
            left: 100%;
        }
        
        .btn-success {
            background: linear-gradient(135deg, #00ff88, #00cc6a);
            border: none;
            border-radius: 10px;
            padding: 0.75rem 2rem;
            font-weight: 600;
            color: var(--dark-bg);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, var(--accent-color), #ff4757);
            border: none;
            border-radius: 10px;
            padding: 0.75rem 2rem;
            font-weight: 600;
        }
        
        /* 结果显示 */
        .result-card {
            margin-top: 1.5rem;
            padding: 1.5rem;
            border-radius: 16px;
            border-left: 4px solid;
            animation: slideInUp 0.5s ease;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
            position: relative;
            overflow: hidden;
        }
        
        .result-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: inherit;
            opacity: 0.8;
            z-index: -1;
        }
        
        .result-available {
            background: rgba(0, 255, 136, 0.15);
            border-left-color: #00ff88;
            color: #00ff88;
            border: 1px solid rgba(0, 255, 136, 0.3);
        }
        
        .result-used {
            background: rgba(255, 193, 7, 0.15);
            border-left-color: #ffc107;
            color: #ffc107;
            border: 1px solid rgba(255, 193, 7, 0.3);
        }
        
        .result-blocked {
            background: rgba(255, 107, 107, 0.15);
            border-left-color: var(--accent-color);
            color: var(--accent-color);
            border: 1px solid rgba(255, 107, 107, 0.3);
        }
        
        .result-partial {
            background: rgba(255, 193, 7, 0.15);
            border-left-color: #ffc107;
            color: #ffc107;
            border: 1px solid rgba(255, 193, 7, 0.3);
        }
        
        /* 域名列表样式 */
        .domain-list {
            margin-top: 1rem;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .domain-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
            border-radius: 12px;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .domain-item.available {
            background: rgba(0, 255, 136, 0.1);
            border-color: rgba(0, 255, 136, 0.3);
        }
        
        .domain-item.used {
            background: rgba(255, 107, 107, 0.1);
            border-color: rgba(255, 107, 107, 0.3);
        }
        
        .domain-item:hover {
            transform: translateX(5px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }
        
        .domain-name {
            font-family: 'Courier New', monospace;
            font-weight: 600;
            font-size: 0.95rem;
        }
        
        .domain-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            font-weight: 500;
        }
        
        .domain-status.available {
            color: #00ff88;
        }
        
        .domain-status.used {
            color: var(--accent-color);
        }
        
        .domain-actions {
            display: flex;
            gap: 0.5rem;
        }
        
        .btn-mini {
            padding: 0.4rem 0.8rem;
            font-size: 0.8rem;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
        }
        
        .btn-mini.btn-add {
            background: linear-gradient(135deg, #00ff88, #00cc6a);
            color: var(--dark-bg);
        }
        
        .btn-mini.btn-add:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 255, 136, 0.4);
            color: var(--dark-bg);
        }
        
        .btn-mini.btn-login {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
        }
        
        .btn-mini.btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 212, 255, 0.4);
            color: white;
        }
        
        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        /* 统计卡片 */
        .stats-section {
            padding: 4rem 0;
            margin-top: -2rem;
        }
        
        .stat-card {
            text-align: center;
            height: 100%;
            padding: 2.5rem 1.5rem;
            position: relative;
        }
        
        .stat-card::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 60px;
            height: 3px;
            background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
            border-radius: 2px;
            opacity: 0;
            transition: all 0.3s ease;
        }
        
        .stat-card:hover::after {
            opacity: 1;
            width: 80px;
        }
        
        .stat-icon {
            font-size: 3rem;
            color: var(--primary-color);
            margin-bottom: 1rem;
            text-shadow: 0 0 20px var(--glow-color);
        }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: 800;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }
        
        .stat-label {
            color: var(--text-secondary);
            font-weight: 500;
        }
        
        /* 用户状态卡片 */
        .user-status {
            margin-bottom: 2rem;
            padding: 2rem;
            border-radius: 24px;
            background: linear-gradient(135deg, 
                rgba(0, 212, 255, 0.15) 0%, 
                rgba(255, 107, 107, 0.08) 100%);
            border: 1px solid rgba(0, 212, 255, 0.3);
            backdrop-filter: blur(20px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
            position: relative;
            overflow: hidden;
        }
        
        .user-status::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
        }
        
        .user-info-header {
            display: flex;
            align-items: center;
            margin-bottom: 1.5rem;
        }
        
        .user-avatar {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            font-weight: 700;
            color: white;
            margin-right: 1.5rem;
            box-shadow: 0 8px 24px rgba(0, 212, 255, 0.3);
            position: relative;
        }
        
        .user-avatar::after {
            content: '';
            position: absolute;
            inset: -3px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--primary-color), var(--accent-color));
            z-index: -1;
            opacity: 0.3;
        }
        
        .user-details h5 {
            color: var(--text-primary);
            font-weight: 600;
            margin-bottom: 0.5rem;
            font-size: 1.25rem;
        }
        
        .user-meta {
            display: flex;
            gap: 1rem;
            align-items: center;
            margin-bottom: 1.5rem;
        }
        
        .points-badge {
            background: linear-gradient(135deg, #00ff88, #00cc6a);
            color: var(--dark-bg);
            padding: 0.6rem 1.2rem;
            border-radius: 25px;
            font-weight: 700;
            font-size: 0.95rem;
            box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .status-badge {
            background: rgba(0, 212, 255, 0.2);
            color: var(--primary-color);
            padding: 0.4rem 0.8rem;
            border-radius: 15px;
            font-size: 0.85rem;
            font-weight: 500;
            border: 1px solid rgba(0, 212, 255, 0.3);
        }
        
        .user-actions {
            display: flex;
            gap: 1rem;
            justify-content: space-between;
            align-items: center;
        }
        
        .btn-dashboard {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            border: none;
            border-radius: 12px;
            padding: 0.8rem 1.5rem;
            font-weight: 600;
            color: white;
            text-decoration: none;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            box-shadow: 0 6px 20px rgba(0, 212, 255, 0.3);
        }
        
        .btn-dashboard:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0, 212, 255, 0.4);
            color: white;
        }
        
        .quick-stats {
            display: flex;
            gap: 1.5rem;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        
        .quick-stat {
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }
        
        .quick-stat i {
            color: var(--primary-color);
        }
        
        /* 卡片间距优化 */
        .row.g-4 > * {
            margin-bottom: 1.5rem;
        }
        
        .container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        
        /* 响应式设计 */
        @media (max-width: 768px) {
            .hero-title {
                font-size: 2.5rem;
            }
            
            .hero-section {
                padding: 5rem 0 1rem 0;
            }
            
            .query-form {
                flex-direction: column;
                align-items: stretch;
            }
            
            .query-form .btn {
                margin-top: 1rem;
            }
            
            .card-modern {
                padding: 1.5rem;
                border-radius: 20px;
            }
            
            .stat-card {
                padding: 2rem 1rem;
            }
            
            .stats-section {
                padding: 3rem 0;
            }
        }
        
        @media (max-width: 576px) {
            .hero-title {
                font-size: 2rem;
            }
            
            .hero-subtitle {
                font-size: 1.1rem;
            }
            
            .card-modern {
                padding: 1.25rem;
                border-radius: 16px;
            }
            
            .user-status {
                padding: 1.5rem;
            }
            
            .user-info-header {
                flex-direction: column;
                text-align: center;
                margin-bottom: 1rem;
            }
            
            .user-avatar {
                margin-right: 0;
                margin-bottom: 1rem;
                width: 60px;
                height: 60px;
                font-size: 1.5rem;
            }
            
            .user-meta {
                flex-direction: column;
                gap: 0.8rem;
                align-items: center;
                text-align: center;
            }
            
            .user-actions {
                flex-direction: column;
                gap: 1rem;
                text-align: center;
            }
            
            .quick-stats {
                justify-content: center;
                gap: 1rem;
            }
            
            .btn-dashboard {
                width: 100%;
                justify-content: center;
            }
            
            .domain-item {
                flex-direction: column;
                align-items: flex-start;
                gap: 0.5rem;
                padding: 1rem;
            }
            
            .domain-name {
                font-size: 0.9rem;
                word-break: break-all;
            }
            
            .domain-item .d-flex {
                width: 100%;
                justify-content: space-between;
            }
            
            .domain-list {
                max-height: 250px;
            }
        }
        
        /* 滚动条样式 */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--darker-bg);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--primary-color);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--secondary-color);
        }
    </style>
</head>
<body>
    <!-- 动态背景 -->
    <div class="bg-animation"></div>
    
    <!-- 导航栏 -->
    <nav class="navbar navbar-expand-lg fixed-top">
        <div class="container">
            <a class="navbar-brand" href="#">
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
                                <i class="fas fa-tachometer-alt me-1"></i>控制台
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
                            <a class="nav-link" href="user/login.php">
                                <i class="fas fa-user-plus me-1"></i>注册
                            </a>
                        </li>
                        <?php endif; ?>
                    <?php endif; ?>
                    <li class="nav-item">
                        <a class="nav-link" href="admin/login.php">
                            <i class="fas fa-cog me-1"></i>管理
                        </a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>
    
    <!-- 主要内容 -->
    <main class="hero-section">
        <div class="container">
            <div class="row align-items-center">
                <div class="col-lg-6">
                    <div class="hero-content">
                        <h1 class="hero-title">
                            智能DNS解析
                            <br>科技驱动未来
                        </h1>
                        <p class="hero-subtitle">
                            基于Cloudflare的专业DNS管理平台，提供高速、安全、稳定的域名解析服务。
                            支持多种记录类型，实时生效，让您的网站触手可及。
                        </p>
                        
                        <?php if ($is_logged_in): ?>
                        <!-- 已登录用户状态 -->
                        <div class="user-status">
                            <!-- 用户信息头部 -->
                            <div class="user-info-header">
                                <div class="user-avatar">
                                    <?php echo strtoupper(substr($_SESSION['username'], 0, 1)); ?>
                                </div>
                                <div class="user-details">
                                    <h5>欢迎回来，<?php echo htmlspecialchars($_SESSION['username']); ?></h5>
                                    <div class="status-badge">
                                        <i class="fas fa-circle me-1" style="font-size: 0.6rem;"></i>在线
                                    </div>
                                </div>
                            </div>
                            
                            <!-- 用户元信息 -->
                            <div class="user-meta">
                                <div class="points-badge">
                                    <i class="fas fa-coins"></i>
                                    积分: <?php echo $user_points; ?>
                                </div>
                                <div class="quick-stats">
                                    <div class="quick-stat">
                                        <i class="fas fa-list"></i>
                                        <?php 
                                        $stmt = $db->prepare("SELECT COUNT(*) FROM dns_records WHERE user_id = ? AND status = 1");
                                        $stmt->execute([$_SESSION['user_id']]);
                                        $user_records = $stmt->fetchColumn();
                                        echo $user_records; 
                                        ?> 记录
                                    </div>
                                    <div class="quick-stat">
                                        <i class="fas fa-clock"></i>
                                        今日活跃
                                    </div>
                                </div>
                            </div>
                            
                            <!-- 操作按钮 -->
                            <div class="user-actions">
                                <a href="user/dashboard.php" class="btn-dashboard">
                                    <i class="fas fa-tachometer-alt"></i>
                                    进入控制台
                                </a>
                                <div class="quick-stats">
                                    <div class="quick-stat">
                                        <i class="fas fa-calendar-day"></i>
                                        <?php echo date('m月d日'); ?>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <?php endif; ?>
                    </div>
                </div>
                
                <div class="col-lg-6">
                    <!-- 前缀查询卡片 -->
                    <div class="query-card card-modern">
                        <h3 class="mb-4">
                            <i class="fas fa-search me-2"></i>前缀可用性查询
                        </h3>
                        <p class="text-secondary mb-4">输入您想要的子域名前缀，我们将为您检查是否可用</p>
                        
                        <form method="POST" class="query-form">
                            <div class="flex-grow-1">
                                <label for="prefix" class="form-label">子域名前缀</label>
                                <input type="text" 
                                       class="form-control" 
                                       id="prefix" 
                                       name="prefix" 
                                       placeholder="例如: blog, api, www" 
                                       value="<?php echo htmlspecialchars($query_prefix); ?>"
                                       pattern="[a-zA-Z0-9-]+"
                                       title="只能包含字母、数字和连字符"
                                       required>
                            </div>
                            <button type="submit" name="check_prefix" class="btn btn-primary">
                                <i class="fas fa-search me-1"></i>查询
                            </button>
                        </form>
                        
                        <?php if ($query_result): ?>
                        <div class="result-card result-<?php echo $query_result['status']; ?>">
                            <div class="d-flex align-items-center mb-3">
                                <div class="me-3">
                                    <?php if ($query_result['status'] === 'available'): ?>
                                        <i class="fas fa-check-circle fa-2x"></i>
                                    <?php elseif ($query_result['status'] === 'used'): ?>
                                        <i class="fas fa-exclamation-triangle fa-2x"></i>
                                    <?php elseif ($query_result['status'] === 'partial'): ?>
                                        <i class="fas fa-info-circle fa-2x"></i>
                                    <?php else: ?>
                                        <i class="fas fa-times-circle fa-2x"></i>
                                    <?php endif; ?>
                                </div>
                                <div class="flex-grow-1">
                                    <h5 class="mb-1">
                                        <?php echo htmlspecialchars($query_prefix); ?>
                                    </h5>
                                    <p class="mb-0"><?php echo htmlspecialchars($query_result['message']); ?></p>
                                </div>
                            </div>
                            
                            <?php if (!empty($domain_results)): ?>
                            <div class="domain-list">
                                <h6 class="mb-3">
                                    <i class="fas fa-list me-2"></i>域名可用性详情
                                </h6>
                                <?php foreach ($domain_results as $domain): ?>
                                <div class="domain-item <?php echo $domain['available'] ? 'available' : 'used'; ?>">
                                    <div class="domain-name">
                                        <?php echo htmlspecialchars($domain['full_domain']); ?>
                                    </div>
                                    <div class="d-flex align-items-center gap-2">
                                        <div class="domain-status <?php echo $domain['available'] ? 'available' : 'used'; ?>">
                                            <i class="fas fa-<?php echo $domain['available'] ? 'check' : 'times'; ?>"></i>
                                            <?php echo $domain['available'] ? '可用' : '已用'; ?>
                                        </div>
                                        <?php if ($domain['available']): ?>
                                            <div class="domain-actions">
                                                <?php if ($is_logged_in): ?>
                                                    <a href="user/dashboard.php?prefix=<?php echo urlencode($query_prefix); ?>&domain_id=<?php echo $domain['domain_id']; ?>" 
                                                       class="btn-mini btn-add">
                                                        <i class="fas fa-plus"></i>添加
                                                    </a>
                                                <?php else: ?>
                                                    <a href="user/login.php" class="btn-mini btn-login">
                                                        <i class="fas fa-sign-in-alt"></i>登录
                                                    </a>
                                                <?php endif; ?>
                                            </div>
                                        <?php endif; ?>
                                    </div>
                                </div>
                                <?php endforeach; ?>
                            </div>
                            <?php endif; ?>
                        </div>
                        <?php endif; ?>
                        
                        <?php if (!$is_logged_in): ?>
                        <div class="mt-4 text-center">
                            <p class="text-secondary mb-3">还没有账户？</p>
                            <div class="d-flex gap-2 justify-content-center">
                                <a href="user/login.php" class="btn btn-primary">
                                    <i class="fas fa-sign-in-alt me-1"></i>立即登录
                                </a>
                                <?php if ($allow_registration): ?>
                                <a href="user/login.php" class="btn btn-success">
                                    <i class="fas fa-user-plus me-1"></i>免费注册
                                </a>
                                <?php endif; ?>
                            </div>
                        </div>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>
    </main>
    
    <!-- 统计数据 -->
    <section class="stats-section">
        <div class="container">
            <div class="row g-4">
                <div class="col-md-3 col-sm-6">
                    <div class="stat-card card-modern">
                        <div class="stat-icon">
                            <i class="fas fa-users"></i>
                        </div>
                        <div class="stat-number"><?php echo number_format($stats['total_users']); ?></div>
                        <div class="stat-label">注册用户</div>
                    </div>
                </div>
                <div class="col-md-3 col-sm-6">
                    <div class="stat-card card-modern">
                        <div class="stat-icon">
                            <i class="fas fa-globe"></i>
                        </div>
                        <div class="stat-number"><?php echo number_format($stats['total_domains']); ?></div>
                        <div class="stat-label">可用域名</div>
                    </div>
                </div>
                <div class="col-md-3 col-sm-6">
                    <div class="stat-card card-modern">
                        <div class="stat-icon">
                            <i class="fas fa-list"></i>
                        </div>
                        <div class="stat-number"><?php echo number_format($stats['total_records']); ?></div>
                        <div class="stat-label">DNS记录</div>
                    </div>
                </div>
                <div class="col-md-3 col-sm-6">
                    <div class="stat-card card-modern">
                        <div class="stat-icon">
                            <i class="fas fa-chart-line"></i>
                        </div>
                        <div class="stat-number"><?php echo number_format($stats['active_today']); ?></div>
                        <div class="stat-label">今日活跃</div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    
    <script src="assets/js/bootstrap.bundle.min.js"></script>
    <script>
        // 表单验证
        document.getElementById('prefix').addEventListener('input', function(e) {
            const value = e.target.value;
            const regex = /^[a-zA-Z0-9-]*$/;
            
            if (!regex.test(value)) {
                e.target.value = value.replace(/[^a-zA-Z0-9-]/g, '');
            }
        });
        
        // 动态数字动画
        function animateNumbers() {
            const numbers = document.querySelectorAll('.stat-number');
            numbers.forEach(number => {
                const target = parseInt(number.textContent.replace(/,/g, ''));
                const increment = target / 50;
                let current = 0;
                
                const timer = setInterval(() => {
                    current += increment;
                    if (current >= target) {
                        current = target;
                        clearInterval(timer);
                    }
                    number.textContent = Math.floor(current).toLocaleString();
                }, 30);
            });
        }
        
        // 页面加载完成后执行动画
        document.addEventListener('DOMContentLoaded', function() {
            // 延迟执行数字动画
            setTimeout(animateNumbers, 500);
        });
    </script>
</body>
</html>
