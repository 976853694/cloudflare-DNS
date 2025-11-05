# Dashboard Functions API 参考

## 快速开始

```php
require_once 'includes/dashboard_functions.php';
$db = Database::getInstance()->getConnection();
```

## 函数列表

### 1. getDashboardStats($db)
获取核心系统统计数据

**参数:**
- `$db` (SQLite3) - 数据库连接对象

**返回:**
```php
[
    'total_users' => int,        // 总用户数
    'active_users' => int,       // 活跃用户数
    'inactive_users' => int,     // 禁用用户数
    'this_week_users' => int,    // 本周新增用户
    'total_points' => int,       // 总积分
    'total_domains' => int,      // 总域名数
    'total_records' => int,      // 总DNS记录数
    'today_records' => int,      // 今日新增记录
    'domains_with_records' => int, // 有记录的域名数
    'domain_utilization' => float  // 域名利用率(%)
]
```

**示例:**
```php
$stats = getDashboardStats($db);
echo "总用户: " . $stats['total_users'];
echo "域名利用率: " . $stats['domain_utilization'] . "%";
```

---

### 2. getInvitationStats($db)
获取邀请系统统计

**参数:**
- `$db` (SQLite3) - 数据库连接对象

**返回:**
```php
[
    'total_invitations' => int,   // 总邀请码数
    'used_invitations' => int,    // 已使用邀请码
    'active_invitations' => int   // 有效邀请码
]
```

**示例:**
```php
$invStats = getInvitationStats($db);
$usage = calculateUsageRate($invStats['used_invitations'], $invStats['total_invitations']);
echo "邀请码使用率: " . number_format($usage, 2) . "%";
```

**注意:** 
- 如果邀请系统未启用，返回全0
- 自动适配不同的表结构版本

---

### 3. getCardKeyStats($db)
获取卡密系统统计

**参数:**
- `$db` (SQLite3) - 数据库连接对象

**返回:**
```php
[
    'total_card_keys' => int,  // 总卡密数
    'used_card_keys' => int    // 已使用卡密
]
```

**示例:**
```php
$cardStats = getCardKeyStats($db);
echo "可用卡密: " . ($cardStats['total_card_keys'] - $cardStats['used_card_keys']);
```

**注意:**
- 智能检测 used_by、used_count、status 等不同字段
- 如果表不存在，返回全0

---

### 4. getWeeklyRegistrations($db)
获取最近7天的用户注册趋势

**参数:**
- `$db` (SQLite3) - 数据库连接对象

**返回:**
```php
[
    'data' => [
        ['date' => 'Y-m-d', 'count' => int],
        // ... 7天的数据
    ],
    'max_count' => int  // 最大注册数（用于图表缩放）
]
```

**示例:**
```php
$weeklyData = getWeeklyRegistrations($db);
foreach ($weeklyData['data'] as $day) {
    echo $day['date'] . ": " . $day['count'] . " 人\n";
}
```

**特性:**
- 自动填充没有注册的日期（count = 0）
- 返回完整的7天数据
- 提供最大值用于图表显示

---

### 5. getRecentUsers($db, $limit = 5)
获取最近注册的用户

**参数:**
- `$db` (SQLite3) - 数据库连接对象
- `$limit` (int) - 返回的用户数量，默认 5

**返回:**
```php
[
    [
        'id' => int,
        'username' => string,
        'email' => string,
        'status' => int,
        'points' => int,
        'created_at' => timestamp
    ],
    // ...
]
```

**示例:**
```php
$users = getRecentUsers($db, 10);
foreach ($users as $user) {
    echo $user['username'] . " - " . $user['points'] . " 积分\n";
}
```

---

### 6. getRecentDNSRecords($db, $limit = 10)
获取最近创建的DNS记录

**参数:**
- `$db` (SQLite3) - 数据库连接对象
- `$limit` (int) - 返回的记录数量，默认 10

**返回:**
```php
[
    [
        'id' => int,
        'subdomain' => string,
        'type' => string,
        'content' => string,
        'created_at' => timestamp,
        'username' => string,
        'domain_name' => string
    ],
    // ...
]
```

**示例:**
```php
$records = getRecentDNSRecords($db, 5);
foreach ($records as $record) {
    $fullDomain = $record['subdomain'] . '.' . $record['domain_name'];
    echo $fullDomain . " (" . $record['type'] . ")\n";
}
```

**优化:**
- 使用 INNER JOIN 一次性获取所有相关数据
- 只查询需要的字段，减少数据传输

---

### 7. checkInvitationMigration($db)
检查邀请系统是否需要迁移

**参数:**
- `$db` (SQLite3) - 数据库连接对象

**返回:**
- `bool` - true 表示需要迁移，false 表示不需要

**示例:**
```php
if (checkInvitationMigration($db)) {
    echo "邀请系统需要升级为永久邀请码功能";
}
```

**检查逻辑:**
- 检查 invitations 表是否存在 is_active 字段
- 如果不存在，说明是旧版本，需要迁移

---

### 8. checkInvitationRewardUpdate($db)
检查有多少邀请码的奖励积分需要更新

**参数:**
- `$db` (SQLite3) - 数据库连接对象

**返回:**
- `int` - 需要更新的邀请码数量

**示例:**
```php
$outdated = checkInvitationRewardUpdate($db);
if ($outdated > 0) {
    echo "有 {$outdated} 个邀请码需要同步奖励积分";
}
```

**检查逻辑:**
- 比较邀请码的 reward_points 与系统设置中的当前值
- 返回不一致的邀请码数量

---

### 9. checkMissingFeatures($db)
检查系统中缺失的功能模块

**参数:**
- `$db` (SQLite3) - 数据库连接对象

**返回:**
- `array` - 缺失的功能名称数组

**示例:**
```php
$missing = checkMissingFeatures($db);
if (!empty($missing)) {
    echo "缺失功能: " . implode(', ', $missing);
}
```

**检查项:**
- invitations 表 → 邀请系统
- card_keys 表 → 卡密系统

---

### 10. getTableColumns($db, $tableName)
获取数据表的所有列名（带缓存）

**参数:**
- `$db` (SQLite3) - 数据库连接对象
- `$tableName` (string) - 表名

**返回:**
- `array` - 列名数组

**示例:**
```php
$columns = getTableColumns($db, 'users');
if (in_array('github_id', $columns)) {
    echo "用户表支持 GitHub 登录";
}
```

**特性:**
- 静态缓存：同一请求中重复调用直接返回缓存
- 性能提升：缓存命中后几乎零耗时

---

### 11. calculateUsageRate($used, $total)
计算使用率百分比

**参数:**
- `$used` (int) - 已使用数量
- `$total` (int) - 总数量

**返回:**
- `float` - 使用率百分比（0-100）

**示例:**
```php
$rate = calculateUsageRate(75, 100);
echo number_format($rate, 2) . "%";  // 输出: 75.00%

// 处理除零情况
$rate = calculateUsageRate(0, 0);
echo $rate;  // 输出: 0
```

**特性:**
- 自动处理除零情况
- 返回0-100的浮点数

---

## 完整使用示例

```php
<?php
require_once '../config/database.php';
require_once '../includes/functions.php';
require_once 'includes/dashboard_functions.php';

$db = Database::getInstance()->getConnection();

// 获取所有统计数据
$stats = getDashboardStats($db);
$invStats = getInvitationStats($db);
$cardStats = getCardKeyStats($db);
$allStats = array_merge($stats, $invStats, $cardStats);

// 获取趋势和列表数据
$weeklyData = getWeeklyRegistrations($db);
$recentUsers = getRecentUsers($db, 5);
$recentRecords = getRecentDNSRecords($db, 10);

// 计算使用率
$invUsageRate = calculateUsageRate(
    $allStats['used_invitations'], 
    $allStats['total_invitations']
);

// 检查系统状态
$needsMigration = checkInvitationMigration($db);
$outdatedInvitations = checkInvitationRewardUpdate($db);
$missingFeatures = checkMissingFeatures($db);

// 使用数据
echo "系统概览\n";
echo "--------\n";
echo "总用户: {$allStats['total_users']}\n";
echo "活跃用户: {$allStats['active_users']}\n";
echo "域名利用率: " . number_format($allStats['domain_utilization'], 2) . "%\n";
echo "邀请码使用率: " . number_format($invUsageRate, 2) . "%\n";
?>
```

## 性能优化建议

1. **批量获取数据**: 使用 `array_merge()` 合并统计数据
   ```php
   $stats = array_merge(
       getDashboardStats($db),
       getInvitationStats($db),
       getCardKeyStats($db)
   );
   ```

2. **缓存表结构**: `getTableColumns()` 自动缓存，无需手动处理

3. **按需查询**: 只在需要时调用相应函数
   ```php
   if (getSetting('invitation_enabled', '1')) {
       $invStats = getInvitationStats($db);
   }
   ```

4. **控制数据量**: 使用 limit 参数控制返回数量
   ```php
   $topUsers = getRecentUsers($db, 3);  // 只获取3个
   ```

## 错误处理

所有函数都包含容错处理：
- 表不存在时返回安全的默认值（通常是 0 或空数组）
- 字段不存在时自动适配其他可用字段
- 除零操作自动处理返回 0

## 扩展新功能

添加新的统计函数模板：

```php
/**
 * 获取自定义统计数据
 */
function getCustomStats($db) {
    // 检查必要条件
    $tableExists = $db->querySingle("SELECT name FROM sqlite_master WHERE type='table' AND name='your_table'");
    if (!$tableExists) {
        return ['default' => 0];
    }
    
    // 使用聚合查询优化性能
    $stats = $db->querySingle("
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN condition THEN 1 ELSE 0 END) as count_a,
            AVG(value) as average
        FROM your_table
    ", true);
    
    return $stats;
}
```

---

**版本**: 2.0  
**最后更新**: 2024  
**维护者**: Development Team
