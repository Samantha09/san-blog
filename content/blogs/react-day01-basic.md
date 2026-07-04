---
title: "React 学习 Day 01：基础入门"
date: 2026-07-04T12:00:00+08:00
draft: false
tags: ["React", "前端", "学习笔记", "Vite"]
categories: ["前端开发"]
---

> 从零开始，用一个 `react-basic` 项目串起 React 入门必备知识。

---

## 一、项目搭建

使用 Vite 创建 React 项目：

```bash
npm create vite@latest react-basic -- --template react
cd react-basic
npm install
npm run dev
```

常用命令：

| 命令 | 作用 |
|------|------|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 生产构建 |
| `npm run preview` | 预览生产构建 |
| `npm run lint` | 运行 Oxlint |
| `npm test -- --run` | 运行测试 |

---

## 二、JSX 基础

JSX 允许在 JavaScript 中写 HTML 结构，并用 `{}` 嵌入表达式。

```jsx
function Demo() {
  const count = 100
  const getName = () => 'jack'

  return (
    <section>
      this is App
      {'this is message'}        {/* 字符串 */}
      {count}                    {/* 变量 */}
      {getName()}                {/* 函数调用 */}
      {new Date().getDate()}     {/* 方法调用 */}
      <div style={{ color: 'red' }}>this is div</div>  {/* JS 对象 */}
    </section>
  )
}
```

注意点：

- 外层 `{}` 表示 JSX 表达式
- 内层 `{}` 是 JavaScript 对象 `{ color: 'red' }`
- 类名用 `className`，而不是 `class`

---

## 三、组件与 Props

React 应用由组件组成。组件接收 `props`，返回 JSX。

### 3.1 基础组件

```jsx
function Header({ title }) {
  return <h1>{title}</h1>
}

function Button({ children, onClick }) {
  return <button onClick={onClick}>{children}</button>
}
```

### 3.2 使用组件

```jsx
<Header title="Hello React Components" />
<Button onClick={() => alert('clicked')}>Click me</Button>
```

- `props`：父组件向子组件传递数据
- `children`：组件标签中间的内容

---

## 四、useState 基础

`useState` 让函数组件拥有状态。

```jsx
import { useState } from 'react'

function Counter() {
  const [count, setCount] = useState(0)

  return (
    <div>
      <p>{count}</p>
      <button onClick={() => setCount(count + 1)}>+1</button>
    </div>
  )
}
```

- 返回 `[state, setState]`
- 调用 `setState` 会触发重新渲染
- 新值依赖旧值时，推荐函数式更新：`setCount((prev) => prev + 1)`

### 4.1 对象状态

多个相关字段可以放在一个对象里管理：

```jsx
const [user, setUser] = useState({ name: '', age: '', email: '' })

const handleChange = (event) => {
  const { name, value } = event.target
  setUser((prev) => ({ ...prev, [name]: value }))
}
```

重点：**只改一个字段时，也要保留其他字段**。

---

## 五、状态不可变

不要直接修改 state，要创建新的值。

### ❌ 错误

```jsx
users.push(newUser)
setUsers(users)

user.name = 'Jerry'
setUser(user)
```

### ✅ 正确

```jsx
setUsers([...users, newUser])
setUser({ ...user, name: 'Jerry' })

// 删除
setUsers(users.filter((u) => u.id !== id))

// 修改数组中某一项
setUsers(
  users.map((u) => (u.id === id ? { ...u, name: 'New' } : u))
)
```

React 通过引用变化来判断是否需要重新渲染，直接修改原对象不会触发更新。

---

## 六、组件样式方案

### 6.1 CSS Modules

每个组件一个 `.module.css` 文件，类名会被自动哈希，避免全局污染。

```css
/* Card.module.css */
.card {
  padding: 16px;
  border-radius: 8px;
  background: #fff;
}
```

```jsx
import styles from './Card.module.css'

function Card({ title }) {
  return <div className={styles.card}>{title}</div>
}
```

### 6.2 集中式 CSS 变量

把设计 token 放在全局样式文件中：

```css
:root {
  --color-primary: #1890ff;
  --color-bg: #f5f5f5;
  --spacing-md: 16px;
  --radius: 8px;
  --shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
```

组件中引用：

```css
.card {
  padding: var(--spacing-md);
  background: var(--color-surface);
  box-shadow: var(--shadow);
}
```

### 6.3 classnames 处理条件类名

```jsx
import classNames from 'classnames'
import styles from './Card.module.css'

function Card({ highlight }) {
  return (
    <div className={classNames(styles.card, { [styles.highlight]: highlight })}>
      ...
    </div>
  )
}
```

`classnames` 让多条件类名更易读，也避免 false 时产生多余空格。

---

## 七、综合案例：B站评论

实现了一个完整的评论组件 `CommentApp`，覆盖以下功能：

1. 渲染评论列表
2. 删除评论
3. Tab 导航与高亮
4. 评论排序（最新 / 最热）
5. 发布新评论
6. 只有自己的评论才显示删除按钮

### 7.1 组件拆分

```
src/comment/
├── CommentApp.jsx
├── CommentTabs.jsx
├── CommentInput.jsx
├── CommentList.jsx
├── CommentItem.jsx
├── comment.module.css
└── CommentApp.test.jsx
```

### 7.2 核心状态

```jsx
const [comments, setComments] = useState(initialComments)
const [activeTab, setActiveTab] = useState('all')
const [inputValue, setInputValue] = useState('')
```

### 7.3 排序逻辑

```jsx
const sortedComments = [...comments].sort((a, b) => {
  if (activeTab === 'latest') return b.date.localeCompare(a.date)
  if (activeTab === 'hottest') return b.likes - a.likes
  return b.date.localeCompare(a.date)
})
```

### 7.4 权限控制

每条评论带 `uid`，只有 `uid` 与当前用户一致时才显示删除按钮：

```jsx
const isOwn = comment.uid === currentUserId

{isOwn && <button onClick={() => onDelete(comment.id)}>删除</button>}
```

---

## 八、总结

今天从 0 搭建了一个 React 项目，依次学习了：

- JSX 语法与表达式
- 组件拆分、props、children
- useState 数字 / 布尔 / 对象状态
- 状态不可变原则
- 组件样式：CSS Modules、CSS 变量、classnames
- 一个完整的评论案例

下一步可以继续学习：

- `useEffect` 副作用
- 父子组件通信 / 状态提升
- React Router 路由
- 数据请求（fetch / axios）
- 表单校验

---

*文章为 React 12 天学习计划第 1 天笔记，代码位于 `react-basic` 项目中。*
