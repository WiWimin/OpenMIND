# 测试策略

## 测试分层

| 层级 | 范围 | 工具 | 位置 |
| --- | --- | --- | --- |
| 单元测试 | 业务规则、纯函数、解析器 | pytest / vitest | `backend/tests/unit`、`frontend/tests` |
| 接口集成测试 | API 请求、响应与错误结构 | pytest + FastAPI TestClient | `backend/tests/api` |
| 端到端测试 | 关键业务闭环 | 后续引入 Playwright；当前无浏览器 E2E | 尚未创建 |

## 命令

后端：

```bash
cd backend
ruff check .
pytest
```

前端：

```bash
cd frontend
npm run typecheck
npm run lint
npm run test
```

一键：`scripts/test.ps1`（Windows）或 `scripts/test.sh`。

## 约定

- 后端测试文件命名 `test_*.py`，与源码模块对应；`tests/__init__.py` 保证可导入 `app`。
- 前端测试文件命名 `*.spec.ts`，放在 `frontend/tests/`。
- 提交前必须本地通过上述检查；CI（`.github/workflows/ci.yml`）会重复执行。

## 第一阶段覆盖

- 健康检查 `/health` 返回 200。
- OpenAPI 文档可访问。
- 数据库就绪探针 `/api/v1/health/db` 已注册（无数据库时返回 503）。
- 未定义路由返回统一错误结构 `{ status, error_code, message, retryable }`。
- 前端 API 客户端配置校验。

## 模块级验收口径（M01–M09）

| 模块 | 关键验收 |
| --- | --- |
| M01 认证 | 注册/登录/当前用户可用；未登录 `401`；重复 `name` 被拒；不返回密码哈希 |
| M02 会议 | CRUD + 归档；越权 `404`；归档只读；存在已转换任务/任务的会议删除返回 `409` |
| M03 资料 | 上传/详情/删除；同步解析失败以 `failed` + `parse_error` 表达；删除后 RAG 不再命中且记录来源置空 |
| M04 RAG | 跨用户不可检索；无命中返回空来源 + `insufficient_evidence` |
| M05 准备 | 生成草稿（新增记录）；编辑 `version` 递增；失败态正确 |
| M06 记录/问答 | 记录增改查；问答返回 `sources`；证据不足标记正确 |
| M07 纪要/行动项 | 纪要草稿；行动项默认 `pending_confirmation`；未确认不可转任务；重复转换幂等 |
| M08 任务 | 状态流转校验；越权 `404`；取消幂等 |
| M09 问题 | 提取候选；状态流转正确；越权 `404` |

通用：每个模块须覆盖正常流程、越权访问、非法状态流转与统一错误体。

## AI 质量评估

- 建立固定测试集（会议材料 + 记录样例），评测：解析成功率、检索命中率、行动项/问题提取的精确率与召回率。
- 口径固定：以人工标注为基准，记录评测集版本与指标，随 AI 变更更新（见 `docs/ai-design.md` 十一）。

## 当前覆盖现状

- 后端已有单元测试与 API 集成测试（`backend/tests/unit`、`backend/tests/api`），使用 SQLite 和 Mock AI。
- 前端使用 Vitest 组件/Store/API 测试。
- 真实模型 smoke 由 `backend/scripts/check_ai.py`、`check_rag.py` 单独执行，不等同于 Mock/API 测试。
- 浏览器 E2E 尚未引入；不得把 Mock 测试通过描述为浏览器闭环通过。
