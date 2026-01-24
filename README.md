# DNS分发系统 - Linux 部署教程

基于 Cloudflare API 的二级域名分发系统，支持用户自助注册、域名申请、DNS解析管理等功能。

**GitHub**: https://github.com/976853694/cloudflare-DNS

**QQ交流群**: https://qm.qq.com/q/nMNgw1CB7q
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
- 在服务器创建docker-compose.yml


```bash
# DNS 分发系统 Docker 部署配置
# 使用方法: docker-compose up -d
# 停止服务: docker-compose down
# 查看日志: docker-compose logs -f

version: "3.8"

services:
  app:
    image: 167729539/dns:latest
    container_name: dns-app
    restart: unless-stopped
    ports:
      - "5000:5000"                       # Web 服务端口
    
    # 资源限制
    deploy:
      resources:
        limits:
          memory: 512M                    # 最大内存
          cpus: '1.0'                     # CPU 限制
        reservations:
          memory: 256M                    # 最小保留内存
    
    # 环境变量配置
    environment:
      # Flask 应用配置
      FLASK_ENV: production
      SECRET_KEY: change-me-in-production      # ⚠️ 生产环境必须修改
      JWT_SECRET_KEY: change-me-in-production  # ⚠️ 生产环境必须修改
      TZ: Asia/Shanghai                        # 时区设置
      
      # 数据库连接配置（连接宿主机或远程 MySQL）
      DB_HOST: host.docker.internal            # 宿主机 MySQL
      DB_PORT: "3306"
      DB_NAME: dns
      DB_USER: dns
      DB_PASSWORD: dns
      
      # 后台任务配置
      BACKGROUND_TASK_WORKERS: "2"             # 后台任务工作线程数
      BACKGROUND_TASK_MAX_QUEUE: "100"         # 任务队列最大长度
    
    # 宿主机网络映射
    extra_hosts:
      - "host.docker.internal:host-gateway"
    
    # 健康检查
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:5000/ || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    
    # 日志配置
    logging:
      driver: "json-file"
      options:
        max-size: "10m"                        # 单个日志文件最大 10MB
        max-file: "3"                          # 保留最近 3 个日志文件
    
    # 网络配置
    networks:
      - dns-network

# 网络定义
networks:
  dns-network:
    driver: bridge
```

# 更新命令
```
docker compose pull && docker compose down && docker compose up -d
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
