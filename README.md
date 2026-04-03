# session-compact

> 上下文告急时，一句话整理记忆、无缝切换新会话。
>
> *Clean up your AI memory in one sentence — seamlessly continue in a fresh session.*

---

## 你是否遇到过这些情况？

- 跟 AI 聊了很久，上下文快满了，但任务还没做完
- 开了个新对话，AI 完全不记得之前做了什么，又要从头解释
- 日志文件越来越大，里面全是调试输出、搜索结果这些没用的东西
- 重启会话后，重要的决策和文件路径都找不回来了

**session-compact 就是为这个场景设计的。**

## Sound familiar?

- You've been working with AI for a while, context is nearly full, but the task isn't done
- You start a new session and the AI has no idea what happened before — you have to explain everything again
- Your log files keep growing with debug output, search results, and other noise
- After restarting, important decisions and file paths are gone

**session-compact is built exactly for this.**

---

## 它能做什么 / What it does

说一句话，它自动完成 / *Say one sentence. It handles the rest:*

| # | 中文 | English |
|---|------|---------|
| 1 | **清理日志噪音** — 删掉 DEBUG 输出、搜索结果、超长引用 | **Clean log noise** — removes DEBUG output, search results, long quotes |
| 2 | **压缩旧日志** — 超长历史日志按节摘要，体积缩减 80%+ | **Compress old logs** — summarizes by section, 80%+ size reduction |
| 3 | **归档关键事实** — 30天以上日志提炼成 bullet points，写入长期记忆 | **Archive key facts** — distills logs older than 30 days into long-term memory |
| 4 | **生成接力卡** — 一段可直接粘贴到新会话的 briefing | **Generate handoff card** — a paste-ready briefing for your next session |

整个过程 **5ms 以内完成**，纯本地运行，不调用任何 API。

*The entire process completes in **under 5ms**, runs fully local, zero API calls.*

---

## 触发方式 / How to trigger

跟 AI 说以下任意一句 / *Say any of the following to your AI:*

```
上下文快满了，帮我整理一下
我准备新开会话了
收工，帮我压缩一下记忆
今天就到这里

# English equivalents
context is running low, help me clean up
I'm starting a new session
wrapping up, compress my memory
that's all for today
```

不需要记命令，说人话就行。

*No commands to memorize. Just talk naturally.*

---

## 三级压缩策略 / Three-tier compression

灵感来自 Claude Code 源码中的 auto-compact 设计（2026-03-31 泄露分析）。

*Inspired by the auto-compact design found in Claude Code's source (analyzed from the 2026-03-31 leak).*

```
Level 1  Micro Compact       7天内日志 / Logs within 7 days
         └─ 删除 / Remove：DEBUG 章节、搜索结果、超长引用行、分隔线噪音
         └─ 保留 / Keep：任务进展、关键决策、重要文件

Level 2  Session Compact     7–30天日志，超过 8K tokens 时触发
                             Logs 7–30 days old, triggers above 8K tokens
         └─ 每个章节保留前5行精华
         └─ 边界感知：不在工具调用-结果对中间截断

Level 3  Full Archive        30天以上日志 / Logs older than 30 days
         └─ 提取关键事实，归档到 MEMORY.md，原日志可删除
         └─ Extracts key facts into MEMORY.md; original logs can be deleted
```

---

## 新会话接力卡示例 / Handoff card example

压缩完成后自动生成，直接复制粘贴。

*Auto-generated after compaction. Copy and paste into your next session.*

```markdown
## 🔁 Session Restart Briefing

上一会话已执行 session-compact（2026-04-04 01:14）。

请先读取以下文件恢复工作上下文，然后直接继续工作：

1. `.workbuddy/memory/MEMORY.md` — 长期记忆
2. `.workbuddy/memory/2026-04-04.md` — 今日日志（含本次会话摘要）

当前工作状态：
session-compact skill 已创建完成，无未完成任务。
```

---

## 性能 / Performance

| 场景 / Scenario | 文件数 / Files | 数据量 / Tokens | 耗时 / Time |
|----------------|:-------------:|:--------------:|:-----------:|
| 典型 / Typical | 5 | 4,380 | 3 ms |
| 中等 / Medium | 15 | 27,000 | 2 ms |
| 重度 / Heavy | 30 | 104,000 | 4 ms |

纯本地正则处理，无 API 调用，耗时与文件数基本无关。

*Pure local regex processing, no API calls. Time is nearly constant regardless of file count.*

---

## 安装 / Installation

将 skill 目录放到 `~/.workbuddy/skills/session-compact/`，重启 WorkBuddy 即可。

*Place the skill directory at `~/.workbuddy/skills/session-compact/` and restart WorkBuddy.*

```
~/.workbuddy/skills/session-compact/
├── SKILL.md                    ← AI 指令文件 / AI instruction file
├── README.md                   ← 本文件 / This file
├── config.json                 ← 更新配置 / Update config
├── manifest.json               ← 版本清单 / Version manifest
├── scripts/
│   ├── compact_session.py      ← 三级压缩脚本 / Three-tier compression script
│   └── release.sh              ← 发布脚本 / Release script
└── references/
    └── design.md               ← Claude Code auto-compact 设计原理 / Design reference
```

命令行单独运行 / *Or run the script directly from CLI:*

```bash
# 预览模式（不写入）/ Preview mode (no writes)
python3 scripts/compact_session.py --workspace /path/to/workspace --dry-run --verbose

# 实际执行并输出报告 / Execute and output report
python3 scripts/compact_session.py --workspace /path/to/workspace --verbose --output report.md
```

---

## 更新 / Updating

```bash
skillhub upgrade session-compact
```

---

## 设计原则 / Design principles

**保留什么，清理什么 / What's kept vs. cleaned:**

| 保留 ✅ Keep | 清理 ❌ Remove |
|------------|--------------|
| 当前任务状态 / Current task state | DEBUG / INFO 输出 / output |
| 修改过的文件路径 / Modified file paths | 搜索结果原文 / Raw search results |
| 架构决策和技术选型 / Architecture decisions | 已解决问题的调试过程 / Resolved debug trails |
| 错误和修复方案 / Errors and fixes | 超长引用块 / Oversized quote blocks |
| 下一步待办任务 / Next steps | 重复的分隔线 / Redundant dividers |

核心原则来自 Claude Code：**「以最小代价保留最大信息密度」**

*Core principle from Claude Code: **"Maximum information density at minimum cost."***

---

## 依赖 / Requirements

- Python 3.8+（macOS / Linux 自带 / pre-installed）
- 无第三方包依赖 / No third-party dependencies

---

*基于 Claude Code auto-compact 源码分析设计 · 适用于 WorkBuddy*

*Designed from Claude Code auto-compact source analysis · Built for WorkBuddy*
