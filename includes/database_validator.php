<?php
/**
 * 数据库验证和自动迁移类
 * 确保所有必需的表和字段都存在
 */

class DatabaseValidator {
    private $db;
    
    public function __construct($db = null) {
        if ($db === null) {
            $this->db = Database::getInstance()->getConnection();
        } else {
            $this->db = $db;
        }
    }
    
    /**
     * 验证并创建所有必需的表和字段
     */
    public function validateAndMigrate() {
        try {
            // 验证 operation_logs 表
            $this->validateOperationLogsTable();
            
            // 验证 dns_records 表的字段
            $this->validateDnsRecordsTable();
            
            // 验证 login_attempts 表（安全功能）
            $this->validateLoginAttemptsTable();
            
            return ['success' => true, 'message' => '数据库验证完成'];
        } catch (Exception $e) {
            error_log("数据库验证失败: " . $e->getMessage());
            return ['success' => false, 'message' => $e->getMessage()];
        }
    }
    
    /**
     * 验证 operation_logs 表
     */
    private function validateOperationLogsTable() {
        // 检查表是否存在
        $tableExists = $this->db->querySingle(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='operation_logs'"
        );
        
        if (!$tableExists) {
            // 创建表
            $this->db->exec("CREATE TABLE operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                ip_address TEXT,
                operation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )");
            
            // 创建索引
            $this->db->exec("CREATE INDEX IF NOT EXISTS idx_user_action ON operation_logs(user_id, action, operation_time)");
            
            error_log("✓ 已创建 operation_logs 表");
        } else {
            // 表存在，验证字段
            $this->validateTableColumns('operation_logs', [
                'id' => 'INTEGER PRIMARY KEY AUTOINCREMENT',
                'user_id' => 'INTEGER NOT NULL',
                'action' => 'TEXT NOT NULL',
                'ip_address' => 'TEXT',
                'operation_time' => 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
            ]);
            
            // 确保索引存在
            $this->db->exec("CREATE INDEX IF NOT EXISTS idx_user_action ON operation_logs(user_id, action, operation_time)");
        }
    }
    
    /**
     * 验证 dns_records 表的必需字段
     */
    private function validateDnsRecordsTable() {
        $tableExists = $this->db->querySingle(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dns_records'"
        );
        
        if (!$tableExists) {
            throw new Exception("dns_records 表不存在，请先运行系统安装程序");
        }
        
        // 获取现有字段
        $columns = $this->getTableColumns('dns_records');
        
        // 验证必需的字段
        $requiredFields = [
            'status' => 'INTEGER DEFAULT 1',
            'cloudflare_id' => 'TEXT',
            'is_system' => 'INTEGER DEFAULT 0',
            'remark' => 'TEXT DEFAULT \'\'',
        ];
        
        foreach ($requiredFields as $field => $definition) {
            if (!in_array($field, $columns)) {
                // 字段不存在，需要添加
                $this->addColumn('dns_records', $field, $definition);
                error_log("✓ 已添加 dns_records.$field 字段");
            }
        }
    }
    
    /**
     * 验证 login_attempts 表（安全功能）
     */
    private function validateLoginAttemptsTable() {
        $tableExists = $this->db->querySingle(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'"
        );
        
        if (!$tableExists) {
            $this->db->exec("CREATE TABLE login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                username TEXT NOT NULL,
                type TEXT NOT NULL,
                attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )");
            
            error_log("✓ 已创建 login_attempts 表");
        }
    }
    
    /**
     * 获取表的所有字段名
     */
    private function getTableColumns($tableName) {
        $result = $this->db->query("PRAGMA table_info($tableName)");
        $columns = [];
        
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $columns[] = $row['name'];
        }
        
        return $columns;
    }
    
    /**
     * 验证表的字段
     */
    private function validateTableColumns($tableName, $expectedColumns) {
        $existingColumns = $this->getTableColumns($tableName);
        
        foreach ($expectedColumns as $columnName => $definition) {
            if (!in_array($columnName, $existingColumns)) {
                error_log("警告: $tableName 表缺少字段 $columnName");
            }
        }
    }
    
    /**
     * 添加字段到表
     * 注意：SQLite 的 ALTER TABLE 有限制，某些情况下可能需要重建表
     */
    private function addColumn($tableName, $columnName, $definition) {
        try {
            // 尝试直接添加字段
            $sql = "ALTER TABLE $tableName ADD COLUMN $columnName $definition";
            $this->db->exec($sql);
        } catch (Exception $e) {
            error_log("添加字段失败: $tableName.$columnName - " . $e->getMessage());
            throw $e;
        }
    }
    
    /**
     * 检查表是否存在
     */
    public function tableExists($tableName) {
        $result = $this->db->querySingle(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='$tableName'"
        );
        return $result !== null;
    }
    
    /**
     * 检查字段是否存在
     */
    public function columnExists($tableName, $columnName) {
        $columns = $this->getTableColumns($tableName);
        return in_array($columnName, $columns);
    }
    
    /**
     * 获取数据库信息
     */
    public function getDatabaseInfo() {
        $tables = [];
        $result = $this->db->query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name");
        
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
            $tableName = $row['name'];
            $columns = $this->getTableColumns($tableName);
            $tables[$tableName] = [
                'columns' => $columns,
                'column_count' => count($columns)
            ];
        }
        
        return $tables;
    }
}
?>
