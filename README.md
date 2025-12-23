# DNS分发系统 - Linux 部署教程

基于 Cloudflare API 的二级域名分发系统，支持用户自助注册、域名申请、DNS解析管理等功能。

**GitHub**: https://github.com/976853694/cloudflare-DNS

---

## 项目介绍

### 功能特性

**用户端**
- 域名购买 - 选择套餐购买二级域名，支持永久/限时套餐
- DNS解析管理 - 支持 A、AAAA、CNAME、TXT、MX 等记录类型
- 余额系统 - 卡密充值，余额支付
- 个人中心 - 账户信息、修改密码、修改邮箱
- 邮箱验证 - 注册、找回密码均支持邮件验证

**管理端**
- 多账户管理 - 支持多个 Cloudflare 账户
- 域名管理 - 添加/管理主域名，关联 CF 账户
- 套餐管理 - 为每个域名设置不同价格和时长的套餐
- 用户管理 - 用户列表、状态管理、余额调整
- 卡密管理 - 批量生成、导出、禁用卡密
- 公告系统 - 发布公告，支持置顶和弹窗
- 系统设置 - 站点信息、注册开关、SMTP 邮件配置
- 数据统计 - 用户数、域名数、订单数等

### 技术栈

| 类型 | 技术 |
|------|------|
| 后端 | Python 3.9+ / Flask / SQLAlchemy |
| 数据库 | MySQL 8.0+ |
| 前端 | TailwindCSS / Alpine.js |
| 认证 | JWT (Flask-JWT-Extended) |
| DNS | Cloudflare API |
| 邮件 | SMTP (SSL/TLS) |

---

## 第一步：配置数据库

将程序上传到服务器后，在程序目录下创建 `.env` 配置文件：

```bash
nano .env
```

填入以下内容（根据实际情况修改）：

```ini
# 数据库配置
# 数据库地址
DB_HOST=localhost
# 端口
DB_PORT=3306
# 数据库名称
DB_NAME=dns
# 数据库用户名
DB_USER=dns
# 数据库密码
DB_PASSWORD=dns
```

保存并退出（Ctrl+X，然后按 Y 确认）。

---

## 第二步：启动程序

在终端执行以下命令，后台运行程序：

```bash
./dns > app.log 2>&1 &
```

### 命令说明

| 部分 | 说明 |
|------|------|
| `./dns` | 运行程序 |
| `> app.log` | 将输出重定向到 app.log 文件 |
| `2>&1` | 将错误输出也写入日志 |
| `&` | 后台运行 |

---

## 常用命令

### 查看日志

```bash
tail -f app.log
```

### 查看进程

```bash
ps aux | grep ./dns
```

### 停止程序

```bash
pkill -f ./dns
```

### 重启程序

```bash
pkill -f ./dns
./dns > app.log 2>&1 &
```

---

## 访问系统

启动后，通过浏览器访问：

```
http://服务器IP:5000
```

默认管理员账号：
- 用户名：`admin@qq.com`
- 密码：`admin123`

> ⚠️ 首次登录后请立即修改密码！
