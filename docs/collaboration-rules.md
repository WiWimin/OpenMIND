# 协作与分支规则（三流并行）

> **文档目的**：定义 OpenMIND 的三条工作流（stream）、分支模型、合并流程、定期同步与发布节奏。
>
> **唯一事实来源**：本文件是三流分工、分支命名、合并/同步/发布流程的**唯一出处**。`CONTRIBUTING.md` 与 `README.md` 只做摘要并**引用**本文件，不重复声明规则。
>
> **不负责**：接口字段（见 `api.md`）、表结构（见 `database.md`）、测试分层（见 `testing.md`）、模块任务（见 `module-task-plan.md`/`module-development-spec.md`）。

## 一、三条工作流

按角色与代码归属拆分为三条流；每条流只在自己的目录/模块内改动，接口以 `api.md` 为准、数据以 `database.md` 为准。

| 流 | 负责人 | 代码归属 | 主要模块 |
| --- | --- | --- | --- |
| `backend` | A 系统与业务后端 | `backend/app/{models,schemas,repositories,services,api}`、`alembic/`、`docker/`、部署 | M00、M01、M02、M08、M09（业务）、M10 |
| `agent` | B AI 后端 | `backend/app/ai/**` | M03（解析）、M04、M05、M06（AI）、M07、M09（AI） |
| `frontend` | C 前端与体验 | `frontend/src/**` | M01–M09 前端 |

- 跨流改动（如接口、共享 schema）**先改契约文档**（`docs/api.md` / `docs/database.md`）再改代码。
- 一条流的一个任务对应一个工作分支，避免多人共用同一分支产生冲突。

## 二、分支模型

| 分支 | 用途 | 来源 | 合并去向 |
| --- | --- | --- | --- |
| `main` | 稳定、可演示版本 | 仅接受来自 `develop` 的合并 | —— |
| `develop` | 日常开发集成分支 | 接受所有工作分支的 PR | `main`（阶段验收通过后） |
| `feature/<stream>-*` | 功能开发，按流加前缀 | 从 `develop` 切出 | `develop` |
| `fix/*` | 缺陷修复 | 从 `develop` 切出 | `develop` |

命名：`feature/<stream>-<module>-<short-desc>`，例如：

- `feature/backend-m01-m02`（认证 + 会议后端）
- `feature/frontend-m02-meeting`、`feature/agent-m04-rag`

## 三、合并流程（先合 `develop`）

```text
feature/<stream>-* · fix/*
        │  从最新 develop 切出
        │  开发中定期 merge develop
        ▼  PR（head=工作分支，base=develop）
      develop ── 集成测试 ──► main
```

1. 从**最新** `develop` 切出工作分支。
2. 开发；完成前把 `develop` 合并进工作分支（merge，不用 rebase），解决冲突并跑通本地检查。
3. 提 PR：head = 工作分支，base = **`develop`**。
4. CI 全绿 + 至少 1 人 Code Review 通过 → 用 **Create a merge commit** 合并到 `develop`。
5. 合并后删除已并入的工作分支。

**禁止**把 PR 合并到另一个特性分支。历史教训：PR #13 采用“堆叠 PR”，base 是 `feature/m01-auth-ui` 而非 `develop`，导致 `frontend-foundation`/`m01`/`m02`/`m03` 前端工作长期未进入 `develop`。若任务依赖另一分支，应**先把被依赖分支合入 `develop`**，再从 `develop` 切出新分支。

## 四、定期同步（避免长期漂移）

- 工作分支至少每 1–2 天执行一次 `git merge origin/develop`；每次开始新任务前也要先同步。
- 禁止长期不同步的“孤儿分支”；超过 3 天未同步需在协作群说明原因。
- 改动共享文件前先同步 `develop`，减少冲突。共享文件（首批）：
  - `backend/app/api/v1/router.py`、`backend/app/schemas/common.py`、`backend/app/models/__init__.py`、`backend/alembic/env.py`、`backend/tests/conftest.py`
  - `docs/api.md`、`docs/database.md`
- 冲突解决后必须重新跑通本地检查（见 §七）再推送。

## 五、`develop → main` 推进（阶段发布）

- `main` **只接受 `develop` 的合并**，禁止直接向 `main` 提交。
- 推进时机：每个阶段（M00–M10，见 `module-task-plan.md` 六阶段）验收通过后，或里程碑演示前。
- 流程：`develop` 全部 CI 绿 → 以 `develop` 为 head、`main` 为 base 发起“阶段发布”PR（或本地 `git merge`）→ 合并后按阶段打 tag（如 `m01-m02`）。
- **当前状态**：`main` 为 `b7386db`；`develop` 领先 `main` 89 个提交（MVP M00–M10 已完成）。阶段发布待执行，合并后打 `m00-m10` tag。

## 六、提交与 PR 规范

- 提交信息采用 Conventional Commits：`<type>(<scope>): <subject>`，`scope` 用模块号（如 `m01`、`m02`）。
- PR 按 [PR 模板](../.github/pull_request_template.md) 填写：修改目的、关联 Issue、修改内容、测试方式与结果、是否影响数据库 / 环境变量 / API、是否需要其他成员配合。
- 涉及数据库结构变更**必须**附带 Alembic 迁移；每模块一个迁移；已应用迁移不可再修改。
- 涉及环境变量变更**必须**同步 `docker/.env.example`；涉及接口变更**必须**同步 `docs/api.md`。
- 一个 PR 只属一条流；跨流变更需先评审契约。

## 七、准入门槛（Gate）

- 后端：`cd backend && ruff check . && pytest`
- 前端：`cd frontend && npm run typecheck && npm run lint && npm run test`
- 一键：`scripts/test.ps1`（Windows）/ `scripts/test.sh`
- CI（`.github/workflows/ci.yml`）两个 job 全绿；至少 1 人 review。

## 八、待办（本次流程修复）

- [x] 补做一次 `develop → main` 合并（已完成：`b291b7c`）。
- [x] 归拢未并入 `develop` 的前端分支：相关 `feature/*` 分支均已并入 `develop` 并删除。
- [ ] 停止“特性分支堆叠 PR”做法（见 §三）。

## 九、变更记录

| 日期 | 变更 | 说明 |
| --- | --- | --- |
| 2026-10 | 建立协作与分支规则 | 明确三流分工、分支模型、先合 `develop`、定期同步与 `develop → main` 推进 |
| 2026-10 | 阶段发布 | `develop → main` 合并完成（`main @ 332605e`），包含浏览器 E2E、本地 FunASR 与模型 probe 修复 |
