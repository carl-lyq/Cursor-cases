# GitHub 与分支策略

## 仓库建议

将 `Cursor案例库` 作为 **独立 Git 仓库** 推送到 GitHub（与 `AI Projects` 大仓库可分开，避免历史杂乱）。

```bash
cd "/Users/mac/Library/CloudStorage/OneDrive-个人/AI Projects/Cursor案例库"
git init
git remote add origin git@github.com:<你的组织>/cursor-portfolio.git
```

## 分支

| 分支 | 内容 | 谁更新 |
|------|------|--------|
| `portfolio-draft` | 自动扫描的 draft、reviews、inbox | GitHub Action + 本机 scan |
| `main` | `published/` + 已确认的 `state/` | 仅 `confirm` 后 push |

首次 setup：

```bash
git checkout -b main
git add .
git commit -m "chore: init cursor portfolio"
git push -u origin main

git checkout -b portfolio-draft
git push -u origin portfolio-draft
```

## GitHub Actions

工作流：[.github/workflows/portfolio-scan.yml](../.github/workflows/portfolio-scan.yml)

- **触发**：每周一 09:00（UTC+8 需自行改 cron）+ 手动 `workflow_dispatch`
- **执行**：`portfolio.py scan --repo-only`
- **推送**：commit 到 `portfolio-draft` 分支

> Action **无法**读取本机 `~/.cursor/projects` 对话；对话部分由你 Mac 上 `scan` 补全。

## 本机 scan 与 Git 协作

推荐流程：

1. Action 更新 `portfolio-draft`（repo 信号）
2. 本机：`git pull origin portfolio-draft`
3. 本机：`python3 scripts/portfolio.py scan`（含对话）
4. `git push origin portfolio-draft`
5. 确认后：`confirm` → merge / push `main`

若暂时只用单分支 `main`，可简化：draft 与 published 同在 `main`，但务必遵守「confirm 才改 published/」。

## 电脑关机时

- **周一 Action 仍运行**（在 GitHub 云端）
- 你回来后 `git pull` + 本机 `scan` 追平对话
- `reviews/LATEST.md` 会注明是否含积压补扫

## Secrets（后续飞书）

飞书 Webhook 配置见 [05-飞书通知（待接入）.md](./05-飞书通知（待接入）.md)，Secret 名预留：

- `FEISHU_WEBHOOK`
- `FEISHU_SIGN_SECRET`
