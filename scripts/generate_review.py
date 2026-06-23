"""生成待确认 review 清单。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from lib.utils import read_text, write_text


def generate_review(
    run_id: str,
    scan_meta: dict[str, Any],
    case_status: dict[str, Any],
    *,
    reviews_dir: Path,
    published_dir: Path,
    draft_dir: Path,
) -> Path:
    new_cases = scan_meta.get("new_cases") or []
    updated_cases = scan_meta.get("updated_cases") or []
    needs_check = scan_meta.get("needs_user_check") or []
    backlog = scan_meta.get("transcript_backlog", False)

    lines = [
        f"# 案例库更新待确认 · {run_id}",
        "",
        "## 本次扫描概况",
        "",
        f"- **扫描时间**：{scan_meta.get('finished_at', run_id)}",
        f"- **扫描模式**：{scan_meta.get('mode', 'full')}",
        f"- **项目总数**：{scan_meta.get('project_count', 0)}",
        f"- **新增 Agent 会话（建议关注）**：{scan_meta.get('session_count', 0)}",
        "",
    ]

    if backlog:
        lines.append("> ⚠️ 本次包含 **积压对话补扫**（电脑曾关机或离线期间的新会话）。")
        lines.append("")

    if not new_cases and not updated_cases:
        lines.append("**本次无案例卡变更。** 若你刚完成重要协作，可稍后再跑一次扫描。")
        lines.append("")
    else:
        lines.append("## 需要你拍板的项")
        lines.append("")

    for item in new_cases:
        lines.extend(_case_section(item, "🆕 新增", case_status))

    for item in updated_cases:
        lines.extend(_case_section(item, "✏️ 更新", case_status))

    if needs_check:
        lines.append("## ⚠️ 待核实（不会自动写入正式版）")
        lines.append("")
        for item in needs_check:
            lines.append(f"- **{item['project']}**：{item['reason']}")
        lines.append("")

    lines.extend(
        [
            "## 快速操作",
            "",
            "在 Cursor 对话中说：",
            "",
            "- `确认 portfolio` — 发布本次全部待确认案例",
            "- `确认 portfolio <项目名>` — 只发布指定项目（如 `确认 portfolio 押题班画像`）",
            "",
            "或在本仓库执行：",
            "",
            "```bash",
            "python3 scripts/portfolio.py confirm",
            "python3 scripts/portfolio.py confirm --cases 押题班画像",
            "```",
            "",
            "## 文件位置",
            "",
            f"- 草稿总览：[draft/AI-Projects-Portfolio.md](../draft/AI-Projects-Portfolio.md)",
            f"- 正式总览：[published/AI-Projects-Portfolio.md](../published/AI-Projects-Portfolio.md)",
            "",
        ]
    )

    content = "\n".join(lines)
    review_path = reviews_dir / f"{run_id}-review.md"
    write_text(review_path, content)
    write_text(reviews_dir / "LATEST.md", content)

    # 有待确认项时创建标记文件
    pending_flag = reviews_dir.parent / "state" / "PENDING_REVIEW"
    if new_cases or updated_cases:
        write_text(
            pending_flag,
            f"run_id={run_id}\ncreated={datetime.now().isoformat()}\n",
        )
    elif pending_flag.is_file():
        pending_flag.unlink()

    return review_path


def _case_section(
    item: dict[str, Any],
    label: str,
    case_status: dict[str, Any],
) -> list[str]:
    name = item.get("name") or item.get("id")
    title = item.get("title") or name
    status = (case_status.get(name) or case_status.get(item.get("id", "")) or {}).get(
        "status", "draft"
    )
    lines = [
        f"### {label} · {title}",
        "",
        f"- **项目**：`{name}`",
        f"- **当前状态**：{status}",
    ]
    if item.get("one_liner"):
        lines.append(f"- **一句话**：{item['one_liner']}")
    if item.get("change_summary"):
        lines.append(f"- **变更**：{item['change_summary']}")
    lines.append(f"- [查看案例卡](../cases/{item.get('case_file')})")
    lines.append("")
    return lines


def diff_summary(published_path: Path, draft_path: Path) -> list[str]:
    """简单对比：哪些案例文件有变化。"""
    changed: list[str] = []
    pub = read_text(published_path)
    draft = read_text(draft_path)
    if pub != draft:
        changed.append("总览文档有更新")
    return changed
