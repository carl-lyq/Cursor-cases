#!/usr/bin/env bash
# 本机每日同步：全量 scan（含脱敏对话）→ 推送 portfolio-draft
# 安装：见 docs/07-本机每日对话同步.md

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/state/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily-sync-$(date +%Y%m%d).log"

exec >>"$LOG" 2>&1
echo "=== $(date -Iseconds) daily-local-sync start ==="

python3 scripts/portfolio.py scan

git add draft/ cases/ reviews/ inbox/ state/session-digests.json state/last-scan.json state/case-status.json state/PENDING_REVIEW 2>/dev/null || true
git add draft/ cases/ reviews/ inbox/ state/ 2>/dev/null || true

if git diff --staged --quiet; then
  echo "No changes to push"
  exit 0
fi

git commit -m "chore(portfolio): daily local scan with sanitized sessions $(date -u +%Y-%m-%d)"
git push origin portfolio-draft

echo "=== $(date -Iseconds) daily-local-sync done ==="
