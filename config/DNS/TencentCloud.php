<?php
/**
 * 腾讯云API客户端
 */

namespace app\lib\client;

class TencentCloud
{
    private $secretId;
    private $secretKey;
    private $endpoint;
    private $service;
    private $version;
    private $region;
    private $proxy;

    public function __construct($secretId, $secretKey, $endpoint, $service, $version, $region = null, $proxy = null)
    {
        $this->secretId = $secretId;
        $this->secretKey = $secretKey;
        $this->endpoint = $endpoint;
        $this->service = $service;
        $this->version = $version;
        $this->region = $region;
        $this->proxy = $proxy;
    }

    /**
     * 发送API请求
     * @param string $action API动作
     * @param array $params 请求参数
     * @return array
     */
    public function request($action, $params = [])
    {
        $headers = $this->buildHeaders($action, $params);
        $url = 'https://' . $this->endpoint;
        
        $postData = json_encode($params);
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $postData);
        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, false);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        
        if ($this->proxy) {
            curl_setopt($ch, CURLOPT_PROXY, $this->proxy);
        }
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($response === false) {
            $error = curl_error($ch);
            throw new \Exception('cURL请求失败: ' . $error);
        }
        
        // 检查HTTP状态码
        if ($httpCode >= 400) {
            throw new \Exception('HTTP请求失败，状态码: ' . $httpCode . '，响应: ' . substr($response, 0, 500));
        }
        
        $result = json_decode($response, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new \Exception('响应JSON解析失败: ' . json_last_error_msg() . '，原始响应: ' . substr($response, 0, 500));
        }
        
        // 检查腾讯云API错误
        if (isset($result['Response']['Error'])) {
            $error = $result['Response']['Error'];
            throw new \Exception('腾讯云API错误: ' . $error['Code'] . ' - ' . $error['Message']);
        }
        
        return $result;
    }

    /**
     * 构建请求头
     * @param string $action API动作
     * @param array $params 请求参数
     * @return array
     */
    private function buildHeaders($action, $params)
    {
        $timestamp = time();
        $date = gmdate('Y-m-d', $timestamp);
        
        // 构建规范请求字符串
        $httpRequestMethod = 'POST';
        $canonicalUri = '/';
        $canonicalQueryString = '';
        $canonicalHeaders = "content-type:application/json; charset=utf-8\n" .
                           "host:" . $this->endpoint . "\n";
        $signedHeaders = 'content-type;host';
        $hashedRequestPayload = hash('sha256', json_encode($params));
        
        $canonicalRequest = $httpRequestMethod . "\n" .
                           $canonicalUri . "\n" .
                           $canonicalQueryString . "\n" .
                           $canonicalHeaders . "\n" .
                           $signedHeaders . "\n" .
                           $hashedRequestPayload;
        
        // 构建待签名字符串
        $algorithm = 'TC3-HMAC-SHA256';
        // DNSPod API不需要region
        $credentialScope = $date . '/' . $this->service . '/tc3_request';
        $stringToSign = $algorithm . "\n" .
                       $timestamp . "\n" .
                       $credentialScope . "\n" .
                       hash('sha256', $canonicalRequest);
        
        // 计算签名 (DNSPod API不需要region)
        $secretDate = hash_hmac('sha256', $date, 'TC3' . $this->secretKey, true);
        $secretService = hash_hmac('sha256', $this->service, $secretDate, true);
        $secretSigning = hash_hmac('sha256', 'tc3_request', $secretService, true);
        $signature = hash_hmac('sha256', $stringToSign, $secretSigning);
        
        // 构建Authorization
        $authorization = $algorithm . ' ' .
                        'Credential=' . $this->secretId . '/' . $credentialScope . ', ' .
                        'SignedHeaders=' . $signedHeaders . ', ' .
                        'Signature=' . $signature;
        
        return [
            'Content-Type: application/json; charset=utf-8',
            'Host: ' . $this->endpoint,
            'X-TC-Action: ' . $action,
            'X-TC-Version: ' . $this->version,
            'X-TC-Timestamp: ' . $timestamp,
            'Authorization: ' . $authorization
        ];
    }
}