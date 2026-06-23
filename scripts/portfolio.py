#!/usr/bin/env python3
"""
Cursor 案例库 — 命令行入口。

用法：
  python3 scripts/portfolio.py scan [--repo-only | --transcripts-only]
  python3 scripts/portfolio.py status
  python3 scripts/portfolio.py confirm [--cases 项目名 ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 保证 scripts/ 在 path 中
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from config import DIRS, PORTFOLIO_ROOT  # noqa: E402
from confirm import confirm_cases  # noqa: E402
from generate_review import generate_review  # noqa: E402
from lib.sanitize import sanitize_sessions_for_storage  # noqa: E402
from lib.utils import load_json, save_json, utc_now_iso, write_text  # noqa: E402
from scan_projects import scan_all_projects  # noqa: E402
from scan_transcripts import scan_transcripts  # noqa: E402
from synthesize_cases import (  # noqa: E402
    build_portfolio_index,
    synthesize_case_markdown,
    write_case_file,
)


def _attribute_sessions_to_subprojects(
    project_map: dict,
    transcript_by_project: dict,
) -> None:
    """将父目录（如 Miscs）的会话按 touched_paths 拆到子项目。"""
    for parent_key in list(transcript_by_project.keys()):
        if parent_key in (".", "") or "/" in parent_key:
            continue
        sessions = transcript_by_project.get(parent_key, [])
        if not sessions:
            continue
        remaining: list[dict] = []
        for session in sessions:
            matched = _match_session_to_child(parent_key, session, project_map)
            if matched:
                transcript_by_project.setdefault(matched, []).append(session)
            else:
                remaining.append(session)
        transcript_by_project[parent_key] = remaining


def _match_session_to_child(
    parent: str,
    session: dict,
    project_map: dict,
) -> str | None:
    paths = session.get("touched_paths") or []
    candidates = [
        name
        for name in project_map
        if name.startswith(parent + "/") and name != parent
    ]
    candidates.sort(key=len, reverse=True)
    blob = "\n".join(paths)
    for name in candidates:
        suffix = name[len(parent) + 1 :]
        if suffix in blob or name in blob:
            return name
    return None


def _apply_project_overrides(case_status: dict) -> dict:
    """应用 state/project-overrides.json 中的忽略与合并规则。"""
    overrides = load_json(DIRS["state"] / "project-overrides.json", default={})
    for name in overrides.get("ignored", []):
        case_status.setdefault(name, {})
        case_status[name]["status"] = "ignored"
    for name, canonical in (overrides.get("merged_into") or {}).items():
        case_status.setdefault(name, {})
        case_status[name]["status"] = "ignored"
        case_status[name]["merged_into"] = canonical
    return case_status


SESSION_DIGESTS_FILE = "session-digests.json"


def _load_session_digests(state_dir: Path) -> dict[str, Any]:
    return load_json(state_dir / SESSION_DIGESTS_FILE, default={}) or {}


def _merge_sanitized_projects(
    existing: dict[str, list[dict]],
    incoming: dict[str, list[dict]],
    *,
    per_project_limit: int = 15,
) -> dict[str, list[dict]]:
    merged: dict[str, dict[str, dict]] = {}
    for proj, sessions in {**existing, **incoming}.items():
        bucket = merged.setdefault(proj, {})
        for s in sessions:
            sid = s.get("session_id") or s.get("mtime") or ""
            if sid:
                bucket[sid] = s
    out: dict[str, list[dict]] = {}
    for proj, by_id in merged.items():
        out[proj] = sorted(by_id.values(), key=lambda x: x.get("mtime", ""), reverse=True)[
            :per_project_limit
        ]
    return out


def _save_session_digests(
    state_dir: Path,
    projects: dict[str, list[dict]],
    *,
    scanned_files: int = 0,
    unmapped_count: int = 0,
) -> None:
    existing = _load_session_digests(state_dir)
    merged = _merge_sanitized_projects(existing.get("projects") or {}, projects)
    payload = {
        "updated_at": utc_now_iso(),
        "sanitized": True,
        "note": "仅含脱敏后的对话摘要，不含原始 transcript；勿提交密钥或客户隐私原文",
        "scanned_files_last_run": scanned_files,
        "unmapped_count": unmapped_count,
        "projects": merged,
    }
    save_json(state_dir / SESSION_DIGESTS_FILE, payload)


def _transcript_data_from_digests(state_dir: Path) -> dict:
    digests = _load_session_digests(state_dir)
    return {
        "scanned_files": 0,
        "projects": digests.get("projects") or {},
        "unmapped": [],
        "from_digest": True,
        "digest_updated_at": digests.get("updated_at"),
    }


def cmd_scan(args: argparse.Namespace) -> int:
    run_id = datetime.now().strftime("%Y-%m-%d")
    mode = "full"
    if args.repo_only:
        mode = "repo-only"
    if args.transcripts_only:
        mode = "transcripts-only"

    state_dir = DIRS["state"]
    state_dir.mkdir(parents=True, exist_ok=True)
    last_scan = load_json(state_dir / "last-scan.json", default={})
    case_status = load_json(state_dir / "case-status.json", default={})
    case_status = _apply_project_overrides(case_status)

    projects: list[dict] = []
    transcript_data: dict = {"projects": {}, "scanned_files": 0}

    if mode in ("full", "repo-only"):
        projects = scan_all_projects()

    if mode in ("full", "transcripts-only"):
        since_ts = None
        prev_ts = last_scan.get("transcript_last_mtime")
        if prev_ts and mode == "full":
            since_ts = float(prev_ts)
        if mode == "transcripts-only" and prev_ts:
            since_ts = float(prev_ts)
        if mode == "full" and not prev_ts:
            transcript_data = scan_transcripts(since_mtime=None)
        else:
            transcript_data = scan_transcripts(since_mtime=since_ts)

        sanitized = sanitize_sessions_for_storage(transcript_data.get("projects") or {})
        transcript_data["projects"] = sanitized
        _save_session_digests(
            state_dir,
            sanitized,
            scanned_files=transcript_data.get("scanned_files", 0),
            unmapped_count=len(transcript_data.get("unmapped") or []),
        )
    elif mode == "repo-only":
        transcript_data = _transcript_data_from_digests(state_dir)

    # 合并项目 + 对话
    project_map = {p["name"]: p for p in projects}
    _attribute_sessions_to_subprojects(
        project_map, transcript_data.get("projects", {})
    )
    for proj_rel, sessions in transcript_data.get("projects", {}).items():
        key = proj_rel if proj_rel != "." else "."
        if key not in project_map and key != ".":
            # 嵌套项目可能只在 transcript 出现
            project_map[key] = {
                "id": key.replace("/", "-"),
                "name": key,
                "path": str((PORTFOLIO_ROOT.parent / key).resolve()),
                "doc": {},
                "ai_impact": None,
                "git": {},
            }

    new_cases: list[dict] = []
    updated_cases: list[dict] = []
    needs_check: list[dict] = []
    case_entries: list[tuple[str, str, str]] = []

    cases_dir = DIRS["cases"]
    cases_dir.mkdir(parents=True, exist_ok=True)
    inbox_dir = DIRS["inbox"]
    inbox_dir.mkdir(parents=True, exist_ok=True)

    for name, project in sorted(project_map.items(), key=lambda x: x[0]):
        sessions = transcript_data.get("projects", {}).get(name, [])
        if name == ".":
            sessions = transcript_data.get("projects", {}).get(".", sessions)

        status = case_status.get(name) or {}
        if status.get("status") == "ignored":
            continue

        if status.get("status") == "locked" and status.get("case_file"):
            case_file = status["case_file"]
            case_path = cases_dir / case_file
            if case_path.is_file():
                md = case_path.read_text(encoding="utf-8")
                title = _title_from_md(md)
                case_entries.append((name, title, case_file))
                continue

        md = synthesize_case_markdown(project, sessions, status)
        case_file = write_case_file(cases_dir, project, md, status)
        content_hash = hashlib.sha256(md.encode()).hexdigest()[:12]

        prev_hash = status.get("content_hash")
        title = _title_from_md(md)

        case_status.setdefault(name, {})
        case_status[name].update(
            {
                "case_file": case_file,
                "content_hash": content_hash,
                "status": status.get("status") or "draft",
                "updated_at": utc_now_iso(),
            }
        )

        case_entries.append((name, title, case_file))

        item = {
            "name": name,
            "id": project["id"],
            "title": title,
            "case_file": case_file,
            "one_liner": (project.get("ai_impact") or {}).get("one_liner"),
        }

        if not prev_hash:
            new_cases.append(item)
        elif prev_hash != content_hash and status.get("status") != "locked":
            item["change_summary"] = "自动扫描检测到内容更新"
            updated_cases.append(item)

        # 有推断性数字时标记待核实
        impact = (project.get("ai_impact") or {}).get("impact") or {}
        if not impact.get("time_ratio") and sessions and len(sessions) >= 2:
            needs_check.append(
                {
                    "project": name,
                    "reason": "有多次 Agent 协作，但尚未填写量化提效数据（可在 .cursor/ai-impact.yaml 补充）",
                }
            )

    # draft 总览
    draft_dir = DIRS["draft"]
    draft_dir.mkdir(parents=True, exist_ok=True)
    portfolio_md = build_portfolio_index(
        case_entries,
        title="AI Projects · Cursor 提效案例集（草稿）",
        subtitle="**草稿版**：未经确认，请勿直接用于对外汇报。",
    )
    write_text(draft_dir / "AI-Projects-Portfolio.md", portfolio_md)

    # inbox 存档
    inbox_payload = {
        "run_id": run_id,
        "mode": mode,
        "finished_at": utc_now_iso(),
        "projects": projects,
        "transcripts": {
            "scanned_files": transcript_data.get("scanned_files", 0),
            "project_keys": list(transcript_data.get("projects", {}).keys()),
            "unmapped_count": len(transcript_data.get("unmapped", [])),
            "from_digest": bool(transcript_data.get("from_digest")),
            "digest_updated_at": transcript_data.get("digest_updated_at"),
        },
    }
    write_text(
        inbox_dir / f"{run_id}-scan.json",
        json.dumps(inbox_payload, ensure_ascii=False, indent=2) + "\n",
    )

    # 更新 last-scan
    max_mtime = 0.0
    for sessions in transcript_data.get("projects", {}).values():
        for s in sessions:
            try:
                from datetime import datetime as dt

                ts = dt.fromisoformat(s["mtime"]).timestamp()
                max_mtime = max(max_mtime, ts)
            except (ValueError, KeyError, OSError):
                pass

    save_json(
        state_dir / "last-scan.json",
        {
            "repo_last_scan": utc_now_iso(),
            "transcript_last_mtime": max_mtime or last_scan.get("transcript_last_mtime"),
            "last_run_id": run_id,
            "mode": mode,
        },
    )
    save_json(state_dir / "case-status.json", case_status)

    scan_meta = {
        "finished_at": utc_now_iso(),
        "mode": mode,
        "project_count": len(project_map),
        "session_count": sum(
            len(v) for v in transcript_data.get("projects", {}).values()
        ),
        "new_cases": new_cases,
        "updated_cases": updated_cases,
        "needs_user_check": needs_check,
        "transcript_backlog": bool(
            last_scan.get("transcript_last_mtime") and mode != "repo-only"
        ),
    }

    generate_review(
        run_id,
        scan_meta,
        case_status,
        reviews_dir=DIRS["reviews"],
        published_dir=DIRS["published"],
        draft_dir=DIRS["draft"],
    )

    print(f"✓ 扫描完成 ({mode})")
    print(f"  项目：{len(project_map)} · 新案例：{len(new_cases)} · 更新：{len(updated_cases)}")
    print(f"  待确认清单：reviews/LATEST.md")
    if new_cases or updated_cases:
        print(f"  状态：有待确认项 → state/PENDING_REVIEW")
    return 0


def cmd_confirm(args: argparse.Namespace) -> int:
    result = confirm_cases(
        portfolio_root=PORTFOLIO_ROOT,
        case_names=args.cases or None,
    )
    if result["ok"]:
        print(result["message"])
        for name in result["confirmed"]:
            print(f"  ✓ {name}")
        if result["skipped"]:
            print("  跳过：", ", ".join(result["skipped"]))
        return 0
    print(result["message"], file=sys.stderr)
    return 1


def cmd_status(_: argparse.Namespace) -> int:
    state = load_json(DIRS["state"] / "last-scan.json", default={})
    case_status = load_json(DIRS["state"] / "case-status.json", default={})
    pending = (DIRS["state"] / "PENDING_REVIEW").is_file()

    draft_count = sum(
        1 for v in case_status.values() if isinstance(v, dict) and v.get("status") == "draft"
    )
    confirmed_count = sum(
        1
        for v in case_status.values()
        if isinstance(v, dict) and v.get("status") == "confirmed"
    )

    print("Cursor 案例库状态")
    print(f"  上次扫描：{state.get('repo_last_scan', '从未')}")
    print(f"  上次 run_id：{state.get('last_run_id', '-')}")
    print(f"  案例：draft {draft_count} · confirmed {confirmed_count}")
    print(f"  待确认：{'是' if pending else '否'}")
    if pending:
        print("  → 打开 reviews/LATEST.md")
    return 0


def _title_from_md(md: str) -> str:
    for line in md.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "未命名"


def main() -> int:
    parser = argparse.ArgumentParser(description="Cursor 案例库工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="扫描项目与 Agent 对话，生成草稿")
    p_scan.add_argument("--repo-only", action="store_true", help="仅扫 Git/文档（GitHub Action 用）")
    p_scan.add_argument("--transcripts-only", action="store_true", help="仅扫本机 Agent 对话")

    sub.add_parser("status", help="查看案例库状态")

    p_confirm = sub.add_parser("confirm", help="确认 draft 并发布到 published/")
    p_confirm.add_argument("--cases", nargs="*", help="指定项目名，默认全部 draft")

    args = parser.parse_args()
    if args.command == "scan":
        return cmd_scan(args)
    if args.command == "confirm":
        return cmd_confirm(args)
    if args.command == "status":
        return cmd_status(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
