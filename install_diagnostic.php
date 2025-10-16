<?php
/**
 * 安装诊断工具 - 用于检测安装过程中可能出现的问题
 */

// 设置错误报告
error_reporting(E_ALL);
ini_set('display_errors', 1);

$results = [];

// 1. 检查PHP版本
$results['PHP版本'] = [
    'value' => PHP_VERSION,
    'status' => version_compare(PHP_VERSION, '7.0.0', '>=') ? 'ok' : 'error',
    'message' => version_compare(PHP_VERSION, '7.0.0', '>=') ? '符合要求' : '需要PHP 7.0或更高版本'
];

// 2. 检查SQLite3扩展
$results['SQLite3扩展'] = [
    'value' => extension_loaded('sqlite3') ? '已加载' : '未加载',
    'status' => extension_loaded('sqlite3') ? 'ok' : 'error',
    'message' => extension_loaded('sqlite3') ? 'SQLite3 版本: ' . SQLite3::version()['versionString'] : '请启用SQLite3扩展'
];

// 3. 检查data目录
$data_dir = __DIR__ . '/data';
$data_exists = is_dir($data_dir);
$data_writable = $data_exists && is_writable($data_dir);

$results['data目录'] = [
    'value' => $data_exists ? ($data_writable ? '存在且可写' : '存在但不可写') : '不存在',
    'status' => $data_writable ? 'ok' : ($data_exists ? 'warning' : 'error'),
    'message' => $data_writable ? '权限正常' : ($data_exists ? '请设置data目录权限为755或777' : '将自动创建')
];

// 4. 检查磁盘空间
$disk_free = disk_free_space('.');
$disk_total = disk_total_space('.');
$results['磁盘空间'] = [
    'value' => $disk_free !== false ? formatBytes($disk_free) . ' / ' . formatBytes($disk_total) : '无法检测',
    'status' => $disk_free > 10 * 1024 * 1024 ? 'ok' : 'warning',
    'message' => $disk_free > 10 * 1024 * 1024 ? '空间充足' : '磁盘空间不足10MB'
];

// 5. 测试SQLite写入性能
$test_result = testSQLitePerformance();
$results['SQLite写入测试'] = $test_result;

// 6. 检查文件权限设置
$results['umask设置'] = [
    'value' => sprintf('%04o', umask()),
    'status' => 'info',
    'message' => '当前umask值，影响新文件的默认权限'
];

// 7. 检查是否已安装
$install_lock = __DIR__ . '/data/install.lock';
$results['安装状态'] = [
    'value' => file_exists($install_lock) ? '已安装' : '未安装',
    'status' => file_exists($install_lock) ? 'warning' : 'ok',
    'message' => file_exists($install_lock) ? '检测到install.lock文件，如需重新安装请先删除' : '可以开始安装'
];

// 辅助函数
function formatBytes($bytes) {
    if ($bytes < 1024) return $bytes . ' B';
    if ($bytes < 1048576) return round($bytes / 1024, 2) . ' KB';
    if ($bytes < 1073741824) return round($bytes / 1048576, 2) . ' MB';
    return round($bytes / 1073741824, 2) . ' GB';
}

function testSQLitePerformance() {
    $test_db = __DIR__ . '/data/test_performance.db';
    
    try {
        // 确保data目录存在
        if (!is_dir(__DIR__ . '/data')) {
            mkdir(__DIR__ . '/data', 0755, true);
        }
        
        // 删除旧测试文件
        if (file_exists($test_db)) {
            unlink($test_db);
        }
        if (file_exists($test_db . '-wal')) {
            unlink($test_db . '-wal');
        }
        if (file_exists($test_db . '-shm')) {
            unlink($test_db . '-shm');
        }
        
        $start_time = microtime(true);
        
        // 创建测试数据库
        $db = new SQLite3($test_db);
        $db->busyTimeout(5000);
        $db->exec('PRAGMA journal_mode = WAL');
        $db->exec('PRAGMA synchronous = NORMAL');
        
        // 创建测试表
        $db->exec("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, data TEXT)");
        
        // 插入测试数据
        $db->exec('BEGIN TRANSACTION');
        for ($i = 0; $i < 100; $i++) {
            $db->exec("INSERT INTO test (data) VALUES ('test_data_$i')");
        }
        $db->exec('COMMIT');
        
        // 查询测试
        $result = $db->query("SELECT COUNT(*) as cnt FROM test");
        $row = $result->fetchArray();
        
        $db->close();
        
        $elapsed = round((microtime(true) - $start_time) * 1000, 2);
        
        // 清理测试文件
        @unlink($test_db);
        @unlink($test_db . '-wal');
        @unlink($test_db . '-shm');
        
        $status = 'ok';
        $message = "插入100条记录用时 {$elapsed}ms";
        
        if ($elapsed > 5000) {
            $status = 'error';
            $message .= ' - 性能极差，可能导致安装卡死';
        } elseif ($elapsed > 2000) {
            $status = 'warning';
            $message .= ' - 性能较慢，安装可能需要较长时间';
        } else {
            $message .= ' - 性能良好';
        }
        
        return [
            'value' => $elapsed . 'ms',
            'status' => $status,
            'message' => $message
        ];
        
    } catch (Exception $e) {
        // 清理可能的残留文件
        @unlink($test_db);
        @unlink($test_db . '-wal');
        @unlink($test_db . '-shm');
        
        return [
            'value' => '测试失败',
            'status' => 'error',
            'message' => '错误: ' . $e->getMessage()
        ];
    }
}

?>
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>安装诊断工具</title>
    <link href="assets/css/bootstrap.min.css" rel="stylesheet">
    <link href="assets/css/fontawesome.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem 0;
        }
        .diagnostic-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            max-width: 900px;
            margin: 0 auto;
        }
        .diagnostic-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            text-align: center;
        }
        .status-ok { color: #28a745; }
        .status-warning { color: #ffc107; }
        .status-error { color: #dc3545; }
        .status-info { color: #17a2b8; }
    </style>
</head>
<body>
    <div class="container">
        <div class="diagnostic-container">
            <div class="diagnostic-header">
                <h1><i class="fas fa-stethoscope me-2"></i>安装诊断工具</h1>
                <p class="mb-0">检测安装环境和潜在问题</p>
            </div>
            
            <div class="p-4">
                <div class="table-responsive">
                    <table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>检查项</th>
                                <th>检测结果</th>
                                <th>状态</th>
                                <th>说明</th>
                            </tr>
                        </thead>
                        <tbody>
                            <?php foreach ($results as $name => $result): ?>
                            <tr>
                                <td><strong><?php echo htmlspecialchars($name); ?></strong></td>
                                <td><?php echo htmlspecialchars($result['value']); ?></td>
                                <td class="status-<?php echo $result['status']; ?>">
                                    <?php
                                    $icons = [
                                        'ok' => 'fa-check-circle',
                                        'warning' => 'fa-exclamation-triangle',
                                        'error' => 'fa-times-circle',
                                        'info' => 'fa-info-circle'
                                    ];
                                    ?>
                                    <i class="fas <?php echo $icons[$result['status']]; ?>"></i>
                                </td>
                                <td><?php echo htmlspecialchars($result['message']); ?></td>
                            </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
                
                <?php
                $has_error = false;
                $has_warning = false;
                foreach ($results as $result) {
                    if ($result['status'] === 'error') $has_error = true;
                    if ($result['status'] === 'warning') $has_warning = true;
                }
                ?>
                
                <?php if ($has_error): ?>
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-triangle me-2"></i>发现严重问题</h5>
                    <p class="mb-0">请先解决标记为错误的问题后再进行安装。</p>
                </div>
                <?php elseif ($has_warning): ?>
                <div class="alert alert-warning">
                    <h5><i class="fas fa-exclamation-triangle me-2"></i>发现警告</h5>
                    <p class="mb-0">建议解决警告问题以获得更好的安装体验，但可以尝试继续安装。</p>
                </div>
                <?php else: ?>
                <div class="alert alert-success">
                    <h5><i class="fas fa-check-circle me-2"></i>环境检查通过</h5>
                    <p class="mb-0">您的服务器环境符合安装要求，可以开始安装。</p>
                </div>
                <?php endif; ?>
                
                <div class="text-center mt-4">
                    <a href="install.php" class="btn btn-primary btn-lg me-2">
                        <i class="fas fa-download me-2"></i>开始安装
                    </a>
                    <button onclick="location.reload()" class="btn btn-outline-secondary btn-lg">
                        <i class="fas fa-redo me-2"></i>重新检测
                    </button>
                </div>
                
                <div class="mt-4">
                    <h5>常见问题解决方法：</h5>
                    <ul>
                        <li><strong>data目录不可写：</strong>执行命令 <code>chmod 755 data</code> 或 <code>chmod 777 data</code></li>
                        <li><strong>SQLite写入慢：</strong>可能是服务器磁盘I/O性能差，建议使用SSD硬盘或联系服务器提供商</li>
                        <li><strong>磁盘空间不足：</strong>清理服务器磁盘空间，至少保留50MB可用空间</li>
                        <li><strong>已安装：</strong>如需重新安装，删除 <code>data/install.lock</code> 文件</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
