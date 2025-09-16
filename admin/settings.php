<?php
session_start();
require_once '../config/database.php';
require_once '../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 处理DNS记录类型更新
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_dns_types'])) {
    $enabled_types = getPost('enabled_types', []);

    // 获取所有DNS记录类型
    $result = $db->query("SELECT type_name FROM dns_record_types");
    $updated = 0;

    while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
        $type_name = $row['type_name'];
        $enabled = in_array($type_name, $enabled_types) ? 1 : 0;

        $stmt = $db->prepare("UPDATE dns_record_types SET enabled = ? WHERE type_name = ?");
        $stmt->bindValue(1, $enabled, SQLITE3_INTEGER);
        $stmt->bindValue(2, $type_name, SQLITE3_TEXT);

        if ($stmt->execute()) {
            $updated++;
        }
    }

    logAction('admin', $_SESSION['admin_id'], 'update_dns_types', "更新了 {$updated} 个DNS记录类型的启用状态");
    showSuccess("DNS记录类型设置更新成功！已更新 {$updated} 个类型。");
    redirect('settings.php');
}

// 处理邮箱验证设置更新 BY Senvinn
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_settings_verify_mail'])) {
    $settings = [
        'smtp_host' => getPost('smtp_host'),
        'smtp_username' => getPost('smtp_username'),
        'smtp_password' => getPost('smtp_password'),
        'mail_username' => getPost('mail_username'),
        'mail_subject' => getPost('mail_subject'),
        'mail_body' => getPost('mail_body'),
        'mail_verify_enabled' => getPost('mail_verify_enabled', 0)
    ];

    $updated = 0;
    foreach ($settings as $key => $value) {
        if (updateSetting($key, $value)) {
            $updated++;
        }
    }

    if ($updated > 0) {
        logAction('admin', $_SESSION['admin_id'], 'update_verify_mail_settings', "更新了 $updated 项系统设置");
        showSuccess('邮箱验证设置更新成功！');
    } else {
        showError('邮箱验证设置更新失败！');
    }
    redirect('settings.php');
}

// 处理设置更新
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_settings'])) {
    $settings = [
        'site_name' => getPost('site_name'),
        'points_per_record' => getPost('points_per_record'),
        'default_user_points' => getPost('default_user_points'),
        'allow_registration' => getPost('allow_registration', 0),
        'github_oauth_enabled' => getPost('github_oauth_enabled', 0),
        'github_client_id' => getPost('github_client_id'),
        'github_client_secret' => getPost('github_client_secret'),
        'github_auto_register' => getPost('github_auto_register', 0),
        'github_min_account_days' => getPost('github_min_account_days'),
        'github_bonus_points' => getPost('github_bonus_points'),
        'invitation_enabled' => getPost('invitation_enabled', 0),
        'invitation_reward_points' => getPost('invitation_reward_points'),
        'invitee_bonus_points' => getPost('invitee_bonus_points')
    ];

    $updated = 0;
    foreach ($settings as $key => $value) {
        if (updateSetting($key, $value)) {
            $updated++;
        }
    }

    if ($updated > 0) {
        logAction('admin', $_SESSION['admin_id'], 'update_settings', "更新了 $updated 项系统设置");
        showSuccess('系统设置更新成功！');
    } else {
        showError('设置更新失败！');
    }
    redirect('settings.php');
}

// 获取当前设置
$current_settings = [
    'site_name' => getSetting('site_name', 'DNS管理系统'),
    'points_per_record' => getSetting('points_per_record', 1),
    'default_user_points' => getSetting('default_user_points', 100),
    'allow_registration' => getSetting('allow_registration', 1),
    'github_oauth_enabled' => getSetting('github_oauth_enabled', 0),
    'github_client_id' => getSetting('github_client_id', ''),
    'github_client_secret' => getSetting('github_client_secret', ''),
    'github_auto_register' => getSetting('github_auto_register', 1),
    'github_min_account_days' => getSetting('github_min_account_days', 30),
    'github_bonus_points' => getSetting('github_bonus_points', 200)
];

// 获取DNS记录类型 - 从数据库读取
$dns_types = [];
$result = $db->query("SELECT * FROM dns_record_types ORDER BY type_name");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $dns_types[] = $row;
}

$page_title = '系统设置';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>

        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">系统设置</h1>
            </div>

            <!-- 消息提示 -->
            <?php if (isset($messages['success'])): ?>
                <div class="alert alert-success alert-dismissible fade show">
                    <?php echo htmlspecialchars($messages['success']); ?>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            <?php endif; ?>

            <?php if (isset($messages['error'])): ?>
                <div class="alert alert-danger alert-dismissible fade show">
                    <?php echo htmlspecialchars($messages['error']); ?>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            <?php endif; ?>

            <div class="card shadow">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">基本设置</h6>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="site_name" class="form-label">网站名称</label>
                                    <input type="text" class="form-control" id="site_name" name="site_name"
                                        value="<?php echo htmlspecialchars($current_settings['site_name']); ?>" required>
                                </div>

                                <div class="mb-3">
                                    <label for="points_per_record" class="form-label">每条记录消耗积分</label>
                                    <input type="number" class="form-control" id="points_per_record" name="points_per_record"
                                        value="<?php echo $current_settings['points_per_record']; ?>" min="1" required>
                                </div>
                            </div>

                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="default_user_points" class="form-label">新用户默认积分</label>
                                    <input type="number" class="form-control" id="default_user_points" name="default_user_points"
                                        value="<?php echo $current_settings['default_user_points']; ?>" min="0" required>
                                </div>

                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="allow_registration" name="allow_registration" value="1"
                                            <?php echo $current_settings['allow_registration'] ? 'checked' : ''; ?>>
                                        <label class="form-check-label" for="allow_registration">
                                            允许用户注册
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- 邀请系统设置 -->
                        <hr class="my-4">
                        <h6 class="text-primary mb-3">
                            <i class="fas fa-user-friends me-2"></i>邀请系统设置
                        </h6>

                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="invitation_enabled" name="invitation_enabled" value="1"
                                            <?php echo getSetting('invitation_enabled', 1) ? 'checked' : ''; ?>>
                                        <label class="form-check-label" for="invitation_enabled">
                                            启用邀请系统
                                        </label>
                                    </div>
                                    <div class="form-text">关闭后用户将无法生成和使用邀请码</div>
                                </div>

                                <div class="mb-3">
                                    <label for="invitation_reward_points" class="form-label">邀请成功奖励积分</label>
                                    <input type="number" class="form-control" id="invitation_reward_points" name="invitation_reward_points"
                                        value="<?php echo (int)getSetting('invitation_reward_points', 10); ?>" min="0" max="1000">
                                    <div class="form-text">邀请人成功邀请用户注册后获得的积分奖励</div>
                                </div>
                            </div>

                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="invitee_bonus_points" class="form-label">被邀请用户额外积分</label>
                                    <input type="number" class="form-control" id="invitee_bonus_points" name="invitee_bonus_points"
                                        value="<?php echo (int)getSetting('invitee_bonus_points', 5); ?>" min="0" max="1000">
                                    <div class="form-text">使用邀请码注册的用户额外获得的积分</div>
                                </div>

                                <div class="alert alert-info">
                                    <small>
                                        <i class="fas fa-info-circle me-1"></i>
                                        <strong>邀请系统说明：</strong><br>
                                        • 用户可生成邀请码分享给朋友<br>
                                        • 朋友使用邀请码注册可获得额外积分<br>
                                        • 邀请人在朋友注册后获得奖励积分
                                    </small>
                                </div>
                            </div>
                        </div>

                        <!-- GitHub OAuth 设置 -->
                        <hr class="my-4">
                        <h6 class="text-muted mb-3"><i class="fab fa-github me-1"></i>GitHub OAuth 设置</h6>
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="github_oauth_enabled" name="github_oauth_enabled" value="1"
                                            <?php echo ($current_settings['github_oauth_enabled'] ?? 0) ? 'checked' : ''; ?>>
                                        <label class="form-check-label" for="github_oauth_enabled">
                                            启用 GitHub OAuth 登录
                                        </label>
                                    </div>
                                    <div class="form-text">允许用户使用GitHub账户登录</div>
                                </div>

                                <div class="mb-3">
                                    <label for="github_client_id" class="form-label">GitHub Client ID</label>
                                    <input type="text" class="form-control" id="github_client_id" name="github_client_id"
                                        value="<?php echo htmlspecialchars($current_settings['github_client_id'] ?? ''); ?>"
                                        placeholder="从GitHub OAuth App获取">
                                    <div class="form-text">在GitHub创建OAuth App后获得的Client ID</div>
                                </div>
                            </div>

                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="github_client_secret" class="form-label">GitHub Client Secret</label>
                                    <input type="password" class="form-control" id="github_client_secret" name="github_client_secret"
                                        value="<?php echo htmlspecialchars($current_settings['github_client_secret'] ?? ''); ?>"
                                        placeholder="从GitHub OAuth App获取">
                                    <div class="form-text">在GitHub创建OAuth App后获得的Client Secret</div>
                                </div>

                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="github_auto_register" name="github_auto_register" value="1"
                                            <?php echo ($current_settings['github_auto_register'] ?? 1) ? 'checked' : ''; ?>>
                                        <label class="form-check-label" for="github_auto_register">
                                            允许GitHub用户自动注册
                                        </label>
                                    </div>
                                    <div class="form-text">新的GitHub用户可以自动创建账户</div>
                                </div>

                                <div class="mb-3">
                                    <label for="github_min_account_days" class="form-label">GitHub账户最低注册天数</label>
                                    <input type="number" class="form-control" id="github_min_account_days" name="github_min_account_days"
                                        value="<?php echo $current_settings['github_min_account_days']; ?>" min="0" max="3650">
                                    <div class="form-text">GitHub账户注册天数达到此值才能获得奖励积分</div>
                                </div>

                                <div class="mb-3">
                                    <label for="github_bonus_points" class="form-label">GitHub用户奖励积分</label>
                                    <input type="number" class="form-control" id="github_bonus_points" name="github_bonus_points"
                                        value="<?php echo $current_settings['github_bonus_points']; ?>" min="0" max="10000">
                                    <div class="form-text">满足注册天数要求的GitHub用户获得的积分</div>
                                </div>
                            </div>
                        </div>

                        <div class="alert alert-info">
                            <h6><i class="fas fa-info-circle me-1"></i>GitHub OAuth 配置说明</h6>
                            <ol class="mb-0">
                                <li>访问 <a href="https://github.com/settings/applications/new" target="_blank" class="text-decoration-none">GitHub Developer Settings</a></li>
                                <li>创建新的OAuth App</li>
                                <li>设置Authorization callback URL为: <br><code class="text-break"><?php echo (isset($_SERVER['HTTPS']) ? 'https' : 'http') . '://' . $_SERVER['HTTP_HOST'] . '/user/github_callback.php'; ?></code></li>
                                <li>复制Client ID和Client Secret到上面的字段</li>
                                <li>保存设置并启用GitHub OAuth登录</li>
                            </ol>
                        </div>

                        <hr>

                        <div class="d-flex justify-content-between">
                            <button type="submit" name="update_settings" class="btn btn-primary">
                                <i class="fas fa-save me-1"></i>保存设置
                            </button>
                            <a href="dashboard.php" class="btn btn-secondary">
                                <i class="fas fa-arrow-left me-1"></i>返回仪表板
                            </a>
                        </div>
                    </form>
                </div>
            </div>

            <!-- 注册邮箱验证设置 BY Senvinn -->
            <div class="card shadowm mt-4">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">注册邮箱验证设置</h6>
                </div>
                <form method="POST">
                    <div class="card-body">
                        <!-- 注册邮箱验证设置 -->
                        <h6 class="text-primary mb-3">
                            <i class="fas fa-envelope me-2"></i>注册邮箱验证设置
                        </h6>

                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="mail_verify_enabled" name="mail_verify_enabled" value="0"
                                            <?php echo getSetting('mail_verify_enabled', 0) ? 'checked' : ''; ?>>
                                        <label class="form-check-label" for="invitation_enabled">
                                            启用注册邮箱验证
                                        </label>
                                    </div>
                                </div>

                                <div class="mb-3">
                                    <label for="smtp_host" class="form-label">邮箱服务器</label>
                                    <input type="text" class="form-control" id="smtp_host" name="smtp_host"
                                        value="<?php echo getSetting('smtp_host', 'smtp.qq.com'); ?>" required>
                                </div>
                                <div class="mb-3">
                                    <label for="smtp_username" class="form-label">发送者邮箱</label>
                                    <input type="text" class="form-control" id="smtp_username" name="smtp_username"
                                        value="<?php echo getSetting('smtp_username', 'example@qq.com'); ?>" required>
                                </div>
                                <div class="mb-3">
                                    <label for="smtp_password" class="form-label">发送者邮箱邮箱授权码</label>
                                    <input type="text" class="form-control" id="smtp_password" name="smtp_password"
                                        value="<?php echo getSetting('smtp_password', 'xxxxxx'); ?>" required>
                                </div>
                            </div>

                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="mail_username" class="form-label">发送者邮箱名</label>
                                    <input type="text" class="form-control" id="mail_username" name="mail_username"
                                        value="<?php echo getSetting('mail_username', '管理员'); ?>" required>
                                </div>
                                <div class="mb-3">
                                    <label for="mail_subject" class="form-label">邮件主题</label>
                                    <input type="text" class="form-control" id="mail_subject" name="mail_subject"
                                        value="<?php echo getSetting('mail_subject', '注册验证码'); ?>" required>
                                </div>
                                <div class="mb-3">
                                    <label for="mail_body" class="form-label">邮件正文</label>
                                    <input type="text" class="form-control" id="mail_body" name="mail_body"
                                        value="<?php
                                                $arr1 = array('<', '>', '"', '\'');
                                                $arr2 = array('&lt;', '&gt;', '&quot;', '&apos;');
                                                echo str_replace($arr1, $arr2, getSetting('mail_body', "<h2>您好，您的注册验证码为: <strong>{code}</h2>"));
                                                ?>" required>
                                    <div class="form-text">`{code}`将替换为验证码，正文可用html标签</div>
                                </div>


                                <div class="alert alert-info">
                                    <small>
                                        <i class="fas fa-info-circle me-1"></i>
                                        <strong>邮箱验证说明：</strong><br>
                                        • 验证码有效期为5分钟<br>
                                        • 验证码为六位，由大写字母与数字混合<br>
                                        • 注册邮箱验证仅仅为了防止乱输邮箱刷号
                                    </small>
                                </div>
                            </div>
                        </div>
                        <hr>

                        <div class="d-flex justify-content-between">
                            <button type="submit" name="update_settings_verify_mail" class="btn btn-primary">
                                <i class="fas fa-save me-1"></i>保存设置
                            </button>
                        </div>
                    </div>
                </form>
            </div>

            <!-- DNS记录类型管理 -->
            <div class="card shadow mt-4">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">DNS记录类型管理</h6>
                </div>
                <div class="card-body">
                    <p class="text-muted mb-3">
                        <i class="fas fa-info-circle me-1"></i>
                        选择允许用户使用的DNS记录类型。未选中的类型将在用户端隐藏。
                    </p>

                    <form method="POST">
                        <div class="row">
                            <?php foreach ($dns_types as $type): ?>
                                <div class="col-md-4 mb-3">
                                    <div class="card border <?php echo $type['enabled'] ? 'border-success' : 'border-secondary'; ?>">
                                        <div class="card-body p-3">
                                            <div class="form-check">
                                                <input class="form-check-input" type="checkbox"
                                                    id="type_<?php echo $type['type_name']; ?>"
                                                    name="enabled_types[]"
                                                    value="<?php echo $type['type_name']; ?>"
                                                    <?php echo $type['enabled'] ? 'checked' : ''; ?>>
                                                <label class="form-check-label" for="type_<?php echo $type['type_name']; ?>">
                                                    <strong><?php echo htmlspecialchars($type['type_name']); ?></strong>
                                                    <br>
                                                    <small class="text-muted"><?php echo htmlspecialchars($type['description']); ?></small>
                                                </label>
                                            </div>
                                            <div class="mt-2">
                                                <?php if ($type['enabled']): ?>
                                                    <span class="badge bg-success">已启用</span>
                                                <?php else: ?>
                                                    <span class="badge bg-secondary">已禁用</span>
                                                <?php endif; ?>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            <?php endforeach; ?>
                        </div>

                        <hr>

                        <div class="d-flex justify-content-between">
                            <button type="submit" name="update_dns_types" class="btn btn-success">
                                <i class="fas fa-save me-1"></i>保存DNS类型设置
                            </button>
                            <div>
                                <button type="button" class="btn btn-outline-primary me-2" onclick="selectAllTypes()">
                                    <i class="fas fa-check-square me-1"></i>全选
                                </button>
                                <button type="button" class="btn btn-outline-secondary" onclick="clearAllTypes()">
                                    <i class="fas fa-square me-1"></i>全不选
                                </button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>

            <!-- 系统信息 -->
            <div class="card shadow mt-4">
                <div class="card-header">
                    <h6 class="m-0 font-weight-bold text-primary">系统信息</h6>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>PHP版本：</strong></td>
                                    <td><?php echo PHP_VERSION; ?></td>
                                </tr>
                                <tr>
                                    <td><strong>SQLite版本：</strong></td>
                                    <td><?php echo SQLite3::version()['versionString']; ?></td>
                                </tr>
                                <tr>
                                    <td><strong>服务器时间：</strong></td>
                                    <td><?php echo date('Y-m-d H:i:s'); ?></td>
                                </tr>
                            </table>
                        </div>
                        <div class="col-md-6">
                            <table class="table table-sm">
                                <tr>
                                    <td><strong>数据库大小：</strong></td>
                                    <td>
                                        <?php
                                        $db_file = '../data/cloudflare_dns.db';
                                        if (file_exists($db_file)) {
                                            echo round(filesize($db_file) / 1024, 2) . ' KB';
                                        } else {
                                            echo '未知';
                                        }
                                        ?>
                                    </td>
                                </tr>
                                <tr>
                                    <td><strong>cURL支持：</strong></td>
                                    <td>
                                        <?php echo function_exists('curl_init') ?
                                            '<span class="badge bg-success">支持</span>' :
                                            '<span class="badge bg-danger">不支持</span>'; ?>
                                    </td>
                                </tr>
                                <tr>
                                    <td><strong>OpenSSL支持：</strong></td>
                                    <td>
                                        <?php echo extension_loaded('openssl') ?
                                            '<span class="badge bg-success">支持</span>' :
                                            '<span class="badge bg-danger">不支持</span>'; ?>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<script>
    function selectAllTypes() {
        document.querySelectorAll('input[name="enabled_types[]"]').forEach(function(checkbox) {
            checkbox.checked = true;
            updateCardBorder(checkbox);
        });
    }

    function clearAllTypes() {
        document.querySelectorAll('input[name="enabled_types[]"]').forEach(function(checkbox) {
            checkbox.checked = false;
            updateCardBorder(checkbox);
        });
    }

    function updateCardBorder(checkbox) {
        const card = checkbox.closest('.card');
        const badge = card.querySelector('.badge');

        if (checkbox.checked) {
            card.className = card.className.replace('border-secondary', 'border-success');
            badge.className = 'badge bg-success';
            badge.textContent = '已启用';
        } else {
            card.className = card.className.replace('border-success', 'border-secondary');
            badge.className = 'badge bg-secondary';
            badge.textContent = '已禁用';
        }
    }

    // 为所有复选框添加事件监听器
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('input[name="enabled_types[]"]').forEach(function(checkbox) {
            checkbox.addEventListener('change', function() {
                updateCardBorder(this);
            });
        });
    });
</script>

<?php include 'includes/footer.php'; ?>