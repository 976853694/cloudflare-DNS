<?php
/**
 * Dashboard 数据处理函数
 * 将数据查询逻辑从视图层分离
 */

/**
 * 获取系统核心统计数据
 * 优化：使用单次查询获取多个统计数据
 */
function getDashboardStats($db) {
    $stats = [];
    
    // 用户统计 - 一次性获取所有用户相关数据
    $userStats = $db->querySingle("
        SELECT 
            COUNT(*) as total_users,
            SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as active_users,
            SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) as inactive_users,
            SUM(CASE WHEN created_at >= date('now', '-7 days') THEN 1 ELSE 0 END) as this_week_users,
            COALESCE(SUM(points), 0) as total_points
        FROM users
    ", true);
    
    $stats = array_merge($stats, $userStats);
    
    // 域名和DNS记录统计 - 一次性获取
    $domainStats = $db->querySingle("
        SELECT 
            (SELECT COUNT(*) FROM domains) as total_domains,
            (SELECT COUNT(*) FROM dns_records) as total_records,
            (SELECT COUNT(*) FROM dns_records WHERE date(created_at) = date('now')) as today_records,
            (SELECT COUNT(DISTINCT domain_id) FROM dns_records) as domains_with_records
        FROM (SELECT 1)
    ", true);
    
    $stats = array_merge($stats, $domainStats);
    
    // 计算域名利用率
    $stats['domain_utilization'] = $stats['total_domains'] > 0 
        ? ($stats['domains_with_records'] / $stats['total_domains']) * 100 
        : 0;
    
    return $stats;
}

/**
 * 获取邀请系统统计
 * 优化：检查表结构并一次性获取数据
 */
function getInvitationStats($db) {
    $stats = [
        'total_invitations' => 0,
        'used_invitations' => 0,
        'active_invitations' => 0
    ];
    
    if (!getSetting('invitation_enabled', '1')) {
        return $stats;
    }
    
    // 检查表是否存在
    $tableExists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='invitations'");
    if (!$tableExists) {
        return $stats;
    }
    
    // 获取表结构
    $columns = getTableColumns($db, 'invitations');
    
    // 根据表结构构建查询
    if (in_array('is_active', $columns) && in_array('used_by', $columns)) {
        $invStats = $db->querySingle("
            SELECT 
                COUNT(*) as total_invitations,
                SUM(CASE WHEN used_by IS NOT NULL THEN 1 ELSE 0 END) as used_invitations,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_invitations
            FROM invitations
        ", true);
    } elseif (in_array('used_by', $columns)) {
        $invStats = $db->querySingle("
            SELECT 
                COUNT(*) as total_invitations,
                SUM(CASE WHEN used_by IS NOT NULL THEN 1 ELSE 0 END) as used_invitations
            FROM invitations
        ", true);
        $invStats['active_invitations'] = $invStats['total_invitations'] - $invStats['used_invitations'];
    } else {
        $invStats = $db->querySingle("
            SELECT 
                COUNT(*) as total_invitations,
                SUM(CASE WHEN last_used_at IS NOT NULL THEN 1 ELSE 0 END) as used_invitations
            FROM invitations
        ", true);
        $invStats['active_invitations'] = $invStats['total_invitations'] - $invStats['used_invitations'];
    }
    
    return $invStats;
}

/**
 * 获取卡密系统统计
 * 优化：智能检测字段并一次性查询
 */
function getCardKeyStats($db) {
    $stats = [
        'total_card_keys' => 0,
        'used_card_keys' => 0
    ];
    
    // 检查表是否存在
    $tableExists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='card_keys'");
    if (!$tableExists) {
        return $stats;
    }
    
    // 获取表结构
    $columns = getTableColumns($db, 'card_keys');
    
    // 根据表结构构建查询
    $usedCondition = '';
    if (in_array('used_by', $columns)) {
        $usedCondition = 'used_by IS NOT NULL';
    } elseif (in_array('used_count', $columns)) {
        $usedCondition = 'used_count > 0';
    } elseif (in_array('status', $columns)) {
        $usedCondition = "status = 'used'";
    } else {
        // 如果没有合适的字段，返回默认值
        $stats['total_card_keys'] = $db->querySingle("SELECT COUNT(*) FROM card_keys");
        return $stats;
    }
    
    $cardStats = $db->querySingle("
        SELECT 
            COUNT(*) as total_card_keys,
            SUM(CASE WHEN {$usedCondition} THEN 1 ELSE 0 END) as used_card_keys
        FROM card_keys
    ", true);
    
    return $cardStats;
}

/**
 * 获取用户注册趋势数据
 * 优化：使用单次查询获取7天数据
 */
function getWeeklyRegistrations($db) {
    $registrations = [];
    $max_count = 0;
    
    // 一次性查询7天的数据
    $result = $db->query("
        SELECT 
            date(created_at) as reg_date,
            COUNT(*) as count
        FROM users
        WHERE created_at >= date('now', '-7 days')
        GROUP BY date(created_at)
        ORDER BY reg_date
    ");
    
    // 创建日期索引的数组
    $dataByDate = [];
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $dataByDate[$row['reg_date']] = (int)$row['count'];
        $max_count = max($max_count, (int)$row['count']);
    }
    
    // 填充完整的7天数据（包括没有注册的日期）
    for ($i = 6; $i >= 0; $i--) {
        $date = date('Y-m-d', strtotime("-$i days"));
        $count = isset($dataByDate[$date]) ? $dataByDate[$date] : 0;
        $registrations[] = [
            'date' => $date,
            'count' => $count
        ];
        $max_count = max($max_count, $count);
    }
    
    return [
        'data' => $registrations,
        'max_count' => $max_count
    ];
}

/**
 * 获取最近注册的用户
 * 优化：只查询需要的字段
 */
function getRecentUsers($db, $limit = 5) {
    $users = [];
    
    $stmt = $db->prepare("
        SELECT id, username, email, status, points, created_at
        FROM users 
        ORDER BY created_at DESC 
        LIMIT ?
    ");
    $stmt->bindValue(1, $limit, SQLITE3_INTEGER);
    $result = $stmt->execute();
    
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $users[] = $row;
    }
    
    return $users;
}

/**
 * 获取最近的DNS记录
 * 优化：使用JOIN减少查询次数，只获取需要的字段
 */
function getRecentDNSRecords($db, $limit = 10) {
    $records = [];
    
    $stmt = $db->prepare("
        SELECT 
            dr.id,
            dr.subdomain,
            dr.type,
            dr.content,
            dr.created_at,
            u.username,
            d.domain_name
        FROM dns_records dr 
        INNER JOIN users u ON dr.user_id = u.id 
        INNER JOIN domains d ON dr.domain_id = d.id 
        ORDER BY dr.created_at DESC 
        LIMIT ?
    ");
    $stmt->bindValue(1, $limit, SQLITE3_INTEGER);
    $result = $stmt->execute();
    
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $records[] = $row;
    }
    
    return $records;
}

/**
 * 检查邀请系统是否需要迁移
 */
function checkInvitationMigration($db) {
    if (!getSetting('invitation_enabled', '1')) {
        return false;
    }
    
    $tableExists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='invitations'");
    if (!$tableExists) {
        return false;
    }
    
    $columns = getTableColumns($db, 'invitations');
    return !in_array('is_active', $columns);
}

/**
 * 检查邀请奖励是否需要更新
 */
function checkInvitationRewardUpdate($db) {
    if (!getSetting('invitation_enabled', '1')) {
        return 0;
    }
    
    $columns = getTableColumns($db, 'invitations');
    if (!in_array('is_active', $columns)) {
        return 0;
    }
    
    $current_reward_points = (int)getSetting('invitation_reward_points', '10');
    $outdated = $db->querySingle("
        SELECT COUNT(*) 
        FROM invitations 
        WHERE is_active = 1 AND reward_points != {$current_reward_points}
    ");
    
    return (int)$outdated;
}

/**
 * 检查缺失的功能模块
 */
function checkMissingFeatures($db) {
    $missing = [];
    
    if (!$db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='invitations'")) {
        $missing[] = '邀请系统';
    }
    if (!$db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='card_keys'")) {
        $missing[] = '卡密系统';
    }
    
    return $missing;
}

/**
 * 获取表的所有列名
 * 辅助函数：缓存表结构信息
 */
function getTableColumns($db, $tableName) {
    static $cache = [];
    
    if (isset($cache[$tableName])) {
        return $cache[$tableName];
    }
    
    $columns = [];
    $result = $db->query("PRAGMA table_info({$tableName})");
    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $columns[] = $row['name'];
    }
    
    $cache[$tableName] = $columns;
    return $columns;
}

/**
 * 计算使用率百分比
 */
function calculateUsageRate($used, $total) {
    return $total > 0 ? ($used / $total) * 100 : 0;
}
