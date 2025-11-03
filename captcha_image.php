<?php
/**
 * 数据库升级入口文件
 * 直接访问此文件即可自动升级数据库
 */

// 安全检查 - 可以根据需要添加IP限制或密码验证
$allowed_ips = ['127.0.0.1', '::1']; // 只允许本地访问，生产环境请修改
$client_ip = $_SERVER['REMOTE_ADDR'] ?? '';

if (!in_array($client_ip, $allowed_ips) && !isset($_GET['force'])) {
    die('Access denied. Add ?force=1 to bypass IP restriction.');
}

?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数据库升级工具</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
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
        .info-box {
            background: #e7f3ff;
            border: 1px solid #b3d9ff;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }
        .warning-box {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            border: none;
            cursor: pointer;
            font-size: 16px;
            margin: 10px 5px;
        }
        .btn:hover {
            background: #0056b3;
        }
        .btn-danger {
            background: #dc3545;
        }
        .btn-danger:hover {
            background: #c82333;
        }
        pre {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 数据库升级工具</h1>
        
        <div class="info-box">
            <h3>📋 功能说明</h3>
            <ul>
                <li>自动检测当前数据库版本</li>
                <li>创建缺失的数据库表和字段</li>
                <li>安全升级，不会删除现有数据</li>
                <li>支持版本管理和增量升级</li>
                <li>完整性验证和错误报告</li>
            </ul>
        </div>
        
        <div class="warning-box">
            <h3>⚠️ 重要提醒</h3>
            <ul>
                <li><strong>升级前请备份数据库文件</strong></li>
                <li>建议在维护时间进行升级操作</li>
                <li>升级过程中请勿关闭浏览器</li>
                <li>如有问题，可恢复备份文件</li>
            </ul>
        </div>
        
        <h3>🔧 当前系统状态</h3>
        <?php
        try {
            require_once 'config/database.php';
            $db = Database::getInstance()->getConnection();
            
            // 检查数据库文件
            $db_file = __DIR__ . '/data/cloudflare_dns.db';
            $db_size = file_exists($db_file) ? round(filesize($db_file) / 1024, 2) : 0;
            
            // 检查表数量
            $table_count = 0;
            $result = $db->query("SELECT COUNT(*) FROM sqlite_master WHERE type='table'");
            if ($result) {
                $table_count = $result->fetchArray(SQLITE3_NUM)[0];
            }
            
            // 检查版本表
            $version_table_exists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='database_versions'");
            $current_version = '未知';
            if ($version_table_exists) {
                $current_version = $db->querySingle("SELECT version FROM database_versions ORDER BY id DESC LIMIT 1") ?: '0.0.0';
            }
            
            echo "<ul>";
            echo "<li><strong>数据库文件:</strong> " . ($db_file) . " ({$db_size} KB)</li>";
            echo "<li><strong>数据表数量:</strong> {$table_count}</li>";
            echo "<li><strong>当前版本:</strong> {$current_version}</li>";
            echo "<li><strong>目标版本:</strong> 1.6.0</li>";
            echo "</ul>";
            
        } catch (Exception $e) {
            echo "<p style='color: red;'>❌ 数据库连接失败: " . htmlspecialchars($e->getMessage()) . "</p>";
        }
        ?>
        
        <h3>🎯 升级操作</h3>
        <p>点击下面的按钮开始数据库升级：</p>
        
        <a href="?action=upgrade" class="btn">开始升级数据库</a>
        <a href="?action=check" class="btn" style="background: #28a745;">仅检查状态</a>
        
        <h3>📖 开发者说明</h3>
        <div class="info-box">
            <h4>添加新功能的数据库变更步骤：</h4>
            <ol>
                <li>在 <code>config/database.php</code> 的 DatabaseUpgrade 类中增加版本号</li>
                <li>在 <code>$database_versions</code> 数组中添加新版本和对应的方法</li>
                <li>创建对应的升级方法，例如：
                    <pre>private function addNewFeature() {
    echo "&lt;p&gt;添加新功能...&lt;/p&gt;";
    
    // 创建新表
    $this->db->exec("CREATE TABLE IF NOT EXISTS new_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )");
    
    // 添加新字段
    $this->addColumnIfNotExists('existing_table', 'new_field', 'TEXT');
}</pre>
                </li>
                <li>访问此页面执行升级</li>
            </ol>
        </div>
        
        <?php
        if (isset($_GET['action'])) {
            echo "<hr><h3>📊 执行结果</h3>";
            
            if ($_GET['action'] === 'upgrade') {
                require_once 'config/database.php';
            } elseif ($_GET['action'] === 'check') {
                echo "<div style='font-family: monospace; background: #f5f5f5; padding: 20px;'>";
                echo "<p>执行数据库状态检查...</p>";
                
                try {
                    $db = Database::getInstance()->getConnection();
                    
                    // 检查所有表
                    $tables = [];
                    $result = $db->query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name");
                    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                        $tables[] = $row['name'];
                    }
                    
                    echo "<p><strong>现有数据表 (" . count($tables) . " 个):</strong></p>";
                    echo "<ul>";
                    foreach ($tables as $table) {
                        $count = $db->querySingle("SELECT COUNT(*) FROM $table");
                        echo "<li>$table ($count 条记录)</li>";
                    }
                    echo "</ul>";
                    
                    echo "<p style='color: green;'>✅ 数据库状态检查完成</p>";
                    
                } catch (Exception $e) {
                    echo "<p style='color: red;'>❌ 检查失败: " . htmlspecialchars($e->getMessage()) . "</p>";
                }
                
                echo "</div>";
            }
        }
        ?>
        
        <hr>
        <p style="text-align: center; color: #666; margin-top: 30px;">
            <small>数据库升级工具 v1.0 | 请在升级前备份数据</small>
        </p>
    </div>
</body>
</html>