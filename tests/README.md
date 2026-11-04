# OpenMIND 5.0 测试基础设施（tests/）

本目录是 **测试专用**，不属于业务代码。用于在独立环境中验证 5.0 基线（`main` @ `ff42641`）。

> 安全说明：`compose.test.yml` 中的 `SECRET_KEY`、数据库口令均为**测试占位值**；不接触开发库（5432）与生产库。Mock 服务只在本机测试网络内使用，禁止部署。

## 文件

| 路径 | 说明 |
| --- | --- |
| `tests/compose.test.yml` | 独立测试编排：db-test(55432)/mock-ai(9000)/backend-test(8010) |
| `tests/mock-ai/app.py` | OpenAI 兼容 Mock：chat/completions、embeddings、models、audio/transcriptions + 模式控制 |
| `tests/scripts/pg_integration.py` | PostgreSQL 真实集成测试 |
| `tests/scripts/check_persist.py` | 重启后持久性检查 |
| `tests/scripts/ai_mock_checks.py` | AI 全链路（BYOK/异常/RAG/整理链） |
| `tests/scripts/audio_mock_checks.py` | 音频全流程（上传/实时分片/重试/确认/隔离/清理） |
| `tests/scripts/security_checks.py` | 安全测试 |
| `tests/scripts/ssrf_checks.py` | SSRF URL 校验（配置级） |
| `tests/scripts/fallback_default_off.py` | `ALLOW_GLOBAL_FALLBACK=false` 默认关闭验证 |
| `tests/storage-test/` | 测试后端文件存储挂载点 |

## 环境与数据库

- 测试数据库：**`openmind-db-test`**（PostgreSQL16 + pgvector，容器 `openmind-test-db-test-1`，宿主机 55432，独立卷 `openmind-test_pgdata_test`）。
- 测试后端：`openmind-test-backend-1`，宿主机 8010，启动时执行 `alembic upgrade head`（当前 head `0022_audio_segments`）。
- 测试前端：宿主机 5174（见下，使用已有 node_modules 卷副本，不重建镜像）。
- 开发环境 8001/5432/5173 不动；生产库不触碰。

## 启动

```bash
docker compose -f tests/compose.test.yml up -d db-test mock-ai backend-test
```

测试前端（`npm ci` 在本机会报 npm 内部错误，故复用已安装卷）：

```bash
docker volume create frontend_node_modules_test        # 已存在可跳过
docker run --rm -v openmind_frontend_node_modules:/from -v frontend_node_modules_test:/to node:22-bookworm sh -c "cp -a /from/. /to/"   # 首次
docker rm -f openmind-frontend-test 2>/dev/null
docker run -d --name openmind-frontend-test \
  -v "<repo>/frontend:/app" -v frontend_node_modules_test:/app/node_modules \
  -p 127.0.0.1:5174:5173 \
  -e VITE_API_BASE_URL=http://localhost:8010/api/v1 \
  -e VITE_DEV_PROXY_TARGET=http://host.docker.internal:8010 \
  -e CHOKIDAR_USEPOLLING=true \
  openmind-frontend:latest
```

## 执行各套件

```bash
docker exec openmind-backend-1 ruff check .
docker exec openmind-backend-1 python -m pytest

docker exec openmind-frontend-1 npm run typecheck
docker exec openmind-frontend-1 npm run lint
docker exec openmind-frontend-1 npm run test

docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/pg_integration.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/ai_mock_checks.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/audio_mock_checks.py
docker exec -e PYTHONPATH=/app openmind-test-backend-test-1 python /tests/scripts/security_checks.py

docker compose -f tests/compose.test.yml run --rm -e ALLOW_PRIVATE_MODEL_ENDPOINTS=false -e PYTHONPATH=/app backend-test python /tests/scripts/ssrf_checks.py
docker compose -f tests/compose.test.yml run --rm -e ALLOW_GLOBAL_FALLBACK=false -e PYTHONPATH=/app backend-test python /tests/scripts/fallback_default_off.py
```

## E2E（Playwright + Edge）

E2E 用例已按 5.0 界面重写（6 spec / 6 case，含行动项→转任务→状态更新闭环），并使用独立测试后端 + Mock AI/ASR：

```bash
cd frontend
npm install --no-save @playwright/test@1.64.1   # 宿主缺少该包时
E2E_BASE_URL=http://localhost:5174 E2E_API_BASE=http://localhost:8010/api/v1 \
E2E_CHANNEL=msedge E2E_EXPECT_ASR=1 npx playwright test
```

覆盖：注册/登录、创建会议（对话框“创建”）、上传材料、会议详情、任务页、AI 材料问答与待办提取、音频上传→转写→编辑→确认生成记录、模型配置（LLM BYOK，自定义提供商）、本地工作区降级提示。

结果与证据见 `docs/techdoc-5.0/06-e2e-test-report.md`。

## Mock 模式控制

```bash
curl -X POST http://127.0.0.1:9000/__mock/mode -H "Content-Type: application/json" -d '{"mode":"429"}'
curl -X POST http://127.0.0.1:9000/__mock/reset
```

模式：`normal | 429 | 500 | 401 | 402 | invalid_json | dim_mismatch`。

## 保留与清理

默认**保留** `openmind-test-db-test-1`、卷、容器与日志。清理：

```bash
docker compose -f tests/compose.test.yml down          # 保留卷
docker compose -f tests/compose.test.yml down -v       # 同时删除测试卷（谨慎）
docker rm -f openmind-frontend-test
```
