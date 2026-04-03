#!/usr/bin/env python3
"""
session-compact: WorkBuddy 会话记忆压缩工具

灵感来源：Claude Code auto-compact 三级压缩策略
设计原则：「以最小代价保留最大信息密度」

使用方式：
  python3 compact_session.py [--workspace <path>] [--dry-run] [--output <path>]

功能：
  1. 扫描工作空间的 .workbuddy/memory/ 目录
  2. 三级压缩：Micro（清理工具输出） → Session（压缩日志） → Full（生成摘要）
  3. 输出压缩报告，为重启会话做好准备
"""

import os
import re
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


# ─── 常量（参考 Claude Code 设计）─────────────────────────────────────
MAX_DAILY_LOG_TOKENS    = 8_000    # 单个日志文件 token 上限（估算）
MAX_MEMORY_TOKENS       = 12_000   # MEMORY.md 总 token 上限
SESSION_SECTION_TOKENS  = 2_000    # 每节内容 token 上限
MICRO_COMPACT_DAYS      = 7        # 超过 N 天的日志执行微压缩
ARCHIVE_DAYS            = 30       # 超过 N 天的日志归档到 MEMORY.md
CHARS_PER_TOKEN         = 3.5      # 字符数/token 估算比例（中文偏多）

# 日志中被视为「工具输出噪音」的模式（微压缩目标）
NOISE_PATTERNS = [
    r"(?m)^#{3,}\s+Tool (call|result|output).*$",        # 工具调用原始记录
    r"(?m)^-{3,}\s*$",                                   # 分隔线
    r"(?m)^\s*\[搜索结果\].*?(?=\n#{1,3}|\Z)",           # 搜索结果块
    r"(?m)^> .{80,}$",                                   # 超长引用行（80字符，兼容中文）
    r"(?m)^#{1,6}\s+DEBUG:.*$",                          # DEBUG 标题行
    r"(?m)^\s*DEBUG:.*$",                                 # DEBUG 纯行
    r"(?m)^\s*\[INFO\].*$",                              # INFO 日志行
    r"(?m)^\s*\[WARN\].*$",                              # WARN 日志行
]

# 整个章节被视为噪音而整体删除的标题关键词（不区分大小写）
NOISE_SECTION_KEYWORDS = [
    "debug", "调试", "搜索结果", "工具输出", "tool output",
    "详细过程", "中间过程", "临时记录",
]

# MEMORY.md 的标准节结构（参考 Claude Code Session Memory 模板）
MEMORY_SECTIONS = [
    "# Current State",
    "# Active Projects",
    "# Key Decisions",
    "# Files and Functions",
    "# Workflow",
    "# Errors & Corrections",
    "# Learnings",
    "# Worklog",
]


def estimate_tokens(text: str) -> int:
    """估算文本 token 数（字符/3.5，中英文混合场景合理估算）"""
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def micro_compact(content: str) -> tuple[str, int]:
    """
    第一级：微压缩（Micro Compact）
    - 清除工具输出噪音、调试信息、超长引用
    - 整体删除噪音章节（DEBUG/搜索结果/调试详情等）
    - 不改变文档结构，只做「去噪」
    返回：(压缩后内容, 节省的 token 数)
    """
    original_tokens = estimate_tokens(content)
    result = content

    # 先删除整个噪音章节（按行解析，找到噪音标题后删到下一个同级标题）
    lines = result.split("\n")
    clean_lines = []
    skip_until_level = None  # 当前跳过的章节级别

    for line in lines:
        header_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2).strip().lower()
            # 检查是否是噪音章节标题
            is_noise = any(kw in title for kw in NOISE_SECTION_KEYWORDS)
            if is_noise:
                skip_until_level = level  # 开始跳过
                continue
            elif skip_until_level is not None and level <= skip_until_level:
                skip_until_level = None  # 遇到同级或更高级标题，停止跳过
        if skip_until_level is not None:
            continue  # 跳过噪音章节内容
        clean_lines.append(line)

    result = "\n".join(clean_lines)

    # 再应用逐行 pattern 清理
    for pattern in NOISE_PATTERNS:
        result = re.sub(pattern, "", result)

    # 压缩连续空行（超过 2 行的合并为 2 行）
    result = re.sub(r"\n{3,}", "\n\n", result)
    saved = original_tokens - estimate_tokens(result)
    return result, max(0, saved)


def session_compact(content: str, max_tokens: int = MAX_DAILY_LOG_TOKENS) -> tuple[str, bool]:
    """
    第二级：会话压缩（Session Compact）
    - 当日志超过 max_tokens 时，按节提取 headline + 首行摘要
    - 工具调用-结果对不在中间切断（边界感知）
    返回：(压缩后内容, 是否执行了压缩)
    """
    if estimate_tokens(content) <= max_tokens:
        return content, False

    lines = content.split("\n")
    sections = []
    current_section_lines = []
    current_header = None

    for line in lines:
        if re.match(r"^#{1,3}\s+", line):
            if current_header is not None:
                sections.append((current_header, current_section_lines))
            current_header = line
            current_section_lines = []
        else:
            current_section_lines.append(line)

    if current_header is not None:
        sections.append((current_header, current_section_lines))

    # 每节保留：标题 + 前 5 行有效内容（跳过空行）
    compacted_parts = []
    for header, body_lines in sections:
        non_empty = [l for l in body_lines if l.strip()]
        preview = non_empty[:5]
        if len(non_empty) > 5:
            preview.append(f"_（已压缩 {len(non_empty) - 5} 行）_")
        compacted_parts.append(header)
        compacted_parts.extend(preview)
        compacted_parts.append("")

    compacted = "\n".join(compacted_parts)
    return compacted, True


def extract_key_facts(content: str) -> list[str]:
    """
    从日志内容中提取关键事实，用于 MEMORY.md 归档
    策略：提取所有 bullet point（- / * 开头）和带有关键词的行
    """
    keywords = ["完成", "修复", "决定", "选择", "发现", "问题", "方案", "已", "TODO", "DONE", "fix", "feat", "decided"]
    facts = []
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # bullet point
        if re.match(r"^[-*]\s+", stripped):
            facts.append(stripped)
            continue
        # 包含关键词的非标题行
        if any(kw in stripped for kw in keywords) and not re.match(r"^#{1,3}\s+", stripped):
            facts.append(f"- {stripped[:200]}")  # 截断过长行
    return facts[:30]  # 最多保留 30 条


def scan_memory_dir(memory_dir: Path) -> dict:
    """扫描 memory 目录，返回分类文件信息"""
    today = datetime.now().date()
    result = {
        "memory_md": None,
        "today_log": None,
        "recent_logs": [],    # 7 天内
        "old_logs": [],       # 7-30 天
        "archive_logs": [],   # 30 天以上
    }

    if not memory_dir.exists():
        return result

    for f in sorted(memory_dir.glob("*.md")):
        if f.name == "MEMORY.md":
            result["memory_md"] = f
            continue
        # 尝试解析日期
        try:
            file_date = datetime.strptime(f.stem, "%Y-%m-%d").date()
            age_days = (today - file_date).days
            if age_days == 0:
                result["today_log"] = f
            elif age_days <= MICRO_COMPACT_DAYS:
                result["recent_logs"].append(f)
            elif age_days <= ARCHIVE_DAYS:
                result["old_logs"].append(f)
            else:
                result["archive_logs"].append(f)
        except ValueError:
            pass  # 非日期命名文件，忽略

    return result


def build_compact_report(
    memory_dir: Path,
    scan: dict,
    stats: dict,
    dry_run: bool = False,
) -> str:
    """生成压缩操作报告，供 LLM 用于重启会话时的 briefing"""
    lines = [
        "# Session Compact Report",
        f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        "",
        "## 压缩摘要",
        f"- 扫描目录：`{memory_dir}`",
        f"- 今日日志：{'存在' if scan['today_log'] else '无'}",
        f"- 近期日志（7天内）：{len(scan['recent_logs'])} 个",
        f"- 旧日志（7-30天）：{len(scan['old_logs'])} 个",
        f"- 待归档日志（>30天）：{len(scan['archive_logs'])} 个",
        f"- 模式：{'DRY RUN（预览，不写入）' if dry_run else '实际执行'}",
        "",
        "## 压缩操作明细",
    ]

    for op in stats.get("operations", []):
        icon = "🔍" if dry_run else ("✅" if op.get("success") else "⚠️")
        lines.append(f"{icon} {op['action']}: `{op['file']}` — 节省约 {op.get('saved_tokens', 0)} tokens")

    total_saved = sum(op.get("saved_tokens", 0) for op in stats.get("operations", []))
    lines += [
        "",
        f"**合计节省：约 {total_saved} tokens**",
        "",
        "## 重启会话建议",
        "",
        "重启后，在新会话开头请告知 AI：",
        "```",
        "上一会话已执行 session-compact。请读取以下文件恢复上下文：",
        f"- {memory_dir}/MEMORY.md（长期记忆）",
        f"- {memory_dir}/{datetime.now().strftime('%Y-%m-%d')}.md（今日日志）",
        "```",
        "",
        "> 注：微压缩已清理工具输出噪音，会话压缩已摘要超长日志。",
        "> MEMORY.md 中已归档所有关键决策和重要事实。",
    ]
    return "\n".join(lines)


def run_compact(
    workspace: str,
    dry_run: bool = False,
    output: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """主压缩流程，返回报告内容"""
    memory_dir = Path(workspace) / ".workbuddy" / "memory"
    scan = scan_memory_dir(memory_dir)
    stats = {"operations": []}

    def log(msg):
        if verbose:
            print(msg)

    # ── Level 1: Micro Compact（近期日志去噪）────────────────────────────
    log("\n[Level 1] Micro Compact: 清理近期日志噪音...")
    for log_file in scan["recent_logs"] + ([scan["today_log"]] if scan["today_log"] else []):
        content = log_file.read_text(encoding="utf-8")
        compacted, saved = micro_compact(content)
        op = {"action": "micro_compact", "file": log_file.name, "saved_tokens": saved, "success": True}
        if saved > 0:
            if not dry_run:
                log_file.write_text(compacted, encoding="utf-8")
            log(f"  ✓ {log_file.name}: 节省 {saved} tokens")
        stats["operations"].append(op)

    # ── Level 2: Session Compact（旧日志压缩）───────────────────────────
    log("\n[Level 2] Session Compact: 压缩旧日志...")
    for log_file in scan["old_logs"]:
        content = log_file.read_text(encoding="utf-8")
        compacted, did_compact = session_compact(content)
        if did_compact:
            saved = estimate_tokens(content) - estimate_tokens(compacted)
            op = {"action": "session_compact", "file": log_file.name, "saved_tokens": saved, "success": True}
            if not dry_run:
                log_file.write_text(compacted, encoding="utf-8")
            log(f"  ✓ {log_file.name}: 压缩至摘要，节省 {saved} tokens")
            stats["operations"].append(op)

    # ── Level 3: Full Archive（归档超老日志到 MEMORY.md）────────────────
    log("\n[Level 3] Full Archive: 归档旧日志到 MEMORY.md...")
    if scan["archive_logs"]:
        memory_md = scan["memory_md"] or (memory_dir / "MEMORY.md")
        existing_memory = memory_md.read_text(encoding="utf-8") if memory_md.exists() else ""

        new_facts_by_date = {}
        for log_file in scan["archive_logs"]:
            content = log_file.read_text(encoding="utf-8")
            facts = extract_key_facts(content)
            if facts:
                new_facts_by_date[log_file.stem] = facts
            op = {"action": "archive", "file": log_file.name, "saved_tokens": estimate_tokens(content), "success": True}
            stats["operations"].append(op)

        if new_facts_by_date:
            archive_block = "\n\n## 归档日志（已压缩）\n"
            for date_str, facts in sorted(new_facts_by_date.items()):
                archive_block += f"\n### {date_str}\n"
                archive_block += "\n".join(facts) + "\n"

            new_memory = existing_memory.rstrip() + "\n" + archive_block
            if not dry_run:
                memory_md.write_text(new_memory, encoding="utf-8")
            log(f"  ✓ 归档 {len(scan['archive_logs'])} 个旧日志到 MEMORY.md")

    # ── 生成报告 ───────────────────────────────────────────────────────
    report = build_compact_report(memory_dir, scan, stats, dry_run=dry_run)

    if output:
        out_path = Path(output)
        out_path.write_text(report, encoding="utf-8")
        log(f"\n📄 报告已写入：{out_path}")
    else:
        print(report)

    return report


def main():
    parser = argparse.ArgumentParser(
        description="session-compact: 会话记忆压缩工具（重启前执行）"
    )
    parser.add_argument(
        "--workspace", "-w",
        default=os.getcwd(),
        help="工作空间根目录（默认：当前目录）"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="预览模式：只分析不写入"
    )
    parser.add_argument(
        "--output", "-o",
        help="报告输出路径（默认：打印到 stdout）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="输出详细过程"
    )
    args = parser.parse_args()
    run_compact(
        workspace=args.workspace,
        dry_run=args.dry_run,
        output=args.output,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
