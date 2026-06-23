# 社区 teach Skill 安装与快速验证

> 项目路径：`Miscs/learning-ielts-writing` · 领域：研发与工具

**一句话**：从网上安装 Matt Pocock 的 teach Skill 到 Cursor 全局，并用雅思写作主题快速跑通验证

## 业务背景

**谁在用**：课程产品、教研、想用 Skill 做教学脚手架的同事

**典型场景**：发现社区推荐 teach Skill，需确认能否装到全局并在真实主题下跑通


社区 Skill（如 aihero.dev 推荐的 teach）可自动生成教学工作区，但安装路径、 触发方式、目录约定不直观。 仅是验证用的测试工作区， 不是独立课程产品。

**要解决什么**：一条对话完成「安装 → 同步 → /teach 冒烟测试」，确认 Skill 可用于后续课程设计。

## 工作痛点

- 不清楚装到 .agents 还是 .cursor/skills
- 装完不知道有没有生效
- 首次验证要读大量文档，半天起步

传统方式下，完成一版可用结果通常需要 **半天到一天**。

## 项目要做什么

从业务视角，本项目最终要交付的是：

### 产出什么

- 全局 Skill `~/.cursor/skills/teach/`

### 验证

- `/teach` + 雅思写作 5.5→6 主题生成 MISSION、L1 HTML

### 结论

- 可安装、可触发、可按约定 scaffold 教学文件

## 工作方式对比

### 传统方式

自己读文档、复制文件、摸索触发词

### 用 Cursor 之后

1. 给出 Skill 来源链接
2. Agent 执行全局安装并同步到 ~/.cursor/skills/teach/
3. 用 /teach + 真实主题做冒烟测试，浏览器打开第一课

## 提效与业务价值

| 维度 | 传统方式 | 用 Cursor 后 |
|------|----------|--------------|
| **耗时** | 半天到一天 | 安装 + 验证约 1 次对话（数十分钟） |
| **质量/口径** | 易不一致、难复用 | 明确 teach 工作区约定（MISSION / lessons / reference） |

- **谁直接受益**：做课程/培训产品的同事（后续可复用 teach 脚手架）
- **业务上新可能**：未读源码也能完成社区 Skill 接入

## Cursor / AI 能力与工具

### Cursor / AI 能力

- Agent Skills 安装与全局验证
- 终端执行（npx skills CLI）

### 使用的工具与技术

- npx skills add mattpocock/skills
- 社区 teach Skill

### 调用的 Skills

- `teach`

---

*本卡由 Cursor 案例库自动整理 · 状态：draft · 文档来源：COURSE-PLAN.md · 生成于 2026-06-23*
