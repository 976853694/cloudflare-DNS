# 用户端 API 接口文档

## 概述

- **Base URL**: `/api`
- **认证方式**: JWT Bearer Token
- **响应格式**: JSON

## 通用响应格式

### 成功响应
```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 错误响应
```json
{
  "code": 400,
  "message": "错误描述"
}
```

---

## 认证模块 `/api/auth`

### 获取图形验证码

**GET** `/api/auth/captcha`

> 登录连续失败3次后需要验证码

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 否 | 验证码ID，用于刷新 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "captcha_id": "abc123",
    "captcha_image": "data:image/png;base64,..."
  }
}
```

---

### 检查登录是否需要验证码

**GET** `/api/auth/login/captcha-status`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 用户邮箱 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "need_captcha": false
  }
}
```

---

### 发送注册验证邮件

**POST** `/api/auth/register/send`

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 邮箱地址 |

#### 响应示例
```json
{
  "code": 200,
  "message": "验证邮件已发送，请查收"
}
```

---

### 完成注册

**POST** `/api/auth/register/complete`

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | 是 | 邮件中的验证token |
| username | string | 是 | 用户名(3-20字符) |
| password | string | 是 | 密码(6-32字符) |

#### 响应示例
```json
{
  "code": 201,
  "message": "注册成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": 1,
      "username": "testuser",
      "email": "test@example.com"
    }
  }
}
```

---

### 传统注册（SMTP未配置时）

**POST** `/api/auth/register`

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名(3-20字符) |
| email | string | 是 | 邮箱地址 |
| password | string | 是 | 密码(6-32字符) |

---

### 用户登录

**POST** `/api/auth/login`

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 邮箱地址 |
| password | string | 是 | 密码 |
| captcha_id | string | 否 | 验证码ID（需要验证码时） |
| captcha_code | string | 否 | 验证码（需要验证码时） |

#### 响应示例
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "user": {
      "id": 1,
      "username": "testuser",
      "email": "test@example.com",
      "role": "user",
      "balance": 100.00,
      "balance_text": "¥100.00"
    }
  }
}
```

---

### 获取当前用户信息

**GET** `/api/auth/me`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "role": "user",
    "status": 1,
    "balance": 100.00,
    "balance_text": "¥100.00",
    "max_domains": 5,
    "used_domains": 2,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

### 发送修改密码验证邮件

**POST** `/api/auth/change-password/send`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "message": "验证邮件已发送"
}
```

---

### 通过邮件验证修改密码

**POST** `/api/auth/change-password/confirm`

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | 是 | 邮件中的验证token |
| password | string | 是 | 新密码 |

---

### 忘记密码

**POST** `/api/auth/forgot-password`

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 注册邮箱 |

---

### 重置密码

**POST** `/api/auth/reset-password`

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | 是 | 邮件中的验证token |
| password | string | 是 | 新密码 |

---

### 传统修改密码

**PUT** `/api/auth/password`

> 验证旧密码后修改新密码

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| old_password | string | 是 | 旧密码 |
| new_password | string | 是 | 新密码 |

---

### 发送修改邮箱验证邮件

**POST** `/api/auth/change-email/send`

> 发送验证邮件到当前邮箱，验证身份后可输入新邮箱

#### 请求头
```
Authorization: Bearer <access_token>
```

---

### 验证并设置新邮箱

**POST** `/api/auth/change-email/verify`

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | 是 | 邮件中的验证token |
| new_email | string | 是 | 新邮箱地址 |

---

### 检查修改邮箱验证链接

**GET** `/api/auth/change-email/check`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | 是 | 验证token |

---

### 检查SMTP状态

**GET** `/api/auth/smtp-status`

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "configured": true
  }
}
```

---

### 验证Token有效性

**GET** `/api/auth/verify`

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | 是 | 验证token |
| type | string | 否 | 验证类型 |

#### 响应示例
```json
{
  "code": 200,
  "message": "验证链接有效",
  "data": {
    "email": "test@example.com",
    "type": "register"
  }
}
```

---

## 域名模块 `/api`

### 获取可用主域名列表

**GET** `/api/domains`

> 无需认证

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "domains": [
      {
        "id": 1,
        "name": "example.com",
        "allow_register": true,
        "subdomains_count": 150
      }
    ]
  }
}
```

---

### 获取域名下的套餐

**GET** `/api/domains/{domain_id}/plans`

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "plans": [
      {
        "id": 1,
        "name": "免费套餐",
        "price": 0,
        "duration_days": 30,
        "duration_text": "30天",
        "min_length": 5,
        "max_length": 20,
        "max_records": 5,
        "max_records_text": "5条"
      },
      {
        "id": 2,
        "name": "永久套餐",
        "price": 10.00,
        "duration_days": -1,
        "duration_text": "永久",
        "min_length": 3,
        "max_length": 30,
        "max_records": -1,
        "max_records_text": "无限"
      }
    ]
  }
}
```

---

### 获取用户的二级域名列表

**GET** `/api/subdomains`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认1 |
| per_page | int | 否 | 每页数量，默认10 |
| domain_id | int | 否 | 按主域名ID筛选 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "subdomains": [
      {
        "id": 1,
        "name": "mysite",
        "full_name": "mysite.example.com",
        "domain": {
          "id": 1,
          "name": "example.com"
        },
        "plan": {
          "id": 1,
          "name": "免费套餐"
        },
        "status": 1,
        "records_count": 3,
        "is_expired": false,
        "days_remaining": 25,
        "created_at": "2024-01-01T00:00:00Z",
        "expires_at": "2024-02-01T00:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 10,
      "total": 1,
      "pages": 1
    }
  }
}
```

---

### 购买域名

**POST** `/api/purchase`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| plan_id | int | 是 | 套餐ID |
| name | string | 是 | 二级域名前缀 |

#### 响应示例
```json
{
  "code": 200,
  "message": "购买成功",
  "data": {
    "subdomain": {
      "id": 1,
      "name": "mysite",
      "full_name": "mysite.example.com",
      "expires_at": "2024-02-01T00:00:00Z"
    },
    "plan": {
      "id": 1,
      "name": "月度套餐"
    },
    "balance": 90.00,
    "balance_text": "¥90.00"
  }
}
```

---

### 续费域名

**POST** `/api/subdomains/{subdomain_id}/renew`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| plan_id | int | 是 | 续费套餐ID |

#### 响应示例
```json
{
  "code": 200,
  "message": "续费成功",
  "data": {
    "subdomain": {
      "id": 1,
      "full_name": "mysite.example.com"
    },
    "expires_at": "2024-03-01T00:00:00Z",
    "balance": 85.00,
    "balance_text": "¥85.00"
  }
}
```

---

### 获取续费套餐

**GET** `/api/subdomains/{subdomain_id}/renew-plans`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "plans": [
      {
        "id": 2,
        "name": "月度套餐",
        "price": 5.00,
        "duration_days": 30,
        "duration_text": "30天"
      }
    ],
    "subdomain": {
      "id": 1,
      "full_name": "mysite.example.com"
    }
  }
}
```

---

### 删除二级域名

**DELETE** `/api/subdomains/{subdomain_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

## 卡密模块 `/api`

### 验证卡密

**POST** `/api/redeem/verify`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 卡密码 |

#### 响应示例
```json
{
  "code": 200,
  "message": "卡密有效",
  "data": {
    "amount": 10.00,
    "amount_text": "¥10.00"
  }
}
```

---

### 使用卡密充值

**POST** `/api/redeem`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 卡密码 |

#### 响应示例
```json
{
  "code": 200,
  "message": "充值成功，到账 ¥10.00",
  "data": {
    "amount": 10.00,
    "balance": 110.00,
    "balance_text": "¥110.00"
  }
}
```

---

## DNS记录模块 `/api`

### 获取二级域名详情

**GET** `/api/subdomains/{subdomain_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "subdomain": {
      "id": 1,
      "name": "mysite",
      "full_name": "mysite.example.com",
      "status": 1,
      "expires_at": "2024-02-01T00:00:00Z",
      "records": [...]
    }
  }
}
```

---

### 获取DNS记录

**GET** `/api/subdomains/{subdomain_id}/records`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "records": [
      {
        "id": "cf_record_id",
        "type": "A",
        "name": "@",
        "content": "1.2.3.4",
        "ttl": 1,
        "proxied": true
      }
    ]
  }
}
```

---

### 添加DNS记录

**POST** `/api/subdomains/{subdomain_id}/records`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 记录类型(A/AAAA/CNAME/TXT/MX) |
| name | string | 否 | 名称前缀，默认@ |
| content | string | 是 | 记录值 |
| ttl | int | 否 | TTL，默认1(自动) |
| proxied | bool | 否 | 是否开启代理，默认false |
| priority | int | 否 | 优先级(MX记录) |

---

### 更新DNS记录

**PUT** `/api/records/{record_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 否 | 记录值 |
| ttl | int | 否 | TTL值 |
| proxied | bool | 否 | 是否代理 |

---

### 删除DNS记录

**DELETE** `/api/records/{record_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

## 购买记录模块 `/api`

### 获取购买记录

**GET** `/api/purchase-records`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认1 |
| per_page | int | 否 | 每页数量，默认20 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "records": [
      {
        "id": 1,
        "subdomain_name": "mysite.example.com",
        "plan_name": "月度套餐",
        "price": 5.00,
        "price_text": "¥5.00",
        "duration_days": 30,
        "duration_text": "30天",
        "type": "renew",
        "created_at": "2024-01-15T10:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 1,
      "pages": 1
    }
  }
}
```

---

## 公告模块 `/api`

### 获取公告列表

**GET** `/api/announcements`

> 可选认证，登录后可获取已读状态

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "announcements": [
      {
        "id": 1,
        "title": "系统公告",
        "content": "公告内容...",
        "type": "info",
        "is_pinned": true,
        "is_popup": false,
        "is_read": false,
        "created_at": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

---

### 获取未读公告

**GET** `/api/announcements/unread`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "unread_count": 2,
    "popup_announcements": [...],
    "announcements": [...]
  }
}
```

---

### 标记公告已读

**POST** `/api/announcements/{id}/read`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

## 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未授权/Token无效 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 500 | 服务器错误 |

## DNS记录类型说明

| 类型 | 说明 | content示例 |
|------|------|-------------|
| A | IPv4地址 | 1.2.3.4 |
| AAAA | IPv6地址 | 2001:db8::1 |
| CNAME | 别名记录 | example.com |
| TXT | 文本记录 | v=spf1 include:example.com |
| MX | 邮件记录 | mail.example.com |
