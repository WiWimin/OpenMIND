# 测试策略

## 测试分层

| 层级 | 范围 | 工具 | 位置 |
| --- | --- | --- | --- |
| 单元测试 | 业务规则、纯函数、解析器 | pytest / vitest | `backend/tests/unit`、`frontend/tests` |
| 接口集成测试 | API 请求、响应与错误结构 | pytest + FastAPI TestClient | `backend/tests/integration` |
| 端到端测试 | 关键业务闭环 | 后续引入（Playwright） | `backend/tests/e2e`、`frontend/tests/e2e` |

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
| M03 资料 | 上传/详情/删除；解析失败返回 `FILE_PARSE_FAILED` + `details.reason`；删除后 RAG 不再命中 |
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

## 后续阶段

- 为核心业务服务编写单元测试与接口集成测试（当前仅 M00 覆盖）。
- 引入端到端测试框架（Playwright）覆盖主闭环。
- 补充权限与数据隔离的专项测试。
