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

// 自动验证和迁移数据库（仅在需要时执行）
if (!defined('SKIP_DB_VALIDATION')) {
    require_once __DIR__ . '/database_validator.php';
    
    // 使用静态变量确保只执行一次
    static $db_validated = false;
    if (!$db_validated) {
        try {
            $validator = new DatabaseValidator();
            $validator->validateAndMigrate();
            $db_validated = true;
        } catch (Exception $e) {
            error_log("数据库验证失败: " . $e->getMessage());
            // 不中断执行，让系统继续运行
        }
    }
}
?>