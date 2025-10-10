<?php
/**
 * DNS提供商配置文件
 * 用于整合各种DNS服务提供商到系统中
 */

// 引入DNS接口和依赖文件
require_once __DIR__ . '/DNS/DnsInterface.php';
require_once __DIR__ . '/DNS/TencentCloud.php';
require_once __DIR__ . '/DNS/functions.php';
require_once __DIR__ . '/dnspod.php';
require_once __DIR__ . '/powerdns.php';

use app\lib\dns\dnspod;
use app\lib\dns\powerdns;

/**
 * DNS提供商工厂类
 */
class DNSProviderFactory {
    
    /**
     * 创建DNS提供商实例
     */
    public static function create($type, $config) {
        switch ($type) {
            case 'dnspod':
                return new dnspod($config);
            case 'powerdns':
                return new powerdns($config);
            default:
                throw new Exception("不支持的DNS提供商类型: {$type}");
        }
    }
    
    /**
     * 获取支持的DNS提供商列表
     */
    public static function getSupportedProviders() {
        return [
            'dnspod' => [
                'name' => 'DNSPod',
                'description' => '腾讯云DNSPod服务',
                'fields' => [
                    'secret_id' => '必填',
                    'secret_key' => '必填',
                    'domain' => '必填'
                ]
            ],
            'powerdns' => [
                'name' => 'PowerDNS',
                'description' => 'PowerDNS权威DNS服务器',
                'fields' => [
                    'api_url' => '必填',
                    'api_key' => '必填',
                    'server_id' => '可选，默认localhost',
                    'domain_id' => '必填'
                ]
            ]
        ];
    }
    
    /**
     * 转换系统配置为DNS库所需格式
     */
    public static function convertConfig($type, $systemConfig) {
        switch ($type) {
            case 'dnspod':
                return [
                    'ak' => $systemConfig['api_key'],      // secret_id存储在api_key字段
                    'sk' => $systemConfig['provider_uid'], // secret_key存储在provider_uid字段
                    'domain' => $systemConfig['domain_name'] ?? $systemConfig['domain'],
                    'proxy' => isset($systemConfig['proxy']) ? $systemConfig['proxy'] : false
                ];
            case 'powerdns':
                return [
                    'ak' => parse_url($systemConfig['api_url'], PHP_URL_HOST),
                    'sk' => parse_url($systemConfig['api_url'], PHP_URL_PORT) ?: '8081',
                    'ext' => $systemConfig['api_key'],
                    'domain' => $systemConfig['domain'],
                    'domainid' => $systemConfig['domain_id'],
                    'proxy' => isset($systemConfig['proxy']) ? $systemConfig['proxy'] : false
                ];
            default:
                throw new Exception("不支持的DNS提供商类型: {$type}");
        }
    }
    
    /**
     * 测试DNS提供商连接
     */
    public static function testConnection($type, $config) {
        try {
            $dns = self::create($type, $config);
            return $dns->check();
        } catch (Exception $e) {
            error_log("DNS连接测试失败 [{$type}]: " . $e->getMessage());
            return false;
        }
    }
}

/**
 * DNS操作帮助函数
 */
function getDNSProvider($channelId, $channelType) {
    $db = Database::getInstance()->getConnection();
    
    switch ($channelType) {
        case 'dnspod':
            $stmt = $db->prepare("SELECT * FROM dnspod_accounts WHERE id = ? AND status = 1");
            $stmt->bindValue(1, $channelId, SQLITE3_INTEGER);
            $result = $stmt->execute();
            $account = $result->fetchArray(SQLITE3_ASSOC);
            
            if (!$account) {
                throw new Exception("DNSPod账户不存在或已禁用");
            }
            
            $config = DNSProviderFactory::convertConfig('dnspod', [
                'secret_id' => $account['secret_id'],
                'secret_key' => $account['secret_key'],
                'domain' => '' // 需要在调用时指定域名
            ]);
            
            return DNSProviderFactory::create('dnspod', $config);
            
        case 'powerdns':
            $stmt = $db->prepare("SELECT * FROM powerdns_accounts WHERE id = ? AND status = 1");
            $stmt->bindValue(1, $channelId, SQLITE3_INTEGER);
            $result = $stmt->execute();
            $account = $result->fetchArray(SQLITE3_ASSOC);
            
            if (!$account) {
                throw new Exception("PowerDNS账户不存在或已禁用");
            }
            
            $config = DNSProviderFactory::convertConfig('powerdns', [
                'api_url' => $account['api_url'],
                'api_key' => $account['api_key'],
                'domain' => '', // 需要在调用时指定域名
                'domain_id' => '' // 需要在调用时指定域名ID
            ]);
            
            return DNSProviderFactory::create('powerdns', $config);
            
        default:
            throw new Exception("不支持的DNS提供商类型: {$channelType}");
    }
}

/**
 * 获取DNS记录
 */
function getDNSRecords($channelId, $channelType, $domain, $options = []) {
    try {
        $dns = getDNSProvider($channelId, $channelType);
        
        // 设置域名
        if (method_exists($dns, 'setDomain')) {
            $dns->setDomain($domain);
        }
        
        $pageNumber = $options['page'] ?? 1;
        $pageSize = $options['limit'] ?? 20;
        $keyword = $options['keyword'] ?? null;
        $subdomain = $options['subdomain'] ?? null;
        $type = $options['type'] ?? null;
        
        return $dns->getDomainRecords($pageNumber, $pageSize, $keyword, $subdomain, null, $type);
        
    } catch (Exception $e) {
        error_log("获取DNS记录失败: " . $e->getMessage());
        return false;
    }
}

/**
 * 添加DNS记录
 */
function addDNSRecord($channelId, $channelType, $domain, $name, $type, $value, $options = []) {
    try {
        $dns = getDNSProvider($channelId, $channelType);
        
        // 设置域名
        if (method_exists($dns, 'setDomain')) {
            $dns->setDomain($domain);
        }
        
        $line = $options['line'] ?? 'default';
        $ttl = $options['ttl'] ?? 600;
        $mx = $options['mx'] ?? 1;
        $weight = $options['weight'] ?? null;
        $remark = $options['remark'] ?? null;
        
        return $dns->addDomainRecord($name, $type, $value, $line, $ttl, $mx, $weight, $remark);
        
    } catch (Exception $e) {
        error_log("添加DNS记录失败: " . $e->getMessage());
        return false;
    }
}

/**
 * 更新DNS记录
 */
function updateDNSRecord($channelId, $channelType, $domain, $recordId, $name, $type, $value, $options = []) {
    try {
        $dns = getDNSProvider($channelId, $channelType);
        
        // 设置域名
        if (method_exists($dns, 'setDomain')) {
            $dns->setDomain($domain);
        }
        
        $line = $options['line'] ?? 'default';
        $ttl = $options['ttl'] ?? 600;
        $mx = $options['mx'] ?? 1;
        $weight = $options['weight'] ?? null;
        $remark = $options['remark'] ?? null;
        
        return $dns->updateDomainRecord($recordId, $name, $type, $value, $line, $ttl, $mx, $weight, $remark);
        
    } catch (Exception $e) {
        error_log("更新DNS记录失败: " . $e->getMessage());
        return false;
    }
}

/**
 * 删除DNS记录
 */
function deleteDNSRecord($channelId, $channelType, $domain, $recordId) {
    try {
        $dns = getDNSProvider($channelId, $channelType);
        
        // 设置域名
        if (method_exists($dns, 'setDomain')) {
            $dns->setDomain($domain);
        }
        
        return $dns->deleteDomainRecord($recordId);
        
    } catch (Exception $e) {
        error_log("删除DNS记录失败: " . $e->getMessage());
        return false;
    }
}