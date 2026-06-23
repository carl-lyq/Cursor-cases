"""扫描本机 Cursor Agent 对话 transcript，归并到 AI Projects 子项目。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from config import AI_PROJECTS_ROOT, CURSOR_PROJECTS_ROOT
from lib.utils import strip_markdown_for_summary


CURSOR_PREFIX = "Users-mac-Library-CloudStorage-OneDrive-AI-Projects"


def map_cursor_folder_to_project(cursor_folder: str) -> str | None:
    """将 ~/.cursor/projects 下的目录名映射到 AI Projects 相对路径。"""
    if cursor_folder == CURSOR_PREFIX:
        return "."

    suffix = cursor_folder
    if suffix.startswith(CURSOR_PREFIX + "-"):
        suffix = suffix[len(CURSOR_PREFIX) + 1 :]
    elif suffix.startswith(CURSOR_PREFIX):
        suffix = suffix[len(CURSOR_PREFIX) :].lstrip("-")
    else:
        return None

    if not suffix:
        return "."

    # 尝试用实际目录名匹配（支持中文文件夹）
    parts = suffix.split("-")
    resolved = _resolve_path_parts(parts)
    return resolved


def _resolve_path_parts(parts: list[str]) -> str | None:
    current = AI_PROJECTS_ROOT.resolve()
    resolved_parts: list[str] = []

    for part in parts:
        if not part:
            continue
        match = _find_child_dir(current, part)
        if not match:
            # 拼接剩余部分再试一次（处理多段被拆开的英文名）
            remainder = "-".join(parts[parts.index(part) :])
            match = _find_child_dir(current, remainder)
            if match:
                resolved_parts.append(match.name)
                return "/".join(resolved_parts) if resolved_parts else match.name
            return "/".join(resolved_parts) if resolved_parts else None
        resolved_parts.append(match.name)
        current = match

    if not resolved_parts:
        return None
    try:
        rel = current.relative_to(AI_PROJECTS_ROOT.resolve())
        return "." if rel == Path(".") else rel.as_posix()
    except ValueError:
        return "/".join(resolved_parts)


def _find_child_dir(parent: Path, token: str) -> Path | None:
    if not parent.is_dir():
        return None
    token_lower = token.lower()
    for child in parent.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name == token:
            return child
        if name.lower() == token_lower:
            return child
        if slug_match(name, token):
            return child
    return None


def slug_match(dir_name: str, token: str) -> bool:
    simplified = re.sub(r"[^\w]", "", dir_name, flags=re.UNICODE).lower()
    token_simplified = re.sub(r"[^\w]", "", token, flags=re.UNICODE).lower()
    return simplified == token_simplified or simplified.startswith(token_simplified)


def iter_transcript_files(cursor_root: Path | None = None) -> Iterator[Path]:
    root = (cursor_root or CURSOR_PROJECTS_ROOT).resolve()
    if not root.is_dir():
        return
    for jsonl in root.rglob("*.jsonl"):
        if "subagents" in jsonl.parts:
            continue
        yield jsonl


def parse_transcript(path: Path) -> dict[str, Any]:
    messages: list[dict[str, Any]] = []
    mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat()

    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            messages.append(row)

    user_queries: list[str] = []
    assistant_summaries: list[str] = []
    touched_paths: set[str] = set()

    for row in messages:
        role = row.get("role")
        message = row.get("message") or {}
        content = message.get("content") or []

        texts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text = block.get("text") or ""
                texts.append(text)
                for m in re.findall(
                    r"(?:/Users/mac/[^\s\"']+|AI Projects/[^\s\"']+)",
                    text,
                ):
                    touched_paths.add(m)
            elif block.get("type") == "tool_use":
                tool_input = block.get("input") or {}
                if isinstance(tool_input, str):
                    try:
                        tool_input = json.loads(tool_input)
                    except json.JSONDecodeError:
                        tool_input = {}
                if isinstance(tool_input, dict):
                    for key in ("path", "target_directory", "working_directory"):
                        val = tool_input.get(key)
                        if isinstance(val, str):
                            touched_paths.add(val)

        joined = "\n".join(texts)
        if role == "user":
            q = _extract_user_query(joined)
            if q:
                user_queries.append(q)
        elif role == "assistant" and joined.strip():
            assistant_summaries.append(strip_markdown_for_summary(joined, 500))

    session_id = path.parent.name
    if session_id == "agent-transcripts":
        session_id = path.stem

    return {
        "session_id": session_id,
        "file": str(path),
        "mtime": mtime,
        "message_count": len(messages),
        "user_queries": user_queries[:5],
        "first_query": user_queries[0] if user_queries else "",
        "last_assistant": assistant_summaries[-1] if assistant_summaries else "",
        "touched_paths": sorted(touched_paths)[:20],
        "score": _score_session(user_queries, assistant_summaries, touched_paths),
    }


def _extract_user_query(text: str) -> str:
    m = re.search(r"<user_query>\s*([\s\S]*?)\s*</user_query>", text)
    if m:
        return strip_markdown_for_summary(m.group(1).strip(), 300)
    if text.startswith("<user_info>"):
        return ""
    return strip_markdown_for_summary(text, 300)


def _score_session(
    user_queries: list[str],
    assistant_summaries: list[str],
    touched_paths: set[str],
) -> int:
    score = 0
    if user_queries:
        score += 2
    if len(user_queries) >= 2:
        score += 1
    if assistant_summaries:
        score += 1
    if touched_paths:
        score += 2
    first = user_queries[0] if user_queries else ""
    if any(k in first for k in ("实现", "落地", "优化", "生成", "分析", "PRD", "案例", "自动化")):
        score += 2
    if len(first) > 40:
        score += 1
    return score


def scan_transcripts(
    since_mtime: float | None = None,
    min_score: int = 3,
) -> dict[str, Any]:
    """按 AI Projects 相对路径归并对话会话。"""
    by_project: dict[str, list[dict[str, Any]]] = {}
    unmapped: list[dict[str, Any]] = []
    scanned = 0

    for jsonl in iter_transcript_files():
        try:
            st = jsonl.stat()
        except OSError:
            continue
        if since_mtime and st.st_mtime <= since_mtime:
            continue

        scanned += 1
        cursor_folder = _cursor_folder_name(jsonl)
        project_rel = map_cursor_folder_to_project(cursor_folder)
        session = parse_transcript(jsonl)
        session["cursor_folder"] = cursor_folder
        session["project_rel"] = project_rel

        if session["score"] < min_score:
            continue

        if project_rel:
            by_project.setdefault(project_rel, []).append(session)
        else:
            unmapped.append(session)

    for sessions in by_project.values():
        sessions.sort(key=lambda s: s.get("mtime", ""), reverse=True)

    return {
        "scanned_files": scanned,
        "projects": by_project,
        "unmapped": unmapped[:20],
    }


def _cursor_folder_name(jsonl_path: Path) -> str:
    parts = jsonl_path.parts
    try:
        idx = parts.index("projects")
        return parts[idx + 1]
    except (ValueError, IndexError):
        return ""
