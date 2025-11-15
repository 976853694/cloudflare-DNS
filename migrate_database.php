<?php
/**
 * 数据库迁移脚本
 * 用于验证和创建所有必需的表和字段
 * 
 * 使用方法：
 * php migrate_database.php
 */

require_once 'config/database.php';
require_once 'includes/database_validator.php';

echo "╔════════════════════════════════════════════════════════╗\n";
echo "║          数据库迁移和验证工具                            ║\n";
echo "╚════════════════════════════════════════════════════════╝\n\n";

try {
    $validator = new DatabaseValidator();
    
    echo "📊 正在分析数据库结构...\n\n";
    
    // 获取数据库信息
    $dbInfo = $validator->getDatabaseInfo();
    
    echo "当前数据库表列表：\n";
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
    foreach ($dbInfo as $tableName => $info) {
        echo sprintf("  ✓ %-30s (%d 个字段)\n", $tableName, $info['column_count']);
    }
    echo "\n";
    
    // 执行验证和迁移
    echo "🔧 正在验证和迁移数据库...\n";
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
    
    $result = $validator->validateAndMigrate();
    
    if ($result['success']) {
        echo "✅ " . $result['message'] . "\n\n";
        
        // 验证关键表
        echo "🔍 验证关键表和字段：\n";
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        
        $checks = [
            'operation_logs' => [
                'description' => '操作日志表（频率限制）',
                'columns' => ['user_id', 'action', 'ip_address', 'operation_time']
            ],
            'dns_records' => [
                'description' => 'DNS记录表',
                'columns' => ['status', 'cloudflare_id', 'is_system', 'remark']
            ],
            'login_attempts' => [
                'description' => '登录尝试表（安全功能）',
                'columns' => ['ip_address', 'username', 'type', 'attempt_time']
            ]
        ];
        
        $allPassed = true;
        
        foreach ($checks as $tableName => $config) {
            echo "\n📋 {$config['description']} ($tableName):\n";
            
            if (!$validator->tableExists($tableName)) {
                echo "  ❌ 表不存在\n";
                $allPassed = false;
                continue;
            }
            
            echo "  ✓ 表存在\n";
            
            foreach ($config['columns'] as $column) {
                $exists = $validator->columnExists($tableName, $column);
                $status = $exists ? '✓' : '❌';
                echo "    $status $column\n";
                if (!$exists) {
                    $allPassed = false;
                }
            }
        }
        
        echo "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
        
        if ($allPassed) {
            echo "✅ 所有检查通过！数据库结构完整。\n";
        } else {
            echo "⚠️  部分检查未通过，请检查上述错误。\n";
        }
        
    } else {
        echo "❌ 迁移失败: " . $result['message'] . "\n";
        exit(1);
    }
    
} catch (Exception $e) {
    echo "❌ 错误: " . $e->getMessage() . "\n";
    exit(1);
}

echo "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
echo "✅ 数据库迁移完成！\n";
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n";
?>
