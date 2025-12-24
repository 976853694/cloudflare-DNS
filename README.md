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
## 部署说明
- 目前使用docker-compose部署
- docker-compose有2种
- 在服务器创建docker-compose.yml
- 第一种内置数据库

```bash
# DNS 分发系统 Docker 部署配置
# 使用方法: docker-compose up -d
# 停止服务: docker-compose down
# 查看日志: docker-compose logs -f

version: "3.8"

services:
  # MySQL 数据库
  db:
    image: mysql:8.0
    container_name: dns-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: root123       # root 密码
      MYSQL_DATABASE: dns                # 自动创建数据库
      MYSQL_USER: dns                    # 创建用户
      MYSQL_PASSWORD: dns                # 用户密码
    volumes:
      - mysql_data:/var/lib/mysql        # 数据持久化
    #ports:
    #  - "3306:3306"                       # 可选：暴露端口供外部访问
    command: --default-authentication-plugin=mysql_native_password

  # DNS 应用
  app:
    image: 167729539/dns:latest
    container_name: dns-app
    restart: unless-stopped
    depends_on:
      - db                               # 等待数据库启动
    ports:
      - "5000:5000"                       # Web 服务端口
    environment:
      # Flask 配置
      FLASK_ENV: production
      SECRET_KEY: change-me-in-production      # 生产环境请修改
      JWT_SECRET_KEY: change-me-in-production  # 生产环境请修改
      # 数据库配置 (连接 Docker MySQL)
      DB_HOST: db                        # Docker 服务名
      DB_PORT: "3306"                    # MySQL 端口
      DB_NAME: dns                       # 数据库名称
      DB_USER: dns                       # 数据库用户名
      DB_PASSWORD: dns                   # 数据库密码

volumes:
  mysql_data:                            # 数据卷，防止数据丢失

```
- 第二种使用外置数据库
```bash
version: "3.8"

services:
  app:
    image: 167729539/dns:latest
    container_name: dns-app
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      FLASK_ENV: production
      SECRET_KEY: change-me-in-production       # 生产环境请修改
      JWT_SECRET_KEY: change-me-in-production   # 生产环境请修改
      DB_HOST: host.docker.internal      # MySQL ip     按需修改
      DB_PORT: "3306"                    # MySQL 端口
      DB_NAME: dns                       # 数据库名称    按需修改
      DB_USER: dns                       # 数据库用户名  按需修改
      DB_PASSWORD: dns                   # 数据库密码    按需修改
    extra_hosts:
      - "host.docker.internal:host-gateway"

```

## 访问系统

启动后，通过浏览器访问：

```
http://服务器IP:5000
```

默认管理员账号：
- 用户名：`admin@qq.com`
- 密码：`admin123`

> ⚠️ 首次登录后请立即修改密码！
