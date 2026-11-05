# 技术文档修订清单（review2）

> 基准：`OpenMIND-技术文档-5.0.md`（25 页） → `OpenMIND-技术文档-5.0-review2.md`（26 页）。
> 原则：保留八章结构、无目录、5.6 音频、第六章创新点独立；不删除必要内容。

| 位置 | 原内容 | 修订后 | 原因 | 证据 |
| --- | --- | --- | --- | --- |
| 摘要 | 分 A/B 两组描述，含“队友补充”“未在本仓库复测”等来源表述 | 统一为项目测试成果：350 pytest、449×5 Vitest、PG 13/13、8/8 E2E、真实 GLM-4-Flash 2 次、FunASR 全流程；未验收项单列 | 统一口径，去除来源区分 | 本轮测试日志、提供的真实服务测试记录 |
| 7.1 | 四类环境描述混杂来源 | 四类环境 + 测试策略：单元、隔离测试栈、真实服务、Playwright | 结构清晰，区分 Mock 与真实 | 代码与环境实测 |
| 7.2 | 表 7-1/7-2 分 A/B 两组，E2E 6/6 | 单一表 7-1：pytest 350、Vitest 449×5、PG 13/13、AI 22、音频 17、安全 14、SSRF 6、Fallback 4、E2E 8/8×3 | 统一项目成果，去除 349/438 与来源标注 | `logs/` 原始日志 |
| 7.2.3 | E2E 6 spec / 6 case | E2E 8 spec / 8 case，逐 spec 覆盖表 + 持久化断言说明 | 恢复覆盖并补 3 条闭环 | `e2e-restored-final-1..3.log` |
| 7.2.4 | PostgreSQL 描述较短 | 明确 PG 16.15 + pgvector 0.8.7、迁移 0022、13/13、ORM 16/16、隔离/JSONB/约束/回滚/重启 | 真实数据库口径 | `pg-integration.log` |
| 7.2.5 | AI/音频/安全分列 | 合并为 Mock 小节，明确 Mock ≠ 真实 | 避免误解 | `ai_mock_checks.log` 等 |
| 7.3 | 无独立真实服务小节 | 新增真实 LLM（GLM-4-Flash 2 次）与真实 FunASR 流程，并声明与 Mock 分开 | 纳入真实成功成果 | 提供的测试报告 |
| 7.4 | 未验收项含来源说明 | 统一表：Embedding、外部 ASR、麦克风、本地目录、RAG 质量、压测、生产部署、原始日志未归档 | 如实标注边界 | 本轮审查 |
| 7.5 | 部署说明简短 | 增加服务/端口表、环境变量分组、图 7-1、生产缺口 | 满足部署写作要求 | `docker/compose.dev.yml`、代码 |
| 8.1 | 表 8-1 含 B 组行 | 统一指标表：350/449/13/22/17/14/6/4/8×3、真实服务 | 统一口径 | 同上 |
| 附录 A | 含版本演进与来源说明 | 统计口径：16/77/16/22/16/16/6/12/12；350/449/8 | 去除来源与不可复核项 | 代码统计 |
| 附录 D | 引用 A/B 组与队友报告 | 测试环境、命令、结果、E2E、真实服务、日志位置、未验证事项 | 满足附录 D 要求 | 同上 |
| 全文 | 含“队友/A 组/B 组/独立环境/e38fe2a”等 | 已清零 | 统一呈现 | 全文检索 0 命中 |

## 关键事实核对（与代码一致）

| 项 | 值 | 代码位置 |
| --- | --- | --- |
| Router / 端点 | 16 / 77（GET25/POST30/PUT3/PATCH9/DELETE9 + `/health`） | `backend/app/api/v1/`、`main.py` |
| ORM / 迁移 | 16 / 22（head `0022_audio_segments`） | `backend/app/models/`、`alembic/versions/` |
| Services / Repos | 16 / 16 | `backend/app/{services,repositories}/` |
| 模板 / 音频接口 / Views | 6 / 12 / 12 | `meeting_template_service.py`、`api/v1/audio.py`、`frontend/src/views/` |
| RAG | top_k=5、min_score=0.3、chunk 800/120、dim 1024 | `ai/rag/`, `indexing_service.py` |
| LLM | 温度 0.2、60s、3 次、退避 1s/3s | `ai/llm/client.py` |
| Embedding | 1024、batch≤16、30s | `ai/embeddings/client.py` |
| BYOK | Fernet + `SECRET_KEY_PREVIOUS` + 掩码 | `app/core/crypto.py` |
| 音频 | mp3/wav/m4a/webm、20MB、状态机、分片、JSONB、确认入记录 | `audio_service.py` |

## 生成物

- `OpenMIND-技术文档-5.0-review2.md`
- `OpenMIND-技术文档-5.0-review2.docx`
- `OpenMIND-技术文档-5.0-review2.pdf`
- 原始 `OpenMIND-技术文档-5.0.*` 未覆盖。
