# Cursor 案例库

跨项目自动整理 **AI Projects** 工作区里各项目的 Cursor 提效案例，生成**同事可读**的汇报材料。

## 快速开始

```bash
cd "/Users/mac/Library/CloudStorage/OneDrive-个人/AI Projects/Cursor案例库"
pip3 install -r requirements.txt   # 首次
python3 scripts/portfolio.py scan
python3 scripts/portfolio.py status
```

扫描完成后打开 **[reviews/LATEST.md](reviews/LATEST.md)** 查看待确认项。

### 确认发布（正式版）

在 Cursor 对话中说：

- `确认 portfolio` — 发布全部 draft 案例
- `确认 portfolio 押题班画像` — 只发布指定项目

或命令行：

```bash
python3 scripts/portfolio.py confirm
python3 scripts/portfolio.py confirm --cases Miscs/押题班画像
```

正式汇报材料：**[published/AI-Projects-Portfolio.md](published/AI-Projects-Portfolio.md)**

## 目录结构

| 路径 | 作用 |
|------|------|
| `cases/` | 每个项目一张案例卡（Markdown） |
| `draft/` | 自动生成的草稿总览 |
| `published/` | **已确认**的正式总览（汇报用） |
| `reviews/` | 每次扫描的待确认清单 |
| `inbox/` | 机器可读的扫描原始结果 |
| `state/` | 扫描水位、案例状态、待确认标记 |
| `scripts/` | 扫描 / 合成 / 确认脚本 |
| `docs/` | 完整文档 |

## 文档索引

0. [设置说明](docs/00-设置说明.md) — **GitHub / 首次配置**
1. [架构说明](docs/01-架构说明.md)
2. [使用手册](docs/02-使用手册.md)
3. [确认发布流程](docs/03-确认发布流程.md)
4. [GitHub 与分支策略](docs/04-GitHub与分支策略.md)
5. [飞书通知（待接入）](docs/05-飞书通知（待接入）.md)
6. [本需求对话记录与决策摘要](docs/06-本需求对话记录与决策摘要.md)

## 设计原则

- **自动只写草稿**，`published/` 仅在你确认后更新
- **业务语言**，避免堆技术日志；证据放在 `inbox/`
- **与躺着学 AI 项目库独立**，本仓库自洽
- **双引擎**：GitHub Action 扫仓库；本机扫 Agent 对话

## 可选：各项目补充事实卡片

在子项目创建 `.cursor/ai-impact.yaml` 可覆盖自动推断（模板见 [templates/ai-impact.example.yaml](templates/ai-impact.example.yaml)）。
