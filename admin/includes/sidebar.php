<?php
// 确保必要的函数已加载
if (!function_exists('getSetting')) {
    require_once __DIR__ . '/../../includes/functions.php';
}
?>
<style>
    /* 可折叠分类样式 */
    .sidebar-heading {
        cursor: pointer;
        user-select: none;
        transition: all 0.3s ease;
        font-size: 1.1rem !important;
        font-weight: 600;
        padding: 6px 12px !important;
        margin: 2px 0 !important;
    }
    
    .sidebar-heading:hover {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
    }
    
    .sidebar-heading .collapse-icon {
        transition: transform 0.3s ease;
    }
    
    .sidebar-heading.collapsed .collapse-icon {
        transform: rotate(-90deg);
    }
    
    .menu-group {
        overflow: hidden;
        max-height: 1000px;
        transition: max-height 0.3s ease, opacity 0.3s ease;
        opacity: 1;
    }
    
    .menu-group.collapsed {
        max-height: 0;
        opacity: 0;
    }
    
    /* 调整菜单项样式 */
    .nav-link {
        font-size: 1rem !important;
        padding: 8px 15px !important;
        margin: 2px 8px !important;
        line-height: 1.2 !important;
    }
    
    /* 仪表板链接特殊样式 */
    .nav-item > .nav-link {
        font-size: 1.05rem !important;
        padding: 10px 15px !important;
    }
</style>

<nav id="sidebarMenu" class="col-md-3 col-lg-2 d-md-block sidebar collapse">
    <div class="position-sticky pt-3 d-flex flex-column sidebar-container">
        <ul class="nav flex-column">
            <!-- 核心功能区 -->
            <li class="nav-item">
                <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'dashboard.php' ? 'active' : ''; ?>" href="dashboard.php">
                    <i class="fas fa-tachometer-alt me-2"></i>仪表板
                </a>
            </li>
            
            <!-- 渠道管理区 -->
            <li class="nav-item mt-2">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-2 mb-1 text-muted" onclick="toggleMenuGroup('channel-menu')">
                    <span><i class="fas fa-plug me-2"></i>渠道管理</span>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </h6>
            </li>
            <div id="channel-menu" class="menu-group">
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'channels_management.php' ? 'active' : ''; ?>" href="channels_management.php">
                        <i class="fas fa-plug me-2"></i>渠道管理
                    </a>
                </li>
            </div>
            
            <!-- 域名管理区 -->
            <li class="nav-item mt-1">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-1 mb-1 text-muted" onclick="toggleMenuGroup('domain-menu')">
                    <span><i class="fas fa-globe me-2"></i>域名管理</span>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </h6>
            </li>
            <div id="domain-menu" class="menu-group">
                <li class="nav-item">
                    <a class="nav-link <?php echo in_array(basename($_SERVER['PHP_SELF']), ['domains.php', 'domain_dns.php']) ? 'active' : ''; ?>" href="domains.php">
                        <i class="fas fa-globe me-2"></i>域名列表
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'dns_records.php' ? 'active' : ''; ?>" href="dns_records.php">
                        <i class="fas fa-list me-2"></i>DNS记录
                    </a>
                </li>
            </div>
            
            <!-- 用户与权限管理区 -->
            <li class="nav-item mt-1">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-1 mb-1 text-muted" onclick="toggleMenuGroup('user-menu')">
                    <span><i class="fas fa-users me-2"></i>用户管理</span>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </h6>
            </li>
            <div id="user-menu" class="menu-group">
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'users.php' ? 'active' : ''; ?>" href="users.php">
                        <i class="fas fa-users me-2"></i>用户管理
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'user_groups.php' ? 'active' : ''; ?>" href="user_groups.php">
                        <i class="fas fa-users-cog me-2"></i>用户组管理
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'card_keys.php' ? 'active' : ''; ?>" href="card_keys.php">
                        <i class="fas fa-credit-card me-2"></i>卡密管理
                    </a>
                </li>
                <?php if (getSetting('invitation_enabled', '1')): ?>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'invitations.php' ? 'active' : ''; ?>" href="invitations.php">
                        <i class="fas fa-user-friends me-2"></i>邀请管理
                    </a>
                </li>
                <?php endif; ?>
            </div>
            
            <!-- 内容与安全管理区 -->
            <li class="nav-item mt-1">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-1 mb-1 text-muted" onclick="toggleMenuGroup('content-menu')">
                    <span><i class="fas fa-shield-alt me-2"></i>内容安全</span>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </h6>
            </li>
            <div id="content-menu" class="menu-group">
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'announcements.php' ? 'active' : ''; ?>" href="announcements.php">
                        <i class="fas fa-bullhorn me-2"></i>公告管理
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'version_updates.php' ? 'active' : ''; ?>" href="version_updates.php">
                        <i class="fas fa-code-branch me-2"></i>版本更新
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'blocked_prefixes.php' ? 'active' : ''; ?>" href="blocked_prefixes.php">
                        <i class="fas fa-shield-alt me-2"></i>前缀拦截
                    </a>
                </li>
            </div>
            
            <!-- 系统管理区 -->
            <li class="nav-item mt-1">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-1 mb-1 text-muted" onclick="toggleMenuGroup('system-menu')">
                    <span><i class="fas fa-cog me-2"></i>系统管理</span>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </h6>
            </li>
            <div id="system-menu" class="menu-group">
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'settings.php' ? 'active' : ''; ?>" href="settings.php">
                        <i class="fas fa-cog me-2"></i>系统设置
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'smtp_settings.php' ? 'active' : ''; ?>" href="smtp_settings.php">
                        <i class="fas fa-envelope me-2"></i>SMTP设置
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'logs.php' ? 'active' : ''; ?>" href="logs.php">
                        <i class="fas fa-history me-2"></i>操作日志
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'profile.php' ? 'active' : ''; ?>" href="profile.php">
                        <i class="fas fa-user-cog me-2"></i>管理设置
                    </a>
                </li>
            </div>
            
            <!-- 系统维护区（仅在需要时显示） -->
            <?php 
            // 检查是否需要显示奖励更新工具
            if (getSetting('invitation_enabled', '1')):
                $current_reward_points = (int)getSetting('invitation_reward_points', '10');
                $outdated_count = $db->querySingle("SELECT COUNT(*) FROM invitations WHERE is_active = 1 AND reward_points != $current_reward_points");
                
                // 检查是否需要显示迁移工具
                $db = Database::getInstance()->getConnection();
                $columns = [];
                $result = $db->query("PRAGMA table_info(invitations)");
                while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
                    $columns[] = $row['name'];
                }
                $needs_migration = !in_array('is_active', $columns);
                
                if ($outdated_count > 0 || $needs_migration):
            ?>
            <li class="nav-item mt-1">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-1 mb-1 text-warning" onclick="toggleMenuGroup('maintenance-menu')">
                    <span><i class="fas fa-exclamation-triangle me-1"></i>系统维护</span>
                    <i class="fas fa-chevron-down collapse-icon"></i>
                </h6>
            </li>
            <div id="maintenance-menu" class="menu-group">
                <?php if ($needs_migration): ?>
                <li class="nav-item">
                    <a class="nav-link text-warning <?php echo basename($_SERVER['PHP_SELF']) == 'migrate_invitations.php' ? 'active' : ''; ?>" href="migrate_invitations.php">
                        <i class="fas fa-database me-2"></i>数据库升级
                        <span class="badge bg-warning text-dark ms-2">!</span>
                    </a>
                </li>
                <?php endif; ?>
                <?php if ($outdated_count > 0): ?>
                <li class="nav-item">
                    <a class="nav-link text-warning <?php echo basename($_SERVER['PHP_SELF']) == 'update_invitation_rewards.php' ? 'active' : ''; ?>" href="update_invitation_rewards.php">
                        <i class="fas fa-sync-alt me-2"></i>奖励同步
                        <span class="badge bg-warning text-dark ms-2"><?php echo $outdated_count; ?></span>
                    </a>
                </li>
                <?php endif; ?>
            </div>
            <?php 
                endif;
            endif; 
            ?>
        </ul>
        
        <!-- 退出登录 -->
        <div class="mt-auto pt-3 border-top">
            <ul class="nav flex-column">
                <li class="nav-item">
                    <a class="nav-link text-danger" href="logout.php" onclick="return confirm('确定要退出登录吗？')">
                        <i class="fas fa-sign-out-alt me-2"></i>退出登录
                    </a>
                </li>
            </ul>
        </div>
    </div>
</nav>

<script>
// 菜单折叠功能
function toggleMenuGroup(menuId) {
    const menu = document.getElementById(menuId);
    const heading = event.currentTarget;
    
    if (menu) {
        menu.classList.toggle('collapsed');
        heading.classList.toggle('collapsed');
        
        // 保存状态到 localStorage
        const isCollapsed = menu.classList.contains('collapsed');
        localStorage.setItem('menu_' + menuId, isCollapsed ? 'collapsed' : 'expanded');
    }
}

// 页面加载时恢复菜单状态
document.addEventListener('DOMContentLoaded', function() {
    const menuIds = ['channel-menu', 'domain-menu', 'user-menu', 'content-menu', 'system-menu', 'maintenance-menu'];
    
    // 检查当前页面，自动展开包含当前页面的菜单组
    const currentPage = '<?php echo basename($_SERVER['PHP_SELF']); ?>';
    const activeLink = document.querySelector('.nav-link.active');
    let currentMenuId = null;
    
    if (activeLink) {
        let parent = activeLink.closest('.menu-group');
        if (parent) {
            currentMenuId = parent.id;
        }
    }
    
    menuIds.forEach(function(menuId) {
        const menu = document.getElementById(menuId);
        if (menu) {
            const savedState = localStorage.getItem('menu_' + menuId);
            
            // 如果有保存的状态，使用保存的状态；否则默认折叠
            if (savedState === 'expanded' || menuId === currentMenuId) {
                // 展开状态
                menu.classList.remove('collapsed');
                const heading = menu.previousElementSibling.querySelector('.sidebar-heading');
                if (heading) {
                    heading.classList.remove('collapsed');
                }
            } else {
                // 默认折叠状态
                menu.classList.add('collapsed');
                const heading = menu.previousElementSibling.querySelector('.sidebar-heading');
                if (heading) {
                    heading.classList.add('collapsed');
                }
            }
        }
    });
    
    // 如果当前页面在某个菜单中，确保该菜单展开并保存状态
    if (currentMenuId) {
        localStorage.setItem('menu_' + currentMenuId, 'expanded');
    }
});
</script>