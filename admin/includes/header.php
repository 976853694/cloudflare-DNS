<?php
// 确保必要的函数已加载
if (!function_exists('getSetting')) {
    require_once __DIR__ . '/../../includes/functions.php';
}
?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo isset($page_title) ? $page_title . ' - ' : ''; ?>管理后台 - <?php echo getSetting('site_name', 'DNS管理系统'); ?></title>
    
    <!-- Bootstrap CSS -->
    <?php 
    // 检测调用此header的脚本路径来确定资源路径
    $calling_script = isset($_SERVER['SCRIPT_NAME']) ? $_SERVER['SCRIPT_NAME'] : '';
    $calling_dir = dirname($calling_script);
    
    if (strpos($calling_dir, '/admin/channels') !== false) {
        $assets_path = '../../assets/';
    } elseif (strpos($calling_dir, '/admin') !== false) {
        $assets_path = '../assets/';
    } else {
        $assets_path = 'assets/';
    }
    ?>
    <link href="<?php echo $assets_path; ?>css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link href="<?php echo $assets_path; ?>css/fontawesome.min.css" rel="stylesheet">
    
    <style>
        /* 全局背景设置 */
        body {
            background-image: url('<?php echo getSetting('background_image_url', 'https://img.6qu.cc/file/img/1757093288720_%E3%80%90%E5%93%B2%E9%A3%8E%E5%A3%81%E7%BA%B8%E3%80%91%E4%BC%A0%E7%BB%9F%E5%BB%BA%E7%AD%91-%E5%92%96%E5%95%A1%E5%B0%8F%E5%BA%97__1_.png?from=admin'); ?>');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
            min-height: 100vh;
            position: relative;
        }
        
        /* 背景遮罩层 */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.3);
            z-index: -1;
        }
        
        .sidebar {
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            z-index: 100;
            padding: 48px 0 0;
            background: transparent;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border-right: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease-in-out, margin-left 0.3s ease-in-out;
        }
        
        /* 侧边栏折叠状态 */
        .sidebar.collapsed {
            margin-left: -250px;
        }
        
        /* 侧边栏折叠按钮 */
        .sidebar-toggle {
            position: fixed;
            top: 60px;
            left: 10px;
            z-index: 1050;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            padding: 8px 12px;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .sidebar-toggle:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: scale(1.05);
        }
        
        .sidebar-toggle.collapsed {
            left: 10px;
        }
        
        .sidebar-sticky {
            position: relative;
            top: 0;
            height: calc(100vh - 48px);
            padding-top: .5rem;
            overflow-x: hidden;
            overflow-y: auto;
        }
        
        .navbar-brand {
            padding-top: .75rem;
            padding-bottom: .75rem;
            color: white !important;
            font-weight: 600;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .navbar .navbar-toggler {
            top: .25rem;
            right: 1rem;
        }
        
        /* 导航链接样式 */
        .nav-link {
            color: rgba(255, 255, 255, 0.9);
            transition: all 0.3s ease;
            border-radius: 8px;
            margin: 2px 8px;
            padding: 10px 15px;
        }
        
        .nav-link:hover {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
        }
        
        .nav-link.active {
            color: #ffffff;
            font-weight: 500;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        /* 侧边栏标题样式 */
        .sidebar-heading {
            color: rgba(255, 255, 255, 0.8) !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* 顶部导航栏毛玻璃效果 */
        .navbar {
            background: transparent !important;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 4px 32px rgba(0, 0, 0, 0.1);
        }
        
        .border-left-primary {
            border-left: 0.25rem solid rgba(78, 115, 223, 0.8) !important;
        }
        
        .border-left-success {
            border-left: 0.25rem solid rgba(28, 200, 138, 0.8) !important;
        }
        
        .border-left-info {
            border-left: 0.25rem solid rgba(54, 185, 204, 0.8) !important;
        }
        
        .border-left-warning {
            border-left: 0.25rem solid rgba(246, 194, 62, 0.8) !important;
        }
        
        .text-gray-800, .text-gray-300 {
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 修复侧边栏在缩放状态下的显示问题 */
        .sidebar-container {
            height: calc(100vh - 48px);
            max-height: calc(100vh - 48px);
            overflow-y: auto;
            overflow-x: hidden;
            padding-bottom: 20px;
        }
        
        /* 优化滚动条样式 */
        .sidebar-container::-webkit-scrollbar {
            width: 6px;
        }
        
        .sidebar-container::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        
        .sidebar-container::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 3px;
        }
        
        .sidebar-container::-webkit-scrollbar-thumb:hover {
            background: #a8a8a8;
        }
        
        /* 确保退出按钮始终在底部可见 */
        .sidebar-container .mt-auto {
            margin-top: auto !important;
            flex-shrink: 0;
        }
        
        /* 响应式改进 - 在小屏幕和缩放状态下优化显示 */
        @media (max-width: 991px) {
            .sidebar-container {
                height: auto;
                max-height: none;
            }
            
            /* 手机端侧边栏改进 */
            .sidebar {
                transform: translateX(-100%);
            }
            
            .sidebar.show {
                transform: translateX(0);
            }
            
            .sidebar.collapsed {
                margin-left: 0;
                transform: translateX(-100%);
            }
            
            /* 手机端主内容区域调整 */
            .main-content {
                margin: 10px;
                padding: 15px;
            }
            
            /* 手机端折叠按钮隐藏，使用导航栏按钮 */
            .sidebar-toggle {
                display: none;
            }
            
            /* 确保内容可以滚动 */
            body {
                overflow-x: hidden;
                overflow-y: auto;
            }
            
            /* 手机端侧边栏遮罩 */
            .sidebar-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 99;
            }
            
            .sidebar-overlay.show {
                display: block;
            }
        }
        
        /* 桌面端主内容区域随侧边栏调整 */
        @media (min-width: 992px) {
            .main-content {
                margin-left: 250px;
                transition: margin-left 0.3s ease-in-out;
            }
            
            .main-content.sidebar-collapsed {
                margin-left: 0;
            }
        }
        
        /* 针对高DPI和缩放显示的优化 */
        @media (-webkit-device-pixel-ratio: 1.5), (min-resolution: 144dpi) {
            .nav-link {
                padding: 0.75rem 1rem;
                font-size: 0.95rem;
                line-height: 1.4;
            }
            
            .sidebar-heading {
                font-size: 0.8rem;
                padding: 0.5rem 1rem;
            }
        }
        
        /* 主内容区域毛玻璃效果 */
        .main-content {
            background: transparent;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            margin: 20px;
            padding: 20px;
            min-height: calc(100vh - 100px);
            overflow-x: auto;
            overflow-y: visible;
        }
        
        /* 容器改进，确保内容可以滚动 */
        .container-fluid {
            width: 100%;
            padding-right: 15px;
            padding-left: 15px;
            margin-right: auto;
            margin-left: auto;
        }
        
        /* 卡片毛玻璃效果 */
        .card {
            background: transparent;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
        }
        
        /* 模态框毛玻璃效果 */
        .modal-content {
            background: transparent;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 16px 64px rgba(0, 0, 0, 0.2);
        }
        
        .modal-header {
            border-bottom: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .modal-footer {
            border-top: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .modal-title, .modal-body {
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 表单控件毛玻璃效果 */
        .form-control, .form-select {
            background: transparent;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .form-control:focus, .form-select:focus {
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.5);
            box-shadow: 0 0 0 0.2rem rgba(255, 255, 255, 0.2);
            color: white;
        }
        
        /* 下拉选择框选项样式 - 深色主题 */
        .form-select option {
            background: rgba(10, 14, 39, 0.95) !important;
            color: #fff !important;
            padding: 8px 12px;
            text-shadow: none;
        }
        
        .form-select option:hover,
        .form-select option:checked {
            background: rgba(0, 212, 255, 0.3) !important;
            color: #fff !important;
        }
        
        /* select 元素特殊样式 */
        select.form-control,
        select.form-select {
            background: rgba(255, 255, 255, 0.1) !important;
            backdrop-filter: blur(10px);
            color: #fff !important;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        select.form-control option,
        select.form-select option {
            background: rgba(10, 14, 39, 0.95) !important;
            color: #fff !important;
            padding: 10px;
        }
        
        /* 输入组中的 select */
        .input-group .form-select,
        .input-group select {
            background: rgba(255, 255, 255, 0.1) !important;
        }
        
        .input-group .form-select option,
        .input-group select option {
            background: rgba(10, 14, 39, 0.95) !important;
            color: #fff !important;
        }
        
        /* 按钮毛玻璃效果 */
        .btn {
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            transition: all 0.3s ease;
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .btn-primary {
            background: transparent;
            border-color: rgba(255, 255, 255, 0.4);
        }
        
        .btn-primary:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(255, 255, 255, 0.2);
            border-color: rgba(255, 255, 255, 0.5);
        }
        
        /* 警告框毛玻璃效果 */
        .alert {
            background: transparent;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 表格毛玻璃效果 */
        .table {
            background: transparent;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            color: white;
        }
        
        .table th {
            background: transparent;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border-color: rgba(255, 255, 255, 0.3);
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .table td {
            background: transparent;
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
            border-color: rgba(255, 255, 255, 0.1);
        }
        
        /* 徽章毛玻璃效果 */
        .badge {
            background: transparent !important;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 全局文字颜色设置为白色 */
        body, p, span, div, a, label, small, strong, em, i, b {
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        h1, h2, h3, h4, h5, h6 {
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 链接颜色 */
        a {
            color: rgba(255, 255, 255, 0.9) !important;
        }
        
        a:hover {
            color: white !important;
        }
        
        /* 列表文字 */
        ul, ol, li {
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 输入框占位符文字 */
        .form-control::placeholder,
        .form-select::placeholder {
            color: rgba(255, 255, 255, 0.6) !important;
        }
        
        /* 文本颜色调整 */
        .text-muted {
            color: rgba(255, 255, 255, 0.7) !important;
        }
        
        .text-primary {
            color: rgba(78, 115, 223, 1) !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .text-success {
            color: rgba(28, 200, 138, 1) !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .text-warning {
            color: rgba(246, 194, 62, 1) !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .text-info {
            color: rgba(54, 185, 204, 1) !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .text-danger {
            color: rgba(220, 53, 69, 1) !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 图标颜色调整 */
        .fas, .fa {
            color: rgba(255, 255, 255, 0.8) !important;
        }
        
        /* 列表组样式 */
        .list-group-item {
            background: transparent !important;
            backdrop-filter: blur(50px);
            -webkit-backdrop-filter: blur(50px);
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .list-group-item:hover {
            background: rgba(255, 255, 255, 0.1) !important;
        }
    </style>
</head>
<body>
    <!-- 手机端侧边栏遮罩 -->
    <div class="sidebar-overlay d-md-none" id="sidebarOverlay" onclick="closeMobileSidebar()"></div>
    
    <!-- 侧边栏折叠按钮（仅桌面端显示） -->
    <button class="sidebar-toggle d-none d-md-block" id="sidebarToggle" onclick="toggleSidebar()">
        <i class="fas fa-bars"></i>
    </button>
    
    <nav class="navbar navbar-dark sticky-top flex-md-nowrap p-0 shadow">
        <a class="navbar-brand col-md-3 col-lg-2 me-0 px-3" href="dashboard.php">
            <i class="fas fa-cogs me-2"></i>管理后台
        </a>
        <button class="navbar-toggler position-absolute d-md-none collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#sidebarMenu" onclick="toggleMobileSidebar()">
            <span class="navbar-toggler-icon"></span>
        </button>
    </nav>
    
    <script>
        // 桌面端侧边栏折叠功能
        function toggleSidebar() {
            const sidebar = document.getElementById('sidebarMenu');
            const mainContent = document.querySelector('.main-content');
            const toggleBtn = document.getElementById('sidebarToggle');
            
            sidebar.classList.toggle('collapsed');
            if (mainContent) {
                mainContent.classList.toggle('sidebar-collapsed');
            }
            toggleBtn.classList.toggle('collapsed');
            
            // 保存状态到 localStorage
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
        }
        
        // 手机端侧边栏切换
        function toggleMobileSidebar() {
            const sidebar = document.getElementById('sidebarMenu');
            const overlay = document.getElementById('sidebarOverlay');
            sidebar.classList.toggle('show');
            if (overlay) {
                overlay.classList.toggle('show');
            }
        }
        
        // 关闭手机端侧边栏
        function closeMobileSidebar() {
            const sidebar = document.getElementById('sidebarMenu');
            const overlay = document.getElementById('sidebarOverlay');
            sidebar.classList.remove('show');
            if (overlay) {
                overlay.classList.remove('show');
            }
        }
        
        // 页面加载时恢复侧边栏状态
        document.addEventListener('DOMContentLoaded', function() {
            const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
            if (isCollapsed && window.innerWidth >= 992) {
                const sidebar = document.getElementById('sidebarMenu');
                const mainContent = document.querySelector('.main-content');
                const toggleBtn = document.getElementById('sidebarToggle');
                
                sidebar.classList.add('collapsed');
                if (mainContent) {
                    mainContent.classList.add('sidebar-collapsed');
                }
                if (toggleBtn) {
                    toggleBtn.classList.add('collapsed');
                }
            }
            
            // 监听窗口大小变化
            window.addEventListener('resize', function() {
                if (window.innerWidth >= 992) {
                    // 桌面端，关闭手机端遮罩
                    const overlay = document.getElementById('sidebarOverlay');
                    if (overlay) {
                        overlay.classList.remove('show');
                    }
                    const sidebar = document.getElementById('sidebarMenu');
                    if (sidebar) {
                        sidebar.classList.remove('show');
                    }
                }
            });
        });
    </script>