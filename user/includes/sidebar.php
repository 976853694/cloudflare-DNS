<nav id="sidebarMenu" class="col-md-3 col-lg-2 d-md-block sidebar collapse">
    <div class="position-sticky pt-3 d-flex flex-column" style="height: calc(100vh - 48px);">
        <!-- 用户信息 -->
        <div class="user-info">
            <div class="d-flex align-items-center">
                <i class="fas fa-user-circle fa-2x me-2"></i>
                <div>
                    <div class="fw-bold"><?php echo htmlspecialchars($_SESSION['username']); ?></div>
                    <small><?php echo htmlspecialchars($_SESSION['user_email'] ?? ''); ?></small>
                </div>
            </div>
            <div class="points-badge">
                <i class="fas fa-coins me-1"></i>
                积分: <?php echo $_SESSION['user_points']; ?>
            </div>
        </div>
        
        <!-- 导航菜单 -->
        <ul class="nav flex-column">
            <li class="nav-item">
                <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'dashboard.php' ? 'active' : ''; ?>" href="dashboard.php">
                    <i class="fas fa-tachometer-alt me-2"></i>DNS管理
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'records.php' ? 'active' : ''; ?>" href="records.php">
                    <i class="fas fa-list me-2"></i>我的记录
                </a>
            </li>
            <li class="nav-item">
                <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'recharge.php' ? 'active' : ''; ?>" href="recharge.php">
                    <i class="fas fa-credit-card me-2"></i>积分充值
                </a>
            </li>
            <?php if (getSetting('invitation_enabled', '1')): ?>
            <li class="nav-item">
                <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'invitations.php' ? 'active' : ''; ?>" href="invitations.php">
                    <i class="fas fa-user-friends me-2"></i>邀请管理
                </a>
            </li>
            <?php endif; ?>
            <li class="nav-item">
                <a class="nav-link <?php echo basename($_SERVER['PHP_SELF']) == 'profile.php' ? 'active' : ''; ?>" href="profile.php">
                    <i class="fas fa-user-cog me-2"></i>个人设置
                </a>
            </li>
        </ul>
        
        <h6 class="sidebar-heading d-flex justify-content-between align-items-center px-3 mt-4 mb-1 text-muted">
            <span>帮助信息</span>
        </h6>
        <ul class="nav flex-column mb-2">
            <li class="nav-item">
                <a class="nav-link" href="#" data-bs-toggle="modal" data-bs-target="#helpModal">
                    <i class="fas fa-question-circle me-2"></i>使用帮助
                </a>
            </li>
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

<!-- 帮助模态框 -->
<div class="modal fade" id="helpModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">使用帮助</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <h6>DNS记录类型说明：</h6>
                <ul>
                    <li><strong>A记录</strong>：将域名指向IPv4地址</li>
                    <li><strong>AAAA记录</strong>：将域名指向IPv6地址</li>
                    <li><strong>CNAME记录</strong>：将域名指向另一个域名</li>
                    <li><strong>MX记录</strong>：邮件交换记录</li>
                    <li><strong>TXT记录</strong>：文本记录，常用于验证</li>
                </ul>
                
                <h6>积分系统：</h6>
                <p>每添加一条DNS记录需要消耗 <?php echo getSetting('points_per_record', 1); ?> 积分。积分不足时无法添加新记录，请联系管理员充值。</p>
                
                <h6>代理状态：</h6>
                <p>启用Cloudflare代理后，流量将通过Cloudflare的CDN网络，提供加速和安全防护功能。</p>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
            </div>
        </div>
    </div>
</div>