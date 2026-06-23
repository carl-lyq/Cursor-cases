"""Cursor 案例库 — 路径与常量配置。"""

from __future__ import annotations

import os
from pathlib import Path

# 案例库根目录（本仓库）
PORTFOLIO_ROOT = Path(__file__).resolve().parent.parent

# AI Projects 父目录（与案例库平级）
AI_PROJECTS_ROOT = Path(
    os.environ.get(
        "AI_PROJECTS_ROOT",
        str(PORTFOLIO_ROOT.parent),
    )
).resolve()

# Cursor 本机项目元数据（Agent 对话）
CURSOR_PROJECTS_ROOT = Path(
    os.environ.get(
        "CURSOR_PROJECTS_ROOT",
        os.path.expanduser("~/.cursor/projects"),
    )
).resolve()

# 扫描时跳过的目录名（精确匹配）
SKIP_DIR_NAMES = {
    ".git",
    ".cursor",
    ".venv",
    "node_modules",
    "__pycache__",
    "Cursor案例库",
    "躺着学AI项目库",
}

# 用于推断项目简介的文档（按优先级）
PROJECT_DOC_CANDIDATES = (
    "PRD.md",
    "README.md",
    "MISSION.md",
    "AGENTS.md",
    "COURSE-PLAN.md",
)

# 人工维护的项目事实卡片（可选，放在各子项目 .cursor/ 下）
AI_IMPACT_FILENAMES = (
    ".cursor/ai-impact.yaml",
    ".cursor/ai-impact.yml",
    "ai-impact.yaml",
)

# 案例库子目录
DIRS = {
    "published": PORTFOLIO_ROOT / "published",
    "draft": PORTFOLIO_ROOT / "draft",
    "cases": PORTFOLIO_ROOT / "cases",
    "inbox": PORTFOLIO_ROOT / "inbox",
    "reviews": PORTFOLIO_ROOT / "reviews",
    "state": PORTFOLIO_ROOT / "state",
    "templates": PORTFOLIO_ROOT / "templates",
}

BRANCH_DRAFT = "portfolio-draft"
BRANCH_PUBLISHED = "main"
