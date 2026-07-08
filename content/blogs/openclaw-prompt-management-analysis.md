---
title: "OpenClaw 提示词管理系统深度剖析"
slug: openclaw-prompt-management-analysis
date: 2026-07-08T12:00:00+08:00
draft: false
tags: ["AI", "LLM", "Agent", "提示词工程", "源码分析", "OpenClaw"]
categories: ["技术笔记"]
---

> 目标读者：核心开发者 / 贡献者  
> 范围：OpenClaw 运行时如何为每一次 Agent 运行组装、缓存、注入 system prompt，以及 Skill prompt、Provider 贡献、子代理提示词等周边机制。

---

## 1. 引言：什么在管理“提示词”

在 OpenClaw 中，所谓“提示词管理”并不是单一文件或类，而是一个**以 `src/agents/system-prompt.ts` 为核心的分层装配流水线**。它的输入是：

- 当前 Agent 的配置（`openclaw.json`）
- 运行时事实（workspace、channel、capabilities、tools、sandbox、model 等）
- 项目上下文文件（`AGENTS.md`、`SOUL.md`、`TOOLS.md`、`MEMORY.md`、`HEARTBEAT.md`、`BOOTSTRAP.md`）
- Skill 元数据与可用技能列表
- Provider 插件贡献的模型专属提示词片段

输出是**一个完整的 system prompt 字符串**，被注入到 LLM 请求中。所有与“最终 prompt 长什么样”相关的决策，几乎都在这条流水线里完成。

文档 `docs/concepts/system-prompt.md` 是这套系统的官方设计说明；本文则从源码层面系统化拆解其结构、数据流与扩展点。

---

## 2. 总体架构：三层流水线

官方文档把 system prompt 组装划分为三层：

1. **渲染层（Renderer）** — `src/agents/system-prompt.ts`  
   纯函数 `buildAgentSystemPrompt`，只接受显式参数，不直接读全局配置。
2. **配置解析层（Config Resolver）** — `src/agents/system-prompt-config.ts`  
   `resolveAgentSystemPromptConfig` 把 `openclaw.json` 里与 prompt 相关的字段解析成渲染层能理解的参数。
3. **运行时适配层（Runtime Adapters）** — 分散在 embedded runner、CLI、auto-reply、compaction 等模块  
   收集实时事实（tools、sandbox、channel capabilities、context files、provider contributions），调用配置过的 prompt facade。

这种分层的目的：让导出/调试 prompt 表面与真实运行保持一致，同时避免把每个运行时细节都塞进一个巨型 builder。

```
openclaw.json + agent defaults
        │
        ▼
resolveAgentSystemPromptConfig
        │
        ▼
embedded/cli/auto-reply runtime  ──►  buildAgentSystemPrompt  ──►  system prompt string
        │                                    ▲
        └──── runtime facts ────────────────┘
              tools, channel, sandbox,
              context files, provider contrib
```

---

## 3. 渲染层核心：`src/agents/system-prompt.ts`

### 3.1 入口函数

`buildAgentSystemPrompt(params)` 是核心入口（`src/agents/system-prompt.ts:682`）。它接收一个庞大的 options 对象，涵盖：

- `workspaceDir`：工作目录
- `toolNames` / `capabilityToolNames` / `toolSummaries`：可用工具
- `contextFiles`：项目上下文文件数组
- `bootstrapMode` / `bootstrapTruncationNotice`：BOOTSTRAP 状态
- `skillsPrompt` / `heartbeatPrompt`：技能与心跳提示词
- `runtimeInfo`：agentId、session、channel、capabilities、model 等
- `promptMode`：`full` | `minimal` | `none`
- `silentReplyPromptMode` / `sourceReplyDeliveryMode`：回复投递模式
- `subagentDelegationMode` / `acpEnabled`：子代理/ACP 配置
- `promptSurface`：prompt 表面类型
- `promptContribution`：Provider 贡献
- 各种 owner、timezone、TTS、model alias、memory、sandbox 等配置

函数内部按顺序拼接固定区块，最终返回一个字符串。

### 3.2 Prompt 模式

类型定义在 `src/agents/system-prompt.types.ts`：

```ts
export type PromptMode = "full" | "minimal" | "none";
export type SilentReplyPromptMode = "generic" | "none";
```

- `full`：主 Agent，包含所有区块。
- `minimal`：子代理，省略 Memory、Self-Update、Model Aliases、User Identity、Messaging、Silent Replies、Heartbeats 等。
- `none`：只保留基础身份行。

`isMinimal` 在渲染器内部被频繁用来开关各区块。

### 3.3 固定区块与职责

| 区块 | 构建函数 | 说明 |
|------|---------|------|
| Tooling | 主函数内联 | 列出可用工具、tool schema 延迟加载提示、工作流提示 |
| Sub-Agent Delegation | `buildSubagentDelegationPreferenceSection` | `prefer` 模式下强化子代理委派 |
| Tool Call Style | `buildOverridablePromptSection` | 可被 Provider 覆盖 |
| Execution Bias | `buildExecutionBiasSection` | 强调“ actionable request 立即行动” |
| Safety | 主函数内联 | 防止权力寻求、绕过监管 |
| OpenClaw Control | 主函数内联 | 优先用 `gateway` 工具，不 invent 命令 |
| OpenClaw Self-Update | 主函数内联 | `gateway` 配置/更新指南 |
| Skills | `buildSkillsSection` | 如何按需读取 SKILL.md |
| Skill Workshop | `buildSkillWorkshopPromptSection` | Skill Workshop 工具说明 |
| Memory | `buildMemorySection` | memory 工具与引用模式 |
| Workspace | 主函数内联 | 工作目录、FS policy |
| Documentation | `buildDocsSection` | docs/source 路径 |
| Project Context | `buildProjectContextSection` | 注入的上下文文件 |
| Assistant Output Directives | `buildAssistantOutputDirectivesSection` | `MEDIA:`、`message` tool 输出规则 |
| Silent Replies | 主函数内联 | `NO_REPLY` 规则 |
| Webchat Canvas | `buildWebchatCanvasSection` | webchat 富渲染 |
| Messaging | `buildMessagingSection` | 当前会话/跨会话消息、子代理编排 |
| Voice | `buildVoiceSection` | TTS hint |
| Heartbeats | `buildHeartbeatSection` | 心跳轮询行为 |
| Runtime | 主函数内联 + `buildRuntimeLine` | 运行时元数据 |

### 3.4 项目上下文文件处理

`contextFiles` 是 `EmbeddedContextFile[]`。渲染器会：

1. 过滤掉无效路径。
2. 按 `CONTEXT_FILE_ORDER` 排序：`agents.md` → `soul.md` → `identity.md` → `user.md` → `tools.md` → `bootstrap.md` → `memory.md`。
3. 区分 stable 与 dynamic 文件；目前 `HEARTBEAT.md` 是唯一的 dynamic 文件。
4. 对 `HEARTBEAT.md` 内容做特殊过滤，防止触发 Claude Code 订阅模式拒绝。
5. 渲染为 `## <path>` 段落。

### 3.5 缓存边界与 Stable Prefix 缓存

OpenClaw 在 prompt 中插入一个内部缓存边界 `SYSTEM_PROMPT_CACHE_BOUNDARY`（定义在 `src/agents/system-prompt-cache-boundary.ts`）。

- **Stable Prefix**（边界之上）：项目上下文、工具说明、Safety、Workspace 等跨 turn 变化较小的内容。
- **Dynamic Suffix**（边界之下）：Messaging、Runtime、Heartbeat、Group Chat Context 等随 turn 变化的内容。

为了进一步提升性能，`buildAgentSystemPrompt` 对 stable prefix 做了**进程内 LRU 缓存**：

```ts
const stablePromptPrefixCache = new Map<string, StablePromptPrefixCacheEntry>();
const SYSTEM_PROMPT_STABLE_PREFIX_CACHE_LIMIT = 64;
```

缓存 key 通过对一组稳定输入做 `sha256` 得到（`hashStablePromptInput`），包含 workspaceDir、toolLines、ownerLine、reasoningLevel、runtimeChannel、capabilities、context files 等。

### 3.6 工具名称解析

渲染器内部维护了一个 `canonicalByNormalized` Map，保留调用方传入的工具大小写，同时按小写去重：

```ts
const canonicalByNormalized = new Map<string, string>();
for (const name of canonicalToolNames) {
  const normalized = name.toLowerCase();
  if (!canonicalByNormalized.has(normalized)) {
    canonicalByNormalized.set(normalized, name);
  }
}
```

核心工具按固定 `toolOrder` 输出，额外工具按字母排序输出。

---

## 4. 配置解析层：`src/agents/system-prompt-config.ts`

### 4.1 职责

这一层把 `openclaw.json` 的复杂配置映射为 `buildAgentSystemPrompt` 的参数。核心函数：

- `resolveAgentSystemPromptConfig({ config, agentId })`（`src/agents/system-prompt-config.ts:35`）
- `buildConfiguredAgentSystemPrompt(params)`（`src/agents/system-prompt-config.ts:58`）

### 4.2 解析的字段

```ts
type ResolvedAgentSystemPromptConfig = Pick<
  AgentSystemPromptRenderParams,
  | "ownerDisplay"
  | "ownerDisplaySecret"
  | "subagentDelegationMode"
  | "ttsHint"
  | "modelAliasLines"
  | "memoryCitationsMode"
  | "fsWorkspaceOnly"
>;
```

- `ownerDisplay` / `ownerDisplaySecret`：来自 `resolveOwnerDisplaySetting`
- `subagentDelegationMode`：从 `config.agents.list[].subagents.delegationMode` 或 defaults 读取，默认 `suggest`
- `ttsHint`：来自 `buildTtsSystemPromptHint`
- `modelAliasLines`：来自 `buildModelAliasLines`
- `memoryCitationsMode`：`config.memory.citations`
- `fsWorkspaceOnly`：`resolveEffectiveToolFsWorkspaceOnly`

这样，渲染层本身不需要知道 `openclaw.json` 的结构；测试渲染层时也可以直接传参。

---

## 5. 提示词表面与运行时适配

### 5.1 Prompt Surface：`src/agents/prompt-surface.ts`

Prompt Surface 决定工具提示词如何根据运行环境变化。类型 `AgentPromptSurfaceKind` 来自 `src/plugins/types.ts`，常见值：

- `openclaw_main`：标准 OpenClaw 运行时
- `subagent`：子代理
- `acp_backend`：ACP harness（如 Codex）

`resolveAgentPromptSurfaceForSessionKey` 根据 session key 判断 surface：

```ts
export function resolveAgentPromptSurfaceForSessionKey(sessionKey?: string): AgentPromptSurfaceKind {
  if (sessionKey && isAcpSessionKey(sessionKey)) {
    return "acp_backend";
  }
  return sessionKey && isSubagentSessionKey(sessionKey) ? "subagent" : "openclaw_main";
}
```

`buildOpenClawToolFallbackText` 在 `openclaw_main` 表面下提供完整工具说明；在其他表面下只给出通用提示。

### 5.2 子代理提示词：`src/agents/subagent-system-prompt.ts`

`buildSubagentSystemPrompt` 生成子代理会话的专属提示词，包含：

- Your Role：明确只是执行任务，不是主 Agent
- Rules：专注、完成任务、不主动、不心跳、信任 push-based completion
- Output Format：最终回复应包含什么
- Sub-Agent Spawning：是否能继续 spawn（由 `childDepth` 与 `maxSpawnDepth` 决定）
- Session Context：requester session、channel 等

### 5.3 心跳提示词：`src/agents/heartbeat-system-prompt.ts`

为 heartbeat 轮询提供行为规则，例如无事项时回复 `HEARTBEAT_OK`。

### 5.4 Bootstrap 提示词：`src/agents/bootstrap-prompt.ts`

处理 `BOOTSTRAP.md` 的两种模式：

- `full`：完整 BOOTSTRAP 工作流
- `limited`：受限运行，提示 Agent 无法安全完成完整流程

---

## 6. Provider 贡献机制

### 6.1 类型：`src/agents/system-prompt-contribution.ts`

Provider 可以通过 `ProviderSystemPromptContribution` 在不替换整个 prompt 的前提下影响最终输出：

```ts
export type ProviderSystemPromptContribution = {
  stablePrefix?: string;           // 缓存边界之上
  dynamicSuffix?: string;          // 缓存边界之下
  sectionOverrides?: Partial<Record<
    ProviderSystemPromptSectionId,
    string
  >>;
};
```

可覆盖的 section：

- `interaction_style`
- `tool_call_style`
- `execution_bias`

### 6.2 GPT-5 覆盖：`src/agents/gpt5-prompt-overlay.ts`

针对 OpenAI GPT-5 家族的 overlay，添加模型专属指导：persona latching、concise output、tool discipline、parallel lookup、deliverable coverage 等。

### 6.3 处理流程

在 `buildAgentSystemPrompt` 中：

1. `normalizeProviderPromptBlock` 对 contribution 文本做归一化（去回车、去行尾空白、trim）。
2. `providerStablePrefix` 在 stable prefix 区域追加。
3. `providerSectionOverrides` 通过 `buildOverridablePromptSection` 替换对应区块。
4. `providerDynamicSuffix` 在 dynamic 区域追加。

---

## 7. Skill 提示词管理

Skill 不是直接塞进 system prompt 的大段文本，而是通过**可用技能列表**让模型按需读取。

### 7.1 技能格式化：`src/skills/loading/skill-contract.ts`

`formatSkillsForPrompt(skills)` 把 skill 列表渲染为 XML：

```xml
<available_skills>
  <skill>
    <name>...</name>
    <description>...</description>
    <location>...</location>
    <version>sha256:...</version>
  </skill>
</available_skills>
```

模型被指示：当任务匹配描述时，用 `read` 工具读取对应 `SKILL.md`。

### 7.2 技能解析与预算：`src/skills/loading/workspace.ts`

`resolveSkillsPromptForRun`（`src/skills/loading/workspace.ts:1503`）决定最终注入的 skill prompt：

1. 如果 `skillsSnapshot.prompt` 存在，优先使用 snapshot。
2. 否则从 `entries` 构建：
   - `buildWorkspaceSkillsPrompt` 筛选 eligible skills
   - `compactSkillPaths` 压缩路径（如 `~/...`）
   - `applySkillsPromptLimits` 应用字符预算
   - `buildRenderedSkillsPrompt` 渲染最终文本

预算来源：

- 全局默认：`skills.limits.maxSkillsPromptChars`
- 单 Agent 覆盖：`agents.list[].skillsLimits.maxSkillsPromptChars`

### 7.3 Skill Prompt Blob：`src/config/sessions/skill-prompt-blobs.ts`

当 skill prompt 很大时，OpenClaw 会把它外置到内容寻址的 blob 文件，而不是直接内联在 session store 中：

- 目录：`skills-prompts/sha256/<prefix>/<hash>.txt`
- 阈值：`MIN_PROMPT_BLOB_CHARS = 512`
- 上限：`MAX_PROMPT_BLOB_BYTES = 512 * 1024`

关键函数：

- `projectSessionStoreForPersistence`：把 store 中 inline 的 skill prompt 替换为 `promptRef`
- `ensureSessionStorePromptBlobsForPersistence`：确保 blob 文件写入
- `hydrateSessionStoreSkillPromptRefs`：从 blob 还原 prompt；若 blob 缺失/损坏则删除整个 snapshot

这减少了 session store 体积，同时保证内容寻址的完整性。

---

## 8. 缓存稳定性与文本归一化

### 8.1 `src/agents/prompt-cache-stability.ts`

提供两个核心工具：

- `normalizeStructuredPromptSection(text)`：统一换行符、去掉行尾空白、trim。用于 prompt 哈希或快照比较前。
- `normalizePromptCapabilityIds(capabilities)`：小写、去重、排序 capability ids，保证 prompt payload 稳定。

### 8.2 `src/agents/sanitize-for-prompt.ts`

`sanitizeForPromptLiteral` 对要插入 prompt 的字符串做转义处理，防止破坏提示词结构。

---

## 9. 测试与快照机制

### 9.1 单元测试

- `src/agents/system-prompt.test.ts`：主渲染器行为
- `src/agents/prompt-composition.test.ts`：prompt 组合
- `src/agents/system-prompt-cache-boundary.test.ts`：缓存边界
- `src/agents/system-prompt-stability.test.ts`：稳定性归一化
- `src/agents/prompt-overlay-runtime-contract.test.ts`：overlay 运行时契约
- `src/skills/loading/prompt-resolution.test.ts`：skill prompt 解析

### 9.2 Prompt 快照

目录：`test/fixtures/agents/prompt-snapshots/codex-runtime-happy-path/`

这些快照覆盖 Telegram direct、Discord group、heartbeat 等典型 turn，包含：

- 固定的 Codex `gpt-5.5` model prompt fixture
- OpenClaw developer instructions
- turn-scoped collaboration-mode instructions
- user turn input
- dynamic tool specs 引用

生成与校验命令：

```bash
pnpm prompt:snapshots:gen      # 重新生成
pnpm prompt:snapshots:check    # 校验漂移
pnpm prompt:snapshots:sync-codex-model  # 同步 Codex model fixture
```

CI 在 boundary shard 中运行 drift check，确保 prompt 变更与快照更新绑定在同一 PR。

---

## 10. 扩展与定制指南

### 10.1 修改 System Prompt 内容

直接编辑 `src/agents/system-prompt.ts` 中对应区块的构建函数。注意：

- 保持缓存边界上下内容的语义区分。
- 若新增跨 turn 稳定内容，考虑加入 stable prefix cache key。
- 若新增 Provider 可覆盖区块，在 `ProviderSystemPromptSectionId` 中声明。

### 10.2 添加新的 Provider 覆盖

1. 在 `src/agents/system-prompt-contribution.ts` 的 `ProviderSystemPromptSectionId` 中扩展可覆盖区块（如需）。
2. Provider 插件在运行时返回 `ProviderSystemPromptContribution`。
3. 渲染层通过 `buildOverridablePromptSection` 合并。

### 10.3 添加新的 Prompt Surface

1. 在 `src/plugins/types.ts` 扩展 `AgentPromptSurfaceKind`。
2. 在 `src/plugins/agent-prompt-surface-kind.ts` 添加归一化判断。
3. 在 `src/agents/prompt-surface.ts` 添加对应 fallback 文本与 workflow hint 规则。

### 10.4 扩展 Skill 提示词

Skill 本身的文本由 skill 作者决定；OpenClaw 侧主要控制：

- `formatSkillsForPrompt`：修改 XML 格式
- `applySkillsPromptLimits`：修改预算逻辑
- `skill-prompt-blobs.ts`：修改 blob 阈值或存储布局

### 10.5 调试

- 使用 `/context list` 或 `/context detail` 查看每个注入文件对 prompt 的贡献。
- 运行 `openclaw status` 查看当前会话状态。
- 查看 `test/fixtures/agents/prompt-snapshots/` 对比预期输出。

---

## 11. 关键数据流总结

一次典型 Agent 运行的 prompt 组装流程：

```
1. 运行时（embedded/cli/auto-reply）收集事实
   ├─ tools, capabilities, channel, chatType
   ├─ workspaceDir, contextFiles
   ├─ sandboxInfo, runtimeInfo
   ├─ skillsPrompt / heartbeatPrompt
   └─ provider prompt contribution

2. resolveAgentSystemPromptConfig({ config, agentId })
   └─ 解析 ownerDisplay、ttsHint、modelAliasLines、
      subagentDelegationMode、memoryCitationsMode、fsWorkspaceOnly

3. buildConfiguredAgentSystemPrompt({ ...runtimeFacts, ...configParams })
   └─ 调用 buildAgentSystemPrompt

4. buildAgentSystemPrompt 内部
   ├─ 计算 stable prefix cache key
   ├─ 命中缓存则复用；否则构建 stable prefix
   │   ├─ Tooling、Safety、Skills、Memory、Workspace、Project Context
   │   └─ 插入 SYSTEM_PROMPT_CACHE_BOUNDARY
   ├─ 追加 dynamic suffix
   │   ├─ Messaging、Voice、Group/Subagent Context、Reactions
   │   ├─ Provider dynamicSuffix
   │   └─ Heartbeats、Runtime
   └─ 返回最终字符串

5. 最终 system prompt 进入 LLM 请求
```

---

## 12. 设计取舍与注意点

1. **渲染器保持纯函数**：`buildAgentSystemPrompt` 不直接读全局配置，便于测试和复现。
2. **配置与运行时分离**：配置解析一次，运行时事实每次可能变化。
3. **缓存边界是内部约定**：不是模型 API 的 cache control，而是 OpenClaw 自己用于 stable prefix 缓存和 Provider 贡献分区。
4. **Skill prompt 不内联大文本**：通过 `<available_skills>` 列表 + 按需 `read` 控制上下文窗口。
5. **Blob 外置是存储优化**：不改变 prompt 语义，只是让 session store 更小。
6. **Provider 贡献受限**：只能覆盖三个 section 和注入 prefix/suffix，防止 Provider 破坏 OpenClaw 核心提示词结构。
7. **Prompt 快照是契约测试**：任何对 prompt 文本的修改都会触发快照漂移，强制作者在 PR 中同步更新。

---

## 13. 相关文件索引

| 文件 | 作用 |
|------|------|
| `src/agents/system-prompt.ts` | 核心 system prompt 渲染器 |
| `src/agents/system-prompt.types.ts` | PromptMode / SilentReplyPromptMode 类型 |
| `src/agents/system-prompt-config.ts` | 配置解析层 |
| `src/agents/prompt-surface.ts` | Prompt surface 工具提示 |
| `src/agents/subagent-system-prompt.ts` | 子代理提示词 |
| `src/agents/heartbeat-system-prompt.ts` | 心跳提示词 |
| `src/agents/bootstrap-prompt.ts` | BOOTSTRAP 提示词 |
| `src/agents/system-prompt-contribution.ts` | Provider 贡献类型 |
| `src/agents/gpt5-prompt-overlay.ts` | GPT-5 overlay |
| `src/agents/prompt-cache-stability.ts` | 缓存稳定性归一化 |
| `src/agents/sanitize-for-prompt.ts` | Prompt 字面量清理 |
| `src/agents/system-prompt-cache-boundary.ts` | 缓存边界标记 |
| `src/plugins/agent-prompt-surface-kind.ts` | Surface kind 归一化 |
| `src/skills/loading/skill-contract.ts` | Skill XML 格式化 |
| `src/skills/loading/workspace.ts` | Skill prompt 解析与预算 |
| `src/config/sessions/skill-prompt-blobs.ts` | Skill prompt blob 存储 |
| `docs/concepts/system-prompt.md` | 官方设计文档 |
| `test/fixtures/agents/prompt-snapshots/` | 提交级 prompt 快照 |

---

## 14. 结语

OpenClaw 的提示词管理系统是一个**高度结构化、分层、可测试、可扩展**的装配流水线。它把“最终 prompt 是什么”这个问题拆成了：

- 配置解析
- 运行时事实收集
- 纯函数渲染
- Provider 贡献合并
- Skill 提示词按需注入
- 缓存与存储优化

理解这条流水线的关键是抓住三个层次和三个边界：

- **三层**：渲染器、配置解析器、运行时适配器
- **三边界**：stable/dynamic prompt 缓存边界、Provider 贡献边界、OpenClaw 核心与 Plugin 扩展边界

如果要从一个文件开始阅读，首选 `src/agents/system-prompt.ts`；如果要理解整体契约，先读 `docs/concepts/system-prompt.md`。
