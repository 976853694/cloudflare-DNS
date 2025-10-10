<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo isset($page_title) ? $page_title . ' - ' : ''; ?><?php echo getSetting('site_name', 'DNS管理系统'); ?></title>
    
    <!-- Bootstrap CSS -->
    <link href="../assets/css/bootstrap.min.css" rel="stylesheet">
    <!-- Font Awesome -->
    <link href="../assets/css/fontawesome.min.css" rel="stylesheet">
    
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
            backdrop-filter: blur(70);
            -webkit-backdrop-filter: blur(70px);
            border-right: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
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
        }
        
        .navbar .navbar-toggler {
            top: .25rem;
            right: 1rem;
        }
        
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
            backdrop-filter: blur(70);
            -webkit-backdrop-filter: blur(70px);
        }
        
        .nav-link.active {
            color: #ffffff;
            font-weight: 500;
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        .user-info {
            background: transparent;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            color: white;
            padding: 1rem;
            margin: 1rem;
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .points-badge {
            background: transparent;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            padding: 0.5rem 1rem;
            border-radius: 25px;
            display: inline-block;
            margin-top: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.3);
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 顶部导航栏毛玻璃效果 */
        .navbar {
            background: transparent !important;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 4px 32px rgba(0, 0, 0, 0.1);
        }
        
        .navbar-brand {
            color: white !important;
            font-weight: 600;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 主内容区域毛玻璃效果 */
        .main-content {
            background: transparent;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            margin: 20px;
            padding: 20px;
            min-height: calc(100vh - 100px);
        }
        
        /* 卡片毛玻璃效果 */
        .card {
            background: transparent;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
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
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
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
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
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
        
        /* 按钮毛玻璃效果 */
        .btn {
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            transition: all 0.3s ease;
        }
        
        .btn-primary {
            background: transparent;
            border-color: rgba(255, 255, 255, 0.4);
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .btn-primary:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(255, 255, 255, 0.2);
            color: white;
            border-color: rgba(255, 255, 255, 0.5);
        }
        
        /* 警告框毛玻璃效果 */
        .alert {
            background: transparent;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 表格毛玻璃效果 */
        .table {
            background: transparent;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            color: white;
        }
        
        .table th {
            background: transparent;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            border-color: rgba(255, 255, 255, 0.3);
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .table td {
            background: transparent;
            color: white;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .table td {
            border-color: rgba(255, 255, 255, 0.1);
        }
        
        /* 徽章毛玻璃效果 */
        .badge {
            background: transparent !important;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 文本颜色调整 */
        .text-muted {
            color: rgba(255, 255, 255, 0.7) !important;
        }
        
        h1, h2, h3, h4, h5, h6 {
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 全局文字颜色设置为白色 */
        body, p, span, div, a, label, small, strong, em, i, b {
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
        
        /* 按钮文字 */
        .btn {
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 表格文字确保白色 */
        .table th, .table td {
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        /* 邀请页面特殊样式毛玻璃化 */
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
        
        .text-xs {
            color: rgba(255, 255, 255, 0.9) !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .font-weight-bold {
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
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
        
        /* 列表组样式 */
        .list-group-item {
            background: transparent !important;
            backdrop-filter: blur(70px);
            -webkit-backdrop-filter: blur(70px);
            border: 1px solid rgba(255, 255, 255, 0.2) !important;
            color: white !important;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.8);
        }
        
        .list-group-item:hover {
            background: rgba(255, 255, 255, 0.1) !important;
        }
        
        /* 图标颜色调整 */
        .fas, .fa {
            color: rgba(255, 255, 255, 0.8) !important;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark sticky-top bg-primary flex-md-nowrap p-0 shadow">
        <a class="navbar-brand col-md-3 col-lg-2 me-0 px-3" href="dashboard.php">
            <i class="fas fa-cloud me-2"></i><?php echo getSetting('site_name', 'DNS管理系统'); ?>
        </a>
        <button class="navbar-toggler position-absolute d-md-none collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#sidebarMenu">
            <span class="navbar-toggler-icon"></span>
        </button>
    </nav>