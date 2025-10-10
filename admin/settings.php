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

// 处理设置更新
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['update_settings'])) {
    $settings = [
        'site_name' => getPost('site_name'),
        'points_per_record' => getPost('points_per_record'),
        'default_user_points' => getPost('default_user_points'),
        'allow_registration' => getPost('allow_registration', 0),
        'background_image_url' => getPost('background_image_url'),
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
    'background_image_url' => getSetting('background_image_url', 'https://img.6qu.cc/file/img/1757093288720_%E3%80%90%E5%93%B2%E9%A3%8E%E5%A3%81%E7%BA%B8%E3%80%91%E4%BC%A0%E7%BB%9F%E5%BB%BA%E7%AD%91-%E5%92%96%E5%95%A1%E5%B0%8F%E5%BA%97__1_.png?from=admin'),
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

<style>
/* 自定义设置页面样式 */
.modern-form {
    animation: fadeInUp 0.5s ease-out;
}

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(30px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.form-floating > .form-control {
    border-radius: 12px;
    border-width: 2px;
    transition: all 0.3s ease;
}

.form-floating > .form-control:focus {
    border-color: #0d6efd;
    box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.15);
    transform: translateY(-2px);
}

.modern-switch-container {
    background: transparent;
    backdrop-filter: blur(50px);
    -webkit-backdrop-filter: blur(50px);
    border: 2px solid rgba(255, 255, 255, 0.3);
    transition: all 0.3s ease;
}

.modern-switch-container:hover {
    border-color: rgba(255, 255, 255, 0.5);
    transform: translateY(-2px);
}

.form-check-input:checked + .form-check-label {
    color: #0d6efd;
}

.form-check-input:checked {
    background-color: #0d6efd;
    border-color: #0d6efd;
}

.settings-divider {
    position: relative;
    text-align: center;
}

.divider-line {
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #dee2e6, transparent);
}

.divider-content {
    background: transparent;
    backdrop-filter: blur(50px);
    -webkit-backdrop-filter: blur(50px);
    padding: 0 2rem;
    display: inline-flex;
    align-items: center;
    position: relative;
    z-index: 1;
}

.info-card {
    background: transparent;
    backdrop-filter: blur(50px);
    -webkit-backdrop-filter: blur(50px);
    border: 1px solid rgba(255, 255, 255, 0.3);
    transition: all 0.3s ease;
}

.info-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
}

.github-config-info {
    background: transparent;
    backdrop-filter: blur(50px);
    -webkit-backdrop-filter: blur(50px);
    border: 1px solid rgba(255, 255, 255, 0.3);
}

.config-step {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
}

.step-number {
    background: linear-gradient(135deg, #007bff, #0056b3);
    color: white;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 0.875rem;
    flex-shrink: 0;
}

.step-content {
    flex: 1;
}

.dns-type-card {
    transition: all 0.3s ease;
    cursor: pointer;
}

.dns-type-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
}

.dns-type-switch {
    transform: scale(1.2);
}

.dns-actions {
    background: transparent;
    backdrop-filter: blur(50px);
    -webkit-backdrop-filter: blur(50px);
    border: 1px solid rgba(255, 255, 255, 0.3);
}

.info-item {
    transition: all 0.3s ease;
}

.info-item:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}

.bg-gradient-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.bg-gradient-success {
    background: linear-gradient(135deg, #56ab2f 0%, #a8e6cf 100%);
}

.bg-gradient-info {
    background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
}

.btn-lg.rounded-pill {
    transition: all 0.3s ease;
}

.btn-lg.rounded-pill:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.2);
}

.transition-all {
    transition: all 0.3s ease;
}

.text-purple {
    color: #6f42c1;
}

.bg-success-subtle {
    background: transparent;
    backdrop-filter: blur(50px);
    -webkit-backdrop-filter: blur(50px);
}

.glass-container {
    background: transparent;
    backdrop-filter: blur(50px);
    -webkit-backdrop-filter: blur(50px);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

/* 响应式改进 */
@media (max-width: 768px) {
    .divider-content {
        padding: 0 1rem;
    }
    
    .config-step {
        flex-direction: column;
        text-align: center;
    }
    
    .step-number {
        margin: 0 auto;
    }
    
    .dns-actions .d-flex {
        flex-direction: column;
        gap: 1rem;
    }
    
    .btn-group {
        width: 100%;
    }
    
    .btn-group .btn {
        flex: 1;
    }
}
</style>

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
            
            <div class="card shadow-lg border-0 rounded-3">
                <div class="card-header bg-gradient-primary text-white border-0 rounded-top-3">
                    <div class="d-flex align-items-center">
                        <i class="fas fa-cog me-3 fs-5"></i>
                        <h5 class="mb-0 fw-bold">基本设置</h5>
                    </div>
                </div>
                <div class="card-body p-4">
                    <form method="POST" class="modern-form">
                        <div class="row g-4">
                            <div class="col-md-6">
                                <div class="form-floating mb-3">
                                    <input type="text" class="form-control form-control-lg border-2" id="site_name" name="site_name" 
                                           value="<?php echo htmlspecialchars($current_settings['site_name']); ?>" required
                                           placeholder="网站名称">
                                    <label for="site_name"><i class="fas fa-globe me-2"></i>网站名称</label>
                                </div>
                                
                                <div class="form-floating mb-3">
                                    <input type="number" class="form-control form-control-lg border-2" id="points_per_record" name="points_per_record" 
                                           value="<?php echo $current_settings['points_per_record']; ?>" min="1" required
                                           placeholder="每条记录消耗积分">
                                    <label for="points_per_record"><i class="fas fa-coins me-2"></i>每条记录消耗积分</label>
                                </div>
                            </div>
                            
                            <div class="col-md-6">
                                <div class="form-floating mb-3">
                                    <input type="number" class="form-control form-control-lg border-2" id="default_user_points" name="default_user_points" 
                                           value="<?php echo $current_settings['default_user_points']; ?>" min="0" required
                                           placeholder="新用户默认积分">
                                    <label for="default_user_points"><i class="fas fa-user-plus me-2"></i>新用户默认积分</label>
                                </div>
                                
                                <div class="modern-switch-container p-3 rounded-3">
                                    <div class="form-check form-switch form-check-lg">
                                        <input class="form-check-input" type="checkbox" id="allow_registration" name="allow_registration" value="1"
                                               <?php echo $current_settings['allow_registration'] ? 'checked' : ''; ?>>
                                        <label class="form-check-label fw-bold" for="allow_registration">
                                            <i class="fas fa-user-check me-2"></i>允许用户注册
                                        </label>
                                    </div>
                                    <small class="text-muted">关闭后新用户无法注册账户</small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 界面设置 -->
                        <div class="settings-divider my-5">
                            <div class="divider-line"></div>
                            <div class="divider-content">
                                <i class="fas fa-palette text-primary fs-4"></i>
                                <h5 class="fw-bold text-primary mb-0 ms-2">界面设置</h5>
                            </div>
                        </div>
                        
                        <div class="row g-4">
                            <div class="col-md-12">
                                <div class="form-floating mb-3">
                                    <input type="url" class="form-control form-control-lg border-2" id="background_image_url" name="background_image_url" 
                                           value="<?php echo htmlspecialchars($current_settings['background_image_url']); ?>" 
                                           placeholder="https://example.com/image.jpg">
                                    <label for="background_image_url"><i class="fas fa-image me-2"></i>背景图片URL</label>
                                </div>
                                <div class="glass-container p-3 rounded-3">
                                    <small class="text-muted">
                                        <i class="fas fa-info-circle me-1"></i>
                                        设置网站背景图片，支持HTTPS链接。留空则使用默认背景。
                                    </small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 邀请系统设置 -->
                        <div class="settings-divider my-5">
                            <div class="divider-line"></div>
                            <div class="divider-content">
                                <i class="fas fa-user-friends text-success fs-4"></i>
                                <h5 class="fw-bold text-success mb-0 ms-2">邀请系统设置</h5>
                            </div>
                        </div>
                        
                        <div class="row g-4">
                            <div class="col-md-6">
                                <div class="modern-switch-container p-3 glass-container rounded-3 mb-3">
                                    <div class="form-check form-switch form-check-lg">
                                        <input class="form-check-input" type="checkbox" id="invitation_enabled" name="invitation_enabled" value="1"
                                               <?php echo getSetting('invitation_enabled', 1) ? 'checked' : ''; ?>>
                                        <label class="form-check-label fw-bold" for="invitation_enabled">
                                            <i class="fas fa-handshake me-2"></i>启用邀请系统
                                        </label>
                                    </div>
                                    <small class="text-muted">关闭后用户将无法生成和使用邀请码</small>
                                </div>
                                
                                <div class="form-floating mb-3">
                                    <input type="number" class="form-control form-control-lg border-2" id="invitation_reward_points" name="invitation_reward_points" 
                                           value="<?php echo (int)getSetting('invitation_reward_points', 10); ?>" min="0" max="1000"
                                           placeholder="邀请成功奖励积分">
                                    <label for="invitation_reward_points"><i class="fas fa-gift me-2"></i>邀请成功奖励积分</label>
                                </div>
                            </div>
                            
                            <div class="col-md-6">
                                <div class="form-floating mb-3">
                                    <input type="number" class="form-control form-control-lg border-2" id="invitee_bonus_points" name="invitee_bonus_points" 
                                           value="<?php echo (int)getSetting('invitee_bonus_points', 5); ?>" min="0" max="1000"
                                           placeholder="被邀请用户额外积分">
                                    <label for="invitee_bonus_points"><i class="fas fa-star me-2"></i>被邀请用户额外积分</label>
                                </div>
                                
                                <div class="info-card p-4 rounded-3">
                                    <div class="d-flex align-items-start">
                                        <i class="fas fa-lightbulb text-warning fs-4 me-3 mt-1"></i>
                                        <div>
                                            <h6 class="fw-bold mb-2">邀请系统说明</h6>
                                            <ul class="list-unstyled mb-0 small">
                                                <li class="mb-1"><i class="fas fa-check text-success me-2"></i>用户可生成邀请码分享给朋友</li>
                                                <li class="mb-1"><i class="fas fa-check text-success me-2"></i>朋友使用邀请码注册可获得额外积分</li>
                                                <li><i class="fas fa-check text-success me-2"></i>邀请人在朋友注册后获得奖励积分</li>
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- GitHub OAuth 设置 -->
                        <div class="settings-divider my-5">
                            <div class="divider-line"></div>
                            <div class="divider-content">
                                <i class="fab fa-github text-dark fs-4"></i>
                                <h5 class="fw-bold text-dark mb-0 ms-2">GitHub OAuth 设置</h5>
                            </div>
                        </div>
                        
                        <div class="row g-4">
                            <div class="col-md-6">
                                <div class="modern-switch-container p-3 glass-container rounded-3 mb-3">
                                    <div class="form-check form-switch form-check-lg">
                                        <input class="form-check-input" type="checkbox" id="github_oauth_enabled" name="github_oauth_enabled" value="1" 
                                               <?php echo ($current_settings['github_oauth_enabled'] ?? 0) ? 'checked' : ''; ?>>
                                        <label class="form-check-label fw-bold" for="github_oauth_enabled">
                                            <i class="fab fa-github me-2"></i>启用 GitHub OAuth 登录
                                        </label>
                                    </div>
                                    <small class="text-muted">允许用户使用GitHub账户登录</small>
                                </div>
                                
                                <div class="form-floating mb-3">
                                    <input type="text" class="form-control form-control-lg border-2" id="github_client_id" name="github_client_id" 
                                           value="<?php echo htmlspecialchars($current_settings['github_client_id'] ?? ''); ?>" 
                                           placeholder="从GitHub OAuth App获取">
                                    <label for="github_client_id"><i class="fas fa-key me-2"></i>GitHub Client ID</label>
                                </div>
                                
                                <div class="form-floating mb-3">
                                    <input type="password" class="form-control form-control-lg border-2" id="github_client_secret" name="github_client_secret" 
                                           value="<?php echo htmlspecialchars($current_settings['github_client_secret'] ?? ''); ?>" 
                                           placeholder="从GitHub OAuth App获取">
                                    <label for="github_client_secret"><i class="fas fa-lock me-2"></i>GitHub Client Secret</label>
                                </div>
                            </div>
                            
                            <div class="col-md-6">
                                <div class="modern-switch-container p-3 glass-container rounded-3 mb-3">
                                    <div class="form-check form-switch form-check-lg">
                                        <input class="form-check-input" type="checkbox" id="github_auto_register" name="github_auto_register" value="1" 
                                               <?php echo ($current_settings['github_auto_register'] ?? 1) ? 'checked' : ''; ?>>
                                        <label class="form-check-label fw-bold" for="github_auto_register">
                                            <i class="fas fa-user-plus me-2"></i>允许GitHub用户自动注册
                                        </label>
                                    </div>
                                    <small class="text-muted">新的GitHub用户可以自动创建账户</small>
                                </div>
                                
                                <div class="form-floating mb-3">
                                    <input type="number" class="form-control form-control-lg border-2" id="github_min_account_days" name="github_min_account_days" 
                                           value="<?php echo $current_settings['github_min_account_days']; ?>" min="0" max="3650"
                                           placeholder="GitHub账户最低注册天数">
                                    <label for="github_min_account_days"><i class="fas fa-calendar me-2"></i>GitHub账户最低注册天数</label>
                                </div>
                                
                                <div class="form-floating mb-3">
                                    <input type="number" class="form-control form-control-lg border-2" id="github_bonus_points" name="github_bonus_points" 
                                           value="<?php echo $current_settings['github_bonus_points']; ?>" min="0" max="10000"
                                           placeholder="GitHub用户奖励积分">
                                    <label for="github_bonus_points"><i class="fas fa-trophy me-2"></i>GitHub用户奖励积分</label>
                                </div>
                            </div>
                        </div>
                        
                        <div class="github-config-info p-4 rounded-3 mb-4">
                            <div class="d-flex align-items-start">
                                <i class="fas fa-cog text-info fs-3 me-3 mt-1"></i>
                                <div class="flex-grow-1">
                                    <h6 class="fw-bold mb-3 text-info">GitHub OAuth 配置指南</h6>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <div class="config-step mb-3">
                                                <div class="step-number">1</div>
                                                <div class="step-content">
                                                    <p class="mb-1 fw-bold">访问GitHub设置</p>
                                                    <a href="https://github.com/settings/applications/new" target="_blank" class="btn btn-sm btn-outline-info">
                                                        <i class="fab fa-github me-1"></i>GitHub Developer Settings
                                                    </a>
                                                </div>
                                            </div>
                                            <div class="config-step mb-3">
                                                <div class="step-number">2</div>
                                                <div class="step-content">
                                                    <p class="mb-1 fw-bold">创建OAuth App</p>
                                                    <small class="text-muted">填写应用名称和描述</small>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="config-step mb-3">
                                                <div class="step-number">3</div>
                                                <div class="step-content">
                                                    <p class="mb-1 fw-bold">设置回调URL</p>
                                                    <code class="d-block text-break small glass-container p-2 rounded">
                                                        <?php echo (isset($_SERVER['HTTPS']) ? 'https' : 'http') . '://' . $_SERVER['HTTP_HOST'] . '/user/github_callback.php'; ?>
                                                    </code>
                                                </div>
                                            </div>
                                            <div class="config-step">
                                                <div class="step-number">4</div>
                                                <div class="step-content">
                                                    <p class="mb-1 fw-bold">获取密钥</p>
                                                    <small class="text-muted">复制Client ID和Secret到上方</small>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 保存按钮 -->
                        <div class="text-center my-5">
                            <button type="submit" name="update_settings" class="btn btn-primary btn-lg px-5 py-3 rounded-pill shadow-lg">
                                <i class="fas fa-save me-2"></i>
                                <span class="fw-bold">保存所有设置</span>
                            </button>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- DNS记录类型管理 -->
            <div class="card shadow-lg border-0 rounded-3 mt-5">
                <div class="card-header bg-gradient-success text-white border-0 rounded-top-3">
                    <div class="d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center">
                            <i class="fas fa-network-wired me-3 fs-5"></i>
                            <h5 class="mb-0 fw-bold">DNS记录类型管理</h5>
                        </div>
                        <div class="badge glass-container text-white fs-6">
                            共 <?php echo count($dns_types); ?> 种类型
                        </div>
                    </div>
                </div>
                <div class="card-body p-4">
                    <div class="glass-container border-0 rounded-3 mb-4 p-3">
                        <div class="d-flex align-items-center">
                            <i class="fas fa-info-circle fs-4 me-3 text-info"></i>
                            <div>
                                <strong>使用说明：</strong>选择允许用户使用的DNS记录类型。未选中的类型将在用户端隐藏。
                            </div>
                        </div>
                    </div>
                    
                    <form method="POST" class="dns-types-form">
                        <div class="row g-3">
                            <?php foreach ($dns_types as $type): ?>
                            <div class="col-lg-4 col-md-6">
                                <div class="dns-type-card border rounded-3 h-100 <?php echo $type['enabled'] ? 'border-success bg-success-subtle' : 'border-secondary'; ?> transition-all">
                                    <div class="card-body p-3">
                                        <div class="form-check form-switch form-check-lg">
                                            <input class="form-check-input dns-type-switch" type="checkbox" 
                                                   id="type_<?php echo $type['type_name']; ?>" 
                                                   name="enabled_types[]" 
                                                   value="<?php echo $type['type_name']; ?>"
                                                   <?php echo $type['enabled'] ? 'checked' : ''; ?>>
                                            <label class="form-check-label w-100" for="type_<?php echo $type['type_name']; ?>">
                                                <div class="d-flex align-items-center justify-content-between">
                                                    <div>
                                                        <h6 class="fw-bold mb-1"><?php echo htmlspecialchars($type['type_name']); ?></h6>
                                                        <small class="text-muted"><?php echo htmlspecialchars($type['description']); ?></small>
                                                    </div>
                                                    <div class="ms-2">
                                                        <?php if ($type['enabled']): ?>
                                                            <span class="badge bg-success status-badge">
                                                                <i class="fas fa-check me-1"></i>已启用
                                                            </span>
                                                        <?php else: ?>
                                                            <span class="badge bg-secondary status-badge">
                                                                <i class="fas fa-times me-1"></i>已禁用
                                                            </span>
                                                        <?php endif; ?>
                                                    </div>
                                                </div>
                                            </label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <?php endforeach; ?>
                        </div>
                        
                        <div class="dns-actions mt-4 p-3 rounded-3">
                            <div class="d-flex flex-wrap justify-content-between align-items-center gap-3">
                                <div class="btn-group">
                                    <button type="button" class="btn btn-outline-primary rounded-pill" onclick="selectAllTypes()">
                                        <i class="fas fa-check-double me-1"></i>全选
                                    </button>
                                    <button type="button" class="btn btn-outline-secondary rounded-pill" onclick="clearAllTypes()">
                                        <i class="fas fa-square me-1"></i>全不选
                                    </button>
                                </div>
                                
                                <button type="submit" name="update_dns_types" class="btn btn-success btn-lg rounded-pill px-4 shadow">
                                    <i class="fas fa-save me-2"></i>
                                    <span class="fw-bold">保存DNS类型设置</span>
                                </button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- 系统信息 -->
            <div class="card shadow-lg border-0 rounded-3 mt-5">
                <div class="card-header bg-gradient-info text-white border-0 rounded-top-3">
                    <div class="d-flex align-items-center">
                        <i class="fas fa-server me-3 fs-5"></i>
                        <h5 class="mb-0 fw-bold">系统信息</h5>
                    </div>
                </div>
                <div class="card-body p-4">
                    <div class="row g-4">
                        <div class="col-md-6">
                            <div class="info-section">
                                <h6 class="fw-bold text-primary mb-3">
                                    <i class="fas fa-code me-2"></i>运行环境
                                </h6>
                                <div class="system-info-grid">
                                    <div class="info-item p-3 glass-container rounded-3 mb-3">
                                        <div class="d-flex align-items-center justify-content-between">
                                            <div class="d-flex align-items-center">
                                                <i class="fab fa-php text-purple fs-4 me-3"></i>
                                                <div>
                                                    <strong>PHP版本</strong>
                                                    <br><small class="text-muted">运行时版本</small>
                                                </div>
                                            </div>
                                            <span class="badge bg-primary fs-6"><?php echo PHP_VERSION; ?></span>
                                        </div>
                                    </div>
                                    
                                    <div class="info-item p-3 glass-container rounded-3 mb-3">
                                        <div class="d-flex align-items-center justify-content-between">
                                            <div class="d-flex align-items-center">
                                                <i class="fas fa-database text-success fs-4 me-3"></i>
                                                <div>
                                                    <strong>SQLite版本</strong>
                                                    <br><small class="text-muted">数据库引擎</small>
                                                </div>
                                            </div>
                                            <span class="badge bg-success fs-6"><?php echo SQLite3::version()['versionString']; ?></span>
                                        </div>
                                    </div>
                                    
                                    <div class="info-item p-3 glass-container rounded-3">
                                        <div class="d-flex align-items-center justify-content-between">
                                            <div class="d-flex align-items-center">
                                                <i class="fas fa-clock text-warning fs-4 me-3"></i>
                                                <div>
                                                    <strong>服务器时间</strong>
                                                    <br><small class="text-muted">当前系统时间</small>
                                                </div>
                                            </div>
                                            <span class="badge bg-warning text-dark fs-6"><?php echo date('Y-m-d H:i:s'); ?></span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <div class="info-section">
                                <h6 class="fw-bold text-success mb-3">
                                    <i class="fas fa-check-circle me-2"></i>系统状态
                                </h6>
                                <div class="system-info-grid">
                                    <div class="info-item p-3 glass-container rounded-3 mb-3">
                                        <div class="d-flex align-items-center justify-content-between">
                                            <div class="d-flex align-items-center">
                                                <i class="fas fa-hdd text-info fs-4 me-3"></i>
                                                <div>
                                                    <strong>数据库大小</strong>
                                                    <br><small class="text-muted">磁盘占用空间</small>
                                                </div>
                                            </div>
                                            <span class="badge bg-info fs-6">
                                                <?php 
                                                $db_file = '../data/cloudflare_dns.db';
                                                if (file_exists($db_file)) {
                                                    $size = filesize($db_file);
                                                    if ($size > 1024 * 1024) {
                                                        echo round($size / (1024 * 1024), 2) . ' MB';
                                                    } else {
                                                        echo round($size / 1024, 2) . ' KB';
                                                    }
                                                } else {
                                                    echo '未知';
                                                }
                                                ?>
                                            </span>
                                        </div>
                                    </div>
                                    
                                    <div class="info-item p-3 glass-container rounded-3 mb-3">
                                        <div class="d-flex align-items-center justify-content-between">
                                            <div class="d-flex align-items-center">
                                                <i class="fas fa-globe text-primary fs-4 me-3"></i>
                                                <div>
                                                    <strong>cURL支持</strong>
                                                    <br><small class="text-muted">网络请求功能</small>
                                                </div>
                                            </div>
                                            <?php if (function_exists('curl_init')): ?>
                                                <span class="badge bg-success fs-6">
                                                    <i class="fas fa-check me-1"></i>支持
                                                </span>
                                            <?php else: ?>
                                                <span class="badge bg-danger fs-6">
                                                    <i class="fas fa-times me-1"></i>不支持
                                                </span>
                                            <?php endif; ?>
                                        </div>
                                    </div>
                                    
                                    <div class="info-item p-3 glass-container rounded-3">
                                        <div class="d-flex align-items-center justify-content-between">
                                            <div class="d-flex align-items-center">
                                                <i class="fas fa-shield-alt text-danger fs-4 me-3"></i>
                                                <div>
                                                    <strong>OpenSSL支持</strong>
                                                    <br><small class="text-muted">SSL/TLS加密</small>
                                                </div>
                                            </div>
                                            <?php if (extension_loaded('openssl')): ?>
                                                <span class="badge bg-success fs-6">
                                                    <i class="fas fa-check me-1"></i>支持
                                                </span>
                                            <?php else: ?>
                                                <span class="badge bg-danger fs-6">
                                                    <i class="fas fa-times me-1"></i>不支持
                                                </span>
                                            <?php endif; ?>
                                        </div>
                                    </div>
                                </div>
                            </div>
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
    const card = checkbox.closest('.dns-type-card');
    const badge = card.querySelector('.status-badge');
    
    if (checkbox.checked) {
        card.className = card.className.replace('border-secondary', 'border-success');
        card.classList.add('bg-success-subtle');
        badge.className = 'badge bg-success status-badge';
        badge.innerHTML = '<i class="fas fa-check me-1"></i>已启用';
    } else {
        card.className = card.className.replace('border-success', 'border-secondary');
        card.classList.remove('bg-success-subtle');
        badge.className = 'badge bg-secondary status-badge';
        badge.innerHTML = '<i class="fas fa-times me-1"></i>已禁用';
    }
}

// 为所有复选框添加事件监听器
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.dns-type-switch').forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            updateCardBorder(this);
        });
    });
});
</script>

<?php include 'includes/footer.php'; ?>