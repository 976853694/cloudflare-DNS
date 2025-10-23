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
    
    <link href="assets/css/bootstrap.min.css" rel="stylesheet">
    <link href="assets/css/fontawesome.min.css" rel="stylesheet">
    
    <style>
        :root {
            /* 赛博朋克二次元配色方案 */
            --neon-cyan: #00f5ff;
            --neon-pink: #ff006e;
            --neon-purple: #bf00ff;
            --neon-blue: #0080ff;
            --neon-green: #00ff88;
            --neon-yellow: #ffd700;
            --cyber-dark: #0a0e27;
            --cyber-darker: #050814;
            --cyber-card: rgba(15, 25, 50, 0.75);
            
            /* 主要配色 */
            --primary-color: #00f5ff;
            --secondary-color: #bf00ff;
            --accent-color: #ff006e;
            --success-color: #00ff88;
            --warning-color: #ffaa00;
            --danger-color: #ff0055;
            
            /* 文字颜色 */
            --text-primary: #ffffff;
            --text-secondary: #b4c4ff;
            --text-muted: #8896b3;
            --text-glow: #00f5ff;
            --text-white: #ffffff;
            
            /* 毛玻璃背景色 */
            --bg-primary: #0a0e27;
            --bg-glass: rgba(10, 14, 39, 0.65);
            --bg-glass-light: rgba(15, 25, 50, 0.55);
            --bg-glass-dark: rgba(5, 8, 20, 0.85);
            --bg-card: rgba(15, 25, 50, 0.75);
            
            /* 发光阴影效果 - 多层次 */
            --shadow-neon-cyan: 0 0 20px rgba(0, 245, 255, 0.5), 0 0 40px rgba(0, 245, 255, 0.3), 0 0 60px rgba(0, 245, 255, 0.1);
            --shadow-neon-pink: 0 0 20px rgba(255, 0, 110, 0.5), 0 0 40px rgba(255, 0, 110, 0.3), 0 0 60px rgba(255, 0, 110, 0.1);
            --shadow-neon-purple: 0 0 20px rgba(191, 0, 255, 0.5), 0 0 40px rgba(191, 0, 255, 0.3), 0 0 60px rgba(191, 0, 255, 0.1);
            --shadow-cyber: 0 8px 32px rgba(0, 245, 255, 0.2), 0 4px 16px rgba(191, 0, 255, 0.15);
            --shadow-cyber-hover: 0 12px 48px rgba(0, 245, 255, 0.3), 0 6px 24px rgba(191, 0, 255, 0.25);
            --shadow-deep: 0 20px 60px rgba(0, 0, 0, 0.5), 0 10px 30px rgba(0, 245, 255, 0.2);
            
            /* 渐变效果 */
            --gradient-cyber: linear-gradient(135deg, #00f5ff 0%, #bf00ff 50%, #ff006e 100%);
            --gradient-neon: linear-gradient(90deg, #00f5ff, #bf00ff, #ff006e);
            --gradient-matrix: linear-gradient(180deg, rgba(0, 255, 136, 0.1) 0%, transparent 100%);
            --gradient-kawaii: linear-gradient(135deg, #ff006e 0%, #bf00ff 50%, #00f5ff 100%);
            --gradient-magical: linear-gradient(135deg, #ffd700 0%, #ff006e 50%, #bf00ff 100%);
            --gradient-sky: linear-gradient(135deg, #00f5ff 0%, #0080ff 100%);
            --gradient-sunset: linear-gradient(135deg, #ff006e 0%, #ffaa00 100%);
            
            /* 可爱风格阴影 */
            --shadow-kawaii: 0 8px 32px rgba(255, 105, 180, 0.3), 0 4px 16px rgba(221, 160, 221, 0.2);
            --shadow-dreamy: 0 12px 48px rgba(255, 182, 193, 0.4), 0 6px 24px rgba(221, 160, 221, 0.3);
            --shadow-magic: 0 16px 64px rgba(255, 215, 0, 0.3), 0 8px 32px rgba(255, 105, 180, 0.25);
            --shadow-cute: 0 4px 16px rgba(255, 182, 193, 0.3);
            
            /* 可爱配色 */
            --sakura-pink: #ffb7c5;
            --lavender: #e6e6fa;
            --mint: #98fb98;
            --peach: #ffd1dc;
            --sky-blue: #87ceeb;
            --darker-bg: #1a1a2e;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Orbitron', 'Rajdhani', 'Share Tech Mono', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            overflow-x: hidden;
            min-height: 100vh;
            position: relative;
        }
        
        /* 赛博网格背景 */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                repeating-linear-gradient(
                    0deg,
                    rgba(0, 245, 255, 0.05) 0px,
                    transparent 1px,
                    transparent 40px
                ),
                repeating-linear-gradient(
                    90deg,
                    rgba(191, 0, 255, 0.05) 0px,
                    transparent 1px,
                    transparent 40px
                );
            z-index: -2;
            pointer-events: none;
            animation: grid-move 30s linear infinite;
        }
        
        @keyframes grid-move {
            0% { transform: translate(0, 0); }
            100% { transform: translate(40px, 40px); }
        }
        
        /* 科技感动态背景 - 多层次光效 */
        .bg-animation {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            background: 
                radial-gradient(circle at 20% 30%, rgba(0, 245, 255, 0.2) 0%, transparent 40%),
                radial-gradient(circle at 80% 70%, rgba(191, 0, 255, 0.2) 0%, transparent 40%),
                radial-gradient(circle at 50% 50%, rgba(255, 0, 110, 0.15) 0%, transparent 50%);
            animation: pulse-bg 8s ease-in-out infinite;
        }
        
        @keyframes pulse-bg {
            0%, 100% { 
                opacity: 0.6; 
                filter: blur(60px);
            }
            50% { 
                opacity: 0.9; 
                filter: blur(80px);
            }
        }
        
        /* 添加科技粒子效果层 */
        .bg-animation::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(0, 245, 255, 0.1) 1px, transparent 1px),
                radial-gradient(circle at 90% 80%, rgba(255, 0, 110, 0.1) 1px, transparent 1px),
                radial-gradient(circle at 50% 50%, rgba(191, 0, 255, 0.1) 1px, transparent 1px);
            background-size: 300px 300px, 250px 250px, 400px 400px;
            animation: particle-float 20s linear infinite;
        }
        
        @keyframes particle-float {
            0% { transform: translate(0, 0); }
            100% { transform: translate(100px, -100px); }
        }
        
        /* 添加扫描线效果 */
        .bg-animation::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, 
                transparent 0%, 
                rgba(0, 245, 255, 0.8) 50%, 
                transparent 100%);
            box-shadow: 0 0 20px rgba(0, 245, 255, 0.5);
            animation: scan-line 4s linear infinite;
        }
        
        @keyframes scan-line {
            0% { transform: translateY(0); }
            100% { transform: translateY(100vh); }
        }
        
        @keyframes sparkle {
            0% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(180deg); }
            100% { transform: translateY(0) rotate(360deg); }
        }
        
        @keyframes kawaii-float {
            0%, 100% { transform: translateY(0) scale(1); }
            50% { transform: translateY(-10px) scale(1.02); }
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-20px) rotate(180deg); }
        }
        
        /* 赛博朋克导航栏 - 加强毛玻璃效果 */
        .navbar {
            background: var(--bg-glass) !important;
            backdrop-filter: blur(25px) saturate(180%);
            -webkit-backdrop-filter: blur(25px) saturate(180%);
            border-bottom: 1px solid rgba(0, 245, 255, 0.3);
            padding: 1rem 0;
            box-shadow: var(--shadow-cyber), inset 0 1px 0 rgba(255, 255, 255, 0.1);
            position: relative;
            border-radius: 0;
        }
        
        .navbar::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, 
                rgba(0, 245, 255, 0.05) 0%, 
                rgba(191, 0, 255, 0.03) 50%, 
                rgba(255, 0, 110, 0.05) 100%);
            z-index: -1;
        }
        
        .navbar::after {
            content: '';
            position: absolute;
            bottom: -1px;
            left: 0;
            width: 100%;
            height: 2px;
            background: var(--gradient-neon);
            animation: neon-flow 3s linear infinite;
            box-shadow: 0 0 10px rgba(0, 245, 255, 0.5);
        }
        
        @keyframes neon-flow {
            0% { transform: translateX(-100%); opacity: 0; }
            50% { opacity: 1; }
            100% { transform: translateX(100%); opacity: 0; }
        }
        
        .navbar-brand {
            font-weight: 900;
            font-size: 1.8rem;
            background: var(--gradient-cyber);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-shadow: 0 0 20px rgba(0, 245, 255, 0.5);
            position: relative;
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        
        .navbar-brand::before {
            content: '◢';
            position: absolute;
            left: -1.5rem;
            color: var(--primary-color);
            animation: glitch-1 2s infinite;
        }
        
        .navbar-brand::after {
            content: '◣';
            position: absolute;
            right: -1.5rem;
            color: var(--accent-color);
            animation: glitch-2 2s infinite;
        }
        
        @keyframes glitch-1 {
            0%, 100% { opacity: 1; transform: translateX(0); }
            25% { opacity: 0.5; transform: translateX(-5px); }
            75% { opacity: 0.8; transform: translateX(3px); }
        }
        
        @keyframes glitch-2 {
            0%, 100% { opacity: 1; transform: translateX(0); }
            30% { opacity: 0.7; transform: translateX(5px); }
            70% { opacity: 0.9; transform: translateX(-3px); }
        }
        
        @keyframes twinkle {
            0%, 100% { opacity: 1; transform: translateY(-50%) scale(1); }
            50% { opacity: 0.5; transform: translateY(-50%) scale(1.2); }
        }
        
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }
        
        .navbar-nav .nav-link {
            color: var(--text-secondary) !important;
            font-weight: 700;
            margin: 0 0.5rem;
            transition: all 0.3s ease;
            position: relative;
            padding: 0.5rem 1.2rem !important;
            border: 1px solid transparent;
            border-radius: 5px;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-size: 0.9rem;
        }
        
        .navbar-nav .nav-link::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 0;
            height: 100%;
            background: var(--gradient-cyber);
            transition: width 0.3s ease;
            z-index: -1;
            border-radius: 5px;
        }
        
        .navbar-nav .nav-link:hover {
            color: var(--text-primary) !important;
            border-color: var(--primary-color);
            box-shadow: var(--shadow-neon-cyan);
            transform: translateY(-2px);
        }
        
        .navbar-nav .nav-link:hover::before {
            width: 100%;
        }
        
        .navbar-nav .nav-link::after {
            content: '▸';
            position: absolute;
            right: 0.5rem;
            opacity: 0;
            transition: all 0.3s ease;
            color: var(--primary-color);
        }
        
        .navbar-nav .nav-link:hover::after {
            opacity: 1;
            right: 0.3rem;
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
            font-weight: 900;
            margin-bottom: 1.5rem;
            background: var(--gradient-magical);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1.2;
            text-shadow: 3px 3px 6px rgba(255, 105, 180, 0.3);
            position: relative;
            animation: rainbow-text 3s ease-in-out infinite;
        }
        
        .hero-title::before {
            content: '🌸';
            position: absolute;
            left: -3rem;
            top: 0;
            font-size: 2rem;
            animation: petal-fall 4s ease-in-out infinite;
        }
        
        .hero-title::after {
            content: '✨';
            position: absolute;
            right: -3rem;
            top: 0;
            font-size: 2rem;
            animation: sparkle-dance 3s ease-in-out infinite;
        }
        
        .hero-subtitle {
            font-size: 1.25rem;
            color: var(--text-secondary);
            margin-bottom: 2rem;
            line-height: 1.6;
            position: relative;
        }
        
        .hero-subtitle::before {
            content: '💖 ';
            color: var(--primary-color);
        }
        
        .hero-subtitle::after {
            content: ' 💖';
            color: var(--accent-color);
        }
        
        /* 赛博毛玻璃卡片 - 多层次深度 */
        .card-modern {
            background: var(--bg-glass-light);
            backdrop-filter: blur(30px) saturate(150%);
            -webkit-backdrop-filter: blur(30px) saturate(150%);
            border: 1px solid rgba(0, 245, 255, 0.2);
            border-radius: 20px;
            padding: 2.5rem;
            box-shadow: 
                var(--shadow-deep),
                inset 0 1px 0 rgba(255, 255, 255, 0.1),
                inset 0 -1px 0 rgba(0, 0, 0, 0.1);
            transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
            transform-style: preserve-3d;
        }
        
        /* 卡片内部发光边框 */
        .card-modern::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: 20px;
            padding: 1px;
            background: linear-gradient(135deg, 
                rgba(0, 245, 255, 0.5) 0%,
                rgba(191, 0, 255, 0.3) 50%,
                rgba(255, 0, 110, 0.5) 100%);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            opacity: 0;
            transition: opacity 0.5s ease;
            pointer-events: none;
        }
        
        /* 卡片背景纹理 */
        .card-modern::after {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(0, 245, 255, 0.1) 1px, transparent 1px);
            background-size: 50px 50px;
            opacity: 0.3;
            animation: texture-move 20s linear infinite;
            pointer-events: none;
            z-index: 0;
        }
        
        @keyframes texture-move {
            0% { transform: translate(0, 0) rotate(0deg); }
            100% { transform: translate(50px, 50px) rotate(360deg); }
        }
        
        @keyframes rainbow-text {
            0%, 100% { filter: hue-rotate(0deg); }
            50% { filter: hue-rotate(90deg); }
        }
        
        @keyframes petal-fall {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(10px) rotate(180deg); }
        }
        
        @keyframes sparkle-dance {
            0%, 100% { transform: scale(1) rotate(0deg); }
            50% { transform: scale(1.2) rotate(360deg); }
        }
        
        /* 卡片悬停效果 - 3D提升 */
        .card-modern:hover {
            transform: translateY(-15px) translateZ(30px) scale(1.02);
            box-shadow: 
                var(--shadow-cyber-hover),
                0 30px 80px rgba(0, 0, 0, 0.6),
                inset 0 2px 0 rgba(255, 255, 255, 0.2);
            border-color: rgba(0, 245, 255, 0.5);
        }
        
        .card-modern:hover::before {
            opacity: 1;
        }
        
        .card-modern:hover::after {
            opacity: 0.5;
            animation-duration: 10s;
        }
        
        /* 卡片内容层叠 */
        .card-modern > * {
            position: relative;
            z-index: 1;
        }
        
        @keyframes heart-beat {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
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
        
        /* 赛博毛玻璃输入框 */
        .form-control {
            background: rgba(15, 25, 50, 0.5);
            border: 1px solid rgba(0, 245, 255, 0.3);
            border-radius: 15px;
            color: var(--text-primary);
            padding: 1rem 1.5rem;
            font-size: 1.1rem;
            font-weight: 500;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
            backdrop-filter: blur(20px) saturate(150%);
            -webkit-backdrop-filter: blur(20px) saturate(150%);
            position: relative;
            box-shadow: 
                inset 0 1px 0 rgba(255, 255, 255, 0.1),
                0 4px 16px rgba(0, 0, 0, 0.2);
        }
        
        .form-control:focus {
            background: rgba(15, 25, 50, 0.7);
            border-color: var(--primary-color);
            box-shadow: 
                var(--shadow-neon-cyan),
                inset 0 1px 0 rgba(255, 255, 255, 0.2),
                0 0 0 3px rgba(0, 245, 255, 0.1);
            color: var(--text-primary);
            outline: none;
            transform: translateY(-2px);
        }
        
        .form-control::placeholder {
            color: var(--text-muted);
            font-style: italic;
        }
        
        /* 可爱按钮样式 */
        .btn-primary {
            background: var(--gradient-kawaii);
            border: none;
            border-radius: 25px;
            padding: 1rem 2.5rem;
            font-weight: 700;
            color: var(--text-white);
            font-size: 1.1rem;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            box-shadow: var(--shadow-cute);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .btn-primary::before {
            content: '✨';
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            opacity: 0;
            transition: all 0.3s ease;
        }
        
        .btn-primary::after {
            content: '🌟';
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            opacity: 0;
            transition: all 0.3s ease;
        }
        
        .btn-primary:hover {
            transform: translateY(-5px) scale(1.05);
            box-shadow: var(--shadow-magic);
            color: var(--text-white);
            animation: button-glow 0.5s ease-in-out;
        }
        
        .btn-primary:hover::before,
        .btn-primary:hover::after {
            opacity: 1;
        }
        
        .btn-success {
            background: var(--gradient-sky);
            border: none;
            border-radius: 25px;
            padding: 1rem 2rem;
            font-weight: 700;
            color: var(--text-white);
            box-shadow: var(--shadow-cute);
            transition: all 0.3s ease;
            position: relative;
        }
        
        .btn-success::before {
            content: '🌱';
            margin-right: 0.5rem;
        }
        
        .btn-success:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow-magic);
            color: var(--text-white);
        }
        
        .btn-danger {
            background: var(--gradient-sunset);
            border: none;
            border-radius: 25px;
            padding: 1rem 2rem;
            font-weight: 700;
            color: var(--text-white);
            box-shadow: var(--shadow-cute);
            transition: all 0.3s ease;
            position: relative;
        }
        
        .btn-danger::before {
            content: '⚠️';
            margin-right: 0.5rem;
        }
        
        .btn-danger:hover {
            transform: translateY(-3px);
            box-shadow: var(--shadow-magic);
            color: var(--text-white);
        }
        
        @keyframes button-glow {
            0%, 100% { filter: brightness(1); }
            50% { filter: brightness(1.2); }
        }
        
        /* 可爱结果显示 */
        .result-card {
            margin-top: 1.5rem;
            padding: 2rem;
            border-radius: 25px;
            border: 3px solid;
            animation: slideInUp 0.5s ease, result-shimmer 2s ease-in-out infinite;
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            box-shadow: var(--shadow-kawaii);
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
            opacity: 0.95;
            z-index: -1;
        }
        
        .result-available {
            background: rgba(152, 251, 152, 0.2);
            border-color: var(--success-color);
            color: var(--text-primary);
        }
        
        .result-available::after {
            content: '✅ 可用哦~ ';
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.2rem;
            animation: bounce 1s ease-in-out infinite;
        }
        
        .result-used {
            background: rgba(255, 165, 0, 0.2);
            border-color: var(--warning-color);
            color: var(--text-primary);
        }
        
        .result-used::after {
            content: '⚠️ 已被使用 ';
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.2rem;
        }
        
        .result-blocked {
            background: rgba(255, 20, 147, 0.2);
            border-color: var(--danger-color);
            color: var(--text-primary);
        }
        
        .result-blocked::after {
            content: '❌ 被阻止了 ';
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.2rem;
        }
        
        .result-partial {
            background: rgba(255, 182, 193, 0.2);
            border-color: var(--primary-color);
            color: var(--text-primary);
        }
        
        .result-partial::after {
            content: '💫 部分可用 ';
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.2rem;
        }
        
        @keyframes result-shimmer {
            0%, 100% { box-shadow: var(--shadow-kawaii); }
            50% { box-shadow: var(--shadow-magic); }
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
            padding: 1rem 1.5rem;
            margin-bottom: 0.8rem;
            border-radius: 20px;
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            transition: all 0.3s ease;
            border: 2px solid var(--sakura-pink);
            background: rgba(255, 255, 255, 0.8);
            position: relative;
        }
        
        .domain-item::before {
            content: '🌸';
            position: absolute;
            left: -15px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 1.2rem;
            opacity: 0;
            transition: all 0.3s ease;
        }
        
        .domain-item.available {
            background: rgba(152, 251, 152, 0.3);
            border-color: var(--success-color);
        }
        
        .domain-item.used {
            background: rgba(255, 182, 193, 0.3);
            border-color: var(--danger-color);
        }
        
        .domain-item:hover {
            transform: translateX(10px) scale(1.02);
            box-shadow: var(--shadow-kawaii);
            background: rgba(255, 255, 255, 0.95);
        }
        
        .domain-item:hover::before {
            opacity: 1;
            left: -10px;
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
            color: var(--success-color);
            font-weight: 700;
            text-shadow: 1px 1px 2px rgba(50, 205, 50, 0.3);
        }
        
        .domain-status.available::before {
            content: '💚 ';
        }
        
        .domain-status.used {
            color: var(--danger-color);
            font-weight: 700;
            text-shadow: 1px 1px 2px rgba(255, 20, 147, 0.3);
        }
        
        .domain-status.used::before {
            content: '💔 ';
        }
        
        .domain-actions {
            display: flex;
            gap: 0.8rem;
        }
        
        .btn-mini {
            padding: 0.6rem 1.2rem;
            font-size: 0.9rem;
            border-radius: 20px;
            border: none;
            font-weight: 700;
            text-decoration: none;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            box-shadow: var(--shadow-cute);
            position: relative;
        }
        
        .btn-mini.btn-add {
            background: var(--gradient-sky);
            color: var(--text-white);
        }
        
        .btn-mini.btn-add::before {
            content: '➕';
        }
        
        .btn-mini.btn-add:hover {
            transform: translateY(-3px) scale(1.05);
            box-shadow: var(--shadow-magic);
            color: var(--text-white);
        }
        
        .btn-mini.btn-login {
            background: var(--gradient-kawaii);
            color: var(--text-white);
        }
        
        .btn-mini.btn-login::before {
            content: '🔑';
        }
        
        .btn-mini.btn-login:hover {
            transform: translateY(-3px) scale(1.05);
            box-shadow: var(--shadow-magic);
            color: var(--text-white);
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
            font-size: 4rem;
            background: var(--gradient-kawaii);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 1rem;
            animation: icon-bounce 2s ease-in-out infinite;
            filter: drop-shadow(2px 2px 4px rgba(255, 105, 180, 0.3));
        }
        
        .stat-number {
            font-size: 3rem;
            font-weight: 900;
            background: var(--gradient-magical);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .stat-label {
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 1.1rem;
        }
        
        @keyframes icon-bounce {
            0%, 100% { transform: translateY(0) scale(1); }
            50% { transform: translateY(-5px) scale(1.1); }
        }
        
        /* 可爱用户状态卡片 */
        .user-status {
            margin-bottom: 2rem;
            padding: 2.5rem;
            border-radius: 30px;
            background: linear-gradient(135deg, 
                rgba(255, 182, 193, 0.3) 0%, 
                rgba(221, 160, 221, 0.2) 50%,
                rgba(173, 216, 230, 0.3) 100%);
            border: 3px solid var(--primary-color);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            box-shadow: var(--shadow-dreamy);
            position: relative;
            overflow: hidden;
        }
        
        .user-status::before {
            content: '🌈✨💖';
            position: absolute;
            top: 1rem;
            right: 1rem;
            font-size: 1.5rem;
            animation: float-emojis 3s ease-in-out infinite;
        }
        
        @keyframes float-emojis {
            0%, 100% { transform: translateY(0) rotate(0deg); }
            50% { transform: translateY(-10px) rotate(10deg); }
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
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: var(--gradient-kawaii);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            font-weight: 800;
            color: var(--text-white);
            margin-right: 2rem;
            box-shadow: var(--shadow-kawaii);
            position: relative;
            animation: avatar-glow 3s ease-in-out infinite;
        }
        
        .user-avatar::after {
            content: '✨';
            position: absolute;
            top: -5px;
            right: -5px;
            font-size: 1.2rem;
            animation: twinkle 2s ease-in-out infinite;
        }
        
        .user-details h5 {
            color: var(--text-primary);
            font-weight: 700;
            margin-bottom: 0.5rem;
            font-size: 1.4rem;
        }
        
        .user-details h5::before {
            content: '👋 ';
        }
        
        .user-meta {
            display: flex;
            gap: 1.5rem;
            align-items: center;
            margin-bottom: 1.5rem;
        }
        
        .points-badge {
            background: var(--gradient-sky);
            color: var(--text-white);
            padding: 0.8rem 1.5rem;
            border-radius: 30px;
            font-weight: 800;
            font-size: 1rem;
            box-shadow: var(--shadow-cute);
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            animation: badge-pulse 2s ease-in-out infinite;
        }
        
        .points-badge::before {
            content: '💰';
        }
        
        .status-badge {
            background: rgba(255, 182, 193, 0.3);
            color: var(--primary-color);
            padding: 0.6rem 1rem;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            border: 2px solid var(--primary-color);
        }
        
        .status-badge::before {
            content: '🎯 ';
        }
        
        @keyframes avatar-glow {
            0%, 100% { box-shadow: var(--shadow-kawaii); }
            50% { box-shadow: var(--shadow-magic); }
        }
        
        @keyframes badge-pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        .user-actions {
            display: flex;
            gap: 1rem;
            justify-content: space-between;
            align-items: center;
        }
        
        .btn-dashboard {
            background: var(--gradient-magical);
            border: none;
            border-radius: 30px;
            padding: 1rem 2rem;
            font-weight: 800;
            color: var(--text-white);
            text-decoration: none;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.8rem;
            box-shadow: var(--shadow-kawaii);
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }
        
        .btn-dashboard::before {
            content: '🚀';
            font-size: 1.2rem;
        }
        
        .btn-dashboard::after {
            content: '✨';
            position: absolute;
            right: 10px;
            animation: sparkle-dance 2s ease-in-out infinite;
        }
        
        .btn-dashboard:hover {
            transform: translateY(-5px) scale(1.05);
            box-shadow: var(--shadow-dreamy);
            color: var(--text-white);
            animation: rainbow-glow 1s ease-in-out;
        }
        
        @keyframes rainbow-glow {
            0%, 100% { filter: hue-rotate(0deg) brightness(1); }
            50% { filter: hue-rotate(180deg) brightness(1.2); }
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
        
        /* 域名到期时间表格样式 - 强制覆盖Bootstrap默认样式 */
        .domains-expiration-section .table,
        .domains-expiration-section .table-responsive,
        .domains-expiration-section .table > :not(caption) > * > * {
            background-color: transparent !important;
            background: transparent !important;
            color: var(--text-primary) !important;
        }
        
        .domains-expiration-section .table thead {
            backdrop-filter: blur(15px) saturate(150%);
            -webkit-backdrop-filter: blur(15px) saturate(150%);
            background-color: transparent !important;
        }
        
        .domains-expiration-section .table tbody {
            background: transparent !important;
            background-color: transparent !important;
        }
        
        .domains-expiration-section .table tbody tr {
            cursor: pointer;
            backdrop-filter: blur(20px) saturate(150%);
            -webkit-backdrop-filter: blur(20px) saturate(150%);
            background-color: rgba(15, 25, 50, 0.4) !important;
        }
        
        .domains-expiration-section .table tbody tr:hover {
            background: rgba(0, 245, 255, 0.15) !important;
            background-color: rgba(0, 245, 255, 0.15) !important;
            box-shadow: inset 0 0 20px rgba(0, 245, 255, 0.2);
            transform: translateX(5px);
            backdrop-filter: blur(25px) saturate(180%);
            -webkit-backdrop-filter: blur(25px) saturate(180%);
        }
        
        .domains-expiration-section .table td,
        .domains-expiration-section .table th {
            border-color: rgba(0, 245, 255, 0.1) !important;
            background-color: transparent !important;
        }
        
        /* 移除Bootstrap表格的条纹和悬停默认样式 */
        .domains-expiration-section .table-striped > tbody > tr:nth-of-type(odd) > * {
            background-color: transparent !important;
        }
        
        .domains-expiration-section .table-hover > tbody > tr:hover > * {
            background-color: transparent !important;
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
                            <a class="nav-link" href="user/register_verify.php">
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
                                        $stmt->bindValue(1, $_SESSION['user_id'], SQLITE3_INTEGER);
                                        $result = $stmt->execute();
                                        $user_records = $result->fetchArray(SQLITE3_NUM)[0];
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
                                <a href="user/register_verify.php" class="btn btn-success">
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
    
    <!-- 域名到期时间表格 -->
    <?php if (!empty($domains_with_expiration)): ?>
    <section class="domains-expiration-section" style="padding: 4rem 0; background: rgba(255, 255, 255, 0.02);">
        <div class="container">
            <div class="text-center mb-4">
                <h2 class="section-title" style="font-size: 2.5rem; font-weight: 900; background: var(--gradient-kawaii); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 1rem;">
                    <i class="fas fa-calendar-alt me-2"></i>域名到期时间
                </h2>
                <p class="text-secondary">系统域名到期时间一览</p>
            </div>
            
            <div class="card-modern">
                <div class="table-responsive" style="background: transparent;">
                    <table class="table table-hover align-middle" style="margin-bottom: 0; background: transparent; color: var(--text-primary);">
                        <thead style="background: linear-gradient(135deg, rgba(255, 182, 193, 0.15) 0%, rgba(221, 160, 221, 0.15) 100%); border-bottom: 2px solid var(--primary-color); backdrop-filter: blur(15px); -webkit-backdrop-filter: blur(15px);">
                            <tr>
                                <th style="padding: 1rem; font-weight: 700; color: var(--text-primary); border-color: rgba(0, 245, 255, 0.1);">
                                    <i class="fas fa-globe me-2"></i>域名
                                </th>
                                <th style="padding: 1rem; font-weight: 700; color: var(--text-primary); border-color: rgba(0, 245, 255, 0.1);">
                                    <i class="fas fa-clock me-2"></i>到期时间
                                </th>
                                <th style="padding: 1rem; font-weight: 700; color: var(--text-primary); border-color: rgba(0, 245, 255, 0.1);">
                                    <i class="fas fa-info-circle me-2"></i>状态
                                </th>
                            </tr>
                        </thead>
                        <tbody style="background: transparent;">
                            <?php foreach ($domains_with_expiration as $domain): ?>
                            <tr style="transition: all 0.3s ease; border-bottom: 1px solid rgba(0, 245, 255, 0.1); background: rgba(15, 25, 50, 0.4); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);">
                                <td style="padding: 1rem; border-color: rgba(0, 245, 255, 0.1);">
                                    <span style="font-weight: 600; color: var(--text-primary); font-size: 1.05rem;">
                                        <?php echo htmlspecialchars($domain['domain_name']); ?>
                                    </span>
                                </td>
                                <td style="padding: 1rem; border-color: rgba(0, 245, 255, 0.1);">
                                    <?php if (!empty($domain['expiration_time'])): ?>
                                        <?php
                                        $expiration_date = strtotime($domain['expiration_time']);
                                        $now = time();
                                        $days_until_expiration = floor(($expiration_date - $now) / 86400);
                                        ?>
                                        <span style="color: var(--text-secondary); font-size: 0.95rem;">
                                            <i class="far fa-calendar me-1"></i>
                                            <?php echo date('Y-m-d H:i', $expiration_date); ?>
                                        </span>
                                        <?php if ($days_until_expiration > 0): ?>
                                        <small style="display: block; color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.25rem;">
                                            (还有 <?php echo $days_until_expiration; ?> 天)
                                        </small>
                                        <?php endif; ?>
                                    <?php else: ?>
                                        <span style="color: var(--accent-color); font-weight: 600;">
                                            <i class="fas fa-infinity me-1"></i>永久
                                        </span>
                                    <?php endif; ?>
                                </td>
                                <td style="padding: 1rem; border-color: rgba(0, 245, 255, 0.1);">
                                    <?php if (empty($domain['expiration_time'])): ?>
                                        <span class="badge badge-permanent" style="background: var(--gradient-magical); color: var(--text-white); padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.85rem; font-weight: 700; box-shadow: var(--shadow-cute);">
                                            <i class="fas fa-star me-1"></i>永久域名
                                        </span>
                                    <?php else: ?>
                                        <?php
                                        $expiration_date = strtotime($domain['expiration_time']);
                                        $now = time();
                                        $days_until_expiration = floor(($expiration_date - $now) / 86400);
                                        
                                        if ($days_until_expiration < 0) {
                                            $badge_class = 'danger';
                                            $icon = 'fa-times-circle';
                                            $text = '已过期';
                                            $bg_style = 'background: var(--gradient-sunset); box-shadow: 0 4px 16px rgba(255, 0, 85, 0.4);';
                                        } elseif ($days_until_expiration <= 30) {
                                            $badge_class = 'warning';
                                            $icon = 'fa-exclamation-triangle';
                                            $text = '即将到期';
                                            $bg_style = 'background: linear-gradient(135deg, var(--warning-color), #ff9800); box-shadow: 0 4px 16px rgba(255, 170, 0, 0.4);';
                                        } elseif ($days_until_expiration <= 90) {
                                            $badge_class = 'info';
                                            $icon = 'fa-info-circle';
                                            $text = '注意续费';
                                            $bg_style = 'background: var(--gradient-sky); box-shadow: 0 4px 16px rgba(0, 245, 255, 0.3);';
                                        } else {
                                            $badge_class = 'success';
                                            $icon = 'fa-check-circle';
                                            $text = '正常';
                                            $bg_style = 'background: linear-gradient(135deg, var(--success-color), #00cc70); box-shadow: 0 4px 16px rgba(0, 255, 136, 0.3);';
                                        }
                                        ?>
                                        <span class="badge badge-<?php echo $badge_class; ?>" style="<?php echo $bg_style; ?> color: var(--text-white); padding: 0.5rem 1rem; border-radius: 20px; font-size: 0.85rem; font-weight: 700;">
                                            <i class="fas <?php echo $icon; ?> me-1"></i><?php echo $text; ?>
                                        </span>
                                    <?php endif; ?>
                                </td>
                            </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </section>
    <?php endif; ?>
    
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
