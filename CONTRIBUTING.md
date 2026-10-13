# 贡献指南

> 三流分工、分支命名、合并/同步/发布流程的**唯一事实来源**是 [`docs/collaboration-rules.md`](docs/collaboration-rules.md)；本节仅作摘要，冲突时以该文件为准。

## 分支策略

- `main`：稳定、可演示分支，只接受来自 `develop` 的合并。
- `develop`：日常开发集成分支，工作分支合并到这里。
- `feature/<stream>-*`：功能开发，按流加前缀（`backend` / `frontend` / `agent`）。
- `fix/*`：Bug 修复。

命名示例：`feature/backend-m01-m02`、`feature/frontend-m02-meeting`、`feature/agent-m04-rag`、`fix/m02-meeting-list`。

### 协作流程

```text
feature/<stream>-* · fix/*
        ↓  合并到 develop（先合 develop，禁止合到其他特性分支）
      develop ── 集成测试 ──► main（阶段验收通过后）
```

- **先合 `develop`**：PR 的 base 必须是 `develop`，不得把 PR 合并到另一个特性分支（历史上“堆叠 PR”曾导致前端工作长期未并入 `develop`）。
- **定期同步**：工作分支至少每 1–2 天 `git merge origin/develop`，防止长期漂移。
- **推进 `main`**：`develop` 集成测试通过后，以 `develop` 为 head 发起阶段发布合并到 `main`（`main` 目前停留在 M00 初始化提交，需补做一次）。

## 提交信息

采用 Conventional Commits：

```text
<type>(<scope>): <subject>
```

- type：`feat` | `fix` | `docs` | `style` | `refactor` | `test` | `chore`
- scope 建议使用模块号，如 `m00`、`m02`。

## 拉取请求（PR）

1. 从 `develop` 拉出 `feature/*` 或 `fix/*` 分支。
2. 提交前本地通过：后端 `ruff check .` + `pytest`；前端 `npm run typecheck` + `npm run lint` + `npm run test`。
3. 使用 [PR 模板](.github/pull_request_template.md) 填写：修改目的、关联 Issue、修改内容、测试方式、测试结果，以及是否修改数据库 / 环境变量 / API、是否需要其他成员配合。
4. 至少一名成员 Code Review 通过、CI 全绿后合并到 `develop`。
5. `develop` 验证通过后合并到 `main`。
6. 涉及数据库结构变更必须附带 Alembic 迁移文件；涉及环境变量变更必须同步 `docker/.env.example`；涉及接口变更必须同步 [`docs/api.md`](docs/api.md)。

## Issue

- 功能需求使用 [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md) 模板。
- 缺陷报告使用 [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) 模板。
- 模块任务规划见 [`docs/module-task-plan.md`](docs/module-task-plan.md)。

## 本地开发

见 [`docs/development.md`](docs/development.md)。

## 接口与数据契约

- 接口以 [`docs/api.md`](docs/api.md) 为准。
- 数据模型以 [`docs/database.md`](docs/database.md) 为准。
- 修改契约需先评审，再同步前后端类型。

## 协作原则

- 先接口，后并行；先闭环，后扩展；先保证业务正确，再优化 AI。
- 个人数据隔离、原始数据与 AI 结果分离、候选与确认分离、业务状态由后端控制。
