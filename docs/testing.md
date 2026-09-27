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
- 未定义路由返回统一错误结构 `{ status, error_code, message }`。
- 前端 API 客户端配置校验。

## 后续阶段

- 为核心业务服务编写单元测试与接口集成测试。
- 建立 AI 固定测试集与质量评估（精确率/召回率），明确计算口径。
- 补充权限与数据隔离的专项测试。
