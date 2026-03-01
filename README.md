# DNS 分发系统

基于 Cloudflare API 的二级域名分发系统，支持用户自助注册、域名申请、DNS 解析管理等功能。

**GitHub**: https://github.com/976853694/cloudflare-DNS

**QQ交流群**: https://qm.qq.com/q/nMNgw1CB7q

---

## ⚠️ 版本说明

| 项目 | 说明 |
|------|------|
| 开源版本 | **v2.8**（本仓库最终开源版本） |
| 后续版本 | v2.8 之后的版本**不再开源** |
| 获取新版 | 通过 Docker 镜像更新获取最新版本 |

> 📌 v2.8 为最后一个开源版本，源码可自由使用和修改。后续版本仅以 Docker 镜像形式发布，请通过 Docker 方式更新部署。

---

## 项目介绍

### 功能特性

**用户端**
- 域名购买 — 选择套餐购买二级域名，支持永久/限时套餐
- DNS 解析管理 — 支持 A、AAAA、CNAME、TXT、MX 等记录类型
- 余额系统 — 卡密充值 / 余额支付
- 积分系统 — 签到获取积分，积分兑换余额
- 个人中心 — 账户信息、修改密码、修改邮箱
- 邮箱验证 — 注册、找回密码均支持邮件验证
- 工单系统 — 提交工单与管理员沟通
- 域名转让 — 用户间域名转让
- WHOIS 查询 — 域名信息查询
- 多语言支持 — 中文 / English
- Telegram Bot — 通过 Telegram 管理域名

**管理端**
- 多账户管理 — 支持多个 Cloudflare 账户
- 多 DNS 渠道 — 支持 Cloudflare、阿里云、DNSPod、百度云、华为云、GoDaddy、Name.com、NameSilo、Namecheap、PowerDNS、Route53、西部数码等
- 域名管理 — 添加/管理主域名，关联 DNS 渠道
- 套餐管理 — 为每个域名设置不同价格和时长的套餐
- 用户管理 — 用户列表、状态管理、余额调整
- 卡密管理 — 批量生成、导出、禁用卡密
- 优惠券系统 — 创建和管理优惠券
- 公告系统 — 发布公告，支持置顶和弹窗
- 工单管理 — 处理用户工单
- 邮件营销 — 邮件模板、邮件群发
- IP 黑名单 — 封禁恶意 IP
- 系统设置 — 站点信息、注册开关、SMTP 配置
- 数据统计 — 用户数、域名数、订单数等图表统计
- 定时任务 — 域名到期检查、自动续费、闲置清理
- 数据备份 — 系统数据备份与恢复
- 插件系统 — 支持插件扩展功能

---

### 技术栈

| 类型 | 技术 |
|------|------|
| 后端 | Python 3.9+ / Flask 3.0 / SQLAlchemy |
| 数据库 | MySQL 5.6+ (PyMySQL) |
| 前端 | TailwindCSS / Alpine.js / ECharts |
| 认证 | JWT (Flask-JWT-Extended) |
| DNS | Cloudflare API / 多渠道 DNS 插件 |
| 邮件 | SMTP (SSL/TLS) / 阿里云 DirectMail |
| 短信 | 阿里云短信服务 |
| 定时任务 | APScheduler |
| 生产服务器 | Gunicorn / Waitress |

---

## 源码结构

```
cloudflare-DNS/
├── app/
│   ├── __init__.py              # Flask 应用工厂，数据库迁移
│   ├── models/                  # 数据模型
│   │   ├── user.py              # 用户模型
│   │   ├── domain.py            # 域名模型
│   │   ├── record.py            # DNS 记录模型
│   │   ├── plan.py              # 套餐模型
│   │   ├── coupon.py            # 优惠券模型
│   │   ├── ticket.py            # 工单模型
│   │   ├── announcement.py      # 公告模型
│   │   ├── dns_channel.py       # DNS 渠道模型
│   │   ├── email_campaign.py    # 邮件营销模型
│   │   ├── point_record.py      # 积分记录模型
│   │   └── ...                  # 其他模型
│   ├── routes/                  # 路由（API + 页面）
│   │   ├── auth.py              # 认证（登录/注册/找回密码）
│   │   ├── domain.py            # 域名操作
│   │   ├── record.py            # DNS 记录操作
│   │   ├── ticket.py            # 工单
│   │   ├── points.py            # 积分
│   │   ├── transfer.py          # 域名转让
│   │   ├── whois.py             # WHOIS 查询
│   │   ├── open_api.py          # 开放 API
│   │   ├── health.py            # 健康检查
│   │   └── admin/               # 管理后台路由
│   │       ├── users.py         # 用户管理
│   │       ├── domains.py       # 域名管理
│   │       ├── plans.py         # 套餐管理
│   │       ├── channels.py      # DNS 渠道管理
│   │       ├── coupons.py       # 优惠券管理
│   │       ├── stats.py         # 数据统计
│   │       ├── settings.py      # 系统设置
│   │       └── ...              # 其他管理路由
│   ├── services/                # 业务逻辑层
│   │   ├── cloudflare.py        # Cloudflare API 封装
│   │   ├── domain_service.py    # 域名业务逻辑
│   │   ├── plan_service.py      # 套餐服务
│   │   ├── points_service.py    # 积分服务
│   │   ├── email.py             # 邮件发送
│   │   ├── sms.py               # 短信发送
│   │   ├── scheduler.py         # 定时任务调度
│   │   ├── dns/                 # 多渠道 DNS 服务
│   │   │   ├── base.py          # DNS 服务基类
│   │   │   ├── factory.py       # DNS 服务工厂
│   │   │   ├── cloudflare.py    # Cloudflare
│   │   │   ├── aliyun.py        # 阿里云 DNS
│   │   │   ├── dnspod.py        # DNSPod
│   │   │   └── ...              # 其他 DNS 提供商
│   │   └── telegram/            # Telegram Bot
│   │       ├── service.py       # Bot 主服务
│   │       ├── handlers/        # 命令处理器
│   │       ├── keyboards/       # 键盘布局
│   │       ├── messages/        # 多语言消息
│   │       └── notifications/   # 通知发送
│   └── templates/               # Jinja2 HTML 模板
│       ├── base.html            # 基础布局
│       ├── login.html           # 登录页
│       ├── register.html        # 注册页
│       ├── user/                # 用户端页面
│       ├── admin/               # 管理端页面
│       ├── host/                # 主机相关页面
│       └── email/               # 邮件模板
├── static/                      # 静态资源（全部本地化）
│   ├── css/                     # 样式文件
│   │   ├── tailwind.min.css     # TailwindCSS
│   │   ├── style.css            # 自定义样式
│   │   └── slider-captcha.css   # 滑块验证码样式
│   ├── js/                      # JavaScript
│   │   ├── alpine.min.js        # Alpine.js
│   │   ├── echarts.min.js       # ECharts 图表
│   │   ├── app.js               # 应用主逻辑
│   │   ├── i18n.js              # 国际化
│   │   ├── utils.js             # 工具函数
│   │   └── sortable.min.js      # 拖拽排序
│   └── locales/                 # 语言包
│       ├── zh.json              # 中文
│       └── en.json              # English
├── plugins/                     # 插件目录（可扩展）
├── scripts/                     # 脚本工具
│   └── backup.py                # 数据备份脚本
├── config.py                    # 应用配置
├── run.py                       # 应用入口
├── requirements.txt             # Python 依赖
├── docker-compose.yml           # Docker 部署配置
└── .env                         # 环境变量配置
```

---

## 部署方式

### 方式一：Docker 部署（推荐）

适用于所有版本，包括 v2.8 之后的闭源版本。

#### 1. 环境要求

- Linux 服务器（推荐 Ubuntu 20.04+/CentOS 7+）
- Docker 20.10+
- Docker Compose v2+
- MySQL 5.6+（需自行安装或使用云数据库）

#### 2. 安装 Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# 验证安装
docker --version
docker compose version
```

#### 3. 创建项目目录

```bash
mkdir -p /opt/dns && cd /opt/dns
```

#### 4. 创建环境配置文件

```bash
cat > .env << 'EOF'
# Flask 配置
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=请替换为随机字符串

# 数据库配置
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=dns_system
DB_USER=root
DB_PASSWORD=你的数据库密码

# JWT 配置
JWT_SECRET_KEY=请替换为随机字符串
JWT_ACCESS_TOKEN_EXPIRES=86400

# 应用配置
APP_NAME=DNS分发系统
APP_URL=https://你的域名
DEFAULT_MAX_DOMAINS=5

# 后台任务
BACKGROUND_TASK_WORKERS=2
BACKGROUND_TASK_MAX_QUEUE=100

# 备份保留天数
BACKUP_RETENTION_DAYS=7
EOF
```

> ⚠️ 请务必修改 `SECRET_KEY`、`JWT_SECRET_KEY` 为随机字符串，修改数据库相关配置为实际值。

#### 5. 创建 docker-compose.yml

```yaml
version: "3.8"

services:
  app:
    image: 167729539/dns:latest
    container_name: dns-app
    restart: unless-stopped
    network_mode: host
    
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
        reservations:
          memory: 256M
    
    volumes:
      - ./plugins:/opt/dns/plugins      # 插件目录
      - ./logs:/opt/dns/logs            # 日志目录
      - ./backups:/opt/dns/backups      # 备份目录
      - ./.env:/opt/dns/.env:ro         # 配置文件（只读）
    
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:5000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

#### 6. 启动服务

```bash
docker compose up -d
```

#### 7. 查看运行状态

```bash
# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f
```

#### 8. 更新到最新版本

```bash
docker compose pull && docker compose down && docker compose up -d
```

---

### 方式二：源码部署（仅限 v2.8 开源版本）

适用于需要二次开发或自定义修改的场景。

#### 1. 环境要求

- Python 3.9+
- MySQL 5.6+
- Git

#### 2. 克隆代码

```bash
git clone https://github.com/976853694/cloudflare-DNS.git
cd cloudflare-DNS
```

#### 3. 安装 Python 依赖

```bash
# 建议使用虚拟环境
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

#### 4. 配置数据库

```sql
-- 登录 MySQL 创建数据库
CREATE DATABASE dns_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### 5. 配置环境变量

编辑项目根目录下的 `.env` 文件，参考上方 Docker 部署中的配置说明，修改数据库连接等信息。

#### 6. 启动应用

```bash
# 开发模式
python run.py

# 生产模式（使用 Gunicorn）
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

---

## 访问系统

启动后通过浏览器访问：

```
http://服务器IP:5000
```

默认管理员账号：
- 用户名：`admin@qq.com`
- 密码：`admin123`

> ⚠️ 首次登录后请立即修改密码！

---

## 反向代理配置（可选）

推荐使用 Nginx 反向代理并配置 SSL：

```nginx
server {
    listen 80;
    server_name 你的域名;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name 你的域名;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 支持的 DNS 渠道

| 渠道 | 说明 |
|------|------|
| Cloudflare | 默认支持，通过 API Token 或 Global API Key |
| 阿里云 DNS | 阿里云域名解析 |
| DNSPod | 腾讯云 DNSPod |
| 百度云 DNS | 百度智能云域名解析 |
| 华为云 DNS | 华为云域名解析 |
| GoDaddy | GoDaddy 域名 DNS |
| Name.com | Name.com DNS |
| NameSilo | NameSilo DNS |
| Namecheap | Namecheap DNS |
| PowerDNS | 自建 PowerDNS |
| Route53 | AWS Route53 |
| 西部数码 | 西部数码 DNS |

> DNS 渠道通过插件机制实现，可在管理后台「渠道管理」中配置。

---

## 常见问题

**Q: 如何生成随机密钥？**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Q: 容器启动失败怎么办？**
```bash
# 查看详细日志
docker compose logs -f

# 常见原因：数据库连接失败，请检查 .env 中的数据库配置
```

**Q: 如何备份数据？**
```bash
# 数据库备份
mysqldump -u root -p dns_system > backup.sql

# Docker 挂载目录中的 backups/ 也会保存系统自动备份
```

**Q: 忘记管理员密码？**

直接在数据库中重置，或使用系统的找回密码功能（需配置 SMTP 邮件）。

---

## 版权与授权声明

**© 本系统已申请专利，受知识产权法律保护。**

### v2.8 开源版本授权

- ✅ 允许个人学习、研究、测试使用
- ❌ **禁止任何形式的商业用途**（包括但不限于出售、付费服务等）
- ❌ 禁止去除或修改版权标识
- ❌ 禁止以任何形式声称为自有产品

### 后续版本

v2.8 之后的版本不再开源，仅通过 Docker 镜像分发。

> ⚠️ 违反授权条款的行为将依法追究法律责任。
