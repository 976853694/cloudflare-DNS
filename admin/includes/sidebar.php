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
            <li class="nav-item mt-3">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-4 mb-1 text-muted">
                    <span>渠道管理</span>
                </h6>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'channels_management.php' ? 'active' : ''; ?>" href="channels_management.php">
                    <i class="fas fa-plug me-2"></i>渠道管理
                </a>
            </li>
            
            <!-- 域名管理区 -->
            <li class="nav-item mt-3">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-4 mb-1 text-muted">
                    <span>域名管理</span>
                </h6>
            </li>
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
            
            <!-- 用户与权限管理区 -->
            <li class="nav-item mt-3">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-4 mb-1 text-muted">
                    <span>用户管理</span>
                </h6>
            </li>
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
            
            <!-- 内容与安全管理区 -->
            <li class="nav-item mt-3">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-4 mb-1 text-muted">
                    <span>内容安全</span>
                </h6>
            </li>
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
            
            <!-- 系统管理区 -->
            <li class="nav-item mt-3">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-4 mb-1 text-muted">
                    <span>系统管理</span>
                </h6>
            </li>
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
            <li class="nav-item mt-3">
                <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-4 mb-1 text-warning">
                    <span><i class="fas fa-exclamation-triangle me-1"></i>系统维护</span>
                </h6>
            </li>
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