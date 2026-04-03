# Session Compact 设计参考

> 本文档记录 Claude Code auto-compact 的核心设计思想，作为本 skill 的理论基础。
> 源自对 Claude Code 源码泄露（2026-03-31）的分析。

---

## 一、核心问题

长会话中，上下文空间被以下内容持续消耗：

| 组件 | 典型占用 | 压缩后保留？ |
|------|---------|------------|
| 系统提示 + 内置工具 | ~20,000 tokens | ✅ 保留 |
| Memory 文件 (MEMORY.md) | ~200 行 | ✅ 保留 |
| 对话历史 + 工具输出 | 100K-140K tokens | ❌ 被压缩 |

**关键洞察**：工具输出（文件读取、搜索结果、命令输出）占总上下文的 60-80%，是首要清理目标。

---

## 二、三级压缩策略（Claude Code 设计）

```
Micro Compact（微压缩）
  ↓ 清理过期的大型工具结果，不调用 API
Session Memory Compact（会话内存压缩）
  ↓ 零 API 调用，用已有 memory 文件替代早期消息
Full Compact via LE6（完整压缩）
  ↓ 调用 Claude API 生成智能摘要
  ↓ 恢复关键附件（文件、计划、已激活技能）
```

### 2.1 Micro Compact（microCompact.ts）

- **触发**：对话间隔超过 60 分钟，或主动调用
- **操作**：将特定工具的旧输出替换为 `[Old tool result content cleared]`
- **保留**：最近 5 个工具调用结果（keepRecent=5）
- **目标工具**：Read、Bash、Glob、Grep、LS、WebFetch、WebSearch

### 2.2 Session Memory Compact（sessionMemoryCompact.ts）

- **触发**：会话 token 积累达到 10K-40K 时
- **操作**：用 session memory 文件内容替代被切割的消息
- **边界感知**：不在工具调用-结果对中间切断（B87() 边界修正函数）
- **成本**：零 API 调用

### 2.3 Full Compact（compact.ts）

- **触发**：有效窗口使用率达到阈值（窗口大小 - 20K输出预留 - 13K缓冲）
- **操作**：调用 Claude API，将 100K+ tokens 压缩至 5K-10K 的摘要
- **恢复**：压缩后重新附加最近 5 个读取文件（最多 50K tokens）

---

## 三、Session Memory 模板（Claude Code 原版）

Claude Code 使用以下 10 节结构存储会话记忆：

```markdown
# Session Title          → 5-10字简洁标题
# Current State          → 当前正在做什么，下一步是什么
# Task specification     → 用户要求做什么，设计决策
# Files and Functions    → 重要文件和函数
# Workflow               → 常用命令及执行顺序
# Errors & Corrections   → 遇到的错误和修复方案
# Codebase Documentation → 重要系统组件
# Learnings              → 什么有效，什么无效
# Key results            → 用户要求的具体输出
# Worklog                → 逐步操作记录（极简）
```

**写作规则**（必须遵守）：
1. 不修改节标题（# 开头）
2. 不修改节描述（_斜体_ 行）
3. 内容要「信息密集」：包含文件路径、函数名、错误信息、精确命令
4. 每节限制约 2,000 tokens
5. 整个文件限制 12,000 tokens

---

## 四、什么信息必须保留

压缩时，以下信息绝对不能丢失：

- ✅ 当前进行中的任务状态（Current State）
- ✅ 修改过的文件路径（精确到文件名）
- ✅ 重要的架构决策
- ✅ 遇到的错误及其修复方案
- ✅ 用户明确要求保留的内容

以下可以安全清理：

- ❌ 中间调试输出
- ❌ 已解决问题的讨论过程
- ❌ 重复的工具输出（保留最新的）
- ❌ 超长的搜索结果（保留摘要/关键点）

---

## 五、本 Skill 的适配方案

WorkBuddy 的记忆体系对应关系：

| Claude Code 概念 | WorkBuddy 对应 |
|----------------|---------------|
| Session Memory | `.workbuddy/memory/YYYY-MM-DD.md` |
| MEMORY.md | `.workbuddy/memory/MEMORY.md` |
| CLAUDE.md | SOUL.md / MEMORY.md |
| Session History (.jsonl) | 对话本身（无持久化） |

**核心差异**：WorkBuddy 没有 session history 文件，所以「恢复上下文」完全依赖 MEMORY.md 和日志文件的质量。这意味着压缩前必须确保关键信息已写入持久化文件。

---

## 六、触发信号

以下场景应触发 session-compact skill：

1. 用户明确说「上下文快满了」「context 告急」「快撑不住了」
2. 用户说「要重启会话」「开个新对话」「换个 session」
3. AI 感知到回复质量下降（开始重复历史、遗忘早期决策）
4. 对话轮次超过 50 轮且任务尚未完成

---

## 七、压缩后的会话衔接 Prompt 模板

重启新会话时，建议用户发送以下内容：

```
上一会话已执行 session-compact。请先读取以下文件恢复工作上下文：
1. ~/.workbuddy/memory/MEMORY.md（长期记忆）
2. .workbuddy/memory/YYYY-MM-DD.md（最新日志）

读取完成后，直接从上次停下的地方继续，不需要确认或复述摘要。
```

---

*参考来源：Claude Code 源码分析（shenhan.cc/projects/claude-code/05_module_context.html）及 Morph 团队分析报告*
