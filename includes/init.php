<?php
/**
 * 系统初始化文件
 * 在所有页面开头包含此文件以确保系统正常运行
 */

// 确保必要的文件已包含
if (!class_exists('Database')) {
    require_once __DIR__ . '/../config/database.php';
}

if (!function_exists('getSetting')) {
    require_once __DIR__ . '/functions.php';
}

// 设置错误报告（生产环境中应该关闭）
if (!defined('PRODUCTION')) {
    error_reporting(E_ALL);
    ini_set('display_errors', 1);
}

// 设置时区
if (!ini_get('date.timezone')) {
    date_default_timezone_set('Asia/Shanghai');
}
?>