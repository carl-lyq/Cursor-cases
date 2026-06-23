# Portfolio Owner Ops — Reference

## 文档

| 文档 | 内容 |
|------|------|
| `docs/07-本机每日对话同步.md` | 脱敏 digest、launchd、22:00 节奏 |
| `docs/03-确认发布流程.md` | confirm 与 published/ |
| `docs/02-使用手册.md` | 扫描模式说明 |
| `docs/00-设置说明.md` | 首次环境与日常节奏 |
| `.cursor/rules/portfolio-confirm.mdc` | 确认发布规则 |

## 扫描模式

| 命令 | 作用 |
|------|------|
| `python3 scripts/portfolio.py scan` | 仓库 + 对话全量；写脱敏 digest |
| `python3 scripts/portfolio.py scan --repo-only` | 仅仓库（GitHub Action 用） |
| `python3 scripts/portfolio.py scan --transcripts-only` | 仅补对话 |
| `python3 scripts/portfolio.py status` | 待办概况 |
| `python3 scripts/portfolio.py confirm [--cases 名]` | 发布到 published/ |

## 双引擎时间线（给用户解释用）

- **22:00** 本机 `daily-local-sync.sh`：对话脱敏 → push `portfolio-draft`
- **次日 09:00** GitHub Action `--repo-only`：读 digest + 仓库 → 更新案例卡

Mac 合盖睡眠时 22:00 **不会跑**；需手动 **D** 补跑。

## 脱敏范围（自动，无需手改）

`scripts/lib/sanitize.py`：邮箱、手机、证件号、密钥、本机路径；敏感关键词任务整段跳过。原始 `.jsonl` 不上 GitHub。

## Git 分支

| 分支 | 内容 |
|------|------|
| `portfolio-draft` | draft、cases、reviews、inbox、state（含 session-digests） |
| `main` | published/ + 确认后的 state |

Remote（当前）：`git@github.com:carl-lyq/Cursor-cases.git`

## launchd 首次安装（不在 skill 菜单内）

见 `docs/07-本机每日对话同步.md`。skill 菜单仅保留 **A 重载**（已安装后更新配置用）。

## launchd 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.cursor.portfolio-daily-sync.plist
rm ~/Library/LaunchAgents/com.cursor.portfolio-daily-sync.plist
```
