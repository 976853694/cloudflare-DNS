<?php
/**
 * MySQL数据库配置示例文件
 * 复制此文件为 database.php 并修改相应配置
 */

class Database {
    private static $instance = null;
    private $db;

    private function __construct() {
        // MySQL 数据库配置 - 请根据实际情况修改
        $host = 'localhost';
        $dbname = 'cloudflare_dns';
        $username = 'root';
        $password = '';
        $charset = 'utf8mb4';
        
        // 创建MySQL数据库连接
        try {
            $dsn = "mysql:host=$host;dbname=$dbname;charset=$charset";
            $options = [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
                PDO::ATTR_PERSISTENT => false
            ];
            
            $this->db = new PDO($dsn, $username, $password, $options);
            
            // 设置MySQL连接参数
            $this->db->exec("SET NAMES '$charset'");
            $this->db->exec("SET time_zone = '+00:00'");
            $this->db->exec("SET sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'");
            
        } catch (PDOException $e) {
            throw new Exception("数据库连接失败: " . $e->getMessage());
        }
        
        $this->initTables();
    }

    public static function getInstance() {
        if (self::$instance === null) {
            self::$instance = new Database();
        }
        return self::$instance;
    }

    public function getConnection() {
        return $this->db;
    }
    
    public function getPDO() {
        return $this->db;
    }

    private function initTables() {
        // MySQL数据库表初始化代码
        // 实际配置请参考原始 database.php 文件
    }
}
?>