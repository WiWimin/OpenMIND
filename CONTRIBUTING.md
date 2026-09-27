# 贡献指南

## 分支策略

- `main`：稳定、可演示分支，只接受来自 `develop` 的合并。
- `develop`：日常开发集成分支，功能分支合并到这里。
- `feature/*`：具体功能开发。
- `fix/*`：Bug 修复。

命名示例：`feature/m00-project-scaffold`、`feature/m02-record-capture`、`fix/m02-meeting-list`。

### 协作流程

```text
feature/* · fix/*
        ↓  Pull Request
      develop
        ↓  测试
       main
```

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
