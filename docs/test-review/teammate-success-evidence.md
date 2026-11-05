# 统一测试成果证据表（内部审查记录）

> 用途：记录本轮可纳入技术文档的成功测试成果及其证据强度。
> 说明：最终技术文档统一表述为 OpenMIND 项目测试成果，不出现执行者或环境来源区分。

## 一、可纳入的成功成果

| 项目 | 结果 | 证据 | 强度 | 文档处理 |
| --- | --- | --- | --- | --- |
| 后端 pytest | 350 passed / 0 failed / 0 skipped / 0 errors / 1 warning / 98.94 s | `docs/test-review/logs/backend-pytest.log` | 强（本轮实际执行） | 纳入 §7.2 |
| 后端 ruff | All checks passed | `logs/backend-ruff.log` | 强 | 纳入 §7.2 |
| 前端 Vitest | 87 files / 449 passed，连续 5 次 | `logs/frontend-vitest*.log` | 强 | 纳入 §7.2 |
| typecheck / lint / build | 全部通过 | `logs/frontend-{typecheck,lint,build}.log` | 强 | 纳入 §7.2 |
| PostgreSQL 集成 | 13/13，ORM 16/16，重启持久性 | `logs/pg-integration.log`、`logs/pg-persistence.log` | 强 | 纳入 §7.2 |
| AI Mock | 22/22 | `logs/ai_mock_checks.log` | 强 | 纳入 §7.2 |
| 音频 Mock | 17/17 | `logs/audio_mock_checks.log` | 强 | 纳入 §7.2 |
| 安全 | 14/14 | `logs/security_checks.log` | 强 | 纳入 §7.2 |
| SSRF | 6/6 | `logs/ssrf_checks.log` | 强 | 纳入 §7.2 |
| Fallback 默认关闭 | 4/4 | `logs/fallback_default_off.log` | 强 | 纳入 §7.2 |
| Playwright E2E | 8/8，连续 3 轮（55.7 / 52.3 / 59.9 s） | `logs/e2e-restored-final-1..3.log` | 强 | 纳入 §7.2.3 |
| 真实 GLM-4-Flash | 2 次调用成功 | 提供的测试报告（`tests/队友测试补充报告.doc`） | 中（无原始调用日志） | 纳入 §7.3，并在 §7.4 标注原始日志未归档 |
| 本地 FunASR | 转写→确认→生成会议记录全流程成功 | 同上 | 中（无原始运行日志） | 纳入 §7.3，并在 §7.4 标注原始日志未归档 |

## 二、不纳入的成功口径

| 项目 | 原因 |
| --- | --- |
| pytest 349 / Vitest 438 | 来自不同代码提交，不与 350 / 449 相加或混用 |
| E2E 2 passed / 3 skipped | 旧轮次结果；skipped 不计为通过，已被 8/8 取代 |
| Embedding 调用 | 两次 RATE_LIMITED，未成功，列为未验收 |
| 实时录音、本地目录真实写入 | 未执行人工验收，不得写成成功 |

## 三、口径说明

- 不同测试集保留各自口径，不把不同报告的数量相加。
- Mock 测试与真实供应商测试分开描述；GLM/FunASR 为真实服务记录，但原始日志未归档，已在文档限制项中说明。
- 最终技术文档不出现“队友”“A 组/B 组”“独立环境”等来源区分表述。
