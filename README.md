# 🌐 六趣DNS - 现代化DNS管理系统

<div align="center">
  <img src="https://img.shields.io/badge/PHP-7.4+-blue.svg" alt="PHP Version">
  <img src="https://img.shields.io/badge/License-Non--Commercial-red.svg" alt="License">
  <img src="https://img.shields.io/badge/Database-SQLite3-orange.svg" alt="Database">
  <img src="https://img.shields.io/badge/Framework-Bootstrap%205-purple.svg" alt="Frontend">
  <img src="https://img.shields.io/badge/Status-Active-brightgreen.svg" alt="Status">
</div>

<div align="center">
  <h3>🚀 支持多DNS提供商 | 💎 现代化界面 | 🔒 企业级安全</h3>
  <p>一个功能强大、界面精美的DNS记录管理系统，支持Cloudflare、彩虹DNS等多种DNS服务商</p>
</div>

---

## 🌟 在线演示

<div align="center">
  <a href="https://dns.6qu.cc/" target="_blank">
    <img src="https://img.shields.io/badge/🌐-在线演示-00b4d8?style=for-the-badge&logo=cloudflare" alt="在线演示">
  </a>
</div>

## 💬 社区交流

<div align="center">
  
### 🎯 六趣M技术交流群

<img src="qrcode_1756871735695.jpg" alt="六趣M QQ群二维码" width="300" style="border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">

<p><strong>群号：1044379774</strong></p>
<p>扫码加入群聊，与开发者和其他用户实时交流！</p>

<a href="https://qm.qq.com/q/qYN7MywxO0" target="_blank">
  <img src="https://img.shields.io/badge/💬-点击加入QQ群-00a86b?style=for-the-badge&logo=tencentqq" alt="QQ群">
</a>

</div>

## ⚙️ 环境配置

### 🔧 Nginx 伪静态配置

```nginx
# 安全防护 - 禁止访问data目录
location /data/ {
    return 404;
}

```

---

## 📖 项目简介

**六趣DNS** 是一个基于PHP开发的现代化DNS管理系统，为用户提供简洁、高效的DNS记录管理体验。系统支持多DNS提供商（Cloudflare、彩虹DNS、DNSPod、PowerDNS），具备完善的用户管理、积分系统和邮件验证功能。

### 🎯 设计理念

- **🎨 用户体验优先** - 简洁直观的操作界面
- **🔒 安全第一** - 企业级安全防护机制  
- **⚡ 性能优化** - 快速响应的系统架构
- **🌐 多平台支持** - 完美适配各种设备

### ✨ 核心特性

<table>
<tr>
<td width="50%">

#### 🌐 多DNS提供商
- **Cloudflare** - 全球CDN加速
- **彩虹DNS** - 国内优质解析
- **DNSPod** - 腾讯云DNS服务
- **PowerDNS** - 开源DNS服务器

</td>
<td width="50%">

#### 🔒 企业级安全
- **多重验证** - 邮箱+图形验证码
- **操作审计** - 完整的操作日志
- **权限控制** - 细粒度用户组管理
- **数据加密** - 密码安全存储

</td>
</tr>
<tr>
<td width="50%">

#### 💰 智能积分系统
- **灵活计费** - 按记录类型收费
- **用户组权限** - VIP/SVIP特权
- **邀请奖励** - 推广激励机制
- **卡密充值** - 便捷充值方式

</td>
<td width="50%">

#### 🎨 现代化界面
- **精美认证页** - 全新登录/注册UI
- **响应式设计** - 完美适配移动端
- **动画效果** - 流畅的过渡动画
- **实时反馈** - 优雅的交互体验

</td>
</tr>
</table>

## 🎉 最新更新

<div align="center">

### ✨ 认证界面全新升级 (Latest)

我们对用户认证相关页面进行了全面的UI升级，带来更加现代化、优雅的视觉体验！

#### 📱 升级页面清单

| 页面 | 文件路径 | 更新内容 |
|------|---------|---------|
| **🔑 用户登录** | `/user/login.php` | 简化表单、增强视觉效果、优化移动端体验 |
| **📝 用户注册** | `/user/register_verify.php` | 3步进度条、动画反馈、成功动效 |
| **🔓 找回密码** | `/user/forgot_password.php` | 图标化流程、统一配色、动画优化 |

#### 🎨 设计亮点

<table>
<tr>
<td width="50%">

**🌈 视觉设计**
- 紫色渐变主题 (#667eea → #764ba2)
- 圆角设计 (8px/15px)
- 阴影层次感 (0 20px 60px)
- 一致的配色方案

</td>
<td width="50%">

**✨ 动画效果**
- 按钮悬停抬升效果
- 成功页面脉冲动画
- 平滑过渡 (0.3s)
- 表单焦点光晕

</td>
</tr>
<tr>
<td width="50%">

**📱 响应式优化**
- 移动端布局优化
- 触控友好的按钮尺寸
- 自适应表单间距
- 灵活的栅格系统

</td>
<td width="50%">

**🎯 用户体验**
- 图标化表单标签
- 可关闭的提示消息
- 自动聚焦输入框
- 实时验证反馈

</td>
</tr>
</table>

#### 🔧 技术实现

```css
/* 统一的渐变按钮 */
.btn-primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 8px;
    transition: all 0.3s;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}

/* 成功动画效果 */
@keyframes successPulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}
```

#### 📊 改进对比

| 改进项 | 升级前 | 升级后 |
|--------|--------|--------|
| **设计风格** | 基础 Bootstrap | 现代渐变 + 动画 |
| **表单体验** | 标准输入框 | 图标 + 圆角 + 阴影 |
| **响应式** | 基础适配 | 完美移动端体验 |
| **动画效果** | 无/简单 | 丰富的交互动画 |
| **视觉层次** | 扁平 | 多层次阴影效果 |

</div>

---

## 🚀 功能特色

### 👤 用户功能

<div align="center">

| 功能模块 | 功能描述 | 支持状态 |
|---------|---------|---------|
| 🎨 **现代化认证界面** | 全新设计的登录/注册/找回密码页面 | ✅ 完整支持 |
| 🌐 **DNS记录管理** | 支持A、AAAA、CNAME、TXT、MX等记录类型 | ✅ 完整支持 |
| 🔍 **实时前缀查询** | 检查子域名可用性，避免冲突 | ✅ 完整支持 |
| 📧 **邮箱验证系统** | 注册、密码重置、邮箱更换验证 | ✅ 完整支持 |
| 💰 **积分充值系统** | 卡密充值，灵活计费 | ✅ 完整支持 |
| 🎁 **邀请奖励机制** | 邀请新用户获得积分奖励 | ✅ 完整支持 |
| 👥 **用户组权限** | 默认组/VIP组/SVIP组权限管理 | ✅ 完整支持 |

</div>

### 🛠️ 管理功能

<div align="center">

| 管理模块 | 功能描述 | 支持状态 |
|---------|---------|---------|
| 👥 **用户管理** | 用户账户管理、积分调整、用户组管理 | ✅ 完整支持 |
| 🌐 **域名管理** | 多渠道域名添加和管理 | ✅ 完整支持 |
| 🔧 **系统设置** | SMTP配置、系统参数调整 | ✅ 完整支持 |
| 📧 **邮件模板** | 自定义邮件模板编辑 | ✅ 完整支持 |
| 📊 **操作日志** | 完整的操作审计记录 | ✅ 完整支持 |
| 🎫 **卡密管理** | 充值卡密生成和管理 | ✅ 完整支持 |
| 📈 **数据统计** | 用户使用情况、系统性能监控 | ✅ 完整支持 |

</div>

## 🛠️ 技术栈

<div align="center">

### 🔧 后端技术

| 技术栈 | 版本 | 用途 | 优势 |
|--------|------|------|------|
| **PHP** | 7.4+ | 服务端开发语言 | 成熟稳定，生态丰富 |
| **SQLite3** | 3.x | 轻量级数据库 | 零配置，高性能 |
| **PHPMailer** | 6.x | 邮件发送组件 | 功能强大，支持多种协议 |
| **cURL** | 内置 | HTTP客户端 | 支持HTTPS，SSL验证 |

### 🎨 前端技术

| 技术栈 | 版本 | 用途 | 优势 |
|--------|------|------|------|
| **Bootstrap** | 5.x | 响应式UI框架 | 组件丰富，移动优先 |
| **jQuery** | 3.x | JavaScript库 | 简化DOM操作，兼容性好 |
| **FontAwesome** | 6.x | 图标字体库 | 图标丰富，矢量缩放 |
| **CSS3** | 现代 | 样式设计 | 动画效果，毛玻璃效果 |

### 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   用户界面层     │    │   业务逻辑层     │    │   数据访问层     │
│  (User Layer)   │    │ (Business Layer)│    │  (Data Layer)   │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • 用户前台      │    │ • DNS管理器     │    │ • SQLite数据库  │
│ • 管理后台      │◄──►│ • 用户管理器    │◄──►│ • 文件存储      │
│ • API接口       │    │ • 邮件服务      │    │ • 日志系统      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

</div>

## 📦 安装部署

### 🔧 环境要求

<div align="center">

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| **PHP** | 7.4 | 8.0+ | 服务端运行环境 |
| **SQLite3** | 3.0 | 3.35+ | 数据库扩展 |
| **cURL** | 7.0 | 7.80+ | HTTP客户端 |
| **OpenSSL** | 1.0 | 3.0+ | 加密支持 |
| **Web服务器** | - | - | Apache/Nginx |

</div>

### 🚀 快速安装

#### 1️⃣ 克隆项目

```bash
# 克隆仓库
git clone https://github.com/976853694/cloudflare-DNS.git
cd cloudflare-DNS

# 设置权限
chmod 755 data/
chmod 666 data/cloudflare_dns.db
```

#### 2️⃣ 配置Web服务器

**Nginx 配置示例：**
```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/cloudflare-DNS;
    index index.php;
    
    # 安全防护 - 禁止访问data目录
    location /data/ {
        return 404;
    }
    
    # 安全防护 - 禁止访问敏感文件
    location ~* \.(db|sqlite|sql|bak|backup|log)$ {
        return 404;
    }
    
    # 优化静态资源缓存
    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # PHP处理
    location ~ \.php$ {
        fastcgi_pass unix:/var/run/php/php8.0-fpm.sock;
        fastcgi_index index.php;
        include fastcgi_params;
    }
}
```

#### 3️⃣ 访问安装页面

```
🌐 访问: http://your-domain.com/install.php
```

#### 4️⃣ 完成安装

<div align="center">

| 步骤 | 操作 | 说明 |
|------|------|------|
| **1** | 数据库初始化 | 自动创建数据表和索引 |
| **2** | 创建管理员账户 | 设置管理员用户名和密码 |
| **3** | 配置系统参数 | 设置站点名称、SMTP等 |
| **4** | 完成安装 | 删除install.php文件 |

</div>


## 🔧 配置说明

### 📧 SMTP邮件配置

<div align="center">

| 邮件服务商 | 服务器地址 | 端口 | 加密方式 | 认证方式 |
|-----------|-----------|------|---------|---------|
| **QQ邮箱** | smtp.qq.com | 465 | SSL | 授权码 |
| **Gmail** | smtp.gmail.com | 465 | SSL | 应用专用密码 |
| **163邮箱** | smtp.163.com | 465 | SSL | 授权码 |
| **Outlook** | smtp-mail.outlook.com | 587 | TLS | 密码/授权码 |

</div>

**配置步骤：**
1. 登录管理后台 → SMTP设置
2. 填写邮件服务器信息
3. 发送测试邮件验证配置
4. 保存设置即可使用

### 🌐 DNS提供商配置

#### Cloudflare 配置

<div align="center">

| 步骤 | 操作 | 说明 |
|------|------|------|
| **1** | 获取API Token | 登录Cloudflare → My Profile → API Tokens |
| **2** | 创建Token | 选择"Custom token"，权限：Zone:Read, DNS:Edit |
| **3** | 添加账户 | 后台"管理CF账户" → 添加账户 |
| **4** | 导入域名 | 使用"获取域名"功能导入域名 |

</div>

#### 彩虹DNS 配置

<div align="center">

| 步骤 | 操作 | 说明 |
|------|------|------|
| **1** | 获取API密钥 | 登录彩虹DNS控制台获取API密钥 |
| **2** | 配置服务器信息 | 填写API基础URL、用户ID、API密钥 |
| **3** | 添加账户 | 后台"管理彩虹账户" → 添加账户 |
| **4** | 导入域名 | 从账户中导入可用域名 |

</div>

## 📊 系统架构

<div align="center">

```
📁 cloudflare-DNS/
├── 📁 admin/                    # 🛠️ 管理后台
│   ├── 📁 includes/            # 后台公共组件
│   ├── 📄 *.php               # 管理功能页面
│   └── 📁 api/                # API接口
├── 📁 user/                     # 👤 用户前台
│   ├── 📁 includes/           # 前台公共组件
│   └── 📄 *.php              # 用户功能页面
├── 📁 config/                  # ⚙️ 配置文件
│   ├── 📄 database.php        # 数据库配置
│   ├── 📄 smtp.php           # 邮件服务
│   ├── 📄 cloudflare.php     # Cloudflare API
│   ├── 📄 rainbow_dns.php    # 彩虹DNS API
│   └── 📄 dnspod.php         # DNSPod API
├── 📁 includes/                # 🔧 公共功能
│   ├── 📄 functions.php      # 通用函数
│   ├── 📄 captcha.php        # 验证码类
│   └── 📄 user_groups.php    # 用户组管理
├── 📁 assets/                 # 🎨 静态资源
│   ├── 📁 css/              # 样式文件
│   ├── 📁 js/               # JavaScript文件
│   └── 📁 images/            # 图片资源
└── 📁 data/                  # 💾 数据目录
    └── 📄 cloudflare_dns.db  # SQLite数据库
```

</div>

### 🏗️ 目录结构说明

<div align="center">

| 目录 | 功能 | 重要文件 |
|------|------|---------|
| **admin/** | 管理后台 | 用户管理、域名管理、系统设置 |
| **user/** | 用户前台 | DNS管理、个人中心、邀请系统 |
| **config/** | 配置文件 | 数据库、邮件、API配置 |
| **includes/** | 公共功能 | 通用函数、验证码、用户组 |
| **assets/** | 静态资源 | CSS样式、JavaScript、图片 |
| **data/** | 数据存储 | SQLite数据库、日志文件 |

</div>

## 🔐 安全特性

<div align="center">

### 🛡️ 多重验证机制

| 安全层 | 防护措施 | 实现方式 | 安全等级 |
|--------|---------|---------|---------|
| **📧 邮箱验证** | 注册、密码重置、邮箱更换 | PHPMailer + SMTP | ⭐⭐⭐⭐⭐ |
| **🖼️ 图形验证码** | 防止自动化攻击 | GD库生成验证码 | ⭐⭐⭐⭐ |
| **🔑 密码强度** | 强制密码复杂度 | 正则表达式验证 | ⭐⭐⭐⭐ |
| **🔒 用户组权限** | 细粒度权限控制 | 数据库权限表 | ⭐⭐⭐⭐⭐ |

### 📝 操作审计系统

| 审计项目 | 记录内容 | 存储方式 | 保留时间 |
|---------|---------|---------|---------|
| **📝 操作日志** | 所有关键操作记录 | SQLite数据库 | 永久保存 |
| **🔍 IP追踪** | 操作来源IP地址 | 数据库记录 | 永久保存 |
| **⏰ 时间戳** | 精确操作时间 | 数据库时间戳 | 永久保存 |
| **👤 用户标识** | 操作用户信息 | 用户ID关联 | 永久保存 |

### 🔐 数据保护机制

| 保护类型 | 实现方式 | 技术细节 | 安全等级 |
|---------|---------|---------|---------|
| **🔐 密码加密** | PHP内置密码哈希 | password_hash() | ⭐⭐⭐⭐⭐ |
| **🛡️ SQL注入防护** | 预处理语句 | PDO/SQLite3 | ⭐⭐⭐⭐⭐ |
| **🚫 XSS防护** | 输出内容转义 | htmlspecialchars() | ⭐⭐⭐⭐ |
| **🔒 文件访问控制** | 伪静态规则 | Nginx/Apache | ⭐⭐⭐⭐ |

</div>

## 🎨 界面预览

<div align="center">

### 🔐 认证界面 (全新设计)

| 页面 | 设计亮点 | 用户体验 |
|------|---------|---------|
| **🔑 登录页面** | 紫色渐变背景 + 圆角卡片 | 简洁优雅，一键登录 |
| **📝 注册页面** | 3步进度指示 + 动画反馈 | 清晰的注册流程引导 |
| **🔓 找回密码** | 图标化步骤 + 成功动画 | 直观的密码重置流程 |

**✨ 界面特色：**
- 🎨 统一的紫色渐变配色 (#667eea → #764ba2)
- 🔄 流畅的过渡动画和悬停效果
- 📱 完美的移动端响应式适配
- 💫 优雅的成功状态脉冲动画
- 🎯 图标化表单标签，提升可读性
- ⚡ 可关闭的提示消息，提升体验

### 👤 用户前台界面

| 界面特色 | 技术实现 | 用户体验 |
|---------|---------|---------|
| **🌙 深色主题** | CSS3 + 毛玻璃效果 | 现代科技风格，护眼舒适 |
| **📱 响应式设计** | Bootstrap 5 + 媒体查询 | 完美适配手机、平板、桌面 |
| **⚡ 快速操作** | jQuery + AJAX | 一键DNS记录管理，实时反馈 |
| **🎨 毛玻璃效果** | backdrop-filter | 现代化视觉层次，科技感十足 |

### 🛠️ 管理后台界面

| 管理功能 | 界面特色 | 操作体验 |
|---------|---------|---------|
| **📊 数据仪表板** | 卡片式布局 + 图表展示 | 直观的数据可视化 |
| **🛠️ 功能管理** | 模块化设计 + 统一风格 | 完整的系统管理功能 |
| **📈 统计分析** | 实时数据 + 趋势分析 | 详细的使用统计和报表 |
| **🔧 系统设置** | 分组配置 + 实时预览 | 便捷的系统参数调整 |

</div>

## 🤝 贡献指南

<div align="center">

### 💡 贡献方式

| 贡献类型 | 描述 | 如何参与 |
|---------|------|---------|
| **🐛 Bug报告** | 发现问题请提交Issue | GitHub Issues |
| **✨ 功能建议** | 新功能想法和改进建议 | GitHub Discussions |
| **📝 文档改进** | 完善项目文档 | Pull Request |
| **💻 代码贡献** | 提交代码改进 | Pull Request |

### 🛠️ 开发环境搭建

```bash
# 1️⃣ Fork 项目到您的GitHub账户
# 2️⃣ 克隆您的Fork
git clone https://github.com/YOUR_USERNAME/cloudflare-DNS.git
cd cloudflare-DNS

# 3️⃣ 创建功能分支
git checkout -b feature/your-feature-name

# 4️⃣ 开发和测试
# 5️⃣ 提交Pull Request
```

### 📋 贡献规范

<div align="center">

| 规范项目 | 要求 | 说明 |
|---------|------|------|
| **代码风格** | PSR-4 标准 | 遵循PHP编码规范 |
| **提交信息** | 清晰描述 | 使用英文描述变更内容 |
| **测试覆盖** | 功能测试 | 确保新功能正常工作 |
| **文档更新** | 同步更新 | 新功能需要更新文档 |

</div>

</div>

## 📞 支持与反馈

<div align="center">

### 🆘 获取帮助

| 帮助方式 | 描述 | 响应时间 | 适用场景 |
|---------|------|---------|---------|
| **📖 项目文档** | 查看Wiki和README | 即时 | 基础配置问题 |
| **💬 QQ交流群** | 实时技术交流 | 1-2小时 | 复杂技术问题 |
| **🐛 GitHub Issues** | 问题报告和追踪 | 1-3天 | Bug报告和功能请求 |
| **📧 邮件支持** | 一对一技术支持 | 1-2天 | 商业技术支持 |

### 📞 联系方式

<div align="center">

| 联系方式 | 链接 | 说明 |
|---------|------|------|
| **🏠 GitHub仓库** | [cloudflare-DNS](https://github.com/976853694/cloudflare-DNS) | 项目主页和代码仓库 |
| **💬 QQ交流群** | [六趣M技术群](https://qm.qq.com/q/qYN7MywxO0) | 实时技术交流和支持 (群号: 1044379774) |
| **🌐 在线演示** | [dns.6qu.cc](https://dns.6qu.cc/) | 功能演示和体验 |
| **📧 邮件反馈** | 通过GitHub Issues | 详细问题描述和截图 |

</div>

</div>

## 📈 项目统计

<div align="center">

[![Stargazers over time](https://starchart.cc/976853694/cloudflare-DNS.svg?variant=adaptive)](https://starchart.cc/976853694/cloudflare-DNS)

</div>

---

## ❓ 常见问题

<div align="center">

### 🔧 配置问题

<details>
<summary><strong>📧 如何配置SMTP邮件发送？</strong></summary>

<div align="left">

**配置步骤：**
1. 登录管理后台 → SMTP设置
2. 填写邮箱服务器信息（服务器、端口、用户名、密码）
3. 选择加密方式（SSL/TLS）
4. 发送测试邮件验证配置
5. 保存设置即可使用

**常见邮箱配置：**
- QQ邮箱：smtp.qq.com:465 (SSL)
- Gmail：smtp.gmail.com:465 (SSL)
- 163邮箱：smtp.163.com:465 (SSL)

</div>
</details>

<details>
<summary><strong>🌐 如何添加Cloudflare域名？</strong></summary>

<div align="left">

**操作步骤：**
1. 登录Cloudflare → My Profile → API Tokens
2. 创建Custom token，权限：Zone:Read, DNS:Edit
3. 后台"管理CF账户" → 添加账户
4. 使用"获取域名"功能导入域名
5. 在用户前台选择域名使用

**注意事项：**
- 确保API Token有足够权限
- 域名必须在Cloudflare账户中
- 检查域名状态是否正常

</div>
</details>

<details>
<summary><strong>📝 如何自定义邮件模板？</strong></summary>

<div align="left">

**编辑步骤：**
1. 进入后台"SMTP设置"
2. 点击"邮件模板"按钮
3. 选择要编辑的模板类型（注册、密码重置等）
4. 修改HTML模板内容
5. 保存模板即可生效

**模板变量：**
- `{$username}` - 用户名
- `{$code}` - 验证码
- `{$change_time}` - 修改时间

</div>
</details>

</div>

## 📄 开源协议

<div align="center">

本项目采用 **非商业许可证**，禁止商业用途。

| 协议条款 | 说明 |
|---------|------|
| **❌ 商业使用** | **禁止**在商业项目中使用 |
| **✅ 修改** | 允许修改源代码 |
| **✅ 分发** | 允许分发和传播 |
| **✅ 私人使用** | 允许私人使用 |
| **✅ 学习研究** | 允许学习和研究用途 |
| **📝 许可证和版权声明** | 必须包含原始许可证和版权声明 |

### ⚠️ 重要声明

**本项目仅供学习和研究使用，禁止任何形式的商业用途！**

- 🚫 **禁止商用**：不得用于任何商业项目
- 🚫 **禁止盈利**：不得通过本项目获取商业利益
- 🚫 **禁止销售**：不得将本项目作为商品销售
- ✅ **允许学习**：可以用于学习和技术研究
- ✅ **允许修改**：可以修改源代码用于学习

</div>

## 🙏 致谢

<div align="center">

### 🛠️ 开源项目

| 项目名称 | 用途 | 链接 |
|---------|------|------|
| **Bootstrap** | 响应式UI框架 | [getbootstrap.com](https://getbootstrap.com/) |
| **PHPMailer** | PHP邮件发送库 | [github.com/PHPMailer](https://github.com/PHPMailer/PHPMailer) |
| **FontAwesome** | 图标字体库 | [fontawesome.com](https://fontawesome.com/) |
| **jQuery** | JavaScript库 | [jquery.com](https://jquery.com/) |

### 💝 特别感谢

感谢所有为这个项目做出贡献的开发者、测试者和用户！

</div>

---

<div align="center">
  <h3>⭐ 如果这个项目对您有帮助，请给我们一个Star支持！</h3>
  <p>Made with ❤️ by 六趣M</p>
  
  <a href="https://github.com/976853694/cloudflare-DNS" target="_blank">
    <img src="https://img.shields.io/badge/⭐-Star%20this%20project-yellow?style=for-the-badge" alt="Star this project">
  </a>
  
  <a href="https://github.com/976853694/cloudflare-DNS/fork" target="_blank">
    <img src="https://img.shields.io/badge/🍴-Fork%20this%20project-blue?style=for-the-badge" alt="Fork this project">
  </a>
</div>