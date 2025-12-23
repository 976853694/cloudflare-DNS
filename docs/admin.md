# 管理端 API 接口文档

## 概述

- **Base URL**: `/api/admin`
- **认证方式**: JWT Bearer Token
- **权限要求**: 管理员角色 (role = admin)
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
  "code": 403,
  "message": "权限不足"
}
```

---

## 统计模块

### 获取系统统计

**GET** `/api/admin/stats`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "users_count": 100,
    "domains_count": 5,
    "subdomains_count": 500,
    "records_count": 1500,
    "today_new_users": 10,
    "today_new_subdomains": 25,
    "today_logins": 50,
    "redeem_codes_total": 200,
    "redeem_codes_unused": 150,
    "redeem_codes_used": 50,
    "plans_count": 10,
    "cf_accounts_count": 2,
    "expiring_soon": 5
  }
}
```

---

## 用户管理模块

### 获取用户列表

**GET** `/api/admin/users`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认1 |
| per_page | int | 否 | 每页数量，默认20 |
| search | string | 否 | 搜索关键词(用户名/邮箱) |
| status | int | 否 | 用户状态筛选 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "users": [
      {
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
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

---

### 获取用户详情

**GET** `/api/admin/users/{user_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "user": {
      "id": 1,
      "username": "testuser",
      "email": "test@example.com",
      "role": "user",
      "status": 1,
      "balance": 100.00,
      "max_domains": 5,
      "used_domains": 2,
      "created_at": "2024-01-01T00:00:00Z"
    }
  }
}
```

---

### 更新用户

**PUT** `/api/admin/users/{user_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 否 | 用户名 |
| email | string | 否 | 邮箱 |
| status | int | 否 | 状态(0禁用/1正常) |
| role | string | 否 | 角色(user/admin) |
| max_domains | int | 否 | 最大域名数 |
| password | string | 否 | 重置密码 |

#### 响应示例
```json
{
  "code": 200,
  "message": "更新成功",
  "data": {
    "user": {
      "id": 1,
      "username": "testuser",
      "status": 1,
      "role": "user",
      "max_domains": 10,
      "balance": 200.00
    }
  }
}
```

---

### 删除用户

**DELETE** `/api/admin/users/{user_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

> 注意：删除用户会同时删除该用户的所有域名和DNS记录

#### 响应示例
```json
{
  "code": 200,
  "message": "用户删除成功"
}
```

---

## 主域名管理模块

### 获取所有主域名

**GET** `/api/admin/domains`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "domains": [
      {
        "id": 1,
        "name": "example.com",
        "cf_zone_id": "zone_id_xxx",
        "cf_account": {
          "id": 1,
          "name": "主账户"
        },
        "allow_register": true,
        "status": 1,
        "subdomains_count": 150,
        "created_at": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

---

### 添加主域名

**POST** `/api/admin/domains`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cf_account_id | int | 是 | Cloudflare账户ID |
| name | string | 是 | 域名 |
| cf_zone_id | string | 是 | Cloudflare Zone ID |
| allow_register | bool | 否 | 是否开放注册，默认true |

#### 响应示例
```json
{
  "code": 201,
  "message": "域名添加成功",
  "data": {
    "domain": {
      "id": 1,
      "name": "example.com"
    }
  }
}
```

---

### 更新主域名

**PUT** `/api/admin/domains/{domain_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| allow_register | bool | 否 | 是否开放注册 |
| status | int | 否 | 状态(0禁用/1正常) |

---

### 删除主域名

**DELETE** `/api/admin/domains/{domain_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

> 注意：删除主域名会同时删除该域名下所有二级域名及其DNS记录

---

## Cloudflare账户管理模块

### 获取CF账户列表

**GET** `/api/admin/cf-accounts`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "accounts": [
      {
        "id": 1,
        "name": "主账户",
        "email": "admin@example.com",
        "auth_type": "api_key",
        "domains_count": 5,
        "created_at": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

---

### 添加CF账户

**POST** `/api/admin/cf-accounts`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 账户名称 |
| email | string | 是 | Cloudflare邮箱 |
| auth_type | string | 是 | 认证方式(api_key/api_token) |
| api_key | string | 否 | Global API Key(api_key方式) |
| api_token | string | 否 | API Token(api_token方式) |

#### 响应示例
```json
{
  "code": 201,
  "message": "账户添加成功",
  "data": {
    "account": {
      "id": 1,
      "name": "主账户"
    }
  }
}
```

---

### 更新CF账户

**PUT** `/api/admin/cf-accounts/{account_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 账户名称 |
| email | string | 否 | 邮箱 |
| api_key | string | 否 | API Key |
| api_token | string | 否 | API Token |

---

### 删除CF账户

**DELETE** `/api/admin/cf-accounts/{account_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

> 注意：需先删除该账户下的所有域名

---

### 获取CF账户的Zone列表

**GET** `/api/admin/cf-accounts/{account_id}/zones`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "zones": [
      {
        "id": "zone_id_xxx",
        "name": "example.com",
        "status": "active"
      }
    ]
  }
}
```

---

## 套餐管理模块

### 获取套餐列表

**GET** `/api/admin/plans`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| domain_id | int | 否 | 筛选域名 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "plans": [
      {
        "id": 1,
        "name": "免费套餐",
        "domain_id": 1,
        "domain_name": "example.com",
        "price": 0,
        "duration_days": 30,
        "duration_text": "30天",
        "min_length": 5,
        "max_length": 20,
        "max_records": 5,
        "max_records_text": "5条",
        "status": 1,
        "created_at": "2024-01-01T00:00:00Z"
      }
    ]
  }
}
```

---

### 创建套餐

**POST** `/api/admin/plans`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| domain_id | int | 是 | 域名ID |
| name | string | 是 | 套餐名称 |
| price | float | 否 | 价格，默认0 |
| duration_days | int | 否 | 有效天数(-1为永久)，默认30 |
| min_length | int | 否 | 最小长度，默认1 |
| max_length | int | 否 | 最大长度，默认63 |
| max_records | int | 否 | 最大记录数，默认10 |
| description | string | 否 | 套餐描述 |
| sort_order | int | 否 | 排序权重，默认0 |

#### 响应示例
```json
{
  "code": 201,
  "message": "套餐创建成功",
  "data": {
    "plan": {
      "id": 1,
      "name": "月度套餐",
      "domain_id": 1,
      "price": 5.00,
      "duration_days": 30
    }
  }
}
```

---

### 更新套餐

**PUT** `/api/admin/plans/{plan_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 套餐名称 |
| price | float | 否 | 价格 |
| duration_days | int | 否 | 有效天数 |
| min_length | int | 否 | 最小长度 |
| max_length | int | 否 | 最大长度 |
| max_records | int | 否 | 最大记录数 |
| description | string | 否 | 套餐描述 |
| status | int | 否 | 状态(0禁用/1正常) |
| sort_order | int | 否 | 排序权重 |

---

### 删除套餐

**DELETE** `/api/admin/plans/{plan_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

## 卡密管理模块

### 获取卡密列表

**GET** `/api/admin/redeem-codes`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| per_page | int | 否 | 每页数量 |
| status | int | 否 | 状态(0未使用/1已使用/2已禁用) |
| batch_no | string | 否 | 批次号 |
| search | string | 否 | 搜索卡密码 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "codes": [
      {
        "id": 1,
        "code": "XXXX-XXXX-XXXX-XXXX",
        "amount": 10.00,
        "amount_text": "¥10.00",
        "status": 0,
        "batch_no": "20240101100000",
        "used_by": null,
        "used_at": null,
        "expires_at": null,
        "created_at": "2024-01-01T00:00:00Z",
        "user": null
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

---

### 批量生成卡密

**POST** `/api/admin/redeem-codes/generate`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| amount | float | 是 | 充值金额(-1为无限余额) |
| count | int | 否 | 生成数量(1-100)，默认1 |
| expires_days | int | 否 | 过期天数 |

#### 响应示例
```json
{
  "code": 201,
  "message": "成功生成 10 张卡密",
  "data": {
    "batch_no": "20240101100000",
    "codes": [
      {
        "id": 1,
        "code": "XXXX-XXXX-XXXX-XXXX",
        "amount": 10.00
      }
    ]
  }
}
```

---

### 更新卡密状态

**PUT** `/api/admin/redeem-codes/{code_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | int | 否 | 状态(0未使用/2禁用) |

> 注意：已使用的卡密不能修改状态

---

### 删除卡密

**DELETE** `/api/admin/redeem-codes/{code_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

### 批量删除卡密

**POST** `/api/admin/redeem-codes/batch-delete`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| batch_no | string | 否 | 按批次号删除(只删除未使用的) |
| ids | array | 否 | 按ID列表删除 |

---

### 导出卡密

**GET** `/api/admin/redeem-codes/export`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| batch_no | string | 否 | 批次号 |
| status | int | 否 | 状态 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "codes": ["XXXX-XXXX-XXXX-XXXX", "YYYY-YYYY-YYYY-YYYY"],
    "count": 2
  }
}
```

---

## 订单管理模块

### 获取购买记录列表

**GET** `/api/admin/purchase-records`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认1 |
| per_page | int | 否 | 每页数量，默认20 |
| user_id | int | 否 | 按用户ID筛选 |
| search | string | 否 | 搜索(域名/套餐名) |

#### 响应示例
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "records": [
      {
        "id": 1,
        "user_id": 1,
        "subdomain_id": 1,
        "plan_id": 1,
        "plan_name": "月度套餐",
        "domain_name": "example.com",
        "subdomain_name": "mysite.example.com",
        "price": 5.00,
        "price_text": "¥5.00",
        "duration_days": 30,
        "duration_text": "30天",
        "payment_method": "balance",
        "payment_method_text": "余额支付",
        "created_at": "2024-01-01T00:00:00",
        "user": {
          "id": 1,
          "username": "testuser",
          "email": "test@example.com"
        }
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

---

### 删除购买记录

**DELETE** `/api/admin/purchase-records/{record_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

### 批量删除购买记录

**POST** `/api/admin/purchase-records/batch-delete`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | array | 是 | 记录ID数组 |

---

## DNS记录管理模块

### 获取所有DNS记录

**GET** `/api/admin/dns-records`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| domain_id | int | 否 | 筛选主域名 |
| source | string | 否 | 来源(system/cloudflare/all) |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "records": [
      {
        "id": "cf_record_id",
        "type": "A",
        "name": "mysite.example.com",
        "content": "1.2.3.4",
        "ttl": 1,
        "proxied": true,
        "source": "system",
        "subdomain": {
          "id": 1,
          "name": "mysite"
        },
        "user": {
          "id": 1,
          "username": "testuser"
        }
      }
    ]
  }
}
```

---

### 更新DNS记录

**PUT** `/api/admin/dns-records/{record_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 否 | 记录值 |
| ttl | int | 否 | TTL |
| proxied | bool | 否 | 是否代理 |

---

### 删除DNS记录

**DELETE** `/api/admin/dns-records/{record_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

## 公告管理模块

### 获取公告列表

**GET** `/api/admin/announcements`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| per_page | int | 否 | 每页数量 |
| status | int | 否 | 状态筛选 |

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
        "status": 1,
        "created_at": "2024-01-01T00:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 10,
      "pages": 1
    }
  }
}
```

---

### 创建公告

**POST** `/api/admin/announcements`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 标题 |
| content | string | 是 | 内容 |
| type | string | 否 | 类型(info/warning/success/error)，默认info |
| is_pinned | bool | 否 | 是否置顶，默认false |
| is_popup | bool | 否 | 是否弹窗显示，默认false |
| status | int | 否 | 状态(0草稿/1发布)，默认1 |

---

### 更新公告

**PUT** `/api/admin/announcements/{ann_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 否 | 标题 |
| content | string | 否 | 内容 |
| type | string | 否 | 类型(info/warning/success/error) |
| is_pinned | bool | 否 | 是否置顶 |
| is_popup | bool | 否 | 是否弹窗显示 |
| status | int | 否 | 状态(0草稿/1发布) |

---

### 删除公告

**DELETE** `/api/admin/announcements/{ann_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

## 系统设置模块

### 获取系统设置

**GET** `/api/admin/settings`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "settings": {
      "site_name": "DNS分发系统",
      "site_description": "基于Cloudflare的二级域名分发平台",
      "site_logo": "",
      "site_favicon": "",
      "admin_email": "admin@example.com",
      "smtp_host": "smtp.example.com",
      "smtp_port": "465",
      "smtp_user": "noreply@example.com",
      "smtp_password": "***",
      "smtp_ssl": "1",
      "redeem_channel_text": "购买卡密",
      "redeem_channel_url": "https://example.com/buy"
    }
  }
}
```

---

### 更新系统设置

**PUT** `/api/admin/settings`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| site_name | string | 否 | 站点名称 |
| site_description | string | 否 | 站点描述 |
| site_logo | string | 否 | Logo URL |
| site_favicon | string | 否 | Favicon URL |
| admin_email | string | 否 | 管理员邮箱 |
| smtp_host | string | 否 | SMTP服务器 |
| smtp_port | string | 否 | SMTP端口 |
| smtp_user | string | 否 | SMTP用户名 |
| smtp_password | string | 否 | SMTP密码 |
| smtp_ssl | string | 否 | 是否SSL(0/1) |
| redeem_channel_text | string | 否 | 卡密渠道按钮文字 |
| redeem_channel_url | string | 否 | 卡密渠道链接 |

---

### 测试SMTP

**POST** `/api/admin/settings/test-smtp`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| email | string | 是 | 测试邮箱 |

---

## 操作日志模块

### 获取操作日志

**GET** `/api/admin/logs`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| per_page | int | 否 | 每页数量 |
| action | string | 否 | 操作类型筛选 |

#### 响应示例
```json
{
  "code": 200,
  "data": {
    "logs": [
      {
        "id": 1,
        "user_id": 1,
        "username": "admin",
        "action": "create",
        "target_type": "domain",
        "target_id": 1,
        "detail": "添加主域名",
        "ip_address": "127.0.0.1",
        "created_at": "2024-01-01T10:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 100,
      "pages": 5
    }
  }
}
```

---

### 删除单条日志

**DELETE** `/api/admin/logs/{log_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

### 批量删除日志

**POST** `/api/admin/logs/batch-delete`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | array | 否 | 日志ID数组 |
| clear_all | bool | 否 | 是否清空所有日志 |

---

## 用户域名管理模块

### 获取所有二级域名

**GET** `/api/admin/subdomains`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 查询参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| per_page | int | 否 | 每页数量 |
| user_id | int | 否 | 按用户筛选 |
| domain_id | int | 否 | 按主域名筛选 |
| status | int | 否 | 状态筛选 |
| search | string | 否 | 搜索域名 |
| expired | string | 否 | 是否过期(1=已过期/0=未过期) |

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
        "domain_id": 1,
        "domain_name": "example.com",
        "status": 1,
        "expires_at": "2024-02-01T00:00:00Z",
        "is_expired": false,
        "records_count": 3,
        "user": {
          "id": 1,
          "username": "testuser",
          "email": "test@example.com"
        }
      }
    ],
    "pagination": {...}
  }
}
```

---

### 获取二级域名详情

**GET** `/api/admin/subdomains/{subdomain_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

### 更新二级域名

**PUT** `/api/admin/subdomains/{subdomain_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | int | 否 | 状态(0禁用/1正常/2待审核) |
| expires_at | string | 否 | 到期时间(ISO格式) |
| extend_days | int | 否 | 延期天数 |

---

### 删除二级域名

**DELETE** `/api/admin/subdomains/{subdomain_id}`

#### 请求头
```
Authorization: Bearer <access_token>
```

> 注意：删除域名会同时删除Cloudflare上的DNS记录

---

### 批量删除二级域名

**POST** `/api/admin/subdomains/batch-delete`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | array | 是 | 域名ID数组 |

---

### 批量更新二级域名

**POST** `/api/admin/subdomains/batch-update`

#### 请求头
```
Authorization: Bearer <access_token>
```

#### 请求参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| ids | array | 是 | 域名ID数组 |
| status | int | 否 | 状态 |
| extend_days | int | 否 | 延期天数 |

---

### 发送到期提醒邮件

**POST** `/api/admin/subdomains/{subdomain_id}/send-expiry-email`

#### 请求头
```
Authorization: Bearer <access_token>
```

---

### 清理域名DNS记录

**POST** `/api/admin/subdomains/{subdomain_id}/clear-dns`

#### 请求头
```
Authorization: Bearer <access_token>
```

> 清理该域名的所有DNS记录

---

## 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未授权/Token无效 |
| 403 | 权限不足(非管理员) |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 500 | 服务器错误 |
