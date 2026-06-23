"""将扫描信号合成为可读案例卡（业务语言，非技术向）。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from lib.utils import write_text


def synthesize_case_markdown(
    project: dict[str, Any],
    sessions: list[dict[str, Any]] | None = None,
    existing_status: dict[str, Any] | None = None,
) -> str:
    name = project["name"]
    doc = project.get("doc") or {}
    impact = project.get("ai_impact") or {}
    git = project.get("git") or {}
    sessions = sessions or []

    title = (
        impact.get("one_liner")
        or impact.get("project")
        or doc.get("title")
        or name
    )

    domain = impact.get("domain") or _guess_domain(doc.get("title") or "", name)
    traditional = impact.get("traditional") or {}
    with_cursor = impact.get("with_cursor") or {}
    impact_block = impact.get("impact") or {}

    lines: list[str] = [
        f"# {title}",
        "",
        f"> 项目路径：`{name}` · 领域：{domain}",
        "",
    ]

    # 背景
    lines.append("## 背景")
    lines.append("")
    background = (
        impact.get("background")
        or _background_from_doc(doc)
        or f"「{name}」是 AI Projects 工作区中的活跃项目。"
    )
    lines.append(background)
    lines.append("")

    # 以前怎么做
    lines.append("## 以前怎么做")
    lines.append("")
    if isinstance(traditional, dict) and traditional.get("workflow"):
        lines.append(traditional["workflow"])
        if traditional.get("pain"):
            lines.append("")
            lines.append(f"**痛点**：{traditional['pain']}")
        if traditional.get("baseline"):
            lines.append("")
            lines.append(f"**通常耗时**：{traditional['baseline']}")
    else:
        lines.append(_infer_traditional(doc, sessions))
    lines.append("")

    # 用 Cursor 之后
    lines.append("## 用 Cursor 之后")
    lines.append("")
    if isinstance(with_cursor, dict) and with_cursor.get("workflow"):
        lines.append(with_cursor["workflow"])
        tools = with_cursor.get("tools")
        if tools:
            if isinstance(tools, list):
                lines.append("")
                lines.append("**主要用法**：" + "、".join(str(t) for t in tools))
            else:
                lines.append("")
                lines.append(f"**主要用法**：{tools}")
    else:
        lines.append(_infer_cursor_workflow(sessions, git, doc))
    lines.append("")

    # 带来的变化
    lines.append("## 带来的变化")
    lines.append("")
    changes: list[str] = []
    if isinstance(impact_block, dict):
        if impact_block.get("time_ratio"):
            changes.append(f"- **效率**：{impact_block['time_ratio']}")
        if impact_block.get("quality"):
            changes.append(f"- **质量**：{impact_block['quality']}")
        if impact_block.get("enabled"):
            changes.append(f"- **新突破**：{impact_block['enabled']}")
    if not changes:
        changes = _infer_impact(sessions, git)
    lines.extend(changes or ["- 待补充：请在本项目 `.cursor/ai-impact.yaml` 中填写量化收益。"])
    lines.append("")

    # 会话证据（可读摘要，非技术日志）
    if sessions:
        lines.append("## 近期协作摘要")
        lines.append("")
        for s in sessions[:3]:
            q = s.get("first_query") or "（无明确任务描述）"
            lines.append(f"- **{s.get('mtime', '')[:10]}**：{q}")
        lines.append("")

    # 待确认区块（自动更新时追加，不覆盖 confirmed 正文 — 由 confirm 流程处理）
    pending = (existing_status or {}).get("pending_append")
    if pending:
        lines.append("---")
        lines.append("")
        lines.append(f"<!-- 待确认更新 {pending} -->")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*本卡由 Cursor 案例库自动整理 · 状态：{(existing_status or {}).get('status', 'draft')}*")
    lines.append("")

    return "\n".join(lines)


def _guess_domain(title: str, name: str) -> str:
    text = f"{title} {name}".lower()
    rules = [
        ("数据分析", ["画像", "数据", "csv", "dashboard", "看板"]),
        ("课程与内容", ["课程", "ielts", "写作", "营销", "逐字稿"]),
        ("产品与设计", ["prd", "落地页", "demo", "原型"]),
        ("运营与销售", ["签转", "喜报", "销售"]),
        ("研发与工具", ["skill", "hook", "proto", "openspec", "spec"]),
    ]
    for label, keys in rules:
        if any(k in text for k in keys):
            return label
    return "综合"


def _background_from_doc(doc: dict[str, Any]) -> str:
    excerpt = doc.get("excerpt") or ""
    if not excerpt:
        return ""
    for line in excerpt.splitlines():
        line = line.strip()
        if line.startswith("## ") and ("背景" in line or "目标" in line):
            continue
        if line and not line.startswith("#"):
            return line[:280]
    return ""


def _infer_traditional(doc: dict[str, Any], sessions: list[dict[str, Any]]) -> str:
    title = doc.get("title") or ""
    if "画像" in title or "看板" in title:
        return "以往多依赖 Excel 手工汇总，改一个统计维度就要重新做表，沟通成本高、迭代慢。"
    if "营销" in title or "课程" in title:
        return "以往教研与运营需多轮改稿，话术风格难统一，四门课难以复用同一套方法。"
    if "PRD" in title or "落地页" in title:
        return "以往产品、设计、开发分段推进，需求文档与实现容易脱节，来回对齐占用大量时间。"
    if sessions:
        q = sessions[0].get("first_query", "")
        if q:
            return f"以往类似「{q[:80]}…」的工作，主要靠人工逐步摸索完成。"
    return "以往以人工查阅资料、手工整理为主，过程重复且难以沉淀为可复用经验。"


def _infer_cursor_workflow(
    sessions: list[dict[str, Any]],
    git: dict[str, Any],
    doc: dict[str, Any],
) -> str:
    parts: list[str] = []
    if sessions:
        parts.append(
            "通过 Cursor Agent 用自然语言描述目标，由 AI 协助完成资料阅读、方案起草与文件生成；"
            "对话过程可回溯，减少「口头交代、事后找不到」的问题。"
        )
    if git.get("commits_recent", 0) > 0:
        parts.append(
            f"近期仓库有 **{git['commits_recent']}** 次相关提交，说明人机协作产出在持续迭代。"
        )
    if doc.get("source"):
        parts.append(f"项目以 `{doc['source']}` 为需求/说明入口，便于 AI 理解业务上下文。")
    return " ".join(parts) if parts else "使用 Cursor 进行对话式协作，逐步完成项目任务。"


def _infer_impact(sessions: list[dict[str, Any]], git: dict[str, Any]) -> list[str]:
    items: list[str] = []
    if len(sessions) >= 2:
        items.append("- **协作频次**：近期有多次 Agent 会话，同一项目可快速续接上下文。")
    if git.get("commits_recent", 0) >= 3:
        items.append("- **迭代速度**：代码/文档提交活跃，改版周期明显短于纯人工推进。")
    if sessions and any(s.get("touched_paths") for s in sessions):
        items.append("- **可沉淀**：对话中改动的文件路径可追溯，方便复盘与汇报引用。")
    return items


def build_portfolio_index(
    case_files: list[tuple[str, str, str]],
    *,
    title: str = "AI Projects · Cursor 提效案例集",
    subtitle: str = "",
) -> str:
    """case_files: [(project_name, case_title, filename)]"""
    lines = [
        f"# {title}",
        "",
        subtitle or "面向全公司同事的可读案例汇总，说明各项目如何用 Cursor 提效。",
        "",
        f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## 案例目录",
        "",
    ]
    by_domain: dict[str, list[tuple[str, str, str]]] = {}
    for item in case_files:
        # 从 cases 文件名无法直接得 domain，先统一列表
        by_domain.setdefault("全部项目", []).append(item)

    for domain, items in sorted(by_domain.items()):
        if domain != "全部项目":
            lines.append(f"### {domain}")
            lines.append("")
        for project_name, case_title, filename in sorted(items, key=lambda x: x[0]):
            anchor = Path(filename).stem
            lines.append(f"- [{case_title}](cases/{filename})（`{project_name}`）")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 阅读说明")
    lines.append("")
    lines.append("- 每个案例包含：**背景 → 以前怎么做 → 用 Cursor 之后 → 带来的变化**")
    lines.append("- 标注 `draft` 的为自动草稿，需在 Cursor 中确认后才会进入正式版")
    lines.append("- 确认方式见 [docs/03-确认发布流程.md](docs/03-确认发布流程.md)")
    lines.append("")
    return "\n".join(lines)


def write_case_file(cases_dir: Path, project: dict[str, Any], content: str) -> str:
    filename = f"{project['id']}.md"
    write_text(cases_dir / filename, content)
    return filename
