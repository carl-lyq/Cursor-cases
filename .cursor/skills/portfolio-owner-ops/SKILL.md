---
name: portfolio-owner-ops
description: Runs Cursor 案例库 owner manual ops after user confirmation—scan, daily-local-sync, launchd reload, status, confirm publish, ai-impact.yaml bootstrap, push portfolio-draft. Use when the user invokes this skill, says 案例库运维/同步案例库/跑 daily-local-sync/补扫对话/确认 portfolio prep, or asks Cursor to execute portfolio maintenance commands on their Mac.
---

# Portfolio Owner Ops（案例库运维）

帮 Owner **代跑**案例库需要手动的命令与检查。**必须先确认再执行**（见下方闸门）。

## 调用时首屏（必须）

用户**仅调用本 skill、未指明具体操作**时，**不要先问开放式问题**，直接输出下方「**首屏菜单（A–I）**」全文，并结尾写：

> 请回复选项编号（如 `B` 或 `D 然后 B`），或说明你的场景；确认后我再执行。

用户已指明操作（如「同步并推送」→ B）时，可跳过首屏，进入「执行前复述」。

## 常量

```text
PORTFOLIO_ROOT=/Users/mac/Library/CloudStorage/OneDrive-个人/AI Projects/Cursor案例库
AI_PROJECTS_ROOT=/Users/mac/Library/CloudStorage/OneDrive-个人/AI Projects
BRANCH_DRAFT=portfolio-draft
BRANCH_MAIN=main
LAUNCHD_LABEL=com.cursor.portfolio-daily-sync
SYNC_HOUR=22:00  # 北京时间，见 templates/com.cursor.portfolio-daily-sync.plist
```

所有命令在 `PORTFOLIO_ROOT` 下执行，除非操作子项目路径。

## 闸门（必须遵守）

1. **首屏菜单**：未指明操作时，直接输出「首屏菜单（A–I）」全文（见下节），不用 `AskQuestion` 替代。
2. **执行前复述**：将运行的命令、是否会 `git commit`/`git push`、影响哪些目录，列成简短清单，等用户明确同意（「跑」「可以」「执行」）后再动手。
3. **Git**：除用户已选中的「同步并推送」「推送案例库代码」「确认发布」外，**不要**擅自 commit/push。`daily-local-sync.sh` 内含 commit+push，选中该操作即视为用户授权。
4. **合盖/睡眠**：提醒用户 22:00 定时任务仅在 Mac **醒着**时运行；若刚开机或错过定时，建议补跑 **B（同步并推送）**。
5. **发布**：修改 `published/` 必须走 `portfolio.py confirm`；确认前先摘要 `reviews/LATEST.md` 要点。
6. **失败**：命令非零退出时报告 stderr，给一条下一步建议，不要静默重试同一命令超过 2 次。

## 首屏菜单（A–I）

调用 skill 时**原样展示**本节（可微调排版，但每项说明须保留）：

---

**案例库运维 — 请选择要执行的操作**

**A · 重载定时任务**  
卸载并重新加载本机 22:00 定时任务（改过 plist 或仓库路径时用）。  
**什么时候用**：调整过 `templates/com.cursor.portfolio-daily-sync.plist`；换了案例库目录；想确保 launchd 用的是最新配置。  
**会做什么**：`launchctl unload` → 复制新 plist → `launchctl load`  
**不会**：立刻执行同步（若要马上同步请选 **B**）。  
**说明**：首次安装定时任务见 `docs/07-本机每日对话同步.md`（本 skill 不提供该项）。

**B · 同步并推送（最常用）**  
本机全量扫描 + 对话脱敏 + 更新案例卡 + **提交并 push 到 `portfolio-draft`**。  
**什么时候用**：刚完成重要协作想立刻进案例库；错过昨晚 22:00 定时；出差回来想一次性对齐。  
**会做什么**：`daily-local-sync.sh` → `portfolio.py scan`（仓库+对话）→ 写 `session-digests.json`（脱敏）→ 更新 `draft/`、`cases/`、`reviews/` → **git commit + push**  
**不会**：改 `published/`（对外正式版请 **F→G**）。原始对话 `.jsonl` 不会上 GitHub。

**C · 仅扫描（不推送）**  
和 B 一样的扫描与案例卡更新，但**只改本机文件，不 commit、不 push**。  
**什么时候用**：想先看看扫描结果再决定是否推送；网络不好或暂不想动 GitHub；调试案例卡内容。  
**会做什么**：`python3 scripts/portfolio.py scan`  
**不会**：任何 git 操作。若要上传 GitHub，之后需再选 **B** 或 **H**。

**D · 补扫对话**  
只扫本机 `~/.cursor/projects` 里的 Agent 对话，不重新扫各子项目文档。  
**什么时候用**：关机/合盖几天后回来；文档没变但对话积累了很多；云端案例缺「近期协作摘要」。  
**会做什么**：`portfolio.py scan --transcripts-only` → 脱敏写入 digest  
**建议**：完成后通常再接 **B** 推到 GitHub（我会问你）。

**E · 查看状态**  
只读检查，不修改文件。  
**什么时候用**：想知道有没有待确认案例、上次同步是否成功、digest 里有多少项目对话。  
**会做什么**：`portfolio.py status`；可选看今日 `state/logs/daily-sync-*.log` 末尾、digest 更新时间；摘要 `reviews/LATEST.md`  
**不会**：扫描、commit、push。

**F · 发布前检查**  
对外汇报前的人工把关（只读）。  
**什么时候用**：准备发邮件/汇报前；不确定案例卡有没有敏感信息。  
**会做什么**：读 `reviews/LATEST.md` 列新增/更新/待核实；按你指定的项目抽查 `cases/*.md` 是否含未公开业务、客户隐私、密钥  
**不会**：改 `published/`。检查完若要正式发布请选 **G**。

**G · 确认发布**  
把已确认的草稿写入 **`published/`** 并 push 到 **`main`**（对外正式版）。  
**什么时候用**：F 检查通过（或你明确说跳过）；确定要对外使用当前案例内容。  
**会做什么**：`portfolio.py confirm`（可指定项目）→ commit `published/` + `state/` → push `main`  
**前置**：建议先 **F**；**不可撤销地影响对外版本**，执行前会再要你确认范围。

**H · 推送案例库代码**  
推送**案例库仓库自身**的改动（脚本、文档、skill、workflow 等）到 `portfolio-draft`。  
**什么时候用**：刚改完 `portfolio.py`、PRD、skill、GitHub Action；与 B 不同，这是推「工具代码」而非扫出来的案例内容。  
**会做什么**：`git status/diff` 给你看 → 你确认 commit message → checkout `portfolio-draft` → commit → push  
**不会**：自动跑 scan（除非你也选了 B/C）。

**I · 创建 ai-impact.yaml**  
在某个子项目里加轻量「项目名片」，让案例库在没有 PRD 时也能写出像样的背景。  
**什么时候用**：临时任务、快速原型、有对话但还没写 PRD/README。  
**会做什么**：在 `AI Projects/<路径>/.cursor/ai-impact.yaml` 从模板复制并帮你填 `project`、`one_liner`、`users`、`pain_points` 等  
**不会**：自动扫描（完成后可选 **C** 或 **B**）。**不能**替代在对应文件夹里开 Cursor（对话归项目仍靠工作区路径）。

---

支持多选按序执行，例如：`D 然后 B`、`F 然后 G`。

## 操作菜单（速查）

| ID | 名称 | 一句话 |
|----|------|--------|
| A | 重载定时任务 | 更新 plist 后 reload |
| B | 同步并推送 | scan + 脱敏 + push draft |
| C | 仅扫描 | 本地 scan，不 push |
| D | 补扫对话 | transcripts-only |
| E | 查看状态 | status / 日志 / LATEST |
| F | 发布前检查 | 敏感信息把关 |
| G | 确认发布 | confirm → push main |
| H | 推送案例库代码 | 工具仓库 push draft |
| I | 创建 ai-impact.yaml | 子项目名片 |

## 各操作执行步骤

### A — 重载定时任务

```bash
launchctl unload ~/Library/LaunchAgents/com.cursor.portfolio-daily-sync.plist 2>/dev/null || true
cp "$PORTFOLIO_ROOT/templates/com.cursor.portfolio-daily-sync.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.cursor.portfolio-daily-sync.plist
```

若 plist 里仓库路径与 `PORTFOLIO_ROOT` 不一致，先改模板再 `cp`。  
检查：`launchctl list | grep com.cursor.portfolio-daily-sync`

### B — 同步并推送（推荐日常补跑）

```bash
cd "$PORTFOLIO_ROOT" && ./scripts/daily-local-sync.sh
```

脚本会：全量 `scan` → 写 `state/session-digests.json`（脱敏）→ commit → `push origin portfolio-draft`。

完成后向用户报告：读 `state/logs/daily-sync-$(date +%Y%m%d).log` 末尾，或 `git log -1 --oneline`。

### C — 仅扫描

```bash
cd "$PORTFOLIO_ROOT" && python3 scripts/portfolio.py scan
```

### D — 补扫对话

```bash
cd "$PORTFOLIO_ROOT" && python3 scripts/portfolio.py scan --transcripts-only
```

问用户是否接着执行 **B** 推送到 GitHub。

### E — 查看状态

```bash
cd "$PORTFOLIO_ROOT" && python3 scripts/portfolio.py status
```

可选：

```bash
tail -30 "$PORTFOLIO_ROOT/state/logs/daily-sync-$(date +%Y%m%d).log"
python3 -c "import json;from pathlib import Path;d=json.loads(Path('$PORTFOLIO_ROOT/state/session-digests.json').read_text());print('digest:',d.get('updated_at'),'projects:',len(d.get('projects',{})))"
```

摘要 `reviews/LATEST.md` 前 30 行给用户。

### F — 发布前检查（不改文件）

1. 读 `reviews/LATEST.md`
2. 列出待确认/待核实项
3. 若用户给出项目名，打开对应 `cases/*.md`，检查是否含未公开业务数据、密钥、客户隐私
4. 提醒：脱敏不能替代人工判断

### G — 确认发布

前置：用户已完成 F 或明确表示跳过检查。

```bash
cd "$PORTFOLIO_ROOT"
python3 scripts/portfolio.py confirm
# 或指定：python3 scripts/portfolio.py confirm --cases <项目路径>
```

然后（用户同意后）：

```bash
git add published/ state/
git commit -m "portfolio: confirm cases"
git push origin main
```

向用户说明：`published/AI-Projects-Portfolio.md` 已更新。

### H — 推送案例库代码到 portfolio-draft

1. `git status` + `git diff` 摘要给用户
2. 用户确认 commit message 后：

```bash
cd "$PORTFOLIO_ROOT"
git checkout portfolio-draft
git add <用户确认的文件>
git commit -m "<用户确认的消息>"
git push origin portfolio-draft
```

### I — 创建 ai-impact.yaml

向用户要**子项目相对路径**（如 `Miscs/押题班画像`）。

```bash
mkdir -p "$AI_PROJECTS_ROOT/<路径>/.cursor"
cp "$PORTFOLIO_ROOT/templates/ai-impact.example.yaml" "$AI_PROJECTS_ROOT/<路径>/.cursor/ai-impact.yaml"
```

帮用户改 `project`、`one_liner`、`users`、`pain_points` 最少四项；改完问是否执行 **C** 或 **B**。

## 对话映射提示（仅建议，不自动执行）

- 在**对应子项目文件夹**开 Cursor，对话才易归到正确案例
- 对话对不上：查 `inbox/*-scan.json` 的 `unmapped_count`

## 详细参考

命令与文档索引见 [reference.md](reference.md)
