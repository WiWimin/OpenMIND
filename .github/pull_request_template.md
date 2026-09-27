## 修改目的

<!-- 本次 PR 要解决什么问题，一到两句话 -->

## 关联 Issue

<!-- 填写 Issue 编号与标题；完成后使用 Closes #12 / Fixes #12 自动关闭 -->

Closes #

## 修改内容

<!-- 按模块列出主要改动点，可分条列出 -->

-

## 测试方式

<!-- 复现/验证步骤，以及执行的命令 -->

- 后端：`cd backend && ruff check . && pytest`
- 前端：`cd frontend && npm run typecheck && npm run lint && npm run test && npm run build`
- 手工验证：

## 测试结果

<!-- 贴出实际执行结果摘要，例如 5 passed、0 error -->

-

## 是否修改数据库

- [ ] 否
- [ ] 是（必须附带 Alembic 迁移文件，并说明是否需要 `alembic upgrade head`）

## 是否修改环境变量

- [ ] 否
- [ ] 是（必须同步更新 `docker/.env.example`，并说明新增/变更的变量名）

## 是否修改 API

- [ ] 否
- [ ] 是（必须同步更新 `docs/api.md`，并说明是否需要前后端同时联调）

## 是否需要其他成员配合

- [ ] 否，可独立合并
- [ ] 是（说明需要谁配合做什么，例如：需要 C 更新前端类型、需要 A 评审数据模型）

## 自检清单

- [ ] 分支从 `develop` 切出，命名符合 `feature/*` 或 `fix/*`
- [ ] 后端 `ruff check .` 与 `pytest` 通过
- [ ] 前端 `npm run typecheck`、`npm run lint`、`npm run test` 通过
- [ ] 涉及数据库结构的改动已附带 Alembic 迁移文件
- [ ] 未提交任何密钥或真实会议资料
