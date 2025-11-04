<?php
/**
 * 修复公告表缺失字段
 * 
 * 如果遇到 "no such column: target_user_ids" 错误，运行此脚本
 * 
 * 使用方法：
 * 1. 直接访问此文件：http://your-domain.com/config/repair_announcements.php
 * 2. 或通过命令行运行：php config/repair_announcements.php
 */

// 设置错误报告
error_reporting(E_ALL);
ini_set('display_errors', 1);

// 包含数据库类
require_once __DIR__ . '/database.php';

?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>修复公告表</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .container {
            background: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }
        .success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
        .error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
        .info {
            background: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
        }
        pre {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 修复公告表缺失字段</h1>
        
        <div class="info">
            <strong>📋 此脚本将执行以下操作：</strong>
            <ul>
                <li>检查 announcements 表是否缺失 target_user_ids 字段</li>
                <li>检查 announcements 表是否缺失 auto_close_seconds 字段</li>
                <li>如果字段缺失，将自动添加这些字段</li>
                <li>不会影响现有数据</li>
            </ul>
        </div>

        <?php
        try {
            $db = Database::getInstance()->getConnection();
            
            echo "<h3>🔍 开始检查数据库...</h3>";
            
            // 检查 announcements 表是否存在
            $table_exists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='announcements'");
            
            if (!$table_exists) {
                echo "<div class='error'>❌ announcements 表不存在！请先运行安装程序。</div>";
                exit;
            }
            
            echo "<div class='success'>✅ announcements 表存在</div>";
            
            // 获取表的所有列
            $columns = [];
            $result = $db->query("PRAGMA table_info(announcements)");
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $columns[] = $row['name'];
            }
            
            echo "<h3>📊 当前表结构：</h3>";
            echo "<pre>" . implode("\n", $columns) . "</pre>";
            
            // 检查并添加 target_user_ids 字段
            $target_user_ids_exists = in_array('target_user_ids', $columns);
            if (!$target_user_ids_exists) {
                echo "<p>🔄 添加 target_user_ids 字段...</p>";
                try {
                    $db->exec("ALTER TABLE announcements ADD COLUMN target_user_ids TEXT DEFAULT NULL");
                    echo "<div class='success'>✅ target_user_ids 字段添加成功</div>";
                } catch (Exception $e) {
                    echo "<div class='error'>❌ 添加 target_user_ids 字段失败: " . htmlspecialchars($e->getMessage()) . "</div>";
                }
            } else {
                echo "<div class='info'>ℹ️ target_user_ids 字段已存在，跳过</div>";
            }
            
            // 检查并添加 auto_close_seconds 字段
            $auto_close_seconds_exists = in_array('auto_close_seconds', $columns);
            if (!$auto_close_seconds_exists) {
                echo "<p>🔄 添加 auto_close_seconds 字段...</p>";
                try {
                    $db->exec("ALTER TABLE announcements ADD COLUMN auto_close_seconds INTEGER DEFAULT 0");
                    echo "<div class='success'>✅ auto_close_seconds 字段添加成功</div>";
                } catch (Exception $e) {
                    echo "<div class='error'>❌ 添加 auto_close_seconds 字段失败: " . htmlspecialchars($e->getMessage()) . "</div>";
                }
            } else {
                echo "<div class='info'>ℹ️ auto_close_seconds 字段已存在，跳过</div>";
            }
            
            // 再次检查表结构
            $columns_after = [];
            $result = $db->query("PRAGMA table_info(announcements)");
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $columns_after[] = $row['name'];
            }
            
            echo "<h3>📊 修复后的表结构：</h3>";
            echo "<pre>" . implode("\n", $columns_after) . "</pre>";
            
            // 验证修复是否成功
            if (in_array('target_user_ids', $columns_after) && in_array('auto_close_seconds', $columns_after)) {
                echo "<div class='success'><strong>🎉 修复完成！</strong><br>announcements 表已包含所有必需的字段。</div>";
                echo "<p><a href='../admin/announcements.php' style='color: #007bff;'>← 返回公告管理页面</a></p>";
            } else {
                echo "<div class='error'><strong>❌ 修复未完成</strong><br>某些字段可能添加失败，请检查错误信息。</div>";
            }
            
        } catch (Exception $e) {
            echo "<div class='error'>❌ 执行过程中发生错误: " . htmlspecialchars($e->getMessage()) . "</div>";
            echo "<pre>" . htmlspecialchars($e->getTraceAsString()) . "</pre>";
        }
        ?>
        
        <hr style="margin-top: 30px;">
        <p style="text-align: center; color: #666;">
            <small>数据库修复工具 v1.0</small>
        </p>
    </div>
</body>
</html>
