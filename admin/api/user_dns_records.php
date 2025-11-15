<?php
session_start();
require_once '../../config/database.php';
require_once '../../includes/functions.php';

// 检查管理员登录
checkAdminLogin();

header('Content-Type: application/json');

$user_id = isset($_GET['user_id']) ? (int)$_GET['user_id'] : 0;

if ($user_id <= 0) {
    echo json_encode(['success' => false, 'message' => '无效的用户ID']);
    exit;
}

$db = Database::getInstance()->getConnection();

// 获取用户信息
$user = $db->querySingle("SELECT username FROM users WHERE id = $user_id", true);

if (!$user) {
    echo json_encode(['success' => false, 'message' => '用户不存在']);
    exit;
}

// 获取用户的所有DNS记录
$query = "
    SELECT 
        dr.id,
        dr.subdomain,
        dr.type,
        dr.content,
        dr.proxied,
        dr.remark,
        dr.created_at,
        d.domain_name
    FROM dns_records dr
    LEFT JOIN domains d ON dr.domain_id = d.id
    WHERE dr.user_id = ? AND dr.status = 1
    ORDER BY dr.created_at DESC
";

$stmt = $db->prepare($query);
$stmt->bindValue(1, $user_id, SQLITE3_INTEGER);
$result = $stmt->execute();

$records = [];
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    // 构建完整域名
    $full_domain = $row['subdomain'] === '@' 
        ? $row['domain_name'] 
        : $row['subdomain'] . '.' . $row['domain_name'];
    
    $records[] = [
        'id' => $row['id'],
        'domain_name' => $row['domain_name'],
        'subdomain' => $row['subdomain'],
        'full_domain' => $full_domain,
        'type' => $row['type'],
        'content' => $row['content'],
        'proxied' => $row['proxied'],
        'remark' => $row['remark'],
        'created_at' => $row['created_at']
    ];
}

echo json_encode([
    'success' => true,
    'records' => $records,
    'total' => count($records)
]);
