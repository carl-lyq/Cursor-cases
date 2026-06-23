"""将已确认的 draft 案例合并到 published。"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.utils import load_json, read_text, save_json, write_text


def load_case_status(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "case-status.json"
    data = load_json(path, default={})
    return data if isinstance(data, dict) else {}


def confirm_cases(
    *,
    portfolio_root: Path,
    case_names: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """
    确认并发布案例。
    case_names: 项目相对路径或 case id；None 表示确认所有 draft 状态案例。
    """
    cases_dir = portfolio_root / "cases"
    draft_dir = portfolio_root / "draft"
    published_dir = portfolio_root / "published"
    state_dir = portfolio_root / "state"

    case_status = load_case_status(state_dir)
    confirmed_at = datetime.now().isoformat(timespec="seconds")
    confirmed: list[str] = []
    skipped: list[str] = []

    draft_cases = {p.stem: p for p in cases_dir.glob("*.md")}
    index = _load_index_from_status(case_status, draft_cases)

    targets = _resolve_targets(case_names, index, case_status)

    if not targets:
        return {
            "ok": False,
            "message": "没有可确认的 draft 案例。请先运行 scan，或检查项目名称。",
            "confirmed": [],
            "skipped": [],
        }

    for key in targets:
        info = index.get(key)
        if not info:
            skipped.append(key)
            continue
        status = (case_status.get(info["name"]) or {}).get("status", "draft")
        if status == "locked":
            skipped.append(f"{info['name']} (locked)")
            continue

        case_file = info["case_file"]
        src = cases_dir / case_file
        if not src.is_file():
            skipped.append(f"{info['name']} (missing file)")
            continue

        # 复制到 published/cases（与 draft 共用 cases/ 目录时直接标记状态）
        case_status[info["name"]] = {
            "status": "confirmed",
            "confirmed_at": confirmed_at,
            "case_file": case_file,
            "run_id": run_id,
        }
        confirmed.append(info["name"])

    # 重建 published 总览
    _rebuild_published_portfolio(
        portfolio_root, case_status, confirmed_only=True
    )

    # 同步 draft 总览（与 published 对齐已确认部分）
    pub_portfolio = published_dir / "AI-Projects-Portfolio.md"
    if pub_portfolio.is_file():
        shutil.copy2(pub_portfolio, draft_dir / "AI-Projects-Portfolio.md")

    save_json(state_dir / "case-status.json", case_status)

    pending = state_dir / "PENDING_REVIEW"
    if pending.is_file() and confirmed:
        pending.unlink()

    last_confirmed = {
        "confirmed_at": confirmed_at,
        "cases": confirmed,
        "run_id": run_id,
    }
    save_json(state_dir / "last-confirmed.json", last_confirmed)

    return {
        "ok": True,
        "message": f"已确认 {len(confirmed)} 个案例并更新 published/。",
        "confirmed": confirmed,
        "skipped": skipped,
    }


def _load_index_from_status(
    case_status: dict[str, Any],
    draft_cases: dict[str, Path],
) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for stem, path in draft_cases.items():
        # 从案例卡尾部或 status 反查 name
        name = stem
        for proj_name, meta in case_status.items():
            if isinstance(meta, dict) and meta.get("case_file") == path.name:
                name = proj_name
                break
        index[stem] = {"name": name, "case_file": path.name, "id": stem}
        # 也用项目名作为 key
        index[name] = index[stem]
    return index


def _resolve_targets(
    case_names: list[str] | None,
    index: dict[str, dict[str, str]],
    case_status: dict[str, Any],
) -> list[str]:
    if case_names:
        keys: list[str] = []
        for name in case_names:
            if name in index:
                keys.append(name if name in index and "case_file" in index[name] else name)
            else:
                # 模糊匹配
                for k, v in index.items():
                    if name in v.get("name", ""):
                        keys.append(k)
                        break
        return list(dict.fromkeys(keys))

    # 全部 draft（未 confirmed / locked）
    keys: list[str] = []
    seen_names: set[str] = set()
    for proj_name, meta in case_status.items():
        if not isinstance(meta, dict):
            continue
        status = meta.get("status", "draft")
        if status not in ("draft",):
            continue
        case_file = meta.get("case_file")
        if not case_file:
            continue
        stem = Path(case_file).stem
        if proj_name in seen_names:
            continue
        seen_names.add(proj_name)
        keys.append(stem)
    return keys


def _rebuild_published_portfolio(
    portfolio_root: Path,
    case_status: dict[str, Any],
    *,
    confirmed_only: bool,
) -> None:
    from synthesize_cases import build_portfolio_index

    cases_dir = portfolio_root / "cases"
    published_dir = portfolio_root / "published"
    published_dir.mkdir(parents=True, exist_ok=True)

    case_files: list[tuple[str, str, str]] = []
    for path in sorted(cases_dir.glob("*.md")):
        name = path.stem
        for proj_name, meta in case_status.items():
            if isinstance(meta, dict) and meta.get("case_file") == path.name:
                if confirmed_only and meta.get("status") != "confirmed":
                    continue
                title = _extract_title(read_text(path))
                case_files.append((proj_name, title, path.name))
                break
        else:
            if not confirmed_only:
                title = _extract_title(read_text(path))
                case_files.append((name, title, path.name))

    content = build_portfolio_index(
        case_files,
        title="AI Projects · Cursor 提效案例集（正式版）",
        subtitle="**已确认**案例汇总，可作为汇报与分享材料。",
    )
    write_text(published_dir / "AI-Projects-Portfolio.md", content)


def _extract_title(md: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "未命名案例"
