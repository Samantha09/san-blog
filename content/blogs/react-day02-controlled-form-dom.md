---
title: "React 学习 Day 02：受控表单、DOM、组件通信与 Hooks"
date: 2026-07-05T12:00:00+08:00
draft: false
tags: ["React", "前端", "学习笔记", "Hooks", "表单", "组件通信"]
categories: ["前端开发"]
---

> 延续 Day01，今天一口气覆盖「受控表单、受控 vs 非受控、useRef 获取 DOM、UUID/时间、组件通信、useEffect、自定义 Hook」，并用「请求接口的评论列表」综合案例收口。每个知识点都配项目里的真实案例代码。

---

## 一、DOM 是什么

**DOM = Document Object Model（文档对象模型）**。浏览器加载 HTML 后，把每个标签变成一个 JS 对象，按父子关系组成一棵树。JS 操作页面，本质就是操作这棵树上的节点。

```
<html>               ← 根节点
  <body>             ← 对象 { tagName: 'BODY', children: [...] }
    <div>
      <input />      ← ref.current 拿到的就是这个对象
    </div>
  </body>
</html>
```

每个节点能用 DOM API 读写：

```js
el.focus()                       // 方法
el.value                          // 属性
el.getBoundingClientRect()        // 尺寸
document.createElement('div')     // 创建节点
```

**和 React 的关系**：平时写 JSX，React 帮你算「虚拟 DOM」再去改真实 DOM，你不用碰；少数 React 没封装的事（聚焦、滚动、测尺寸、读 file），才用 `useRef` 直接拿真实 DOM 节点。

---

## 二、受控表单绑定（回顾）

Day01 已接触过文本输入的受控绑定。核心：**state 是唯一数据源**，`value` 绑定 state，`onChange` 更新 state。

```jsx
import { useState } from 'react'

function ControlledForm() {
  const [text, setText] = useState('')

  return (
    <form onSubmit={(e) => { e.preventDefault(); alert(text) }}>
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {/* 受控的优势：每一次按键都能即时派生 */}
      <p>大写：{text.toUpperCase()}</p>
      <p>字符数：{text.length}</p>
    </form>
  )
}
```

受控两要素：`value={state}` + `onChange={setState}`。每按一次键都会 `setState → 重新渲染 → value 流回 input`，形成闭环。

---

## 三、受控 vs 非受控

### 3.1 受控组件（state 驱动）

如上 `ControlledForm`。**优势**：能即时读取、派生、转换、校验输入。

### 3.2 非受控组件（DOM 驱动 + ref）

DOM 本身是数据源，用 `useRef` 在需要时（如提交）才读取；输入过程不触发重新渲染。

```jsx
import { useRef } from 'react'

function UncontrolledForm() {
  const inputRef = useRef(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    alert(inputRef.current.value)   // 提交时才读 DOM
  }

  return (
    <form onSubmit={handleSubmit}>
      {/* 非受控用 defaultValue 设初值，不是 value */}
      <input type="text" ref={inputRef} defaultValue="默认值" />
      <button type="submit">提交</button>
    </form>
  )
}
```

注意：非受控用 `defaultValue` 设初值。若写 `value` 又不写 `onChange`，input 会变只读并报警告。

### 3.3 file 输入：永远只能非受控

出于安全限制，JS 无法用 `value` 设置用户选择的文件，只能通过 ref 读取。

```jsx
function FileInput() {
  const fileRef = useRef(null)
  const handleSubmit = (e) => {
    e.preventDefault()
    const file = fileRef.current.files[0]
    alert(file ? `已选择：${file.name}` : '未选择文件')
  }
  return (
    <form onSubmit={handleSubmit}>
      <input type="file" ref={fileRef} />
      <button type="submit">提交</button>
    </form>
  )
}
```

### 3.4 对比表

| 维度 | 受控组件 | 非受控组件 |
|------|----------|------------|
| 数据源 | React state | DOM 本身 |
| 读取值 | 直接读 state | `ref.current.value` |
| 每次按键是否重渲染 | 是 | 否 |
| 实时校验/转换 | 容易 | 不方便 |
| 初值写法 | `value` | `defaultValue` |
| 典型场景 | 大多数表单 | file、一次性读取、集成非 React 库 |

### 3.5 何时用哪个

- **默认受控**：需要即时校验、派生、受 state 驱动的输入。
- **用非受控**：file 输入、提交时才读一次的简单表单、集成第三方库。

---

## 四、为什么不建议直接操作 DOM

React 是「state 驱动 UI」的，直接改 DOM 会和 React 打架：

1. **覆盖问题**：React 按 state 重新渲染时，可能把你手动改的 DOM 冲掉，UI 与 state 不一致。
2. **破坏数据流**：`state → UI` 的声明式模型被绕过，「谁偷偷改了 DOM」难追踪。
3. **失去 React 优化**：批量更新、并发渲染、diff 都基于「React 接管 DOM」，自己改 DOM 用不上。

```jsx
// ❌ 直接改样式，下次渲染可能被冲掉
ref.current.style.color = 'red'
```

**但不是绝对禁止**。这些场景**必须**用 ref 拿真实 DOM：聚焦/失焦、滚动、测尺寸、读 file、集成非 React 库、动画。

**原则：能用 state 解决就用 state；实在不行才用 ref，且尽量只读不写。**

---

## 五、React 中获取 DOM：useRef

### 5.1 基本用法

```jsx
const ref = useRef(null)
// ...
<input ref={ref} />
// ref.current 即该 DOM 节点
```

### 5.2 三个典型场景

```jsx
import { useEffect, useRef, useState } from 'react'

function DomRef() {
  const inputRef = useRef(null)
  const boxRef = useRef(null)
  const [size, setSize] = useState('')

  // ① 挂载后自动聚焦：DOM 操作必须放 useEffect，不能放渲染期
  useEffect(() => {
    inputRef.current.focus()
  }, [])

  // ② 命令式聚焦（按钮触发）
  const handleFocus = () => inputRef.current.focus()

  // ③ 读 DOM 信息（尺寸）
  const handleMeasure = () => {
    const rect = boxRef.current.getBoundingClientRect()
    setSize(`宽 ${Math.round(rect.width)}px × 高 ${Math.round(rect.height)}px`)
  }

  return (
    <div>
      <input ref={inputRef} placeholder="挂载后自动聚焦" />
      <button onClick={handleFocus}>手动聚焦</button>
      <div ref={boxRef} style={{ width: 200, height: 80, background: '#eee' }}>
        量一下我的尺寸
      </div>
      <button onClick={handleMeasure}>测量</button>
      <p>{size}</p>
    </div>
  )
}
```

### 5.3 关键点

- DOM 操作（focus、读尺寸等）要放在 `useEffect` 里，**不要在渲染期做**，否则可能读到 `null`。
- `ref.current` 在挂载前是 `null`，使用前最好判空。

---

## 六、综合案例：发表评论（从零重写）

把今天学的「受控表单 + state 不可变 + 列表渲染」串成一个完整功能。文件结构：

```
src/comment2/
├── CommentApp.jsx      # 容器：state + handleAdd/handleDelete + 排序
├── CommentTabs.jsx     # 最热/最新 Tab + 高亮
├── CommentInput.jsx    # 受控输入 + 发布按钮
├── CommentList.jsx     # 渲染列表 + 空状态
├── CommentItem.jsx     # 单条评论，自己的才显示删除
└── comment.module.css
```

### 6.1 容器状态

```jsx
const [comments, setComments] = useState(initialComments)
const [activeTab, setActiveTab] = useState('hottest')
const [inputValue, setInputValue] = useState('')
```

### 6.2 发表评论主链路（受控表单串起来）

```jsx
const handleAdd = () => {
  const content = inputValue.trim()
  if (!content) return                  // ① 校验非空

  const newComment = {
    id: Date.now(),
    uid: currentUserId,
    author: '我',
    content,
    date: new Date().toISOString().slice(0, 10),
    likes: 0,
  }
  setComments([newComment, ...comments]) // ② 头部插入（不可变）
  setInputValue('')                      // ③ 清空输入框
}
```

### 6.3 受控 input 做成可复用子组件

父 `CommentApp` 持有 state，子 `CommentInput` 通过 props 接收 `value` / `onChange` / `onSubmit`，把受控绑定透传给内部 input：

```jsx
// 父：把 state 和逻辑通过 props 接进去
<CommentInput
  value={inputValue}
  onChange={setInputValue}
  onSubmit={handleAdd}
/>

// 子：受控绑定 + 把 event 解包成纯字符串
<input
  value={value}
  onChange={(e) => onChange(e.target.value)}
/>
<button onClick={onSubmit} disabled={!value.trim()}>发布</button>
```

数据流闭环：`输入 → onChange 拿值 → 父 setState → 重渲染 → value 流回 input`。

> 和「自包含受控」的区别：state 放父级（状态提升），子组件只管长相、谁用谁传 state。

### 6.4 权限控制（只删自己的）

```jsx
{isOwn && <button onClick={() => onDelete(comment.id)}>删除</button>}
```

---

## 七、清空内容 + 聚焦：受控与 ref 的配合

评论发表后，想「清空输入框 + 光标自动回到框里」，这两个动作机制完全不同，正好把今天两块知识合起来：

| 动作 | 机制 | 在哪做 | 为什么 |
|---|---|---|---|
| 清空内容 | 受控表单 | 父 `setInputValue('')` | input 受控，value 来自父 state，只能改 state |
| 聚焦 | `useRef` + DOM | 子 `inputRef.current.focus()` | 聚焦是 DOM 行为，state 表达不了，只能用 ref |

```jsx
// 子组件 CommentInput
const inputRef = useRef(null)

const handleSubmit = () => {
  onSubmit()               // → 父发表 + setInputValue('')  清空
  inputRef.current.focus() // → DOM 聚焦
}
```

关键：**ref 建在 input 渲染处（子），清空在 state 所在地（父）** —— 这就是「状态在父、DOM 在子」时，两套机制各司其职的典型场景。

---

## 八、组件样式复用：不同输入框不同样式

组件复用时，常遇到「同一个组件在不同地方需要不同样式」。三种主流做法：

### 8.1 `className` prop 合并（最常用）

```jsx
import classNames from 'classnames'
import styles from './comment.module.css'

function CommentInput({ value, onChange, className }) {
  return (
    <input className={classNames(styles.input, className)} ... />
  )
}

// 调用方传自己的 CSS Module 类
<CommentInput className={myStyles.warnInput} />
```

### 8.2 `variant` 变体 prop（样式是固定的几种）

```jsx
<input
  className={classNames(styles.input, {
    [styles.warn]: variant === 'warn',
    [styles.large]: variant === 'large',
  })}
/>

<CommentInput variant="warn" />
```

### 8.3 内联 `style`（动态/一次性）

```jsx
<CommentInput style={{ borderColor: hasError ? 'red' : undefined }} />
```

| 场景 | 选 |
|------|----|
| 每个调用方样式不同、固定 | `className` |
| 只有 2~3 种固定风格 | `variant` |
| 动态值（错误态颜色等） | `style` |

实际项目常 **`className` + `style` 一起用**。

---

## 九、UUID 与时间处理

生成唯一 id 和格式化时间，是实战里高频的小工具。案例：`src/components/UuidAndTime.jsx`。

### 9.1 UUID

```jsx
import { v4 as uuidv4 } from 'uuid'   // 第三方库（需 npm i uuid）
const id1 = crypto.randomUUID()       // 浏览器内置（推荐，零依赖），返回标准 v4
const id2 = uuidv4()                  // uuid 库，需要 v1/v7 等版本时装
```

为什么不用 `Date.now()` 做 id：① 快速连点可能同毫秒撞 id；② 单调递增、可预测。

> 心智模型：React 只管 UI；工具类需求先看**平台有没有内置**（crypto、Date、Intl），不够再上专门的小库（uuid / dayjs）。

### 9.2 时间处理

```jsx
const now = new Date()
now.toISOString()     // '2026-07-05T...' 带 T/Z
now.toLocaleString()  // 本地化

// 手动拼 YYYY-MM-DD HH:mm:ss
const pad = (n) => String(n).padStart(2, '0')
const s = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ` +
          `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

// 相对时间
function timeAgo(date) {
  const diff = (Date.now() - new Date(date).getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return `${Math.floor(diff / 86400)} 天前`
}
```

坑：`Date` 月份从 0 开始，所以 `getMonth() + 1`。复杂格式化建议上 `dayjs`（`dayjs(d).format('YYYY-MM-DD HH:mm')`、`dayjs(d).fromNow()`）。

---

## 十、组件通信

四个层次，按关系复杂度递进。**核心：没有「子改父」、没有「兄弟直连」，一切都靠 props 搭桥。**

### 10.1 父 → 子：props

父把数据当 props 传下去，子直接读。

```jsx
<Child count={count} />
function Child({ count }) {
  return <p>{count}</p>
}
```

### 10.2 子 → 父：回调（props 传函数）

父把**函数**当 props 传下去，子调用它、把数据作为**参数**传回。

```jsx
// 案例 src/components/ChildToParent.jsx
function Sender({ onSendNum }) {
  return <button onClick={() => onSendNum(1)}>给父 +1</button>
}
function ChildToParent() {
  const [num, setNum] = useState(0)
  const handleNum = (n) => setNum((c) => c + n)   // ① 父定义函数
  return <Sender onSendNum={handleNum} />          // ② 把函数传下去
}
```

数据是作为**函数参数**传上去的；子从不直接碰父的 state。

### 10.3 兄弟：状态提升

兄弟之间没有直接通道，把共享 state **提升到共同父组件**。本质 = 两个父子通信拼起来：A→父（回调）、父→B（props）。

```jsx
// 案例 src/components/LiftingState.jsx
function LiftingState() {
  const [name, setName] = useState('')
  return (
    <>
      <NameInput value={name} onChange={setName} />  {/* A 写 */}
      <Greeting name={name} />                        {/* B 读 */}
    </>
  )
}
```

### 10.4 跨层级：Context

解决 **props 钻取**（数据要穿过多层、中间层被迫转发）。三步：`createContext` → `<Provider>` → `useContext`。

```jsx
// 案例 src/components/ContextDemo.jsx
const ThemeContext = createContext('light')          // ① 创建
function ThemeProvider({ children }) {
  const [theme, setTheme] = useState('light')
  return (
    <ThemeContext.Provider value={{ theme, toggle }}>  {/* ② 顶层提供 */}
      {children}
    </ThemeContext.Provider>
  )
}
function ThemedBox() {
  const { theme } = useContext(ThemeContext)         // ③ 任意后代直接取
  return <div>当前主题：{theme}</div>
}
```

中间层完全不碰 theme —— 这就是 Context 省掉的「层层透传」。

### 10.5 通信全家桶对照表

| 关系 | 机制 | 案例 |
|---|---|---|
| 父 → 子 | props（传数据） | `Parent` / `PropsDemo` |
| 子 → 父 | props（传函数，子调用传参） | `ChildToParent` |
| 兄弟 | 状态提升到共同父 | `LiftingState` |
| 跨层级 | Context（Provider + useContext） | `ContextDemo` |

---

## 十一、useEffect 副作用

### 11.1 什么是副作用

组件渲染（算 JSX）是纯的。之外的「额外动作」都是副作用：**发请求、定时器、事件订阅、改 DOM、读写 localStorage**。这些用 `useEffect` 包起来，在**渲染完成后**才跑。

> 教程原话：「不是由事件引起、而是由渲染本身引起的操作」—— 事件用 `onClick`，渲染完自动要做的用 `useEffect`。

### 11.2 依赖数组三种写法

```jsx
useEffect(() => {...})          // 不传：每次渲染后都跑（少用，易死循环）
useEffect(() => {...}, [])      // 空数组：只在挂载后跑一次
useEffect(() => {...}, [count]) // 有依赖：挂载后 + count 变化时跑
```

### 11.3 案例：标题同步 + 计时器（src/components/UseEffectDemo.jsx）

```jsx
function Timer() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)          // ← 清理函数：卸载时清定时器
  }, [])
  return <p>{seconds} 秒</p>
}

function UseEffectDemo() {
  const [count, setCount] = useState(0)
  useEffect(() => {
    document.title = `点击 ${count} 次`       // count 变才同步标签页标题
  }, [count])
  return <button onClick={() => setCount((c) => c + 1)}>+1</button>
}
```

### 11.4 清除副作用（cleanup）

在 `useEffect` 里 `return` 一个函数，它在**卸载时**和**下次 effect 执行前**自动跑。

```jsx
// 案例 src/components/CleanupDemo.jsx —— 鼠标监听
useEffect(() => {
  const handleMove = (e) => setPos({ x: e.clientX, y: e.clientY })
  window.addEventListener('mousemove', handleMove)
  return () => window.removeEventListener('mousemove', handleMove)  // 清理
}, [])
```

| 副作用 | 清理 |
|---|---|
| `setInterval` / `setTimeout` | `clearInterval` / `clearTimeout` |
| `addEventListener` | `removeEventListener` |
| 订阅 | 取消订阅 |
| `fetch` | `AbortController.abort()` |

### 11.5 和 class 生命周期的对应

| 写法 | 类比 class 生命周期 |
|---|---|
| `useEffect(fn, [])` | `componentDidMount` + `componentWillUnmount` |
| `useEffect(fn, [a])` | + `componentDidUpdate`（a 变时） |
| `useEffect(fn)` | + 每次 `componentDidUpdate`（几乎不用） |

> 函数组件本身没有「生命周期」概念，`useEffect` 用依赖数组来表达「什么时机做事」。

---

## 十二、自定义 Hook

### 12.1 是什么

`use` 开头、内部调用别的 Hook、**返回数据（不是 JSX）**的函数 —— 用来抽出和复用「带状态的逻辑」。命名 `useXxx`，放 `src/hooks/`。每次调用各自独立 state（逻辑复用，不是状态共享）。

### 12.2 案例：useMousePosition（抽逻辑）

```jsx
// src/hooks/useMousePosition.js
function useMousePosition() {
  const [pos, setPos] = useState({ x: 0, y: 0 })
  useEffect(() => {
    const handleMove = (e) => setPos({ x: e.clientX, y: e.clientY })
    window.addEventListener('mousemove', handleMove)
    return () => window.removeEventListener('mousemove', handleMove)
  }, [])
  return pos                         // 返回数据，不是 JSX
}
// 用：const pos = useMousePosition()
```

### 12.3 案例：useLocalStorage（组合 Hook）

组合 `useState` + `useEffect`，对外暴露和 `useState` 一样的接口，但值会持久化。

```jsx
// src/hooks/useLocalStorage.js
function useLocalStorage(key, initialValue) {
  const [value, setValue] = useState(() => {
    const saved = localStorage.getItem(key)
    return saved !== null ? JSON.parse(saved) : initialValue
  })
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(value))
  }, [key, value])
  return [value, setValue]
}
```

### 12.4 案例：useToggle（封装 useState）

```jsx
// src/hooks/useToggle.js
function useToggle(initial = false) {
  const [value, setValue] = useState(initial)
  const toggle = (next) => {
    setValue((prev) => (typeof next === 'boolean' ? next : !prev))
    //                                  ↑ prev 就是 value（同一个当前值），由 React 传入
  }
  return [value, toggle]
}
```

> 关于 `prev`：它就是 `value`（同一个当前 state），只是 React 在 `setValue` 内部调用你的函数时把它当参数传进来。新值依赖旧值（取反、累加、追加）时，都用函数式更新 `setValue((prev) => ...)`。

---

## 十三、Hook 使用规范

### 13.1 两条铁律

1. **只在顶层调用** —— 不能放 `if` / 循环 / 嵌套函数里
2. **只在函数组件或自定义 Hook 里调用** —— 不能在普通函数 / 事件处理函数里

项目 `.oxlintrc.json` 把 `react/rules-of-hooks` 设成了 `error`，违规直接报红。

### 13.2 为什么这么设计

React 靠**「Hook 的调用顺序」**给每个 Hook 配对 state（第一个 → state[0]，第二个 → state[1]……）。因为 JS 不给每次函数调用自动分配 id，顺序是唯一稳定的标识。一旦把 Hook 放进条件里，某次渲染可能少执行一行 → 顺序错乱 → state 配对错位。

> 这是「简洁 vs 灵活」的折中：React 选了零样板（写 `useState(0)` 就行），代价是必须遵守两条铁律。

---

## 十四、综合案例：请求接口的评论列表（src/comment3/）

教程三要求：① 请求接口获取列表 ② 自定义 Hook 封装请求 ③ 每项抽成独立组件。

### 14.1 json-server 搭建模拟接口

```bash
npm install --save-dev json-server@0.17.4   # 装一次
npm run server                               # 启动：json-server --watch db.json --port 3004
```

`db.json` 里放一个 `list` 数组，访问 `http://localhost:3004/list` 即可拿到。

### 14.2 useComments 自定义 Hook 封装请求

```jsx
// src/comment3/useComments.js
function useComments(url) {
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false                      // 清除副作用：卸载后别再 setState
    const fetchData = async () => {
      setLoading(true)
      try {
        const res = await fetch(url)
        if (!res.ok) throw new Error(`请求失败：${res.status}`)
        const data = await res.json()
        if (!cancelled) setComments(data)
      } catch (e) {
        if (!cancelled) setError(e.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchData()
    return () => { cancelled = true }
  }, [url])

  return { comments, loading, error }
}
```

### 14.3 CommentItem 抽离独立组件

```jsx
// src/comment3/CommentItem.jsx
function CommentItem({ comment }) {
  return (
    <li className={styles.item}>
      <div className={styles.avatar}>{comment.author.slice(0, 1)}</div>
      <div className={styles.body}>
        <div className={styles.header}>
          <span className={styles.author}>{comment.author}</span>
          <span className={styles.date}>{comment.date}</span>
        </div>
        <p className={styles.content}>{comment.content}</p>
        <span className={styles.likes}>👍 {comment.likes}</span>
      </div>
    </li>
  )
}
```

### 14.4 CommentApp 使用

```jsx
function CommentApp() {
  const { comments, loading, error } = useComments('http://localhost:3004/list')
  return (
    <div className={styles.container}>
      {loading && <p>⏳ 加载中...</p>}
      {error && <p>❌ 出错了：{error}</p>}
      {!loading && !error && (
        <ul>
          {comments.map((c) => <CommentItem key={c.id} comment={c} />)}
        </ul>
      )}
    </div>
  )
}
```

请求细节全封进 Hook，组件只管「拿数据 → 渲染」。

---

## 十五、总结

今天学到的：

- 受控表单：`value` + `onChange`，state 驱动 UI 的闭环
- 受控 vs 非受控：数据源、重渲染、实时校验、file 例外
- 为什么不建议直接操作 DOM：覆盖、数据流、优化
- `useRef` 获取 DOM：聚焦、测尺寸，DOM 操作放 `useEffect`
- 综合案例①：从零重写「发表评论」（受控表单 + 不可变 + 列表渲染）
- 清空 + 聚焦：受控 `setState` 清空、`useRef` 聚焦，状态在父 / DOM 在子各司其职
- 组件样式复用：`className` / `variant` / `style`
- UUID 与时间：`crypto.randomUUID`、`Date` 格式化、相对时间
- 组件通信四件套：父→子 props、子→父回调、兄弟状态提升、跨层级 Context
- `useEffect`：副作用在渲染后跑；依赖数组控制时机；return 清理函数防泄漏
- 自定义 Hook：`useXxx` 复用带状态的逻辑（鼠标、本地存储、切换、请求）
- Hook 规范：只在顶层 + 只在组件/自定义 Hook；背后是调用顺序对应 state
- 综合案例②：json-server 搭接口 + `useComments` 封装请求 + `CommentItem` 抽组件

下一步可以继续学习：

- `useMemo` / `useCallback` 性能优化
- `useRef` 进阶（forwardRef / useImperativeHandle）
- React Router 路由
- 状态管理库（zustand / redux）
- TypeScript 化

---

*文章为 React 12 天学习计划第 2 天笔记，代码位于 `react-basic` 项目（`src/components/`、`src/hooks/`、`src/comment2/`、`src/comment3/`）。*
