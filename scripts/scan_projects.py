"""扫描 AI Projects 下全部子项目，收集结构化信号。"""

from __future__ import annotations

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
from lib.utils import extract_title_from_markdown, read_text, slugify


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


def _load_project_doc(project_dir: Path) -> dict[str, str | None]:
    for name in PROJECT_DOC_CANDIDATES:
        path = project_dir / name
        if not path.is_file():
            continue
        text = read_text(path)
        return {
            "source": name,
            "title": extract_title_from_markdown(text),
            "excerpt": text[:2000],
        }
    return {"source": None, "title": None, "excerpt": None}


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
