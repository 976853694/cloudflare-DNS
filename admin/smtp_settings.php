<?php
/**
 * SMTP邮件设置管理
 */
session_start();
require_once '../config/database.php';
require_once '../config/smtp.php';
require_once '../includes/functions.php';

checkAdminLogin();

$db = Database::getInstance()->getConnection();
$messages = getMessages();

// 处理设置更新
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_smtp'])) {
    $smtp_settings = [
        'smtp_enabled' => getPost('smtp_enabled') ? '1' : '0',
        'smtp_host' => trim(getPost('smtp_host')),
        'smtp_port' => trim(getPost('smtp_port')),
        'smtp_username' => trim(getPost('smtp_username')),
        'smtp_password' => trim(getPost('smtp_password')),
        'smtp_secure' => trim(getPost('smtp_secure')),
        'smtp_from_name' => trim(getPost('smtp_from_name')),
        'smtp_debug' => trim(getPost('smtp_debug')),
        'email_subject_registration' => trim(getPost('email_subject_registration')),
        'email_subject_password_reset' => trim(getPost('email_subject_password_reset')),
        'email_subject_password_change' => trim(getPost('email_subject_password_change')),
        'email_subject_email_change' => trim(getPost('email_subject_email_change')),
        'email_subject_test' => trim(getPost('email_subject_test'))
    ];
    
    $success = true;
    
    foreach ($smtp_settings as $key => $value) {
        try {
            // 先检查设置是否存在
            $exists = $db->querySingle("SELECT COUNT(*) FROM settings WHERE setting_key = '$key'");
            
            if ($exists > 0) {
                // 更新现有设置
                $stmt = $db->prepare("UPDATE settings SET setting_value = ? WHERE setting_key = ?");
                $stmt->bindValue(1, $value, SQLITE3_TEXT);
                $stmt->bindValue(2, $key, SQLITE3_TEXT);
            } else {
                // 插入新设置
                $stmt = $db->prepare("INSERT INTO settings (setting_key, setting_value, description) VALUES (?, ?, ?)");
                $stmt->bindValue(1, $key, SQLITE3_TEXT);
                $stmt->bindValue(2, $value, SQLITE3_TEXT);
                $descriptions = [
                    'smtp_enabled' => '是否启用SMTP邮件发送',
                    'smtp_host' => 'SMTP服务器地址',
                    'smtp_port' => 'SMTP服务器端口',
                    'smtp_username' => 'SMTP用户名（发件邮箱）',
                    'smtp_password' => 'SMTP密码或授权码',
                    'smtp_secure' => 'SMTP安全连接类型（ssl/tls）',
                    'smtp_from_name' => '发件人显示名称',
                    'smtp_debug' => 'SMTP调试模式（0-3）',
                    'email_subject_registration' => '注册验证邮件标题',
                    'email_subject_password_reset' => '密码重置邮件标题',
                    'email_subject_password_change' => '密码修改通知邮件标题',
                    'email_subject_email_change' => '邮箱更换验证邮件标题',
                    'email_subject_test' => '测试邮件标题'
                ];
                $stmt->bindValue(3, $descriptions[$key] ?? '', SQLITE3_TEXT);
            }
            
            if (!$stmt->execute()) {
                $success = false;
                error_log("Failed to update SMTP setting: $key = $value");
                break;
            }
        } catch (Exception $e) {
            $success = false;
            error_log("SMTP setting update error for $key: " . $e->getMessage());
            break;
        }
    }
    
    if ($success) {
        logAction('admin', $_SESSION['admin_id'], 'update_smtp_settings', 'SMTP设置更新');
        showSuccess('SMTP设置更新成功！');
    } else {
        showError('SMTP设置更新失败！');
    }
    
    redirect('smtp_settings.php');
}

// 处理邮件模板更新
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_templates'])) {
    $templates = [
        'email_template_registration' => trim($_POST['registration_template'] ?? ''),
        'email_template_password_reset' => trim($_POST['password_reset_template'] ?? ''),
        'email_template_password_change' => trim($_POST['password_change_template'] ?? ''),
        'email_template_email_change' => trim($_POST['email_change_template'] ?? ''),
        'email_template_test' => trim($_POST['test_email_template'] ?? '')
    ];
    
    try {
        // 保存模板到数据库
        foreach ($templates as $setting_key => $template_content) {
            if (!empty($template_content)) {
                // 检查设置是否已存在
                $stmt = $db->prepare("SELECT id FROM settings WHERE setting_key = ?");
                $stmt->bindValue(1, $setting_key, SQLITE3_TEXT);
                $result = $stmt->execute();
                $existing = $result->fetchArray(SQLITE3_ASSOC);
                
                if ($existing) {
                    // 更新现有设置
                    $stmt = $db->prepare("UPDATE settings SET setting_value = ? WHERE setting_key = ?");
                    $stmt->bindValue(1, $template_content, SQLITE3_TEXT);
                    $stmt->bindValue(2, $setting_key, SQLITE3_TEXT);
                    $stmt->execute();
                } else {
                    // 插入新设置
                    $stmt = $db->prepare("INSERT INTO settings (setting_key, setting_value) VALUES (?, ?)");
                    $stmt->bindValue(1, $setting_key, SQLITE3_TEXT);
                    $stmt->bindValue(2, $template_content, SQLITE3_TEXT);
                    $stmt->execute();
                }
            }
        }
        
        logAction('admin', $_SESSION['admin_id'], 'update_email_templates', '更新邮件模板');
        showSuccess('邮件模板更新成功！所有模板已保存到数据库。');
        
    } catch (Exception $e) {
        showError('邮件模板更新失败：' . $e->getMessage());
    }
    
    redirect('smtp_settings.php');
}

// 处理测试邮件发送
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['test_email'])) {
    $test_email = trim(getPost('test_email'));
    
    if (empty($test_email)) {
        showError('请输入测试邮箱地址');
    } elseif (!filter_var($test_email, FILTER_VALIDATE_EMAIL)) {
        showError('请输入有效的邮箱地址');
    } else {
        try {
            // 检查SMTP是否启用
            $smtp_enabled = $db->querySingle("SELECT setting_value FROM settings WHERE setting_key = 'smtp_enabled'");
            if (!$smtp_enabled || $smtp_enabled !== '1') {
                throw new Exception('SMTP邮件发送功能未启用，请先在设置中启用SMTP');
            }
            
            // 检查必要的SMTP配置
            $required_settings = ['smtp_host', 'smtp_port', 'smtp_username', 'smtp_password'];
            $missing_settings = [];
            
            foreach ($required_settings as $setting) {
                $value = $db->querySingle("SELECT setting_value FROM settings WHERE setting_key = '$setting'");
                if (empty($value)) {
                    $missing_settings[] = $setting;
                }
            }
            
            if (!empty($missing_settings)) {
                throw new Exception('SMTP配置不完整，缺少：' . implode(', ', $missing_settings) . '。请先完善SMTP配置。');
            }
            
            $emailService = new EmailService();
            
            // 发送测试邮件
            $result = $emailService->sendTestEmail($test_email);
            
            if ($result) {
                showSuccess('测试邮件发送成功！请检查邮箱（包括垃圾邮件文件夹）');
                logAction('admin', $_SESSION['admin_id'], 'send_test_email', "发送测试邮件到: $test_email");
            } else {
                throw new Exception('邮件发送返回失败，但未抛出异常');
            }
            
        } catch (Exception $e) {
            $error_message = '测试邮件发送失败：' . $e->getMessage();
            showError($error_message);
            
            // 记录详细错误信息到日志
            error_log("SMTP Test Email Failed: " . $e->getMessage());
            error_log("SMTP Test Email Stack Trace: " . $e->getTraceAsString());
            
            // 记录到操作日志
            logAction('admin', $_SESSION['admin_id'], 'send_test_email_failed', "测试邮件发送失败: " . $e->getMessage());
        }
    }
    
    redirect('smtp_settings.php');
}

// 获取当前SMTP设置和邮件标题
$current_settings = [];
$result = $db->query("SELECT setting_key, setting_value FROM settings WHERE setting_key LIKE 'smtp_%' OR setting_key LIKE 'email_subject_%'");
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $current_settings[$row['setting_key']] = $row['setting_value'];
}

// 模板更新函数
function updateEmailTemplate($content, $template_type, $new_template) {
    $template_patterns = [
        'registration' => '/private function getRegistrationEmailTemplate\(\$username, \$code\) \{.*?return ".*?";.*?\}/s',
        'password_reset' => '/private function getPasswordResetEmailTemplate\(\$username, \$code\) \{.*?return ".*?";.*?\}/s', 
        'password_change' => '/private function getPasswordChangeNotificationTemplate\(\$username\) \{.*?return ".*?";.*?\}/s',
        'email_change' => '/private function getEmailChangeVerificationTemplate\(\$username, \$code\) \{.*?return ".*?";.*?\}/s',
        'test_email' => '/private function getTestEmailTemplate\(\) \{.*?return ".*?";.*?\}/s'
    ];
    
    $template_replacements = [
        'registration' => 'private function getRegistrationEmailTemplate($username, $code) {
        return "' . addslashes($new_template) . '";
    }',
        'password_reset' => 'private function getPasswordResetEmailTemplate($username, $code) {
        return "' . addslashes($new_template) . '";
    }',
        'password_change' => 'private function getPasswordChangeNotificationTemplate($username) {
        $change_time = date(\'Y-m-d H:i:s\');
        return "' . addslashes($new_template) . '";
    }',
        'email_change' => 'private function getEmailChangeVerificationTemplate($username, $code) {
        return "' . addslashes($new_template) . '";
    }',
        'test_email' => 'private function getTestEmailTemplate() {
        $test_time = date(\'Y-m-d H:i:s\');
        return "' . addslashes($new_template) . '";
    }'
    ];
    
    if (isset($template_patterns[$template_type]) && isset($template_replacements[$template_type])) {
        $content = preg_replace($template_patterns[$template_type], $template_replacements[$template_type], $content);
    }
    
    return $content;
}

// 获取当前模板内容（从数据库读取）
function getCurrentTemplate($template_type) {
    global $db;
    
    $template_key = 'email_template_' . $template_type;
    $stmt = $db->prepare("SELECT setting_value FROM settings WHERE setting_key = ?");
    $stmt->bindValue(1, $template_key, SQLITE3_TEXT);
    $result = $stmt->execute();
    $row = $result->fetchArray(SQLITE3_ASSOC);
    
    if ($row && !empty($row['setting_value'])) {
        return $row['setting_value'];
    }
    
    // 如果数据库中没有，返回空字符串
    return '';
}

// 旧的从文件读取模板的函数（已废弃）
function getCurrentTemplateFromFile($template_type) {
    $smtp_file = '../config/smtp.php';
    $content = file_get_contents($smtp_file);
    
    $template_patterns = [
        'registration' => '/private function getRegistrationEmailTemplate\(\$username, \$code\) \{.*?return "(.*?)";.*?\}/s',
        'password_reset' => '/private function getPasswordResetEmailTemplate\(\$username, \$code\) \{.*?return "(.*?)";.*?\}/s',
        'password_change' => '/private function getPasswordChangeNotificationTemplate\(\$username\) \{.*?return "(.*?)";.*?\}/s',
        'email_change' => '/private function getEmailChangeVerificationTemplate\(\$username, \$code\) \{.*?return "(.*?)";.*?\}/s',
        'test_email' => '/private function getTestEmailTemplate\(\) \{.*?return "(.*?)";.*?\}/s'
    ];
    
    if (isset($template_patterns[$template_type])) {
        if (preg_match($template_patterns[$template_type], $content, $matches)) {
            return stripslashes($matches[1]);
        }
    }
    
    return '';
}

$page_title = 'SMTP邮件设置';
include 'includes/header.php';
?>

<div class="container-fluid">
    <div class="row">
        <?php include 'includes/sidebar.php'; ?>
        
        <main class="col-md-9 ms-sm-auto col-lg-10 px-md-4">
            <div class="d-flex justify-content-between flex-wrap flex-md-nowrap align-items-center pt-3 pb-2 mb-3 border-bottom">
                <h1 class="h2">
                    <i class="fas fa-envelope me-2"></i>SMTP邮件设置
                </h1>
                <div class="btn-toolbar mb-2 mb-md-0">
                    <div class="btn-group me-2">
                        <!-- <button type="button" class="btn btn-success" data-bs-toggle="modal" data-bs-target="#testEmailModal">
                            <i class="fas fa-paper-plane me-1"></i>发送测试邮件
                        </button> -->
                        <button type="button" class="btn btn-info" data-bs-toggle="modal" data-bs-target="#templateModal">
                        <a href="../config/migrate_email_templates.php">导入数据库</a>
                        </button>
                        
                        <button type="button" class="btn btn-info" data-bs-toggle="modal" data-bs-target="#templateModal">
                            <i class="fas fa-edit me-1"></i>邮件模板
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- 消息提示 -->
            <?php if (!empty($messages)): ?>
                <?php foreach ($messages as $type => $message): ?>
                    <div class="alert alert-<?php echo $type; ?> alert-dismissible fade show" role="alert">
                        <?php echo htmlspecialchars($message); ?>
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                <?php endforeach; ?>
            <?php endif; ?>
            
            <div class="row">
                <!-- SMTP配置 -->
                <div class="col-lg-8">
                    <div class="card shadow">
                        <div class="card-header">
                            <h6 class="m-0 font-weight-bold text-primary">SMTP服务器配置</h6>
                        </div>
                        <div class="card-body">
                            <form method="POST">
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <div class="form-check form-switch">
                                                <input class="form-check-input" type="checkbox" id="smtp_enabled" name="smtp_enabled" 
                                                       <?php echo ($current_settings['smtp_enabled'] ?? '1') ? 'checked' : ''; ?>>
                                                <label class="form-check-label" for="smtp_enabled">
                                                    <strong>启用SMTP邮件发送</strong>
                                                </label>
                                            </div>
                                            <div class="form-text">关闭后将无法发送任何邮件</div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label for="smtp_debug" class="form-label">调试模式</label>
                                            <select class="form-select" id="smtp_debug" name="smtp_debug">
                                                <option value="0" <?php echo ($current_settings['smtp_debug'] ?? '0') == '0' ? 'selected' : ''; ?>>关闭</option>
                                                <option value="1" <?php echo ($current_settings['smtp_debug'] ?? '0') == '1' ? 'selected' : ''; ?>>客户端消息</option>
                                                <option value="2" <?php echo ($current_settings['smtp_debug'] ?? '0') == '2' ? 'selected' : ''; ?>>客户端和服务器</option>
                                                <option value="3" <?php echo ($current_settings['smtp_debug'] ?? '0') == '3' ? 'selected' : ''; ?>>详细连接</option>
                                            </select>
                                            <div class="form-text">仅在测试时开启</div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label for="smtp_host" class="form-label">SMTP服务器</label>
                                            <input type="text" class="form-control" id="smtp_host" name="smtp_host" 
                                                   value="<?php echo htmlspecialchars($current_settings['smtp_host'] ?? 'smtp.qq.com'); ?>" required>
                                            <div class="form-text">如：smtp.qq.com, smtp.gmail.com</div>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="mb-3">
                                            <label for="smtp_port" class="form-label">端口</label>
                                            <input type="number" class="form-control" id="smtp_port" name="smtp_port" 
                                                   value="<?php echo htmlspecialchars($current_settings['smtp_port'] ?? '465'); ?>" required>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="mb-3">
                                            <label for="smtp_secure" class="form-label">加密方式</label>
                                            <select class="form-select" id="smtp_secure" name="smtp_secure" required>
                                                <option value="ssl" <?php echo ($current_settings['smtp_secure'] ?? 'ssl') == 'ssl' ? 'selected' : ''; ?>>SSL</option>
                                                <option value="tls" <?php echo ($current_settings['smtp_secure'] ?? 'ssl') == 'tls' ? 'selected' : ''; ?>>TLS</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label for="smtp_username" class="form-label">SMTP用户名</label>
                                            <input type="email" class="form-control" id="smtp_username" name="smtp_username" 
                                                   value="<?php echo htmlspecialchars($current_settings['smtp_username'] ?? ''); ?>" required>
                                            <div class="form-text">必须是有效的邮箱地址格式</div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="mb-3">
                                            <label for="smtp_password" class="form-label">SMTP密码</label>
                                            <input type="password" class="form-control" id="smtp_password" name="smtp_password" 
                                                   value="<?php echo htmlspecialchars($current_settings['smtp_password'] ?? ''); ?>" required>
                                            <div class="form-text">邮箱密码或授权码</div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="smtp_from_name" class="form-label">发件人名称</label>
                                    <input type="text" class="form-control" id="smtp_from_name" name="smtp_from_name" 
                                           value="<?php echo htmlspecialchars($current_settings['smtp_from_name'] ?? '六趣DNS'); ?>" required>
                                    <div class="form-text">收件人看到的发件人名称</div>
                                </div>
                                
                                <hr class="my-4">
                                
                                <h6 class="mb-3"><i class="fas fa-heading me-2"></i>邮件标题配置</h6>
                                
                                <div class="mb-3">
                                    <label for="email_subject_registration" class="form-label">注册验证邮件标题</label>
                                    <input type="text" class="form-control" id="email_subject_registration" name="email_subject_registration" 
                                           value="<?php echo htmlspecialchars($current_settings['email_subject_registration'] ?? '六趣DNS - 注册验证码'); ?>" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="email_subject_password_reset" class="form-label">密码重置邮件标题</label>
                                    <input type="text" class="form-control" id="email_subject_password_reset" name="email_subject_password_reset" 
                                           value="<?php echo htmlspecialchars($current_settings['email_subject_password_reset'] ?? '六趣DNS - 密码重置验证码'); ?>" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="email_subject_password_change" class="form-label">密码修改通知邮件标题</label>
                                    <input type="text" class="form-control" id="email_subject_password_change" name="email_subject_password_change" 
                                           value="<?php echo htmlspecialchars($current_settings['email_subject_password_change'] ?? '六趣DNS - 密码修改通知'); ?>" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="email_subject_email_change" class="form-label">邮箱更换验证邮件标题</label>
                                    <input type="text" class="form-control" id="email_subject_email_change" name="email_subject_email_change" 
                                           value="<?php echo htmlspecialchars($current_settings['email_subject_email_change'] ?? '六趣DNS - 邮箱更换验证码'); ?>" required>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="email_subject_test" class="form-label">测试邮件标题</label>
                                    <input type="text" class="form-control" id="email_subject_test" name="email_subject_test" 
                                           value="<?php echo htmlspecialchars($current_settings['email_subject_test'] ?? '六趣DNS - SMTP测试邮件'); ?>" required>
                                </div>
                                
                                <div class="d-grid">
                                    <button type="submit" name="update_smtp" class="btn btn-primary">
                                        <i class="fas fa-save me-1"></i>保存设置
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                
                <!-- 配置说明 -->
                <div class="col-lg-4">
                    <div class="card shadow">
                        <div class="card-header">
                            <h6 class="m-0 font-weight-bold text-info">常用SMTP配置</h6>
                        </div>
                        <div class="card-body">
                            <h6 class="text-primary">QQ邮箱</h6>
                            <ul class="list-unstyled small">
                                <li><strong>服务器:</strong> smtp.qq.com</li>
                                <li><strong>端口:</strong> 465 (SSL) / 587 (TLS)</li>
                                <li><strong>用户名:</strong> 完整QQ邮箱地址</li>
                                <li><strong>密码:</strong> 邮箱授权码</li>
                            </ul>
                            
                            <h6 class="text-primary">Gmail</h6>
                            <ul class="list-unstyled small">
                                <li><strong>服务器:</strong> smtp.gmail.com</li>
                                <li><strong>端口:</strong> 465 (SSL) / 587 (TLS)</li>
                                <li><strong>用户名:</strong> 完整Gmail地址</li>
                                <li><strong>密码:</strong> 应用专用密码</li>
                            </ul>
                            
                            <h6 class="text-primary">163邮箱</h6>
                            <ul class="list-unstyled small">
                                <li><strong>服务器:</strong> smtp.163.com</li>
                                <li><strong>端口:</strong> 465 (SSL) / 994 (TLS)</li>
                                <li><strong>用户名:</strong> 完整163邮箱地址</li>
                                <li><strong>密码:</strong> 邮箱授权码</li>
                            </ul>
                            
                            <div class="alert alert-warning mt-3">
                                <small>
                                    <i class="fas fa-exclamation-triangle me-1"></i>
                                    <strong>注意:</strong> 大多数邮箱服务商需要开启SMTP服务并使用授权码，而不是登录密码。
                                </small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<!-- 测试邮件模态框 -->
<div class="modal fade" id="testEmailModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">
                    <i class="fas fa-paper-plane me-2"></i>发送测试邮件
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="test_email" class="form-label">测试邮箱地址</label>
                        <input type="email" class="form-control" id="test_email" name="test_email" required>
                        <div class="form-text">将向此邮箱发送测试邮件以验证SMTP配置</div>
                    </div>
                    
                    <!-- 当前SMTP配置状态 -->
                    <div class="alert alert-info">
                        <h6 class="alert-heading">
                            <i class="fas fa-info-circle me-2"></i>当前SMTP配置状态
                        </h6>
                        <div class="row">
                            <div class="col-md-6">
                                <small>
                                    <strong>服务器:</strong> <?php echo htmlspecialchars($current_settings['smtp_host'] ?? '未配置'); ?><br>
                                    <strong>端口:</strong> <?php echo htmlspecialchars($current_settings['smtp_port'] ?? '未配置'); ?><br>
                                    <strong>加密:</strong> <?php echo strtoupper($current_settings['smtp_secure'] ?? '未配置'); ?>
                                </small>
                            </div>
                            <div class="col-md-6">
                                <small>
                                    <strong>用户名:</strong> <?php echo htmlspecialchars($current_settings['smtp_username'] ?? '未配置'); ?><br>
                                    <strong>状态:</strong> 
                                    <?php if (($current_settings['smtp_enabled'] ?? '0') === '1'): ?>
                                        <span class="text-success">已启用</span>
                                    <?php else: ?>
                                        <span class="text-danger">未启用</span>
                                    <?php endif; ?>
                                </small>
                            </div>
                        </div>
                    </div>
                    
                    <!-- 常见问题提示 -->
                    <div class="alert alert-warning">
                        <h6 class="alert-heading">
                            <i class="fas fa-exclamation-triangle me-2"></i>常见问题排查
                        </h6>
                        <ul class="mb-0 small">
                            <li>确保SMTP服务已启用并保存配置</li>
                            <li>检查邮箱服务商是否支持SMTP（如QQ邮箱需要开启SMTP服务）</li>
                            <li>确认使用的是授权码而不是登录密码</li>
                            <li>检查防火墙是否阻止了SMTP端口连接</li>
                            <li>如果使用Gmail，需要开启"两步验证"并生成"应用专用密码"</li>
                        </ul>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="test_email" class="btn btn-success">
                        <i class="fas fa-paper-plane me-1"></i>发送测试邮件
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- 邮件模板编辑模态框 -->
<div class="modal fade" id="templateModal" tabindex="-1">
    <div class="modal-dialog modal-xl">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">
                    <i class="fas fa-edit me-2"></i>邮件模板管理
                </h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form method="POST">
                <div class="modal-body">
                    <div class="alert alert-warning">
                        <i class="fas fa-exclamation-triangle me-2"></i>
                        <strong>注意：</strong>修改模板将直接更新 config/smtp.php 文件中的邮件模板。请谨慎操作，建议先备份文件。
                    </div>
                    
                    <!-- 模板选择标签页 -->
                    <ul class="nav nav-tabs" id="templateTabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link active" id="registration-tab" data-bs-toggle="tab" data-bs-target="#registration" type="button" role="tab">
                                <i class="fas fa-user-plus me-1"></i>注册验证
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="password-reset-tab" data-bs-toggle="tab" data-bs-target="#password-reset" type="button" role="tab">
                                <i class="fas fa-key me-1"></i>密码重置
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="password-change-tab" data-bs-toggle="tab" data-bs-target="#password-change" type="button" role="tab">
                                <i class="fas fa-shield-alt me-1"></i>密码修改通知
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="email-change-tab" data-bs-toggle="tab" data-bs-target="#email-change" type="button" role="tab">
                                <i class="fas fa-envelope-open me-1"></i>邮箱更换
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link" id="test-email-tab" data-bs-toggle="tab" data-bs-target="#test-email" type="button" role="tab">
                                <i class="fas fa-flask me-1"></i>测试邮件
                            </button>
                        </li>
                    </ul>
                    
                    <!-- 模板编辑内容 -->
                    <div class="tab-content mt-3" id="templateTabsContent">
                        <!-- 注册验证模板 -->
                        <div class="tab-pane fade show active" id="registration" role="tabpanel">
                            <div class="mb-3">
                                <label for="registration_template" class="form-label">注册验证邮件模板</label>
                                <div class="form-text mb-2">
                                    可用变量：<code>{$username}</code> (用户名), <code>{$code}</code> (验证码)
                                </div>
                                <textarea class="form-control" id="registration_template" name="registration_template" rows="15" style="font-family: monospace; font-size: 12px;"><?php echo htmlspecialchars(getCurrentTemplate('registration')); ?></textarea>
                            </div>
                        </div>
                        
                        <!-- 密码重置模板 -->
                        <div class="tab-pane fade" id="password-reset" role="tabpanel">
                            <div class="mb-3">
                                <label for="password_reset_template" class="form-label">密码重置邮件模板</label>
                                <div class="form-text mb-2">
                                    可用变量：<code>{$username}</code> (用户名), <code>{$code}</code> (验证码)
                                </div>
                                <textarea class="form-control" id="password_reset_template" name="password_reset_template" rows="15" style="font-family: monospace; font-size: 12px;"><?php echo htmlspecialchars(getCurrentTemplate('password_reset')); ?></textarea>
                            </div>
                        </div>
                        
                        <!-- 密码修改通知模板 -->
                        <div class="tab-pane fade" id="password-change" role="tabpanel">
                            <div class="mb-3">
                                <label for="password_change_template" class="form-label">密码修改通知邮件模板</label>
                                <div class="form-text mb-2">
                                    可用变量：<code>{$username}</code> (用户名), <code>{$change_time}</code> (修改时间)
                                </div>
                                <textarea class="form-control" id="password_change_template" name="password_change_template" rows="15" style="font-family: monospace; font-size: 12px;"><?php echo htmlspecialchars(getCurrentTemplate('password_change')); ?></textarea>
                            </div>
                        </div>
                        
                        <!-- 邮箱更换模板 -->
                        <div class="tab-pane fade" id="email-change" role="tabpanel">
                            <div class="mb-3">
                                <label for="email_change_template" class="form-label">邮箱更换验证邮件模板</label>
                                <div class="form-text mb-2">
                                    可用变量：<code>{$username}</code> (用户名), <code>{$code}</code> (验证码)
                                </div>
                                <textarea class="form-control" id="email_change_template" name="email_change_template" rows="15" style="font-family: monospace; font-size: 12px;"><?php echo htmlspecialchars(getCurrentTemplate('email_change')); ?></textarea>
                            </div>
                        </div>
                        
                        <!-- 测试邮件模板 -->
                        <div class="tab-pane fade" id="test-email" role="tabpanel">
                            <div class="mb-3">
                                <label for="test_email_template" class="form-label">测试邮件模板</label>
                                <div class="form-text mb-2">
                                    可用变量：<code>{$test_time}</code> (测试时间), <code>{$this->smtp_host}</code> (SMTP服务器), <code>{$this->smtp_username}</code> (SMTP用户名)
                                </div>
                                <textarea class="form-control" id="test_email_template" name="test_email_template" rows="15" style="font-family: monospace; font-size: 12px;"><?php echo htmlspecialchars(getCurrentTemplate('test_email')); ?></textarea>
                            </div>
                        </div>
                    </div>
                    
                    <div class="alert alert-info mt-3">
                        <i class="fas fa-lightbulb me-2"></i>
                        <strong>提示：</strong>
                        <ul class="mb-0 mt-2">
                            <li>模板使用HTML格式，支持内联CSS样式</li>
                            <li>变量会在发送时自动替换为实际值</li>
                            <li>建议保持邮件的专业性和可读性</li>
                            <li>修改后会立即生效，无需重启服务</li>
                        </ul>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                    <button type="submit" name="update_templates" class="btn btn-primary">
                        <i class="fas fa-save me-1"></i>保存模板
                    </button>
                </div>
            </form>
        </div>
    </div>
</div>

<?php include 'includes/footer.php'; ?>