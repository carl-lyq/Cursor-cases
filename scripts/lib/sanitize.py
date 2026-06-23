"""对话与案例文本脱敏：过滤敏感、隐私信息后再入库或推送 GitHub。"""

from __future__ import annotations

import re
from typing import Any

# 命中后整段替换为占位符（小写匹配）
_SENSITIVE_LINE_PATTERNS = (
    r"password\s*[=:]\s*\S+",
    r"api[_-]?key\s*[=:]\s*\S+",
    r"secret\s*[=:]\s*\S+",
    r"token\s*[=:]\s*\S+",
    r"authorization\s*:\s*\S+",
    r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
)

_REDACT_RULES: list[tuple[re.Pattern[str], str]] = [
    # Token / 密钥
    (re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"), "[已脱敏密钥]"),
    (re.compile(r"\bghp_[a-zA-Z0-9]{20,}\b"), "[已脱敏密钥]"),
    (re.compile(r"\bgho_[a-zA-Z0-9]{20,}\b"), "[已脱敏密钥]"),
    (re.compile(r"\bBearer\s+[a-zA-Z0-9._\-]{10,}\b", re.I), "Bearer [已脱敏]"),
    (re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*\S+"), r"\1=[已脱敏]"),
    # 邮箱、手机、身份证
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[已脱敏邮箱]"),
    (re.compile(r"\b1[3-9]\d{9}\b"), "[已脱敏手机]"),
    (re.compile(r"\b\d{17}[\dXx]\b"), "[已脱敏证件号]"),
    # 银行卡号（16–19 位，避免误伤短数字）
    (re.compile(r"\b\d{16,19}\b"), "[已脱敏号码]"),
    # 本机绝对路径 → 仅保留 AI Projects 相对段或文件名
    (
        re.compile(
            r"/Users/[^\s\"']+?/(?:AI Projects/|Library/CloudStorage/[^/]+/AI Projects/)([^\s\"']+)"
        ),
        r"AI Projects/\1",
    ),
    (re.compile(r"/Users/mac/[^\s\"']+"), "[本机路径]"),
    (re.compile(r"~/.cursor/[^\s\"']+"), "[Cursor路径]"),
]

# 含下列词且脱敏后过短的查询，不写入案例卡
_DROP_QUERY_KEYWORDS = (
    "密码",
    "password",
    "secret",
    "token",
    "api key",
    "身份证",
    "银行卡",
)


def sanitize_text(text: str, *, max_len: int | None = None) -> str:
    if not text:
        return ""
    out = str(text)
    for pat, repl in _REDACT_RULES:
        out = pat.sub(repl, out)
    for pat in _SENSITIVE_LINE_PATTERNS:
        out = re.sub(pat, "[已脱敏]", out, flags=re.I)
    out = re.sub(r"\s+", " ", out).strip()
    if max_len and len(out) > max_len:
        out = out[: max_len - 1] + "…"
    return out


def sanitize_path(path: str) -> str:
    if not path:
        return ""
    p = path.replace("\\", "/")
    marker = "AI Projects/"
    if marker in p:
        return p.split(marker, 1)[-1].split("/")[-1] or p
    if p.startswith("/Users/") or p.startswith("~"):
        name = p.rstrip("/").split("/")[-1]
        return name if name else "[路径]"
    return sanitize_text(p, max_len=80)


def should_drop_query(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in _DROP_QUERY_KEYWORDS)


def sanitize_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """返回脱敏后的会话摘要；敏感任务返回 None 以跳过。"""
    first = sanitize_text(session.get("first_query") or "", max_len=280)
    if not first or should_drop_query(first):
        return None

    cleaned: dict[str, Any] = {
        "session_id": session.get("session_id") or "",
        "mtime": session.get("mtime") or "",
        "score": session.get("score", 0),
        "first_query": first,
        "last_assistant": sanitize_text(session.get("last_assistant") or "", max_len=280),
        "touched_paths": [
            sanitize_path(p)
            for p in (session.get("touched_paths") or [])[:8]
            if sanitize_path(p)
        ],
    }
    # 不写入原始 transcript 路径、cursor 目录等
    return cleaned


def sanitize_sessions_for_storage(
    by_project: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for project, sessions in by_project.items():
        kept: list[dict[str, Any]] = []
        for s in sessions:
            clean = sanitize_session(s)
            if clean:
                kept.append(clean)
        if kept:
            out[project] = kept
    return out
