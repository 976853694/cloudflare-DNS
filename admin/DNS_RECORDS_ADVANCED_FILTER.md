# DNS记录管理 - 高级筛选功能

## 功能概述

为 `admin/dns_records.php` 添加了完善的高级筛选功能，允许管理员通过多个维度快速筛选和查找DNS记录。

## 新增功能

### 1. 高级筛选面板

点击页面右上角的"高级筛选"按钮，展开/收起筛选面板。

#### 筛选条件包括：

| 筛选项 | 说明 | 选项 |
|--------|------|------|
| **记录类型** | 按DNS记录类型筛选 | A, AAAA, CNAME, MX, NS, TXT, SRV, PTR, CAA |
| **域名** | 按域名筛选记录 | 系统中所有可用域名 |
| **用户** | 按创建用户筛选 | 系统中所有注册用户 |
| **代理状态** | 按Cloudflare代理状态筛选 | 已代理 / 仅DNS |
| **记录来源** | 按记录来源筛选 | 系统记录 / 用户记录 |
| **创建日期（起）** | 筛选指定日期之后创建的记录 | 日期选择器 |
| **创建日期（止）** | 筛选指定日期之前创建的记录 | 日期选择器 |

### 2. 智能面板状态

- **自动展开**: 当应用了任何筛选条件时，筛选面板自动展开显示
- **自动收起**: 没有筛选条件时，面板默认收起，保持界面整洁

### 3. 当前筛选条件显示

在筛选面板底部会显示当前激活的所有筛选条件：
- 以标签（Badge）形式展示每个筛选条件
- 实时显示筛选结果的记录数量
- 一目了然地查看当前的筛选状态

### 4. 快速操作

- **应用筛选**: 点击"应用筛选"按钮执行筛选
- **重置**: 点击"重置"按钮清除所有筛选条件，返回完整列表
- **快速搜索**: 筛选面板外的搜索框仍然可用，实现实时搜索

## 技术实现

### 后端优化

#### 1. 安全的参数绑定
```php
// 使用命名参数绑定，防止SQL注入
$stmt = $db->prepare($sql);
foreach ($bind_params as $param => $value) {
    $stmt->bindValue($param, $value);
}
$result = $stmt->execute();
```

#### 2. 灵活的查询构建
```php
// 动态构建WHERE条件
$where_conditions = [];
if (!empty($filter_type)) {
    $where_conditions[] = "dr.type = :type";
    $bind_params[':type'] = $filter_type;
}
// ... 其他条件

$where_sql = !empty($where_conditions) ? 'WHERE ' . implode(' AND ', $where_conditions) : '';
```

#### 3. 数据预加载
```php
// 预加载域名和用户列表用于下拉选择
$domains_list = [];  // 所有域名
$users_list = [];    // 所有用户
$record_types = ['A', 'AAAA', 'CNAME', ...];  // DNS记录类型
```

### 前端优化

#### 1. 美观的UI设计
- 渐变背景的卡片头部
- 平滑的折叠展开动画
- 按钮悬停特效（阴影和位移）
- 标签淡入缩放动画

#### 2. 响应式设计
- 移动端自适应布局
- 灵活的网格系统（Bootstrap Grid）
- 触摸友好的按钮尺寸

#### 3. 用户体验优化
- 保持筛选条件的状态（URL参数）
- 可视化的筛选条件显示
- 实时显示筛选结果数量

## 使用示例

### 示例 1: 查找特定用户的A记录
1. 点击"高级筛选"按钮
2. 在"记录类型"中选择"A"
3. 在"用户"中选择目标用户
4. 点击"应用筛选"

### 示例 2: 查找最近7天创建的系统记录
1. 点击"高级筛选"按钮
2. 在"记录来源"中选择"系统记录"
3. 在"创建日期（起）"中选择7天前的日期
4. 点击"应用筛选"

### 示例 3: 查找已启用代理的CNAME记录
1. 点击"高级筛选"按钮
2. 在"记录类型"中选择"CNAME"
3. 在"代理状态"中选择"已代理"
4. 点击"应用筛选"

### 示例 4: 按域名和用户组合筛选
1. 点击"高级筛选"按钮
2. 在"域名"中选择目标域名
3. 在"用户"中选择目标用户
4. 点击"应用筛选"

## URL参数说明

筛选条件通过GET参数传递，支持直接访问URL：

```
admin/dns_records.php?filter_type=A&filter_proxied=1&filter_record_source=user
```

参数列表：
- `filter_type`: 记录类型（A, AAAA, CNAME等）
- `filter_domain`: 域名ID
- `filter_user`: 用户ID
- `filter_proxied`: 代理状态（0=仅DNS, 1=已代理）
- `filter_record_source`: 记录来源（system=系统, user=用户）
- `filter_date_from`: 起始日期（YYYY-MM-DD）
- `filter_date_to`: 截止日期（YYYY-MM-DD）

## 性能优化

### 1. 单次查询
所有筛选条件在一次SQL查询中完成，避免多次数据库访问：
```sql
SELECT dr.*, ... 
FROM dns_records dr
LEFT JOIN users u ON ...
JOIN domains d ON ...
WHERE dr.type = ? AND dr.proxied = ? AND ...
ORDER BY dr.is_system DESC, dr.created_at DESC
```

### 2. 预处理语句
使用参数绑定提升性能和安全性：
- 数据库可以缓存执行计划
- 防止SQL注入攻击
- 提高查询效率

### 3. 索引友好
查询条件设计考虑了数据库索引：
- `dr.type` - 记录类型索引
- `dr.domain_id` - 域名外键索引
- `dr.user_id` - 用户外键索引
- `dr.created_at` - 时间索引

## 样式特性

### 1. 现代化设计
- 渐变色背景
- 圆角卡片
- 柔和阴影
- 平滑过渡动画

### 2. 交互反馈
```css
/* 按钮悬停效果 */
.btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(13, 110, 253, 0.3);
}

/* 标签淡入动画 */
@keyframes fadeInScale {
    from { opacity: 0; transform: scale(0.8); }
    to { opacity: 1; transform: scale(1); }
}
```

### 3. 响应式布局
```css
@media (max-width: 768px) {
    #advancedFilter .col-md-3 {
        margin-bottom: 1rem;
    }
    #advancedFilter .btn-toolbar .btn {
        width: 100%;
    }
}
```

## 兼容性

### 浏览器支持
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+
- ✅ 移动端浏览器

### 依赖项
- Bootstrap 5.x
- Font Awesome 5.x
- jQuery（用于快速搜索功能）

## 未来扩展建议

### 短期优化
1. **保存筛选预设**: 允许保存常用的筛选条件组合
2. **导出筛选结果**: 支持CSV/Excel导出当前筛选的记录
3. **批量操作**: 对筛选结果进行批量编辑或删除

### 中期优化
1. **高级搜索**: 支持正则表达式或模糊搜索
2. **统计分析**: 显示筛选结果的统计图表
3. **历史记录**: 记录最近使用的筛选条件

### 长期优化
1. **智能推荐**: 根据使用习惯推荐筛选条件
2. **自定义视图**: 允许自定义显示的列和排序方式
3. **实时筛选**: 使用AJAX实现无刷新筛选

## 代码统计

| 指标 | 数量 |
|------|------|
| 新增PHP代码 | ~100行 |
| 新增HTML代码 | ~140行 |
| 新增CSS代码 | ~120行 |
| 筛选维度 | 7个 |
| 支持的记录类型 | 9种 |

## 测试清单

### 功能测试
- [x] 单个筛选条件工作正常
- [x] 多个筛选条件组合工作正常
- [x] 日期范围筛选正确
- [x] 重置按钮清除所有筛选
- [x] URL参数正确传递和解析
- [x] 筛选结果计数准确

### 安全测试
- [x] SQL注入防护（参数绑定）
- [x] XSS防护（输出转义）
- [x] 参数验证和清理

### 性能测试
- [x] 大量记录下的筛选速度
- [x] 数据库查询效率
- [x] 页面加载时间

### UI/UX测试
- [x] 响应式布局在各设备正常
- [x] 动画流畅无卡顿
- [x] 颜色对比度符合可访问性标准
- [x] 移动端触摸操作友好

## 维护说明

### 添加新的筛选条件

1. **后端（PHP）**:
```php
// 获取新参数
$filter_new = isset($_GET['filter_new']) ? $_GET['filter_new'] : '';

// 添加WHERE条件
if (!empty($filter_new)) {
    $where_conditions[] = "dr.new_field = :new_field";
    $bind_params[':new_field'] = $filter_new;
}

// 添加到活跃筛选显示
if (!empty($filter_new)) {
    $active_filters[] = "新条件: $filter_new";
}
```

2. **前端（HTML）**:
```html
<div class="col-md-3">
    <label for="filter_new" class="form-label">新筛选项</label>
    <select class="form-select" name="filter_new">
        <option value="">全部</option>
        <!-- 选项 -->
    </select>
</div>
```

## 常见问题

### Q1: 筛选后快速搜索不工作？
**A**: 快速搜索是在当前筛选结果基础上进行的客户端搜索，两者可以配合使用。

### Q2: 如何清除筛选条件？
**A**: 点击"重置"按钮，或直接访问不带参数的URL：`admin/dns_records.php`

### Q3: 筛选面板为什么自动展开？
**A**: 当检测到有筛选条件激活时，面板会自动展开以显示当前的筛选状态。

### Q4: 可以同时使用多个筛选条件吗？
**A**: 可以，所有筛选条件都是AND关系，即同时满足所有条件的记录才会显示。

### Q5: 筛选条件会保存吗？
**A**: 筛选条件通过URL参数传递，你可以保存URL作为书签来快速访问特定的筛选视图。

## 更新日志

### v2.0 - 2024年
- ✅ 添加高级筛选功能
- ✅ 7个维度的筛选条件
- ✅ 智能面板状态管理
- ✅ 当前筛选条件可视化
- ✅ 美观的UI设计和动画效果
- ✅ 响应式布局优化
- ✅ 性能优化（参数绑定）
- ✅ 安全性增强（SQL注入防护）

---

**文档版本**: 1.0  
**最后更新**: 2024年  
**维护者**: Development Team
