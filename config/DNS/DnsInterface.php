<?php
/**
 * DNS接口定义
 */

namespace app\lib;

interface DnsInterface
{
    /**
     * 获取域名记录列表
     * @param int $PageNumber 页码
     * @param int $PageSize 每页数量
     * @param string $KeyWord 关键词
     * @param string $SubDomain 子域名
     * @param string $Value 记录值
     * @param string $Type 记录类型
     * @param string $Line 线路
     * @param string $Status 状态
     * @return array
     */
    public function getDomainRecords($PageNumber = 1, $PageSize = 20, $KeyWord = null, $SubDomain = null, $Value = null, $Type = null, $Line = null, $Status = null);

    /**
     * 添加DNS记录
     * @param string $Name 记录名称
     * @param string $Type 记录类型
     * @param string $Value 记录值
     * @param string $Line 线路
     * @param int $TTL TTL值
     * @param int $MX MX优先级
     * @param mixed $Weight 权重
     * @param string $Remark 备注
     * @return mixed
     */
    public function addDomainRecord($Name, $Type, $Value, $Line = '0', $TTL = 600, $MX = 1, $Weight = null, $Remark = null);

    /**
     * 修改DNS记录
     * @param string $RecordId 记录ID
     * @param string $Name 记录名称
     * @param string $Type 记录类型
     * @param string $Value 记录值
     * @param string $Line 线路
     * @param int $TTL TTL值
     * @param int $MX MX优先级
     * @param mixed $Weight 权重
     * @param string $Remark 备注
     * @return bool
     */
    public function updateDomainRecord($RecordId, $Name, $Type, $Value, $Line = '0', $TTL = 600, $MX = 1, $Weight = null, $Remark = null);

    /**
     * 删除DNS记录
     * @param string $RecordId 记录ID
     * @return bool
     */
    public function deleteDomainRecord($RecordId);

    /**
     * 获取域名信息
     * @param string $domain 域名
     * @return array
     */
    public function getDomainInfo($domain = null);
}