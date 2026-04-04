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

> **输出原则：所有操作静默执行，对话里只输出一件事——接力卡。**
> 不要在对话中展开压缩明细、文件修改列表、逐条更新内容。

### Step 1：静默运行压缩脚本

确认工作空间路径，然后直接执行（**不加 `--verbose`**）：

```bash
python3 ~/.workbuddy/skills/session-compact/scripts/compact_session.py \
  --workspace {workspace_path}
```

如需预览，加 `--dry-run`。脚本自动完成三级压缩：

| 级别 | 目标 | 操作 |
|------|------|------|
| Micro Compact | 7天内日志 | 去除工具输出噪音、调试信息 |
| Session Compact | 7-30天日志 | 按节摘要，超 8K tokens 则压缩 |
| Full Archive | 30天以上日志 | 提取关键事实归档到 MEMORY.md |

### Step 2：静默写入今日日志

将本次会话摘要追加到今日日志（**直接写文件，不在对话里展开**）：

```markdown
## 会话压缩摘要（{时间戳}）
- Current State: {当前状态，1-2句}
- 已完成: {关键工作条目，精确到文件名/函数名}
- 未完成: {TODO列表}
- 关键文件: `{路径}` — {描述}
```

### Step 3：静默更新 MEMORY.md

将本次会话产生的长期事实（项目约定、技术选型、用户偏好）写入 MEMORY.md，**不在对话中列出变更**。

### Step 4：输出接力卡（唯一对话输出）

接力卡是对话中**唯一需要输出的内容**，控制在 20 行以内：

```markdown
## 🔁 Session Restart Briefing

session-compact 已完成（{date} {time}）。

新会话开头粘贴以下内容即可继续：

---
请读取以下文件恢复上下文，然后直接继续工作：
1. `{MEMORY.md 路径}` — 长期记忆
2. `{今日日志路径}` — 今日日志（含本次摘要）

当前状态：{1-2句话}
下一步：
- {未完成任务1}
- {未完成任务2}
---
```

不附加任何解释、操作说明、压缩统计数字。

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
