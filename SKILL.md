---
name: session-compact
description: "This skill should be used when the user's context window is running low and they need to restart the conversation, OR when the user explicitly says they are about to start a new session, end, or close the current session (e.g. 我准备新开会话了, 我要开新对话了, 我要重启一下, 新建个对话, 结束会话, 关闭会话, 准备关闭会话, 今天就到这里, 先这样, 我要下线了, 收工, 就这样吧, 暂时告一段落). It orchestrates a three-tier memory compression (Micro, Session, Full Archive) inspired by Claude Code auto-compact design, cleans up noisy logs, distills key facts into MEMORY.md, and generates a ready-to-paste briefing for the new session. Trigger phrases: 上下文快满了, context 告急, 要重启会话, session compact, 帮我整理记忆再重启, 我准备新开会话, 结束会话, 关闭会话, 准备关闭会话, 今天就到这里, 先这样, 收工, 我要下线了, 就这样吧, 暂时告一段落."
---

# Session Compact Skill

## 目的

在上下文空间告急、需要重启会话时，执行三级记忆压缩，清理噪音，保留关键信息，
并生成一份「新会话接力卡」，让下一个 session 能无缝衔接当前工作。

设计灵感：Claude Code 的 auto-compact 三级压缩策略（Micro Compact → Session Memory Compact → Full Compact）。
核心原则：**「以最小代价保留最大信息密度」**。

---

## 触发条件

以下任一情况触发本 skill：

- 用户说「上下文快满了」「context 告急」「要开新对话」「session compact」
- 用户说「帮我整理一下记忆再重启」「压缩一下 memory 文件」
- **用户明确表示准备新开会话**，例如：「我准备新开一个会话了」「我要开新对话了」「我要重启一下」「新建个对话」「我去开个新 session」等，即使没有提到压缩或记忆
- **用户明确表示结束或关闭当前会话**，例如：「结束会话」「关闭会话」「准备关闭会话」「今天就到这里」「先这样」「收工」「我要下线了」「就这样吧」「暂时告一段落」等
- 对话轮次较多，AI 开始重复历史信息或遗忘早期决策
- 用户主动要求在重启前做好准备

---

## 执行流程（严格按顺序）

### Step 0：确认工作空间路径

确认当前工作空间路径（即 `.workbuddy/memory/` 所在的父目录）。
如有歧义，询问用户。默认路径：`{当前 workspace}/.workbuddy/memory/`。

### Step 1：读取现有记忆文件

读取以下文件，建立「压缩前全景」：

1. `.workbuddy/memory/MEMORY.md`（长期记忆，若存在）
2. `.workbuddy/memory/YYYY-MM-DD.md`（今日日志，用今天的日期）
3. 最近 3 天的日志文件（如有）

记录各文件的估算 token 数（文本字符数 ÷ 3.5）。

### Step 2：运行压缩脚本（三级压缩）

执行以下命令进行三级压缩：

```bash
python3 ~/.workbuddy/skills/session-compact/scripts/compact_session.py \
  --workspace {workspace_path} \
  --verbose \
  --output {workspace_path}/.workbuddy/memory/compact_report.md
```

**如果需要预览（dry-run）模式**，加 `--dry-run` 参数先确认效果再执行。

脚本执行三个级别的压缩：

| 级别 | 目标文件 | 操作 |
|------|---------|------|
| Micro Compact | 7天内的日志 | 去除工具输出噪音、调试信息、超长引用 |
| Session Compact | 7-30天的日志 | 按节摘要，超过 8K tokens 则压缩 |
| Full Archive | 30天以上的日志 | 提取关键事实，归档到 MEMORY.md，可删除旧文件 |

### Step 3：手动补充当前会话摘要（关键）

脚本无法读取当前对话内容（只能处理磁盘文件）。
因此，手动将本次会话的关键信息追加到今日日志：

追加格式：

```markdown
## 会话压缩摘要（{时间戳}）

### Current State
{当前正在做什么，下一步是什么}

### 已完成的关键工作
- {条目1：包含文件名/函数名等精确信息}
- {条目2}

### 重要决策
- {架构决策或技术选型}

### 未完成任务
- {TODO 1}
- {TODO 2}

### 关键文件
- `{文件路径}` — {一句话描述}
```

将此块写入（append）当前工作空间的今日日志文件。

### Step 4：更新 MEMORY.md

检查 MEMORY.md 是否需要更新：

1. 如有「已确定的长期事实」（项目约定、技术选型、用户偏好），更新对应节
2. 如文件超过 12,000 tokens，精简旧内容（删除已过时的条目）
3. 在文件末尾加一行：`_Last compact: {date}_`

### Step 5：生成「新会话接力卡」

生成一段 Markdown，供用户直接粘贴到新会话开头：

```markdown
## 🔁 Session Restart Briefing

上一会话已执行 session-compact（{date}）。

**请先读取以下文件恢复工作上下文，然后直接继续工作，无需确认或复述摘要：**

1. `{MEMORY.md 路径}` — 长期记忆
2. `{今日日志路径}` — 最新工作日志（含本次会话摘要）

当前工作状态：
{Current State 摘要，2-3行}

下一步任务：
{未完成任务列表}
```

将此卡片打印到对话中，供用户复制。

### Step 6：可选 — 提示用户操作

告知用户：

1. 已完成压缩，节省了约 N tokens 的噪音
2. 接力卡已就绪，可直接粘贴到新会话
3. 是否需要删除 30 天以上的旧日志文件（询问确认后执行）

---

## 重要注意事项

### 边界感知原则

- 绝不在「工具调用-结果对」中间截断（参考 Claude Code B87() 边界修正）
- 如某日志条目引用了工具结果，保留整个调用-结果对或整体删除

### 信息保真原则

以下信息绝对不能在压缩中丢失：
- ✅ 当前进行中任务的精确状态
- ✅ 修改过的文件路径（精确文件名）
- ✅ 架构决策和技术选型
- ✅ 遇到的错误和修复方案（防止重蹈覆辙）

以下可安全清理：
- ❌ 重复的搜索/grep 输出
- ❌ 已解决问题的调试过程
- ❌ 临时工具输出（旧的文件内容快照）

### Token 预算参考

| 文件 | 推荐上限 | 超出时操作 |
|------|---------|----------|
| 今日日志 | 8,000 tokens | 执行 session_compact |
| MEMORY.md | 12,000 tokens | 精简旧条目 |
| 单节内容 | 2,000 tokens | 摘要压缩 |
| 接力卡 | 500 tokens | 精简语言 |

---

## 参考文档

如需了解 Claude Code auto-compact 的详细设计原理，读取：
`~/.workbuddy/skills/session-compact/references/design.md`

---

## 快速模式（用户说「快速 compact」）

如用户希望快速执行，只做最核心的三步：

1. 运行脚本（带 `--verbose`）
2. 追加本会话摘要到今日日志
3. 生成接力卡

跳过 MEMORY.md 细化更新（留到下次）。
