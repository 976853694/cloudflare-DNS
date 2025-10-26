<?php
/**
 * 用户组权限管理类
 * 提供用户组相关的权限检查和管理功能
 */

class UserGroupManager {
    private $db;
    
    public function __construct($db = null) {
        if ($db === null) {
            $this->db = Database::getInstance()->getConnection();
        } else {
            $this->db = $db;
        }
    }
    
    /**
     * 获取用户组信息
     * @param int $user_id 用户ID
     * @return array|null 用户组信息
     */
    public function getUserGroup($user_id) {
        try {
            $stmt = $this->db->prepare("
                SELECT ug.* 
                FROM user_groups ug 
                INNER JOIN users u ON u.group_id = ug.id 
                WHERE u.id = ? AND ug.is_active = 1
            ");
            $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
            $result = $stmt->execute();
            
            $group = $result->fetchArray(SQLITE3_ASSOC);
            return $group ? $group : null;
            
        } catch (Exception $e) {
            error_log("获取用户组失败: " . $e->getMessage());
            return null;
        }
    }
    
    /**
     * 通过组ID获取用户组信息
     * @param int $group_id 用户组ID
     * @return array|null 用户组信息
     */
    public function getGroupById($group_id) {
        try {
            $stmt = $this->db->prepare("SELECT * FROM user_groups WHERE id = ?");
            $stmt->bindValue(1, $group_id, SQLITE3_INTEGER);
            $result = $stmt->execute();
            
            $group = $result->fetchArray(SQLITE3_ASSOC);
            return $group ? $group : null;
            
        } catch (Exception $e) {
            error_log("获取用户组失败: " . $e->getMessage());
            return null;
        }
    }
    
    /**
     * 检查用户是否有权限访问指定域名
     * @param int $user_id 用户ID
     * @param int $domain_id 域名ID
     * @return bool
     */
    public function checkDomainPermission($user_id, $domain_id) {
        try {
            $group = $this->getUserGroup($user_id);
            
            if (!$group) {
                return false;
            }
            
            // 如果可以访问所有域名
            if ($group['can_access_all_domains'] == 1) {
                return true;
            }
            
            // 检查是否在域名白名单中
            $stmt = $this->db->prepare("
                SELECT COUNT(*) 
                FROM user_group_domains ugd 
                INNER JOIN users u ON u.group_id = ugd.group_id 
                WHERE u.id = ? AND ugd.domain_id = ?
            ");
            $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
            $stmt->bindValue(2, $domain_id, SQLITE3_INTEGER);
            $result = $stmt->execute();
            
            $count = $result->fetchArray(SQLITE3_NUM)[0];
            return $count > 0;
            
        } catch (Exception $e) {
            error_log("检查域名权限失败: " . $e->getMessage());
            return false;
        }
    }
    
    /**
     * 获取用户可访问的域名列表
     * @param int $user_id 用户ID
     * @return array 域名数组
     */
    public function getAccessibleDomains($user_id) {
        try {
            $group = $this->getUserGroup($user_id);
            
            if (!$group) {
                return [];
            }
            
            // 如果可以访问所有域名
            if ($group['can_access_all_domains'] == 1) {
                $result = $this->db->query("SELECT * FROM domains WHERE status = 1 ORDER BY domain_name");
                $domains = [];
                while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                    $domains[] = $row;
                }
                return $domains;
            }
            
            // 获取权限范围内的域名
            $stmt = $this->db->prepare("
                SELECT d.* 
                FROM domains d 
                INNER JOIN user_group_domains ugd ON ugd.domain_id = d.id 
                INNER JOIN users u ON u.group_id = ugd.group_id 
                WHERE u.id = ? AND d.status = 1 
                ORDER BY d.domain_name
            ");
            $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
            $result = $stmt->execute();
            
            $domains = [];
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $domains[] = $row;
            }
            
            return $domains;
            
        } catch (Exception $e) {
            error_log("获取可访问域名失败: " . $e->getMessage());
            return [];
        }
    }
    
    /**
     * 获取用户添加记录所需积分
     * @param int $user_id 用户ID
     * @return int 所需积分数
     */
    public function getRequiredPoints($user_id) {
        try {
            $group = $this->getUserGroup($user_id);
            
            if (!$group) {
                // 默认消耗1积分
                return 1;
            }
            
            return intval($group['points_per_record']);
            
        } catch (Exception $e) {
            error_log("获取所需积分失败: " . $e->getMessage());
            return 1;
        }
    }
    
    /**
     * 检查用户是否达到记录数量限制
     * @param int $user_id 用户ID
     * @return bool true=未达到限制，false=已达到限制
     */
    public function checkRecordLimit($user_id) {
        try {
            $group = $this->getUserGroup($user_id);
            
            if (!$group) {
                return false;
            }
            
            // -1 表示无限制
            if ($group['max_records'] == -1) {
                return true;
            }
            
            // 获取用户当前记录数
            $stmt = $this->db->prepare("
                SELECT COUNT(*) 
                FROM dns_records 
                WHERE user_id = ? AND status = 1
            ");
            $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
            $result = $stmt->execute();
            
            $current_count = $result->fetchArray(SQLITE3_NUM)[0];
            
            return $current_count < $group['max_records'];
            
        } catch (Exception $e) {
            error_log("检查记录限制失败: " . $e->getMessage());
            return false;
        }
    }
    
    /**
     * 获取用户当前记录数
     * @param int $user_id 用户ID
     * @return int 当前记录数
     */
    public function getCurrentRecordCount($user_id) {
        try {
            $stmt = $this->db->prepare("
                SELECT COUNT(*) 
                FROM dns_records 
                WHERE user_id = ? AND status = 1
            ");
            $stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
            $result = $stmt->execute();
            
            return intval($result->fetchArray(SQLITE3_NUM)[0]);
            
        } catch (Exception $e) {
            error_log("获取当前记录数失败: " . $e->getMessage());
            return 0;
        }
    }
    
    /**
     * 修改用户组
     * @param int $user_id 用户ID
     * @param int $new_group_id 新用户组ID
     * @param int $admin_id 管理员ID
     * @return bool
     */
    public function changeUserGroup($user_id, $new_group_id, $admin_id) {
        try {
            // 验证新用户组是否存在
            $group = $this->getGroupById($new_group_id);
            if (!$group) {
                return false;
            }
            
            // 更新用户组
            $stmt = $this->db->prepare("
                UPDATE users 
                SET group_id = ?, 
                    group_changed_at = datetime('now'), 
                    group_changed_by = ? 
                WHERE id = ?
            ");
            $stmt->bindValue(1, $new_group_id, SQLITE3_INTEGER);
            $stmt->bindValue(2, $admin_id, SQLITE3_INTEGER);
            $stmt->bindValue(3, $user_id, SQLITE3_INTEGER);
            
            return $stmt->execute() !== false;
            
        } catch (Exception $e) {
            error_log("修改用户组失败: " . $e->getMessage());
            return false;
        }
    }
    
    /**
     * 获取所有用户组列表
     * @param bool $only_active 是否只获取启用的组
     * @return array
     */
    public function getAllGroups($only_active = false) {
        try {
            $sql = "SELECT * FROM user_groups";
            if ($only_active) {
                $sql .= " WHERE is_active = 1";
            }
            $sql .= " ORDER BY priority DESC, id ASC";
            
            $result = $this->db->query($sql);
            
            $groups = [];
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $groups[] = $row;
            }
            
            return $groups;
            
        } catch (Exception $e) {
            error_log("获取用户组列表失败: " . $e->getMessage());
            return [];
        }
    }
    
    /**
     * 获取用户组的域名权限列表
     * @param int $group_id 用户组ID
     * @return array 域名ID数组
     */
    public function getGroupDomains($group_id) {
        try {
            $stmt = $this->db->prepare("
                SELECT domain_id 
                FROM user_group_domains 
                WHERE group_id = ?
            ");
            $stmt->bindValue(1, $group_id, SQLITE3_INTEGER);
            $result = $stmt->execute();
            
            $domain_ids = [];
            while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                $domain_ids[] = $row['domain_id'];
            }
            
            return $domain_ids;
            
        } catch (Exception $e) {
            error_log("获取用户组域名权限失败: " . $e->getMessage());
            return [];
        }
    }
    
    /**
     * 设置用户组的域名权限
     * @param int $group_id 用户组ID
     * @param array $domain_ids 域名ID数组
     * @return bool
     */
    public function setGroupDomains($group_id, $domain_ids) {
        try {
            // 开始事务
            $this->db->exec("BEGIN TRANSACTION");
            
            // 删除现有权限
            $stmt = $this->db->prepare("DELETE FROM user_group_domains WHERE group_id = ?");
            $stmt->bindValue(1, $group_id, SQLITE3_INTEGER);
            $stmt->execute();
            
            // 添加新权限
            if (!empty($domain_ids)) {
                $stmt = $this->db->prepare("
                    INSERT INTO user_group_domains (group_id, domain_id) 
                    VALUES (?, ?)
                ");
                
                foreach ($domain_ids as $domain_id) {
                    $stmt->bindValue(1, $group_id, SQLITE3_INTEGER);
                    $stmt->bindValue(2, $domain_id, SQLITE3_INTEGER);
                    $stmt->execute();
                }
            }
            
            // 提交事务
            $this->db->exec("COMMIT");
            
            return true;
            
        } catch (Exception $e) {
            // 回滚事务
            $this->db->exec("ROLLBACK");
            error_log("设置用户组域名权限失败: " . $e->getMessage());
            return false;
        }
    }
    
    /**
     * 检查子域名前缀长度是否符合用户组的限制
     * @param int $user_id 用户ID
     * @param string $subdomain 子域名前缀
     * @return array ['allowed' => bool, 'message' => string]
     */
    public function checkPrefixLengthRestriction($user_id, $subdomain) {
        try {
            $group = $this->getUserGroup($user_id);
            
            if (!$group) {
                return ['allowed' => false, 'message' => '用户组信息获取失败'];
            }
            
            // 如果没有设置前缀长度限制，则允许（-1或0表示不限制）
            if (!isset($group['max_prefix_length']) || $group['max_prefix_length'] <= 0) {
                return ['allowed' => true, 'message' => ''];
            }
            
            $min_length = intval($group['max_prefix_length']);
            $subdomain_length = strlen($subdomain);
            
            // 检查子域名长度是否低于最小限制
            if ($subdomain_length < $min_length) {
                return [
                    'allowed' => false, 
                    'message' => "子域名前缀长度不足！您的用户组最少需要 {$min_length} 个字符，当前为 {$subdomain_length} 个字符"
                ];
            }
            
            return ['allowed' => true, 'message' => ''];
            
        } catch (Exception $e) {
            error_log("检查前缀长度限制失败: " . $e->getMessage());
            return ['allowed' => false, 'message' => '系统错误'];
        }
    }
    
    /**
     * 获取用户组的前缀长度限制
     * @param int $user_id 用户ID
     * @return int 最小长度，-1或0表示不限制
     */
    public function getMinPrefixLength($user_id) {
        try {
            $group = $this->getUserGroup($user_id);
            
            if (!$group) {
                return -1;
            }
            
            return isset($group['max_prefix_length']) ? intval($group['max_prefix_length']) : -1;
            
        } catch (Exception $e) {
            error_log("获取前缀长度限制失败: " . $e->getMessage());
            return -1;
        }
    }
}

