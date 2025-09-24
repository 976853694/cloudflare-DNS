# 六趣DNS - Cloudflare DNS管理系统

<div align="center">
  <img src="https://img.shields.io/badge/PHP-7.4+-blue.svg" alt="PHP Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Database-SQLite3-orange.svg" alt="Database">
  <img src="https://img.shields.io/badge/Framework-Bootstrap%205-purple.svg" alt="Frontend">
</div>



##  演示地址
https://dns.6qu.cc/

##交流群
点击链接加入群聊【六趣M】：https://qm.qq.com/q/qYN7MywxO0

##  伪静态
#  请注意伪静态必须添加
```bash
location ~* \.(db|sqlite|sql|bak|backup|log)$ {                                                 
  return 301 /;                
}
```

## 📖 项目简介

六趣DNS是一个基于PHP开发的现代化Cloudflare DNS管理系统，为用户提供简洁、高效的DNS记录管理体验。系统支持多DNS提供商（Cloudflare、彩虹DNS），具备完善的用户管理、积分系统和邮件验证功能。

### ✨ 核心特性

- 🌐 **多DNS提供商支持** - 同时支持Cloudflare和彩虹DNS
- 👥 **用户权限管理** - 完整的用户注册、登录、权限控制
- 💰 **积分系统** - 灵活的积分消耗和充值机制
- 📧 **邮件验证** - 完整的邮箱验证码系统
- 🎨 **现代化界面** - 响应式设计，深色科技风格
- 🔒 **安全防护** - 多重验证，操作日志，安全防护

## 🚀 功能特色

### 用户功能
- ✅ **DNS记录管理** - 支持A、AAAA、CNAME、TXT、MX等记录类型
- ✅ **实时前缀查询** - 检查子域名可用性
- ✅ **批量DNS同步** - 从Cloudflare导入现有记录
- ✅ **邮箱验证系统** - 注册、密码重置、邮箱更换验证
- ✅ **积分充值** - 卡密充值系统
- ✅ **邀请奖励** - 邀请新用户获得积分奖励

### 管理功能
- 🛠️ **用户管理** - 用户账户管理、积分调整
- 🌐 **域名管理** - 多渠道域名添加和管理
- 🔧 **系统设置** - SMTP配置、系统参数调整
- 📧 **邮件模板** - 自定义邮件模板编辑
- 📊 **操作日志** - 完整的操作审计记录
- 🎫 **卡密管理** - 充值卡密生成和管理

## 🛠️ 技术栈

### 后端技术
- **PHP 7.4+** - 服务端开发语言
- **SQLite3** - 轻量级数据库
- **PHPMailer** - 邮件发送组件

### 前端技术
- **Bootstrap 5** - 响应式UI框架
- **jQuery** - JavaScript库
- **FontAwesome** - 图标字体

### 系统架构
- **MVC模式** - 清晰的代码结构
- **模块化设计** - 功能模块独立
- **API封装** - 统一的DNS服务接口

## 📦 安装部署

### 环境要求

```bash
PHP >= 7.4
SQLite3 扩展
cURL 扩展
OpenSSL 扩展
Web服务器 (Apache/Nginx)
```

### 快速安装

1. **克隆项目**
```bash
git clone https://github.com/976853694/cloudflare-DNS.git
cd cloudflare-DNS
```

2. **配置Web服务器**
```bash
# 将项目目录设置为Web根目录
# 确保data目录有写入权限
chmod 755 data/
chmod 666 data/cloudflare_dns.db
```

3. **访问安装页面**
```
http://your-domain.com/install.php
```

4. **完成安装**
- 按照安装向导完成数据库初始化
- 创建管理员账户
- 配置基本系统参数


## 🔧 配置说明

### SMTP邮件配置

访问管理后台的"SMTP设置"页面配置邮件服务：

```php
// 支持的SMTP服务商
QQ邮箱: smtp.qq.com:465 (SSL)
Gmail: smtp.gmail.com:465 (SSL)  
163邮箱: smtp.163.com:465 (SSL)
```

### DNS提供商配置

#### Cloudflare配置
1. 获取Cloudflare  Token
2. 在后台"管理CF账户"中添加账户
3. 从账户中导入域名

#### 彩虹DNS配置
1. 获取彩虹DNS API密钥
2. 在后台"管理彩虹账户"中添加账户
3. 从账户中导入域名

## 📊 系统架构

```
cloudflare-DNS/
├── admin/                 # 管理后台
│   ├── includes/         # 后台公共组件
│   ├── *.php            # 管理功能页面
├── user/                 # 用户前台
│   ├── includes/        # 前台公共组件
│   ├── *.php           # 用户功能页面
├── config/              # 配置文件
│   ├── database.php    # 数据库配置
│   ├── smtp.php        # 邮件服务
│   └── *.php          # 其他配置
├── includes/           # 公共功能
│   ├── functions.php   # 通用函数
│   └── captcha.php    # 验证码类
├── assets/            # 静态资源
│   ├── css/          # 样式文件
│   ├── js/           # JavaScript文件
│   └── images/       # 图片资源
└── data/             # 数据目录
    └── cloudflare_dns.db  # SQLite数据库
```

## 🔐 安全特性

### 多重验证
- 📧 **邮箱验证** - 注册、密码重置、邮箱更换
- 🖼️ **图形验证码** - 防止自动化攻击
- 🔑 **密码强度** - 强制密码复杂度要求

### 操作审计
- 📝 **操作日志** - 记录所有关键操作
- 🔍 **IP追踪** - 记录操作来源IP
- ⏰ **时间戳** - 精确的操作时间记录

### 数据保护
- 🔐 **密码加密** - 使用PHP内置密码哈希
- 🛡️ **SQL注入防护** - 预处理语句防护
- 🚫 **XSS防护** - 输出内容转义处理

## 🎨 界面预览

### 用户前台
- 🌙 **深色主题** - 现代科技风格界面
- 📱 **响应式设计** - 完美适配移动设备
- ⚡ **快速操作** - 一键DNS记录管理

### 管理后台
- 📊 **数据仪表板** - 直观的数据展示
- 🛠️ **功能管理** - 完整的系统管理功能
- 📈 **统计分析** - 详细的使用统计

## 🤝 贡献指南

我们欢迎所有形式的贡献，包括但不限于：

- 🐛 **Bug报告** - 发现问题请提交Issue
- ✨ **功能建议** - 新功能想法和改进建议
- 📝 **文档改进** - 完善项目文档
- 💻 **代码贡献** - 提交Pull Request

### 开发环境搭建

```bash
# 1. Fork 项目到您的GitHub账户
# 2. 克隆您的Fork
git clone https://github.com/YOUR_USERNAME/cloudflare-DNS.git

# 3. 创建功能分支
git checkout -b feature/your-feature-name

# 4. 开发和测试
# 5. 提交Pull Request
```

## 📞 支持与反馈

### 获取帮助
- 📖 **文档**: 查看项目Wiki和文档
- 💬 **社区**: 加入QQ群与其他用户交流
- 🐛 **问题报告**: 在GitHub Issues提交问题

### 联系方式
- **GitHub仓库**: [https://github.com/976853694/cloudflare-DNS](https://github.com/976853694/cloudflare-DNS)
- **QQ反馈群**: [点击加入群聊【六趣M】](https://qm.qq.com/q/k6ReSZLpu0)

## Stargazers over time
[![Stargazers over time](https://starchart.cc/976853694/cloudflare-DNS.svg?variant=adaptive)](https://starchart.cc/976853694/cloudflare-DNS)


### 常见问题

<details>
<summary>如何配置SMTP邮件发送？</summary>

1. 登录管理后台
2. 进入"SMTP设置"页面
3. 填写邮箱服务器信息
4. 发送测试邮件验证配置
</details>

<details>
<summary>如何添加Cloudflare域名？</summary>

1. 在Cloudflare获取API Token
2. 后台"管理CF账户"添加账户
3. 使用"获取域名"功能导入域名
4. 在用户前台选择域名使用
</details>

<details>
<summary>如何自定义邮件模板？</summary>

1. 进入后台"SMTP设置"
2. 点击"邮件模板"按钮
3. 选择要编辑的模板类型
4. 修改HTML模板内容
5. 保存模板即可生效
</details>

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

```
MIT License

Copyright (c) 2024 六趣DNS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

## 🙏 致谢

感谢以下开源项目和服务：

- [Bootstrap](https://getbootstrap.com/) - 响应式UI框架
- [PHPMailer](https://github.com/PHPMailer/PHPMailer) - PHP邮件发送库
- [FontAwesome](https://fontawesome.com/) - 图标字体库
- [jQuery](https://jquery.com/) - JavaScript库

---


<div align="center">
  <p>⭐ 如果这个项目对您有帮助，请给我们一个Star支持！</p>
  <p>Made with ❤️ by 六趣M</p>
</div>