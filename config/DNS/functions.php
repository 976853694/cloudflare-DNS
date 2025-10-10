<?php
/**
 * DNS相关辅助函数
 */

/**
 * 检查值是否为空或null
 * @param mixed $value 要检查的值
 * @return bool
 */
function isNullOrEmpty($value) {
    return $value === null || $value === '' || $value === false;
}

/**
 * 验证域名格式
 * @param string $domain 域名
 * @return bool
 */
function validateDomain($domain) {
    return filter_var($domain, FILTER_VALIDATE_DOMAIN, FILTER_FLAG_HOSTNAME);
}

/**
 * 验证IP地址格式
 * @param string $ip IP地址
 * @return bool
 */
function validateIP($ip) {
    return filter_var($ip, FILTER_VALIDATE_IP);
}

/**
 * 验证DNS记录类型
 * @param string $type 记录类型
 * @return bool
 */
function validateRecordType($type) {
    $allowedTypes = ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'SRV', 'CAA', 'PTR'];
    return in_array(strtoupper($type), $allowedTypes);
}

/**
 * 格式化DNS记录响应
 * @param array $record 原始记录数据
 * @return array
 */
function formatDnsRecord($record) {
    return [
        'id' => $record['RecordId'] ?? $record['id'] ?? '',
        'name' => $record['Name'] ?? $record['name'] ?? '',
        'type' => $record['Type'] ?? $record['type'] ?? '',
        'value' => $record['Value'] ?? $record['value'] ?? '',
        'ttl' => $record['TTL'] ?? $record['ttl'] ?? 600,
        'priority' => $record['MX'] ?? $record['priority'] ?? 0,
        'status' => $record['Status'] ?? $record['status'] ?? 'ENABLE'
    ];
}

/**
 * 处理API错误响应
 * @param array $response API响应
 * @return array
 */
function handleApiError($response) {
    if (isset($response['Response']['Error'])) {
        $error = $response['Response']['Error'];
        return [
            'success' => false,
            'message' => $error['Message'] ?? '未知错误',
            'code' => $error['Code'] ?? 'UNKNOWN_ERROR'
        ];
    }
    
    return [
        'success' => true,
        'data' => $response['Response'] ?? $response
    ];
}

/**
 * 生成请求ID
 * @return string
 */
function generateRequestId() {
    return 'req_' . uniqid() . '_' . mt_rand(1000, 9999);
}

/**
 * 记录DNS操作日志
 * @param string $action 操作类型
 * @param string $domain 域名
 * @param array $params 操作参数
 * @param array $result 操作结果
 */
function logDnsOperation($action, $domain, $params = [], $result = []) {
    $logData = [
        'timestamp' => date('Y-m-d H:i:s'),
        'action' => $action,
        'domain' => $domain,
        'params' => $params,
        'result' => $result,
        'ip' => $_SERVER['REMOTE_ADDR'] ?? 'unknown'
    ];
    
    $logFile = __DIR__ . '/../logs/dns_operations.log';
    $logDir = dirname($logFile);
    
    if (!is_dir($logDir)) {
        @mkdir($logDir, 0755, true);
    }
    
    @file_put_contents($logFile, json_encode($logData) . "\n", FILE_APPEND | LOCK_EX);
}