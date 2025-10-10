# 🚀 六趣DNS 安装指南

<div align="center">
  <img src="https://img.shields.io/badge/📦-安装指南-blue?style=for-the-badge" alt="安装指南">
  <img src="https://img.shields.io/badge/⚡-快速部署-green?style=for-the-badge" alt="快速部署">
</div>

---

## 📋 目录

- [环境要求](#环境要求)
- [快速安装](#快速安装)
- [详细配置](#详细配置)
- [常见问题](#常见问题)
- [性能优化](#性能优化)

---

## 🔧 环境要求

### 最低配置

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| **PHP** | 7.4 | 8.0+ | 服务端运行环境 |
| **SQLite3** | 3.0 | 3.35+ | 数据库扩展 |
| **cURL** | 7.0 | 7.80+ | HTTP客户端 |
| **OpenSSL** | 1.0 | 3.0+ | 加密支持 |
| **内存** | 128MB | 256MB+ | 推荐配置 |
| **磁盘空间** | 100MB | 500MB+ | 包含数据库和日志 |

### 必需扩展

```bash
# 检查PHP扩展
php -m | grep -E "(sqlite3|curl|openssl|gd|mbstring)"
```

**必需扩展：**
- `sqlite3` - 数据库支持
- `curl` - HTTP客户端
- `openssl` - 加密支持
- `gd` - 验证码生成
- `mbstring` - 多字节字符串

---

## ⚡ 快速安装

### 1️⃣ 下载项目

```bash
# 克隆仓库
git clone https://github.com/976853694/cloudflare-DNS.git
cd cloudflare-DNS

# 或者下载ZIP包
wget https://github.com/976853694/cloudflare-DNS/archive/main.zip
unzip main.zip
cd cloudflare-DNS-main
```

### 2️⃣ 设置权限

```bash
# 设置目录权限
chmod -R 755 .
chmod 666 data/cloudflare_dns.db

# 如果使用Apache
chown -R www-data:www-data .

# 如果使用Nginx
chown -R nginx:nginx .
```

### 3️⃣ 配置Web服务器

#### Nginx 配置

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/cloudflare-DNS;
    index index.php;
    
    # 安全防护
    location ~* \.(db|sqlite|sql|bak|backup|log)$ {
        return 301 /;
    }
    
    # PHP处理
    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php/php8.0-fpm.sock;
        fastcgi_index index.php;
        include fastcgi_params;
    }
    
    # 静态资源缓存
    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

#### Apache 配置

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    DocumentRoot /path/to/cloudflare-DNS
    
    <Directory /path/to/cloudflare-DNS>
        AllowOverride All
        Require all granted
    </Directory>
    
    # 安全防护
    <FilesMatch "\.(db|sqlite|sql|bak|backup|log)$">
        Require all denied
    </FilesMatch>
</VirtualHost>
```

### 4️⃣ 完成安装

1. 访问 `http://your-domain.com/install.php`
2. 按照安装向导完成配置
3. 创建管理员账户
4. 删除 `install.php` 文件

---

## 🔧 详细配置

### 系统配置

#### 基本设置

```php
// config/settings.php
return [
    'site_name' => '六趣DNS管理系统',
    'default_points' => 100,
    'invitation_reward' => 50,
    'smtp_enabled' => true,
];
```

#### 数据库配置

```php
// config/database.php
class Database {
    private static $instance = null;
    private $db;
    
    private function __construct() {
        $this->db = new SQLite3('data/cloudflare_dns.db');
        $this->initTables();
    }
}
```

### 邮件配置

#### SMTP设置

1. **进入管理后台**
   - 访问 `/admin/smtp_settings.php`
   - 填写SMTP服务器信息

2. **常用配置**
   ```
   QQ邮箱：
   - 服务器：smtp.qq.com
   - 端口：465
   - 加密：SSL
   
   Gmail：
   - 服务器：smtp.gmail.com
   - 端口：465
   - 加密：SSL
   ```

3. **测试邮件**
   - 发送测试邮件验证配置
   - 检查垃圾邮件文件夹

### DNS提供商配置

#### Cloudflare配置

1. **获取API Token**
   - 登录 [Cloudflare](https://dash.cloudflare.com/)
   - My Profile → API Tokens
   - 创建Custom token

2. **权限设置**
   ```
   Zone:Read - 读取域名信息
   DNS:Edit - 编辑DNS记录
   ```

3. **添加账户**
   - 后台 → 管理CF账户
   - 填写Token信息
   - 测试连接

#### 彩虹DNS配置

1. **获取API信息**
   - 登录彩虹DNS控制台
   - 获取API密钥和用户ID

2. **配置账户**
   - 后台 → 管理彩虹账户
   - 填写API信息
   - 验证连接

---

## ❓ 常见问题

### 安装问题

**Q: 无法访问安装页面**
```
A: 检查以下项目：
1. Web服务器是否正常运行
2. PHP是否正常工作
3. 文件权限是否正确
4. 防火墙是否阻止访问
```

**Q: 数据库初始化失败**
```
A: 解决方案：
1. 检查data目录权限
2. 确认SQLite3扩展已安装
3. 查看PHP错误日志
4. 检查磁盘空间
```

**Q: 权限错误**
```
A: 设置正确权限：
chmod -R 755 .
chmod 666 data/cloudflare_dns.db
chown -R www-data:www-data .
```

### 配置问题

**Q: 邮件发送失败**
```
A: 检查项目：
1. SMTP服务器配置
2. 邮箱认证信息
3. 防火墙设置
4. 邮件服务商限制
```

**Q: DNS记录不生效**
```
A: 可能原因：
1. DNS提供商配置错误
2. API权限不足
3. 记录格式错误
4. DNS传播延迟
```

**Q: 验证码显示异常**
```
A: 解决方案：
1. 检查GD扩展
2. 确认字体文件存在
3. 检查PHP内存限制
4. 查看错误日志
```

### 性能问题

**Q: 页面加载缓慢**
```
A: 优化建议：
1. 启用PHP OPcache
2. 配置静态资源缓存
3. 优化数据库查询
4. 使用CDN加速
```

**Q: 内存使用过高**
```
A: 调整配置：
1. 增加PHP内存限制
2. 优化图片处理
3. 清理日志文件
4. 监控内存使用
```

---

## 🚀 性能优化

### PHP优化

#### php.ini 配置

```ini
# 内存和性能
memory_limit = 256M
max_execution_time = 30
max_input_time = 30

# 文件上传
upload_max_filesize = 10M
post_max_size = 10M

# 会话配置
session.gc_maxlifetime = 3600
session.cookie_lifetime = 0

# OPcache优化
opcache.enable = 1
opcache.memory_consumption = 128
opcache.max_accelerated_files = 4000
```

#### 扩展优化

```bash
# 安装性能扩展
sudo apt install php8.0-opcache php8.0-apcu

# 启用扩展
echo "extension=opcache" >> /etc/php/8.0/fpm/php.ini
echo "extension=apcu" >> /etc/php/8.0/fpm/php.ini
```

### 数据库优化

#### SQLite优化

```sql
-- 创建索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_dns_records_domain ON dns_records(domain_id);
CREATE INDEX idx_dns_records_user ON dns_records(user_id);

-- 分析数据库
ANALYZE;

-- 清理数据库
VACUUM;
```

#### 定期维护

```bash
#!/bin/bash
# 数据库维护脚本

# 清理过期日志
find data/logs/ -name "*.log" -mtime +30 -delete

# 优化数据库
sqlite3 data/cloudflare_dns.db "VACUUM;"

# 备份数据库
cp data/cloudflare_dns.db data/backup/cloudflare_dns_$(date +%Y%m%d).db
```

### 服务器优化

#### Nginx优化

```nginx
# 启用gzip压缩
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

# 静态资源缓存
location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}

# 安全头
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
```

#### 系统优化

```bash
# 系统参数优化
echo 'net.core.somaxconn = 65535' >> /etc/sysctl.conf
echo 'net.ipv4.tcp_max_syn_backlog = 65535' >> /etc/sysctl.conf
sysctl -p

# 文件描述符限制
echo '* soft nofile 65535' >> /etc/security/limits.conf
echo '* hard nofile 65535' >> /etc/security/limits.conf
```

---

## 📊 监控和维护

### 系统监控

#### 资源监控

```bash
# CPU和内存监控
htop
iostat -x 1

# 网络连接监控
netstat -an | grep :80
ss -tuln

# 磁盘使用监控
df -h
du -sh data/
```

#### 应用监控

```bash
# 数据库大小
ls -lh data/cloudflare_dns.db

# 日志文件大小
du -sh data/logs/

# 用户数量
sqlite3 data/cloudflare_dns.db "SELECT COUNT(*) FROM users;"

# DNS记录数量
sqlite3 data/cloudflare_dns.db "SELECT COUNT(*) FROM dns_records;"
```

### 备份策略

#### 自动备份脚本

```bash
#!/bin/bash
# backup.sh - 自动备份脚本

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/path/to/backup"
PROJECT_DIR="/path/to/cloudflare-DNS"

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
cp $PROJECT_DIR/data/cloudflare_dns.db $BACKUP_DIR/cloudflare_dns_$DATE.db

# 备份配置文件
tar -czf $BACKUP_DIR/config_$DATE.tar.gz $PROJECT_DIR/config/

# 清理旧备份（保留7天）
find $BACKUP_DIR -name "*.db" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "备份完成: $DATE"
```

#### 定时任务

```bash
# 添加到crontab
crontab -e

# 每天凌晨2点备份
0 2 * * * /path/to/backup.sh

# 每周清理日志
0 3 * * 0 find /path/to/cloudflare-DNS/data/logs/ -name "*.log" -mtime +30 -delete
```

---

<div align="center">
  <p><strong>🚀 六趣DNS 安装指南</strong></p>
  <p>如有问题，请查看Wiki文档或联系技术支持</p>
  <p>Made with ❤️ by 六趣M</p>
</div>
