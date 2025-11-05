# 域名自动绑定默认用户组功能

## 功能说明

当管理员在 `admin/domains.php` 中添加新域名时，系统会自动将该域名绑定到"默认用户组"（group_name = 'default'），使得该用户组的所有用户都能访问新添加的域名。

## 实现细节

### 1. 自动绑定函数

在 `admin/domains.php` 文件顶部定义了 `bindDomainToDefaultGroup()` 函数：

```php
function bindDomainToDefaultGroup($db, $domain_id) {
    // 获取默认用户组（group_name = 'default'）
    // 检查是否已经绑定
    // 如果未绑定，则自动绑定
}
```

### 2. 应用场景

该功能在以下所有域名添加操作后自动执行：

1. **手动添加 Cloudflare 域名**
   - 处理位置：`add_domain` POST 请求处理

2. **批量添加 Cloudflare 域名**
   - 处理位置：`add_selected_domains` POST 请求处理

3. **添加彩虹DNS域名**
   - 处理位置：`add_rainbow_domain` POST 请求处理

4. **批量添加彩虹DNS域名**
   - 处理位置：`add_selected_rainbow_domains` POST 请求处理

5. **批量添加 DNSPod 域名**
   - 处理位置：`add_selected_dnspod_domains` POST 请求处理

6. **批量添加 PowerDNS 域名**
   - 处理位置：`add_selected_powerdns_domains` POST 请求处理

### 3. 执行流程

```
添加域名成功
    ↓
获取新域名 ID ($db->lastInsertRowID())
    ↓
调用 bindDomainToDefaultGroup($db, $domain_id)
    ↓
检查默认用户组是否存在
    ↓
检查域名是否已绑定
    ↓
执行绑定（插入 user_group_domains 表）
    ↓
完成
```

### 4. 数据库表结构

绑定关系存储在 `user_group_domains` 表中：

```sql
CREATE TABLE user_group_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    domain_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES user_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE,
    UNIQUE(group_id, domain_id)
)
```

## 优势

1. **自动化管理**：无需手动为每个新域名配置用户组权限
2. **用户友好**：新用户注册后（默认分配到"默认组"）立即可以使用所有域名
3. **可扩展**：管理员后续仍可在用户组管理页面调整域名权限

## 注意事项

- 该功能仅绑定到"默认用户组"（group_name = 'default'）
- 如果默认用户组不存在或未激活，绑定会静默失败（不影响域名添加）
- 如果域名已经绑定到默认组，会跳过重复绑定
- 管理员可以随时在"用户组管理"页面修改域名权限配置

## 版本

- 创建时间：2024
- 最后更新：2024
