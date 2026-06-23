"""通用工具函数。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def slugify(name: str) -> str:
    s = name.strip()
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unnamed"


def first_meaningful_line(text: str, max_len: int = 120) -> str:
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"\*\*|__", "", line)
        if len(line) > max_len:
            return line[: max_len - 1] + "…"
        return line
    return ""


def extract_title_from_markdown(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return first_meaningful_line(text)


def strip_markdown_for_summary(text: str, max_chars: int = 400) -> str:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1] + "…"
    return text


def extract_markdown_sections(text: str, max_level: int = 3) -> dict[str, str]:
    """按 Markdown 标题切分章节（仅 h1–h3）。"""
    sections: dict[str, str] = {}
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if current_title is not None:
            body = "\n".join(current_lines).strip()
            if body:
                sections[current_title] = body
        current_title = None
        current_lines = []

    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if m and len(m.group(1)) <= max_level:
            flush()
            current_title = re.sub(r"\*\*|__", "", m.group(2)).strip()
            continue
        if current_title is not None:
            current_lines.append(line)
    flush()
    return sections


def _pick_section(sections: dict[str, str], keywords: list[str], *, exclude: list[str] | None = None) -> str:
    exclude = exclude or []
    for title, body in sections.items():
        title_lower = title.lower()
        if any(ex.lower() in title_lower for ex in exclude):
            continue
        if any(k.lower() in title_lower for k in keywords):
            return body
    return ""


def _extract_bullet_items(text: str, limit: int = 6) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"^[-*•]\s+(.+)$", line)
        if m:
            item = strip_markdown_for_summary(m.group(1), 160)
            if item and item not in items:
                items.append(item)
        m = re.match(r"^\d+\.\s+(.+)$", line)
        if m:
            item = strip_markdown_for_summary(m.group(1), 160)
            if item and item not in items:
                items.append(item)
        if len(items) >= limit:
            break
    return items


def _first_paragraphs(text: str, max_paras: int = 2, max_chars: int = 600) -> str:
    if not text:
        return ""
    paras: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("|") or s.startswith("```"):
            if buf:
                paras.append(" ".join(buf))
                buf = []
            if len(paras) >= max_paras:
                break
            continue
        if s.startswith("#"):
            continue
        if re.match(r"^\*\*解决方案\*\*", s) or s.startswith("**解决方案**"):
            break
        if s.startswith("- ✅") or s.startswith("✅"):
            continue
        buf.append(strip_markdown_for_summary(s, 300))
    if buf and len(paras) < max_paras:
        paras.append(" ".join(buf))
    result = "\n\n".join(p for p in paras if p and len(p) > 20)
    if len(result) > max_chars:
        return result[: max_chars - 1] + "…"
    return result


def _extract_table_rows(text: str, limit: int = 6) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|") or "---" in s:
            continue
        cells = [c.strip() for c in s.split("|") if c.strip()]
        if len(cells) < 2:
            continue
        header_tokens = ("文件", "模块", "用途", "读者", "章节", "---", "字段", "目标", "用户角色", "描述", "说明")
        if cells[0] in header_tokens or cells[1] in ("描述", "说明", "描述"):
            continue
        if "✅" in cells[0] or "❌" in cells[0]:
            continue
        if cells[0] == cells[1]:
            continue
        item = f"{cells[0]}：{strip_markdown_for_summary(cells[1], 100)}"
        if item not in items:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def parse_project_doc(text: str) -> dict[str, Any]:
    """从 PRD/README 提取结构化产品信号。"""
    sections = extract_markdown_sections(text)
    background_src = (
        _pick_section(sections, ["产品概述", "项目概述", "项目简介", "背景", "需求背景"])
        or _pick_section(sections, ["产品目标", "目标", "核心价值"], exclude=["用户"])
    )
    pains_src = _pick_section(
        sections, ["痛点", "问题分析", "问题1", "挑战", "以往"], exclude=["解决方案", "改进"]
    )
    features_src = _pick_section(
        sections,
        ["功能特性", "功能", "主要改进", "项目成果", "核心功能", "交付", "能力", "产品目标"],
        exclude=["问题"],
    )
    goals_src = _pick_section(
        sections, ["产品目标", "核心价值", "要解决"], exclude=["用户"]
    ) or _pick_section(sections, ["目标"], exclude=["用户", "问题"])

    bullets: list[str] = []
    for src in (features_src, background_src):
        bullets.extend(_extract_bullet_items(src, 4))
    seen: set[str] = set()
    unique_bullets: list[str] = []
    for b in bullets:
        key = re.sub(r"\s+", "", b.lower())[:40]
        if key not in seen and "已解决" not in b and len(b) > 8:
            seen.add(key)
            unique_bullets.append(b)

    # 从 PRD 表格补充交付物（如 BC 落地页交付包清单）
    table_items = _extract_table_rows(text, 6)
    for t in table_items:
        key = re.sub(r"\s+", "", t.lower())[:40]
        if key not in seen:
            seen.add(key)
            unique_bullets.append(t)

    # 从章节标题提取功能点（如「功能 1：Hero」）
    for title in sections:
        if "功能" in title and len(title) < 80:
            feat = strip_markdown_for_summary(title, 120)
            key = re.sub(r"\s+", "", feat.lower())[:40]
            if key not in seen and len(feat) > 6:
                seen.add(key)
                unique_bullets.append(feat)

    return {
        "title": extract_title_from_markdown(text),
        "excerpt": text[:5000],
        "sections": {k: v[:800] for k, v in list(sections.items())[:20]},
        "background": _first_paragraphs(background_src, 3, 700),
        "goals": _first_paragraphs(goals_src, 2, 400),
        "pains": _first_paragraphs(pains_src, 2, 400),
        "features": unique_bullets[:8],
        "section_titles": list(sections.keys())[:12],
    }
