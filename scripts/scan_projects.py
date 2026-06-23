"""扫描 AI Projects 下全部子项目，收集结构化信号。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from config import (
    AI_IMPACT_FILENAMES,
    AI_PROJECTS_ROOT,
    PROJECT_DOC_CANDIDATES,
    SKIP_DIR_NAMES,
)
from lib.git_signals import collect_git_signals
from lib.utils import extract_title_from_markdown, parse_project_doc, read_text, slugify


def discover_projects(root: Path | None = None) -> list[Path]:
    root = (root or AI_PROJECTS_ROOT).resolve()
    projects: list[Path] = []

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name in SKIP_DIR_NAMES or child.name.startswith("."):
            continue
        projects.append(child)

    # 一层嵌套：Miscs/押题班画像 等独立工作区
    misc_like = root / "Miscs"
    if misc_like.is_dir():
        for child in sorted(misc_like.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            projects.append(child)

    # 去重保序
    seen: set[str] = set()
    unique: list[Path] = []
    for p in projects:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _load_ai_impact(project_dir: Path) -> dict[str, Any] | None:
    for rel in AI_IMPACT_FILENAMES:
        path = project_dir / rel
        if not path.is_file():
            continue
        try:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
        except (OSError, yaml.YAMLError):
            continue
    return None


def _project_tokens(project_name: str) -> list[str]:
    """从项目路径提取用于文档匹配的关键词。"""
    tokens: list[str] = []
    for part in re.split(r"[/\\]", project_name):
        part = part.strip()
        if len(part) >= 2:
            tokens.append(part)
        for piece in re.split(r"[\s_\-]+", part):
            if len(piece) >= 2 and piece not in tokens:
                tokens.append(piece)
    return tokens


def _text_matches_project(text: str, tokens: list[str]) -> bool:
    if not text or not tokens:
        return False
    return any(t in text for t in tokens)


def _score_doc_candidate(path: Path, project_name: str) -> int:
    """为项目根目录下的候选文档打分，越高越适合作为案例卡主文档。"""
    name = path.name
    tokens = _project_tokens(project_name)
    score = 0

    if name == "PRD.md":
        score += 30
    if re.match(r"^00-", name):
        score += 25
    if re.match(r"^01-", name):
        score += 12
    if name == "README.md":
        score += 10
    if name in PROJECT_DOC_CANDIDATES:
        score += 8

    if _text_matches_project(name, tokens):
        score += 15

    title = ""
    try:
        head = read_text(path)[:2000]
        title = extract_title_from_markdown(head)
    except OSError:
        pass

    if _text_matches_project(title, tokens):
        score += 20

    if "PRD" in name.upper():
        score += 5
        if _text_matches_project(name, tokens) or _text_matches_project(title, tokens):
            score += 20
        elif not _text_matches_project(name, tokens) and not _text_matches_project(title, tokens):
            score -= 30

    if re.search(r"todo|待办", name, re.I):
        score -= 12

    # 极短 README 不如其他文档
    if name == "README.md":
        try:
            if len(read_text(path).strip()) < 80:
                score -= 15
        except OSError:
            pass

    return score


def _find_project_doc_path(project_dir: Path) -> Path | None:
    candidates = [
        p
        for p in sorted(project_dir.glob("*.md"))
        if p.is_file() and "node_modules" not in p.parts
    ]
    if not candidates:
        return None

    project_name = project_dir.name
    if project_dir.parent.name == "Miscs":
        project_name = f"Miscs/{project_dir.name}"

    scored = [(p, _score_doc_candidate(p, project_name)) for p in candidates]
    scored.sort(key=lambda x: (-x[1], x[0].name))
    best_path, best_score = scored[0]
    if best_score <= 0 and len(scored) > 1:
        # 全是低分候选时，仍取最高但优先非 PRD
        for p, s in scored:
            if "PRD" not in p.name.upper():
                return p
    return best_path if best_score > 0 else scored[0][0]


def _load_project_doc(project_dir: Path) -> dict[str, Any]:
    path = _find_project_doc_path(project_dir)
    if not path:
        return {
            "source": None,
            "title": None,
            "excerpt": None,
            "parsed": {},
        }
    text = read_text(path)
    parsed = parse_project_doc(text)
    return {
        "source": path.name,
        "title": parsed.get("title"),
        "excerpt": parsed.get("excerpt"),
        "parsed": parsed,
    }


def scan_all_projects(root: Path | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for project_dir in discover_projects(root):
        rel = project_dir.relative_to(AI_PROJECTS_ROOT.resolve())
        doc = _load_project_doc(project_dir)
        impact = _load_ai_impact(project_dir)
        git = collect_git_signals(project_dir)

        results.append(
            {
                "id": slugify(str(rel)),
                "name": str(rel),
                "path": str(project_dir),
                "relative_to_ai_projects": rel.as_posix(),
                "doc": doc,
                "ai_impact": impact,
                "git": git,
            }
        )
    return results
