---
title: "React 学习 Day 03:Redux Toolkit、异步状态与 TypeScript"
date: 2026-07-08T12:00:00+08:00
draft: false
tags: ["React", "前端", "学习笔记", "Redux", "Redux Toolkit", "TypeScript", "状态管理"]
categories: ["前端开发"]
---

> 延续 Day01/Day02（`react-basic` 项目），今天进入 `react-redux` 项目，学三块：① 全局状态管理 **Redux Toolkit**；② 异步数据流 **createAsyncThunk + axios**；③ 把项目 **TypeScript 化**。综合案例：用 RTK + axios + TS 重写「评论列表」，并与 Day02 的 `useComments` 版本对比。代码位于 `react-redux` 项目。

---

## 一、为什么需要 Redux

Day02 学过的状态管理方式，覆盖了大多数场景：

| 方式 | 适用 |
|---|---|
| props（父→子） | 父把数据传给子 |
| 回调（子→父） | 子把数据传回父 |
| 状态提升（兄弟） | 兄弟组件共享，提到共同父 |
| Context（跨层级） | 跨多层传值，省去层层转发 |

但当应用变大，这些方式会力不从心：

1. **props 钻取**：状态提升到很高层级后，中间组件被迫一层层转发它根本不关心的 props。
2. **Context 的局限**：适合「低频变化的全局值」（主题、用户信息），不适合「高频更新、多处共享的复杂状态」（评论列表、购物车）——Context 值一变，所有消费组件全量重渲染，难做精细优化。

**Redux 的思路**：把共享状态从「组件内部」搬到「组件外部的一个仓库（store）」，任何组件直接读写，不用层层传递。

> 心智模型：组件只是仓库的「读写者」，仓库是唯一数据源。

---

## 二、Redux 核心概念

**单向数据流**：

```
UI 事件  →  dispatch(action)  →  reducer(state, action)  →  新 state  →  UI 更新
```

| 概念 | 是什么 | 例子 |
|---|---|---|
| **store** | 仓库，存全局 state | `configureStore({...})` |
| **state** | 仓库里的当前数据 | `{ counter: {value:0}, comments:{...} }` |
| **action** | 描述「发生了什么」的对象 | `{ type: 'counter/incremented' }` |
| **reducer** | 纯函数 `(state, action) => newState` | 根据 action 算新 state |
| **dispatch** | 派发 action 触发更新 | `dispatch(incremented())` |

**三个原则**：

1. **单一数据源**：整个应用只有一个 store、一棵 state 树。
2. **state 只读**：唯一改变 state 的方式是 dispatch action。
3. **纯函数改变**：reducer 必须是纯函数（同样输入同样输出，无副作用）。

---

## 三、Redux Toolkit（RTK）

原生 Redux 样板代码多（action type 常量、action creator、reducer 要分开写还要手写不可变更新）。**RTK 是官方推荐的高层封装**，大幅减少样板。

### 3.1 configureStore —— 创建仓库

```ts
// src/store/index.ts
import { configureStore } from '@reduxjs/toolkit'
import counterReducer from './counterSlice'
import commentsReducer from './commentsSlice'

const store = configureStore({
  reducer: {
    counter: counterReducer,    // → state.counter 由它管
    comments: commentsReducer,  // → state.comments 由它管
  },
})
```

`reducer` 配置对象的 **key 就是 state 树的分支名**。`state.counter`、`state.comments` 由此而来——这也是为什么组件里写 `useSelector((state) => state.comments)`。

### 3.2 createSlice —— 切片

一个 slice 管 state 树的一块分支，包含：名字、初始状态、同步 reducers。

```js
// src/store/counterSlice.js
import { createSlice } from '@reduxjs/toolkit'

const initialState = { value: 0 }

const counterSlice = createSlice({
  name: 'counter',
  initialState,
  reducers: {
    incremented: (state) => { state.value += 1 },        // 看似直接改，实则 Immer 代理
    decremented: (state) => { state.value -= 1 },
    reset: (state) => { state.value = 0 },
    incrementedByAmount: (state, action) => { state.value += action.payload },
  },
})

export const { incremented, decremented, reset, incrementedByAmount } = counterSlice.actions
export default counterSlice.reducer
```

几个关键点：

- `reducers` 里的写法像「直接修改 state」(`state.value += 1`)，但 RTK 内部用 **Immer**，实际产出的是不可变更新。所以**不用手写 `...state` 展开**。
- `counterSlice.actions` 自动生成 action creator：`incremented()` 返回 `{ type: 'counter/incremented' }`。
- action type 自动拼成 `name/reducer名`（`counter/incremented`），不用手写 type 常量。

---

## 四、React-Redux：连接 React 和 Redux

Redux 是独立的状态库，要和 React 连起来用 `react-redux`。

### 4.1 Provider —— 注入仓库

```jsx
// src/main.jsx
import { Provider } from 'react-redux'
import store from './store'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Provider store={store}>
      <App />
    </Provider>
  </StrictMode>,
)
```

`Provider` 把 store 放进 React 上下文，它内部的所有组件都能访问同一个 store。

### 4.2 useSelector / useDispatch —— 读写仓库

```jsx
// src/App.jsx
import { useSelector, useDispatch } from 'react-redux'
import { incremented, decremented, reset, incrementedByAmount } from './store/counterSlice'

function App() {
  const count = useSelector((state) => state.counter.value)  // 读
  const dispatch = useDispatch()                              // 拿派发器

  return (
    <>
      <button onClick={() => dispatch(decremented())}>-1</button>
      <span>Count is {count}</span>
      <button onClick={() => dispatch(incremented())}>+1</button>
    </>
  )
}
```

- **useSelector**：订阅 store，选择器函数 `(state) => ...` 返回组件需要的那块数据；那块数据变了，组件才重渲染。
- **useDispatch**：拿到 `dispatch`，用来派发 action。

完整数据流（点 +1）：

```
点击 +1  →  dispatch(incremented())  →  reducer 把 value+1  →  state 更新
       →  useSelector 订阅到变化  →  count 变  →  按钮文案更新
```

---

## 五、异步状态：createAsyncThunk

### 5.1 同步 reducer 的局限

`counterSlice` 的 `reducers` 处理的是同步操作。但「发请求拿数据」是异步的，而 **reducer 必须是纯函数，不能有副作用**（不能在 reducer 里发请求）。怎么把异步请求的结果送进 store？

### 5.2 createAsyncThunk

```ts
// src/store/commentsSlice.ts
export const fetchComments = createAsyncThunk<Comment[], void, { rejectValue: string }>(
  'comments/fetchComments',
  async (_, { rejectWithValue }) => {
    try {
      const response = await axios.get<Comment[]>('http://localhost:3004/list')
      return response.data
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : '未知错误')
    }
  },
)
```

`createAsyncThunk` 接收一个 async 函数，**自动派发三个 action**：

| 生命周期 | 触发时机 | payload |
|---|---|---|
| `pending` | 请求发出时 | 无 |
| `fulfilled` | 成功时 | async 函数的返回值 |
| `rejected` | 失败时 | `rejectWithValue` 传的值 |

### 5.3 三态模式：loading / error / items

异步请求天然有三种状态，用三个字段表达：

```ts
interface CommentsState {
  items: Comment[]      // 数据
  loading: boolean      // 是否请求中
  error: string | null  // 错误信息
}
```

这是异步数据获取的**通用模板**，几乎所有「请求 + 展示」的场景都这套。

### 5.4 extraReducers 处理三个生命周期

`reducers` 管同步 action，`extraReducers` 管 thunk 派发的异步 action：

```ts
const commentsSlice = createSlice({
  name: 'comments',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchComments.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchComments.fulfilled, (state, action) => {
        state.loading = false
        state.items = action.payload
      })
      .addCase(fetchComments.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload ?? '请求失败'
      })
  },
})
```

整块状态在请求过程中的变化：

| 阶段 | items | loading | error |
|---|---|---|---|
| 初始（initialState） | `[]` | `false` | `null` |
| pending | `[]` | `true` | `null` |
| fulfilled | `[评论数据]` | `false` | `null` |
| rejected | `[]` | `false` | `"错误信息"` |

组件 `useSelector(state => state.comments)` 拿到的，就是这张表里**当前那一行**。

### 5.5 组件里触发请求

```tsx
// src/components/CommentList.tsx
const { items, loading, error } = useAppSelector((state) => state.comments)
const dispatch = useAppDispatch()

useEffect(() => {
  dispatch(fetchComments())
}, [dispatch])
```

**为什么放 `useEffect` 里**：

1. React 渲染必须保持纯净，发请求是副作用，不能在渲染期做，要放进 effect。
2. 控制只请求一次——`dispatch` 引用在组件生命周期里稳定不变，所以 `[dispatch]` 等价于空依赖，effect 只在挂载时跑一次。

> 注意：`extraReducers` 回调里的 `state` 参数，是**这块分支本身**（即 `state.comments`），不是整棵树。所以直接写 `state.items`，不用 `state.comments.items`——`combineReducers` 会把对应分支喂给子 reducer。

---

## 六、网络请求：fetch → axios

### 6.1 两种写法对比

| 维度 | fetch | axios |
|---|---|---|
| 状态码判断 | 手动 `if (!response.ok) throw` | 4xx/5xx **自动抛错**，直接进 catch |
| JSON 解析 | 手动 `await response.json()` | **自动解析**，数据在 `response.data` |
| 错误信息 | 普通 `Error` | 丰富（`error.response.status` / `.data` 等） |
| 取消请求 | `AbortController` | `CancelToken` / `AbortController` |

### 6.2 改造

fetch 版要写两步样板：

```js
const res = await fetch(url)
if (!res.ok) throw new Error(`请求失败：${res.status}`)
const data = await res.json()
```

axios 版一步到位：

```js
const response = await axios.get(url)
return response.data
```

少写了「判断 ok」和「解析 json」两步，因为 axios 把它们内置了。

> 一个小提醒：等下一步学了 **RTK Query**，它内置的 `fetchBaseQuery`（基于 fetch）又会把 axios 替代掉。不同层次的工具：axios 是「发请求的」，RTK Query 是「管缓存和状态的」，两者不冲突但层次不同。

---

## 七、TypeScript 化

### 7.1 为什么要 TS（呼应 Day02 的疑问）

Day02 评论列表里 `items: []`，元素字段没声明，`item.auhtor`（拼错）不报错，运行时渲染成 `undefined`，页面空一块还查不到原因。TS 把字段写明白，**拼错编译期就报红**。

### 7.2 定义数据类型

```ts
// src/store/commentsSlice.ts
export interface Comment {
  id: number
  author: string
  content: string
  date: string
  likes: number
}

interface CommentsState {
  items: Comment[]
  loading: boolean
  error: string | null
}
```

`Comment` 就是 Day02 里「代码没写、要从 db.json 反推」的那个结构，现在写明白了，全项目共享。

### 7.3 createAsyncThunk 的泛型

```ts
createAsyncThunk<Comment[], void, { rejectValue: string }>(...)
//              ↑返回值    ↑参数  ↑rejectWithValue 的值类型
```

三个泛型依次是：**返回值类型、参数类型、rejectValue 类型**。标了之后，`fulfilled` 的 `action.payload` 自动是 `Comment[]`，`rejected` 的 `action.payload` 自动是 `string`。

axios 也标泛型：`axios.get<Comment[]>` 让 `response.data` 是 `Comment[]`。

### 7.4 RootState / AppDispatch —— 自动推导

```ts
// src/store/index.ts
export type RootState = ReturnType<typeof store.getState>
export type AppDispatch = typeof store.dispatch
```

**不手写 RootState 的结构**，用 `ReturnType<typeof store.getState>` 从 store 自动推导：

- `typeof store.getState`：取 `store.getState` 这个函数的类型。
- `ReturnType<...>`：提取它的返回值类型，即整棵 state 树。

好处：`store` 配置改了（加新 slice），`RootState` 自动跟着变，单一数据源、永不失同步。字段类型的源头是各 slice 的 `initialState`（`state.counter` 来自 counterSlice，`state.comments` 来自 commentsSlice 的 `CommentsState`）。

### 7.5 带类型的 hooks

原生 `useSelector` 的 `state` 是 `any`，没补全。包装一层：

```ts
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector
export const useAppDispatch: () => AppDispatch = useDispatch
```

组件里用 `useAppSelector` / `useAppDispatch` 替代原生 hooks，`state` 自动是 `RootState`，输入 `state.` 会提示 `counter` / `comments`。这是 RTK + TS 的标准写法。

### 7.6 tsconfig + 渐进迁移

```json
{
  "compilerOptions": {
    "strict": true,        // 严格模式
    "allowJs": true,       // 允许 .js/.jsx 共存
    "checkJs": false,      // 只检查 .ts/.tsx，不检查 .js/.jsx
    "jsx": "react-jsx",
    "noEmit": true         // 只做类型检查，产出交给 vite/esbuild
  }
}
```

`allowJs` + `checkJs: false` = **渐进迁移**：`.ts/.tsx` 有类型检查，`.js/.jsx` 照常运行不报错。所以不必一次全改，可以一个文件一个文件迁。本项目目前 `commentsSlice` / `store/index` / `CommentList` 是 TS，`counterSlice` / `App` / `main` 还是 JS，混合运行无问题。

### 7.7 .ts vs .tsx

| | `.ts` | `.tsx` |
|---|---|---|
| 含 JSX | ❌ | ✅ |
| 用途 | slice、store 配置、工具、hooks 逻辑 | 组件 |
| 泛型箭头 `<T>` | 正常 | 要写 `<T,>`（否则被误认为 JSX 标签） |

**规则：有 JSX → `.tsx`；没 JSX → `.ts`。** 纯逻辑用 `.tsx` 也能跑，但约定用 `.ts`，文件名一眼能看出里面有没有组件。

---

## 八、综合案例：评论列表演进三连对比

同一个需求（请求评论列表 + 处理 loading/error），三种实现，体现心智演进：

| 版本 | 项目 | 实现 | 状态管理 | 适用场景 |
|---|---|---|---|---|
| v1 | `react-basic/comment3` | `useComments`（useEffect + fetch + cancelled） | 组件内 `useState` | 数据只在局部用 |
| v2 | `react-redux` | `commentsSlice`（createAsyncThunk + axios + extraReducers） | 全局 Redux | 数据多处共享、跨组件 |
| v2+ | `react-redux`（TS） | 同 v2 + `Comment` / `RootState` 类型 | 全局 Redux + 类型安全 | 同上，且有类型保障 |

- **v1 → v2**：从「组件自己管状态」到「全局仓库管状态」，数据能跨组件共享。
- **v2 → v2+**：从「运行时才发现拼错」到「编译期就报红」，代码里终于写明了数据结构。
- **下一步 v3**：用 **RTK Query**，几行代码替代整套 `loading/error/items` + `extraReducers` 样板，还自带缓存/去重。

> 三连对比是理解「数据获取演进」最深刻的方式：同一需求、不同解法，优劣一目了然。

---

## 九、坑点与经验

1. **删 `.js` 换 `.ts` 同名，触发 HMR 缓存错乱**：vite 模块图还指向旧 `.js`，浏览器报 `Failed to load .../index.js` 404。代码本身没问题（`tsc` + `build` 都过）。解决：**重启 dev server + 浏览器硬刷新**（Ctrl+Shift+R 清缓存）。
2. **strict 模式下 props 必须标类型**：`.tsx` 里组件 props 不标会报 `implicitly has an 'any' type`。改 `.tsx` 不只是改后缀，要顺手补类型。
3. **`.tsx` 泛型箭头坑**：`const f = <T>(x) => x` 里 `<T>` 被误认 JSX，要写成 `<T,>`。`.ts` 里没这问题。
4. **`dispatch` 引用稳定**：`useDispatch()` 返回的 dispatch 不变，所以 `useEffect` 依赖 `[dispatch]` 等价空依赖，effect 只跑一次。
5. **reducer 里 `state` 是分支不是整棵树**：`commentsSlice` 的 `extraReducers` 里 `state` 就是 `state.comments` 本身，直接 `state.items`，不用 `state.comments.items`。
6. **key 名决定 state 分支**：`store/index` 的 `reducer` 配置里 key 是 `comments`，所以组件写 `state.comments`。它和 slice 的 `name: 'comments'` 没有绑定关系（虽然常同名），改 key 要跟着改组件。
7. **引用路径带显式后缀要更新**：文件从 `.js` 改成 `.ts` 后，引用它的地方若写死 `./store/index.js`，靠 vite 扩展名替换能跑但不规范，应改成 `./store`。

---

## 十、总结

今天学到的：

- **Redux 解决「跨组件共享状态」**：单向数据流 `dispatch → reducer → state → UI`；三个原则（单一数据源、state 只读、纯函数改变）。
- **RTK 大幅减少样板**：`configureStore` 建仓库，`createSlice` 定义切片；Immer 让你「直接改」state 实则不可变更新。
- **React-Redux 连接**：`Provider` 注入 store，`useSelector` 读、`useDispatch` 写。
- **createAsyncThunk 处理异步**：pending/fulfilled/rejected 三态 + loading/error/items 模式，`extraReducers` 消费。
- **fetch → axios**：少写 ok 判断和 json 解析，错误自动抛。
- **TypeScript 化**：`Comment` 类型写明字段、`createAsyncThunk` 泛型、`RootState` 自动推导、`useAppSelector`/`useAppDispatch` 带类型 hooks、`tsconfig` 渐进迁移。
- **综合案例**：评论列表三连对比（`useComments` → `createAsyncThunk` → +TS）。

---

## 下一步

- **`useReducer`**：组件内的「迷你 Redux」，和今天的 Redux 呼应，理解了 Redux 再看它会秒懂。
- **性能优化**：`useMemo` / `useCallback` / `React.memo`（什么时候用、什么时候别用）。
- **React Router**：多页面路由。
- **RTK Query**：评论列表 v3，几行替代整套 loading/error 样板，自带缓存/去重。
- **继续 TS 化**：把 `counterSlice.js` / `App.jsx` / `main.jsx` 也迁成 TS。

---

*文章为 React 12 天学习计划第 3 天笔记，代码位于 `react-redux` 项目（`src/store/`、`src/components/`）。*
