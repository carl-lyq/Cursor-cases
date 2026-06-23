"""从 Git 历史提取项目活跃信号。"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _run_git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def collect_git_signals(project_dir: Path, days: int = 90) -> dict[str, Any]:
    """收集单个项目目录的 Git 信号（项目自身或父仓库内的相对路径）。"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    rel = _relative_to_repo(project_dir)
    repo_root = _find_git_root(project_dir)

    signals: dict[str, Any] = {
        "has_git": repo_root is not None,
        "repo_root": str(repo_root) if repo_root else None,
        "relative_path": rel,
        "commits_recent": 0,
        "authors_recent": [],
        "last_commit_date": None,
        "changed_files_recent": [],
    }

    if not repo_root:
        return signals

    pathspec = rel or "."
    log_format = "%h|%an|%ci|%s"
    log = _run_git(
        [
            "log",
            f"--since={since}",
            "--pretty=format:" + log_format,
            "--",
            pathspec,
        ],
        repo_root,
    )

    commits = []
    authors: set[str] = set()
    for line in log.splitlines():
        if "|" not in line:
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        commits.append(
            {
                "hash": parts[0],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3],
            }
        )
        authors.add(parts[1])

    signals["commits_recent"] = len(commits)
    signals["authors_recent"] = sorted(authors)
    if commits:
        signals["last_commit_date"] = commits[0]["date"]
        signals["recent_subjects"] = [c["subject"] for c in commits[:5]]

    name_only = _run_git(
        [
            "log",
            f"--since={since}",
            "--name-only",
            "--pretty=format:",
            "--",
            pathspec,
        ],
        repo_root,
    )
    files = sorted({f for f in name_only.splitlines() if f.strip()})
    signals["changed_files_recent"] = files[:30]

    return signals


def _find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _relative_to_repo(project_dir: Path) -> str | None:
    repo_root = _find_git_root(project_dir)
    if not repo_root:
        return None
    try:
        rel = project_dir.resolve().relative_to(repo_root.resolve())
        return "." if rel == Path(".") else rel.as_posix()
    except ValueError:
        return None
