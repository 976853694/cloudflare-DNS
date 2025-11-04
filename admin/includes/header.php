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
    <!-- White Theme CSS -->
    <link href="<?php echo $assets_path; ?>css/white-theme.css" rel="stylesheet">
    
    <style>
        /* Admin 专属样式 - 基于 White Theme */
        body {
            background-color: #f8f9fa;
        }
        
        /* 侧边栏样式 */
        .sidebar {
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            z-index: 100;
            padding: 48px 0 0;
            box-shadow: inset -1px 0 0 rgba(0, 0, 0, .1);
            background-color: #fff;
        }
        
        .sidebar-sticky {
            position: relative;
            top: 0;
            height: calc(100vh - 48px);
            padding-top: .5rem;
            overflow-x: hidden;
            overflow-y: auto;
        }
        
        /* 优化滚动条样式 */
        .sidebar-sticky::-webkit-scrollbar {
            width: 6px;
        }
        
        .sidebar-sticky::-webkit-scrollbar-track {
            background: #f1f1f1;
        }
        
        .sidebar-sticky::-webkit-scrollbar-thumb {
            background: #c1c1c1;
            border-radius: 3px;
        }
        
        .sidebar-sticky::-webkit-scrollbar-thumb:hover {
            background: #a8a8a8;
        }
        
        /* 顶部导航栏 */
        .navbar {
            background-color: #0d6efd !important;
            box-shadow: 0 2px 4px rgba(0,0,0,.1);
        }
        
        .navbar-brand {
            padding-top: .75rem;
            padding-bottom: .75rem;
            font-size: 1rem;
            color: white !important;
            font-weight: 600;
        }
        
        .navbar .navbar-toggler {
            top: .25rem;
            right: 1rem;
        }
        
        /* 导航链接样式 */
        .sidebar .nav-link {
            font-weight: 500;
            color: #333;
            padding: 1rem 1rem;
            border-radius: 0.25rem;
            margin: 0.125rem 0.5rem;
            transition: all 0.2s ease;
        }
        
        .sidebar .nav-link:hover {
            color: #0d6efd;
            background-color: #f8f9fa;
        }
        
        .sidebar .nav-link.active {
            color: #0d6efd;
            background-color: #e7f1ff;
            font-weight: 800;
        }
        
        .sidebar .nav-link i {
            margin-right: 0.5rem;
        }
        
        /* 侧边栏标题样式 */
        .sidebar-heading {
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 800;
            color: #6c757d;
            padding: 0.75rem 1rem 0.25rem;
            cursor: pointer;
            user-select: none;
            transition: color 0.2s ease;
        }
        
        .sidebar-heading:hover {
            color: #495057;
        }
        
        .sidebar-heading .collapse-icon {
            float: right;
            transition: transform 0.3s ease;
        }
        
        .sidebar-heading.collapsed .collapse-icon {
            transform: rotate(-90deg);
        }
        
        /* 菜单组折叠动画 */
        .menu-group {
            overflow: hidden;
            max-height: 1000px;
            transition: max-height 0.3s ease, opacity 0.3s ease;
            opacity: 1;
        }
        
        .menu-group.collapsed {
            max-height: 0;
            opacity: 0;
        }
        
        /* 主内容区域 */
        main {
            padding-top: 48px;
        }
        
        @media (min-width: 768px) {
            main {
                padding-left: 240px;
            }
        }
        
        /* 响应式设计 */
        @media (max-width: 767.98px) {
            .sidebar {
                top: 48px;
                padding-top: 0;
            }
            
            main {
                padding-top: 48px;
                padding-left: 0;
            }
        }
        
        /* 卡片样式增强 */
        .card {
            border: 1px solid rgba(0,0,0,.125);
            box-shadow: 0 0.125rem 0.25rem rgba(0,0,0,.075);
            transition: all 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 0.5rem 1rem rgba(0,0,0,.15);
        }
        
        /* 表格样式 */
        .table {
            color: #212529;
        }
        
        /* 统计卡片边框 */
        .border-left-primary {
            border-left: 0.25rem solid #0d6efd !important;
        }
        
        .border-left-success {
            border-left: 0.25rem solid #198754 !important;
        }
        
        .border-left-info {
            border-left: 0.25rem solid #0dcaf0 !important;
        }
        
        .border-left-warning {
            border-left: 0.25rem solid #ffc107 !important;
        }
        
        .border-left-danger {
            border-left: 0.25rem solid #dc3545 !important;
        }
        
        /* 文本颜色 */
        .text-gray-800 {
            color: #343a40 !important;
        }
        
        .text-gray-300 {
            color: #dee2e6 !important;
        }
        
        /* 页面标题下划线 */
        .page-header {
            border-bottom: 1px solid #e0e0e0;
            padding-bottom: 1rem;
            margin-bottom: 1.5rem;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark sticky-top bg-primary flex-md-nowrap p-0 shadow">
        <a class="navbar-brand col-md-3 col-lg-2 me-0 px-3" href="dashboard.php">
            <i class="fas fa-cogs me-2"></i>管理后台
        </a>
        <button class="navbar-toggler position-absolute d-md-none collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#sidebarMenu">
            <span class="navbar-toggler-icon"></span>
        </button>
    </nav>
