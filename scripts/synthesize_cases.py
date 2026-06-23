"""将扫描信号合成为可读案例卡（业务语言，非技术向）。"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.sanitize import sanitize_text
from lib.utils import strip_markdown_for_summary, write_text


def synthesize_case_markdown(
    project: dict[str, Any],
    sessions: list[dict[str, Any]] | None = None,
    existing_status: dict[str, Any] | None = None,
) -> str:
    name = project["name"]
    doc = project.get("doc") or {}
    parsed = doc.get("parsed") or {}
    impact = project.get("ai_impact") or {}
    git = project.get("git") or {}
    sessions = sessions or []

    title = (
        impact.get("project")
        or doc.get("title")
        or impact.get("one_liner")
        or parsed.get("title")
        or name
    )

    domain = impact.get("domain") or _guess_domain(
        f"{parsed.get('title', '')} {doc.get('title', '')}", name
    )
    traditional = impact.get("traditional") or {}
    with_cursor = impact.get("with_cursor") or {}
    impact_block = impact.get("impact") or {}

    lines: list[str] = [
        f"# {title}",
        "",
        f"> 项目路径：`{name}` · 领域：{domain}",
        "",
    ]

    # 一句话摘要
    one_liner = impact.get("one_liner") or parsed.get("goals") or ""
    if one_liner and one_liner != title:
        lines.append(f"**一句话**：{strip_markdown_for_summary(one_liner, 200)}")
        lines.append("")

    # 业务背景（谁、什么场景、要解决什么）
    lines.append("## 业务背景")
    lines.append("")
    lines.extend(_build_business_background(impact, parsed, doc, name))
    lines.append("")

    # 工作痛点
    pain_lines = _build_pain_points_section(traditional, impact, parsed, name)
    if pain_lines:
        lines.append("## 工作痛点")
        lines.append("")
        lines.extend(pain_lines)
        lines.append("")

    # 项目要做什么（业务交付视角）
    deliverables = _build_deliverables_section(parsed, git, sessions, impact)
    if deliverables:
        lines.append("## 项目要做什么")
        lines.append("")
        lines.append("从业务视角，本项目最终要交付的是：")
        lines.append("")
        lines.extend(deliverables)

    # 工作方式对比：传统 vs Cursor
    lines.append("## 工作方式对比")
    lines.append("")
    lines.extend(_build_workflow_comparison(traditional, with_cursor, sessions, git, doc, parsed, name))
    lines.append("")

    # 提效与业务价值
    lines.append("## 提效与业务价值")
    lines.append("")
    lines.extend(_build_business_value_section(impact_block, traditional, impact, sessions, git, parsed, doc))
    lines.append("")

    # Cursor / AI 能力与工具
    cap_lines = _build_cursor_capabilities_section(with_cursor, sessions, impact, doc)
    if cap_lines:
        lines.append("## Cursor / AI 能力与工具")
        lines.append("")
        lines.extend(cap_lines)

    # 近期协作摘要
    if sessions:
        lines.append("## 近期协作摘要")
        lines.append("")
        lines.append(
            f"近阶段共有 **{len(sessions)}** 次 Cursor Agent 会话与本项目相关"
            "（以下为脱敏摘要，不含原始对话与密钥）。"
        )
        lines.append("")
        for s in sessions[:5]:
            date = (s.get("mtime") or "")[:10]
            q = _safe_session_text(s.get("first_query") or "（无明确任务描述）", 280)
            lines.append(f"### {date}")
            lines.append("")
            lines.append(f"**任务**：{q}")
            last = s.get("last_assistant")
            if last:
                lines.append("")
                lines.append(f"**结果摘要**：{_safe_session_text(last, 280)}")
            touched = _humanize_touched_paths(s.get("touched_paths") or [])
            if touched:
                lines.append("")
                lines.append("**涉及文件**：" + "、".join(touched[:5]))
            lines.append("")

    # 仓库活跃信号
    git_summary = _summarize_git(git)
    if git_summary:
        lines.append("## 仓库活跃信号")
        lines.append("")
        lines.extend(git_summary)
        lines.append("")

    pending = (existing_status or {}).get("pending_append")
    if pending:
        lines.append("---")
        lines.append("")
        lines.append(f"<!-- 待确认更新 {pending} -->")
        lines.append("")

    lines.append("---")
    lines.append("")
    doc_src = doc.get("source") or "无"
    lines.append(
        f"*本卡由 Cursor 案例库自动整理 · 状态：{(existing_status or {}).get('status', 'draft')} · "
        f"文档来源：{doc_src} · 生成于 {datetime.now().strftime('%Y-%m-%d')}*"
    )
    lines.append("")

    return "\n".join(lines)


def _build_business_background(
    impact: dict[str, Any],
    parsed: dict[str, Any],
    doc: dict[str, Any],
    name: str,
) -> list[str]:
    lines: list[str] = []
    users = impact.get("users")
    scenario = impact.get("scenario")
    if users:
        lines.append(f"**谁在用**：{users}")
        lines.append("")
    if scenario:
        lines.append(f"**典型场景**：{scenario}")
        lines.append("")

    background = (
        impact.get("background")
        or parsed.get("background")
        or _background_from_doc(doc, parsed)
        or f"「{name}」是 AI Projects 工作区中的活跃项目，具体业务背景待补充。"
    )
    background = strip_markdown_for_summary(background, 600)
    if lines:
        lines.append("")
    lines.append(background)

    solution = impact.get("solution")
    if solution:
        lines.append("")
        lines.append(f"**要解决什么**：{strip_markdown_for_summary(str(solution), 300)}")

    return lines


def _build_pain_points_section(
    traditional: dict[str, Any],
    impact: dict[str, Any],
    parsed: dict[str, Any],
    name: str,
) -> list[str]:
    points = _as_str_list(impact.get("pain_points"))
    if not points and isinstance(traditional, dict) and traditional.get("pain"):
        pain_raw = str(traditional["pain"])
        points = [p.strip() for p in re.split(r"[；;、\n]", pain_raw) if p.strip()]

    if not points:
        title = f"{parsed.get('title', '')} {name}"
        inferred = _infer_pain_bullets(title)
        if inferred:
            points = inferred

    if not points:
        return []

    lines: list[str] = []
    for p in points[:6]:
        lines.append(f"- {p}")
    if isinstance(traditional, dict) and traditional.get("baseline"):
        lines.append("")
        lines.append(f"传统方式下，完成一版可用结果通常需要 **{traditional['baseline']}**。")
    return lines


def _infer_pain_bullets(title: str) -> list[str]:
    if any(k in title for k in ("画像", "看板", "数据", "签转")):
        return [
            "手工做表、改统计维度就要重头再来",
            "口径难统一，不同人算出的数对不上",
            "不便向管理层或业务方做可交互演示",
        ]
    if any(k in title for k in ("PRD", "落地页", "Demo", "评审")):
        return [
            "需求文档长、结构复杂，评审时难以一眼看清",
            "原型、文档、埋点分散维护，改版要对齐多份材料",
            "产品、设计、研发信息不同步，会议反复对齐",
        ]
    if any(k in title for k in ("申报", "创客")):
        return [
            "材料分散在多个目录，找引用源费时",
            "口径不统一，临近截止常通宵改稿",
            "多人协作难以追溯「这句话从哪来」",
        ]
    if any(k in title for k in ("批改", "仿人工")):
        return [
            "老师手工改一份作文耗时长，难以规模化",
            "批改风格因人而异，质量难统一",
            "重复性修订占用大量教研精力",
        ]
    if any(k in title for k in ("爬", "电子书", "EPUB")):
        return [
            "站点反爬或结构复杂，脚本易失败",
            "正文提取不干净，手工整理不可行",
            "千条级内容难以沉淀为可阅读成品",
        ]
    if any(k in title for k in ("话术", "营销", "课程")):
        return [
            "话术优化靠个人经验，难以复用",
            "审校周期长，缺乏统一检查清单",
            "跨课程风格不一致",
        ]
    if any(k in title for k in ("Skill", "teach", "Demo", "技能")):
        return [
            "重复性工作流程每次从零摸索",
            "经验停留在个人，团队难以复用",
            "集成步骤易漏，踩坑成本高",
        ]
    return []


def _build_workflow_comparison(
    traditional: dict[str, Any],
    with_cursor: dict[str, Any],
    sessions: list[dict[str, Any]],
    git: dict[str, Any],
    doc: dict[str, Any],
    parsed: dict[str, Any],
    name: str,
) -> list[str]:
    lines: list[str] = []

    lines.append("### 传统方式")
    lines.append("")
    if isinstance(traditional, dict) and traditional.get("workflow"):
        lines.append(traditional["workflow"])
    else:
        lines.append(_infer_traditional(parsed, doc, sessions, name))
    lines.append("")

    lines.append("### 用 Cursor 之后")
    lines.append("")
    if isinstance(with_cursor, dict) and with_cursor.get("workflow"):
        wf = str(with_cursor["workflow"]).strip()
        # 将多行 workflow 拆成步骤列表，更易读
        steps = [s.strip() for s in re.split(r"\n+", wf) if s.strip()]
        if len(steps) >= 2 and all(len(s) < 120 for s in steps):
            for i, step in enumerate(steps, 1):
                step = re.sub(r"^[→\-\d\.]+\s*", "", step)
                lines.append(f"{i}. {step}")
        else:
            lines.append(wf)
    else:
        cursor_parts = _infer_cursor_workflow(sessions, git, doc, parsed, name)
        lines.extend(cursor_parts)

    return lines


def _build_business_value_section(
    impact_block: dict[str, Any],
    traditional: dict[str, Any],
    impact: dict[str, Any],
    sessions: list[dict[str, Any]],
    git: dict[str, Any],
    parsed: dict[str, Any],
    doc: dict[str, Any],
) -> list[str]:
    lines: list[str] = []

    baseline = ""
    if isinstance(traditional, dict):
        baseline = str(traditional.get("baseline") or "")

    time_ratio = impact_block.get("time_ratio") if isinstance(impact_block, dict) else None
    if baseline or time_ratio:
        lines.append("| 维度 | 传统方式 | 用 Cursor 后 |")
        lines.append("|------|----------|--------------|")
        if baseline and time_ratio:
            lines.append(f"| **耗时** | {baseline} | {time_ratio} |")
        elif time_ratio:
            lines.append(f"| **耗时** | 显著更长 | {time_ratio} |")
        elif baseline:
            lines.append(f"| **耗时** | {baseline} | 明显缩短 |")
        if isinstance(impact_block, dict) and impact_block.get("quality"):
            lines.append(f"| **质量/口径** | 易不一致、难复用 | {impact_block['quality']} |")
        lines.append("")

    bullets: list[str] = []
    beneficiaries = impact.get("beneficiaries")
    if beneficiaries:
        bullets.append(f"- **谁直接受益**：{beneficiaries}")

    if isinstance(impact_block, dict):
        if impact_block.get("enabled"):
            bullets.append(f"- **业务上新可能**：{impact_block['enabled']}")

    if not bullets:
        bullets = _infer_impact(sessions, git, parsed, doc)
        bullets = [
            b.replace("**能力覆盖**", "**业务覆盖**").replace("**协作频次**", "**协作效率**")
            for b in bullets
        ]

    lines.extend(bullets or ["- 待补充：请在本项目 `.cursor/ai-impact.yaml` 中填写 `impact` 与 `beneficiaries`。"])
    return lines


def _build_deliverables_section(
    parsed: dict[str, Any],
    git: dict[str, Any],
    sessions: list[dict[str, Any]],
    impact: dict[str, Any] | None = None,
) -> list[str]:
    impact = impact or {}
    yaml_items = impact.get("deliverables")
    if isinstance(yaml_items, list) and yaml_items:
        lines = []
        summary = impact.get("deliverables_summary")
        if summary:
            lines.append(strip_markdown_for_summary(summary, 300))
            lines.append("")
        lines.extend(_format_grouped_deliverables(yaml_items))
        return lines

    summary = impact.get("deliverables_summary") or parsed.get("goals") or ""
    items: list[str] = []
    workflow = ""
    wc = impact.get("with_cursor")
    if isinstance(wc, dict):
        workflow = str(wc.get("workflow") or "")
    skip_prd_features = bool(
        impact.get("one_liner")
        and any(k in workflow.lower() for k in ("html", "展示", "评审", "可视化"))
    )

    feature_items: list[str] = []
    if not skip_prd_features:
        for feat in parsed.get("features") or []:
            if _is_poor_deliverable_line(feat):
                continue
            feature_items.append(feat)

    lines: list[str] = []
    if summary:
        lines.append(strip_markdown_for_summary(summary, 300))
        lines.append("")

    if feature_items:
        lines.append("### 核心功能")
        lines.append("")
        for feat in feature_items[:6]:
            lines.append(f"- {feat}")
        lines.append("")

    git_items = _deliverables_from_git(git)
    if git_items:
        lines.append("### 近期产出")
        lines.append("")
        lines.extend(git_items[:4])
        lines.append("")

    if not lines and sessions:
        lines.append("### 近期任务")
        lines.append("")
        for s in sessions[:3]:
            q = s.get("first_query")
            if q:
                lines.append(f"- {strip_markdown_for_summary(q, 120)}")
        lines.append("")

    return lines


_DELIVERABLE_CATEGORY_ORDER = [
    "目标",
    "输入",
    "中间产物",
    "脚本",
    "脚本与实现",
    "产出",
    "输出",
    "核心产出",
    "实例技能",
    "技能包",
    "能力",
    "关键能力",
    "处理规则",
    "规则",
    "边界",
    "边界说明",
    "用途",
    "测试产出",
    "其他",
]


def _format_grouped_deliverables(items: list[str]) -> list[str]:
    groups: dict[str, list[str]] = {}
    for raw in items[:10]:
        cat, body = _split_deliverable_category(str(raw))
        groups.setdefault(cat, []).append(body)

    lines: list[str] = []
    seen: set[str] = set()
    for cat in _DELIVERABLE_CATEGORY_ORDER:
        if cat not in groups:
            continue
        seen.add(cat)
        heading = _deliverable_heading(cat)
        lines.append(f"### {heading}")
        lines.append("")
        for body in groups[cat]:
            lines.append(f"- {body}")
        lines.append("")

    for cat, bodies in groups.items():
        if cat in seen:
            continue
        heading = _deliverable_heading(cat)
        lines.append(f"### {heading}")
        lines.append("")
        for body in bodies:
            lines.append(f"- {body}")
        lines.append("")

    return lines


def _split_deliverable_category(item: str) -> tuple[str, str]:
    m = re.match(r"^([^：:]+)[：:]\s*(.+)$", item.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "其他", item.strip()


def _deliverable_heading(category: str) -> str:
    mapping = {
        "输入": "需要什么输入",
        "产出": "产出什么",
        "输出": "产出什么",
        "脚本": "脚本与实现",
        "能力": "关键能力",
        "规则": "处理规则",
        "边界": "使用边界",
        "用途": "用途",
        "实例技能": "核心产出",
        "技能包": "核心产出",
        "中间产物": "中间产物",
        "测试产出": "验证产出",
        "目标": "要达成什么",
    }
    return mapping.get(category, category)


def _is_poor_deliverable_line(text: str) -> bool:
    s = text.strip()
    if not s or len(s) < 4:
        return True
    if _looks_like_git_subject(s):
        return True
    if re.match(r"^\d+(\.\d+)+(\s|$)", s):
        return True
    if re.match(r"^\*\*[^*]+\.(md|html|pdf)\*\*", s, re.I):
        return True
    if s.startswith(("文档：", "[samples/", "[docs/")):
        return True
    if "：" in s and len(s.split("：", 1)[0]) <= 8 and any(
        k in s for k in ("先查", "怎么填", "字段", "要写什么")
    ):
        return True
    return False


def _build_cursor_capabilities_section(
    with_cursor: dict[str, Any],
    sessions: list[dict[str, Any]],
    impact: dict[str, Any],
    doc: dict[str, Any],
) -> list[str]:
    capabilities = _as_str_list(with_cursor.get("capabilities"))
    tools = _as_str_list(with_cursor.get("tools"))
    skills = _as_str_list(with_cursor.get("skills"))
    mcp_tools = _as_str_list(with_cursor.get("mcp"))

    if not capabilities:
        capabilities = _infer_capabilities(with_cursor, sessions, impact, doc)
    if not tools and isinstance(with_cursor, dict):
        tools = _infer_tools_from_workflow(str(with_cursor.get("workflow") or ""))

    lines: list[str] = []
    if capabilities:
        lines.append("### Cursor / AI 能力")
        lines.append("")
        for item in capabilities:
            lines.append(f"- {item}")
        lines.append("")

    if tools:
        filtered_tools = [
            item
            for item in tools
            if not (
                str(item).startswith("Cursor Agent")
                and any(c.startswith("Cursor Agent") for c in capabilities)
            )
        ]
        if filtered_tools:
            lines.append("### 使用的工具与技术")
            lines.append("")
            for item in filtered_tools:
                lines.append(f"- {item}")
            lines.append("")

    if skills:
        lines.append("### 调用的 Skills")
        lines.append("")
        for item in skills:
            lines.append(f"- `{item}`")
        lines.append("")

    if mcp_tools:
        lines.append("### MCP / 扩展能力")
        lines.append("")
        for item in mcp_tools:
            lines.append(f"- {item}")
        lines.append("")

    return lines


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def _infer_capabilities(
    with_cursor: dict[str, Any],
    sessions: list[dict[str, Any]],
    impact: dict[str, Any],
    doc: dict[str, Any],
) -> list[str]:
    caps: list[str] = ["Cursor Agent 对话式协作（读项目上下文、生成/修改文件）"]
    blob = " ".join(
        [
            str(with_cursor.get("workflow") or ""),
            str(impact.get("one_liner") or ""),
            str(impact.get("background") or ""),
        ]
    ).lower()
    session_blob = " ".join(
        (s.get("first_query") or "") + " " + (s.get("last_assistant") or "")
        for s in sessions[:8]
    ).lower()
    combined = f"{blob} {session_blob}"

    if any(k in combined for k in ("读图", "读帧", "录屏", "多模态", "frame", "screenshot")):
        caps.append("多模态视觉理解（读图 / 视频抽帧识别）")
    if any(k in combined for k in ("skill", "技能", "/teach", "@")):
        caps.append("Agent Skills（按技能指令执行可复用工作流）")
    if doc.get("source") and "prd" in doc["source"].lower():
        caps.append("PRD / 文档驱动开发（以需求文档为验收依据）")
    if any(k in combined for k in ("html", "原型", "demo", "页面")):
        caps.append("交互原型 / Demo 页面生成与迭代")
    if any(k in combined for k in ("python", "脚本", "csv", "爬", "epub")):
        caps.append("终端执行与脚本自动化（跑命令、装依赖、批处理）")
    if sessions:
        caps.append("多轮对话续接（同一项目上下文累积，减少重复交代）")

    # 去重保序
    seen: set[str] = set()
    unique: list[str] = []
    for c in caps:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique[:6]


def _infer_tools_from_workflow(workflow: str) -> list[str]:
    w = workflow.lower()
    tools: list[str] = []
    mapping = [
        (("python", "matplotlib", "pandas", "csv"), "Python 数据分析"),
        (("opencv", "抽帧"), "OpenCV 视频抽帧"),
        (("selenium", "playwright", "浏览器"), "浏览器自动化（Selenium / Playwright）"),
        (("epub", "电子书"), "EPUB 电子书生成"),
        (("html", "react", "css"), "HTML / React 原型"),
        (("word", "docx"), "Word 文档处理"),
        (("excel", "透视"), "Excel / 表格数据处理"),
        (("埋点", "gio", "growingio"), "GrowingIO 埋点"),
        (("git", "github"), "Git 版本管理"),
    ]
    for keys, label in mapping:
        if any(k in w for k in keys):
            tools.append(label)
    return tools


def _looks_like_git_subject(text: str) -> bool:
    return bool(re.match(r"^(feat|fix|chore|docs)(\([^)]+\))?:\s", text, re.I))


def _deliverables_from_git(git: dict[str, Any]) -> list[str]:
    subjects = git.get("recent_subjects") or []
    items: list[str] = []
    for subj in subjects[:4]:
        clean = re.sub(r"^(feat|fix|chore|docs)\([^)]+\):\s*", "", subj, flags=re.I)
        if clean:
            items.append(f"- {clean}")
    return items


def _summarize_git(git: dict[str, Any]) -> list[str]:
    if not git.get("has_git"):
        return []
    lines: list[str] = []
    commits = git.get("commits_recent", 0)
    if commits:
        lines.append(f"- 近 90 天 **{commits}** 次提交")
    if git.get("last_commit_date"):
        lines.append(f"- 最近提交：{git['last_commit_date'][:10]}")
    subjects = git.get("recent_subjects") or []
    if subjects:
        lines.append("- 近期改动方向：")
        for s in subjects[:4]:
            lines.append(f"  - {s}")
    files = git.get("changed_files_recent") or []
    categories = _categorize_changed_files(files)
    if categories:
        parts = [f"{label} {cnt} 个" for label, cnt in categories.most_common(4)]
        lines.append(f"- 主要产出类型：{' · '.join(parts)}")
    return lines


def _categorize_changed_files(files: list[str]) -> Counter[str]:
    cats: Counter[str] = Counter()
    for raw in files:
        f = raw.strip().strip('"').replace("\\", "/")
        name = f.split("/")[-1].lower()
        if name.endswith((".md", ".mdx")):
            cats["文档"] += 1
        elif name.endswith((".html", ".htm")):
            cats["页面原型"] += 1
        elif name.endswith((".tsx", ".jsx", ".vue", ".css")):
            cats["前端"] += 1
        elif name.endswith(".py"):
            cats["脚本"] += 1
        elif name.endswith((".yaml", ".yml", ".json")):
            cats["配置/数据"] += 1
        elif name.endswith((".png", ".jpg", ".svg", ".mp4")):
            cats["素材"] += 1
        else:
            cats["其他"] += 1
    return cats


def _humanize_touched_paths(paths: list[str]) -> list[str]:
    result: list[str] = []
    for p in paths:
        if "AI Projects/" in p:
            p = p.split("AI Projects/", 1)[-1]
        p = p.split("/")[-1] if "/" in p else p
        if p and p not in result:
            result.append(p)
    return result


def _guess_domain(title: str, name: str) -> str:
    text = f"{title} {name}".lower()
    rules = [
        ("产品与设计", ["prd", "落地页", "demo", "原型", "landing", "writeup"]),
        ("数据分析", ["画像", "数据", "csv", "dashboard", "看板", "数据库"]),
        ("课程与内容", ["课程", "ielts", "写作", "营销", "逐字稿", "批改"]),
        ("运营与销售", ["签转", "喜报", "销售", "运营", "申报", "创客"]),
        ("研发与工具", ["skill", "hook", "proto", "openspec", "spec", "爬虫"]),
    ]
    for label, keys in rules:
        if any(k in text for k in keys):
            return label
    return "综合"


def _background_from_doc(doc: dict[str, Any], parsed: dict[str, Any]) -> str:
    if parsed.get("background"):
        return parsed["background"]
    excerpt = doc.get("excerpt") or ""
    if not excerpt:
        return ""
    # 跳过纯标题行，取正文段落
    for block in excerpt.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        if block.startswith("|") or block.startswith("```"):
            continue
        text = strip_markdown_for_summary(block, 500)
        if len(text) > 40:
            return text
    return ""


def _infer_traditional(
    parsed: dict[str, Any],
    doc: dict[str, Any],
    sessions: list[dict[str, Any]],
    name: str,
) -> str:
    if parsed.get("pains"):
        pain_text = parsed["pains"]
        pain_text = re.split(r"\*\*解决方案\*\*", pain_text)[0]
        pain_text = re.sub(r"^\*\*原因分析\*\*[：:\s]*", "", pain_text).strip()
        bg = parsed.get("background") or ""
        # 勿把产品介绍误当作「以前怎么做」
        if (
            "本产品提供" in pain_text
            or "人工批改质量高" in pain_text
            or (bg and pain_text[:60] == bg[:60])
        ):
            pass
        else:
            return _truncate(pain_text, 400)

    title = f"{parsed.get('title', '')} {doc.get('title', '')} {name}"
    if any(k in title for k in ("画像", "看板", "数据")):
        return (
            "以往多依赖 Excel 手工汇总与透视，改一个统计维度就要重新做表；"
            "口径难统一，不便向管理层演示，单次分析常需 **2–3 天**。"
        )
    if any(k in title for k in ("批改", "仿人工")):
        return (
            "以往老师用 Word 手工修订、批注、评分，一份作文常需 **15–30 分钟**；"
            "风格难统一，重复性修改多，难以规模化。"
        )
    if any(k in title for k in ("课程", "营销", "话术", "逐字稿")):
        return (
            "以往教研与运营需多轮线下改稿，话术风格难统一；"
            "跨课程复用方法论成本高，审校周期长。"
        )
    if any(k in title for k in ("PRD", "落地页", "Landing", "Demo")):
        return (
            "以往产品写 PRD、设计出稿、开发实现分段推进，需求与原型易脱节；"
            "埋点、验收、多版本文档对齐占用大量会议时间。"
        )
    if any(k in title for k in ("申报", "创客中国", "商业计划")):
        return (
            "以往大赛申报材料靠多人分工：搜集政策与字段、翻历史材料、手写商业计划书与路演稿，"
            "版本多、口径难统一，临近截止时常通宵拼凑。"
        )
    if any(k in title for k in ("爬虫", "爬取", "epub", "电子书")):
        return (
            "以往需手写爬虫与清洗脚本，遇到反爬、正文提取不准等问题时要反复调试；"
            "全量抓取与导出往往耗时长、难维护。"
        )
    if sessions:
        q = sessions[0].get("first_query", "")
        if q:
            return (
                f"以往完成「{strip_markdown_for_summary(q, 100)}」类任务，"
                "主要靠人工查资料、写文档、改代码逐步推进，过程难沉淀、难复用。"
            )
    return (
        "以往以人工查阅资料、手工整理为主：需求澄清、文档撰写、代码实现分散在多人多轮沟通中，"
        "重复劳动多，经验难以复用到下一个项目。"
    )


def _infer_cursor_workflow(
    sessions: list[dict[str, Any]],
    git: dict[str, Any],
    doc: dict[str, Any],
    parsed: dict[str, Any],
    name: str,
) -> list[str]:
    parts: list[str] = []

    if doc.get("source"):
        parts.append(
            f"以 **`{doc['source']}`** 为需求入口，让 Agent 先理解业务背景与验收标准，再协助改文档、写原型或补代码。"
        )

    if sessions:
        parts.append(
            f"通过 **{len(sessions)}** 次 Cursor Agent 对话，用自然语言描述目标；"
            "AI 协助阅读现有文件、起草方案、批量修改并解释改动，对话记录可回溯。"
        )
        themes = _session_themes(sessions)
        if themes:
            parts.append("")
            parts.append("**典型协作模式**：")
            for t in themes[:4]:
                parts.append(f"- {t}")

    if git.get("commits_recent", 0) > 0:
        parts.append("")
        parts.append(
            f"近 90 天仓库有 **{git['commits_recent']}** 次相关提交，"
            "说明人机协作产出在持续迭代，而非一次性交付。"
        )

    if not parts:
        parts.append("使用 Cursor 进行对话式协作：描述目标 → Agent 读项目上下文 → 生成/修改文件 → 人工验收。")

    return parts


def _session_themes(sessions: list[dict[str, Any]]) -> list[str]:
    themes: list[str] = []
    keywords_map = [
        ("PRD / 需求文档撰写与迭代", ["prd", "需求", "文档", "补充"]),
        ("原型 / Demo / 页面实现", ["demo", "原型", "html", "页面", "落地页", "ui"]),
        ("数据分析 / 脚本 / 自动化", ["分析", "脚本", "数据", "csv", "python", "抓取"]),
        ("营销 / 课程内容优化", ["课程", "营销", "话术", "逐字稿", "改写"]),
        ("调试与联调", ["修复", "bug", "报错", "联调", "埋点"]),
        ("规范与流程搭建", ["规范", "openspec", "skill", "流程", "架构"]),
    ]
    blob = " ".join(
        (s.get("first_query") or "") for s in sessions
    ).lower()
    for label, keys in keywords_map:
        if any(k in blob for k in keys):
            themes.append(label)
    if not themes and sessions:
        themes.append("按对话任务逐项推进（见下方协作摘要）")
    return themes


def _infer_impact(
    sessions: list[dict[str, Any]],
    git: dict[str, Any],
    parsed: dict[str, Any],
    doc: dict[str, Any],
) -> list[str]:
    items: list[str] = []

    if parsed.get("features"):
        items.append(f"- **能力覆盖**：已落地或规划 {len(parsed['features'])} 项核心能力（见上文「项目要做什么」）。")

    if len(sessions) >= 2:
        items.append(
            f"- **协作频次**：近期 **{len(sessions)}** 次 Agent 会话，同一项目可快速续接上下文，减少重复交代。"
        )
    elif sessions:
        items.append("- **协作方式**：已建立 Cursor 对话协作记录，任务过程可追溯。")

    commits = git.get("commits_recent", 0)
    if commits >= 5:
        items.append(
            f"- **迭代速度**：近 90 天 **{commits}** 次提交，文档/原型/代码同步演进，改版周期明显短于纯人工分段推进。"
        )
    elif commits > 0:
        items.append(f"- **持续迭代**：仓库已有 **{commits}** 次近期提交，产出在持续更新。")

    if doc.get("source") and "PRD" in (doc.get("source") or ""):
        items.append(
            "- **需求对齐**：PRD 与 Demo/代码同源维护，减少「文档写完实现跑偏」的情况。"
        )

    if sessions and any(s.get("touched_paths") for s in sessions):
        items.append("- **可沉淀**：对话中改动的文件路径可追溯，方便复盘与汇报引用。")

    if parsed.get("goals"):
        items.append(
            f"- **目标聚焦**：{_truncate(parsed['goals'], 120)}"
        )

    return items


def _truncate(text: str, n: int) -> str:
    text = strip_markdown_for_summary(text, n + 10)
    if len(text) > n:
        return text[: n - 1] + "…"
    return text


def _safe_session_text(text: str, max_len: int) -> str:
    return sanitize_text(text, max_len=max_len)


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
        by_domain.setdefault("全部项目", []).append(item)

    for domain, items in sorted(by_domain.items()):
        if domain != "全部项目":
            lines.append(f"### {domain}")
            lines.append("")
        for project_name, case_title, filename in sorted(items, key=lambda x: x[0]):
            lines.append(f"- [{case_title}](cases/{filename})（`{project_name}`）")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 阅读说明")
    lines.append("")
    lines.append("- 每个案例包含：**业务背景 → 工作痛点 → 项目要做什么 → 工作方式对比 → 提效与业务价值 → Cursor/AI 能力与工具**")
    lines.append("- 标注 `draft` 的为自动草稿，需在 Cursor 中确认后才会进入正式版")
    lines.append("- 确认方式见 [docs/03-确认发布流程.md](docs/03-确认发布流程.md)")
    lines.append("")
    return "\n".join(lines)


def write_case_file(
    cases_dir: Path,
    project: dict[str, Any],
    content: str,
    existing_status: dict[str, Any] | None = None,
) -> str:
    filename = (existing_status or {}).get("case_file") or f"{project['id']}.md"
    write_text(cases_dir / filename, content)
    return filename
