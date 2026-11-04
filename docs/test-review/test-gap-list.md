# OpenMIND 测试缺口清单（Test Gap List）

> 基线：`ff426413ef239e7f23133de206c402cab0b1d2a6`。
> 状态定义：`BLOCKED`=缺凭据/服务；`NOT RUN`=未执行；`MOCK ONLY`=仅 Mock；`UNVERIFIED`=无法从本仓库复核；`UNTESTED`=无覆盖。

## 一、外部服务与真实链路

| ID | 缺口 | 状态 | 现有证据 | 风险 | 下一步 |
| --- | --- | --- | --- | --- | --- |
| G1 | 真实 LLM 调用 | BLOCKED | 测试环境 `LLM_API_BASE=http://mock-ai:9000/v1` | 真实供应商兼容性/配额/错误码未验证 | 提供凭据后执行 2 次真实 chat + 1 次 429 场景 |
| G2 | 真实 Embedding 调用 | BLOCKED | `EMBEDDING_API_BASE` 指向 Mock | 维度/限流/真向量检索未验证 | 真实调用并核对 1024 维、入库与检索 |
| G3 | 真实外部 ASR | BLOCKED | `ASR_API_BASE` 指向 Mock | 外部 ASR 兼容性未验证 | 提供凭据后上传真实音频 |
| G4 | 本地 FunASR | NOT RUN | 无 asr 镜像/容器/模型 | 真实转写质量与性能未知 | 构建 `docker/asr` 或 `scripts/asr.ps1` 后执行 |
| G5 | 浏览器真实麦克风录音 | NOT RUN | E2E 仅文件上传 | MediaRecorder/分片在真实设备上未验证 | 人工按 `manual-acceptance-checklist.md` 执行 |
| G6 | 本地目录真实读写 | NOT RUN | 仅验证 `showDirectoryPicker` 缺失时的降级 | 授权、写入、重开未验证 | 人工在 Edge/Chrome 选择目录并校验文件 |
| G7 | RAG 检索质量 | NOT EVALUATED | 无标注评测集 | 准确率/召回率/引用质量无数据 | 建立 20–50 条问答黄金集后再评测 |

## 二、真实服务与外部记录的可复核性

| ID | 项目 | 状态 | 说明 |
| --- | --- | --- | --- |
| G8 | 外部记录的 pytest 349 / Vitest 438 / E2E 2+3 skipped | 不采用 | 来自不同代码提交，未与本轮 350 / 449 / 8×8 混用 |
| G9 | 真实 GLM-4-Flash 2 次调用 | 已纳入（证据中等） | 提供的测试记录无原始调用日志；文档标注“原始日志未归档” |
| G10 | 真实 FunASR 全流程 | 已纳入（证据中等） | 同上 |
| G11 | 真实 Embedding 调用 | 未成功 | RATE_LIMITED ×2，列为未验收 |

## 三、安全残余风险（已有代码说明，无自动化覆盖）

| ID | 缺口 | 状态 | 说明 |
| --- | --- | --- | --- |
| G13 | DNS 重绑定 | UNTESTED | SSRF 仅校验保存时 URL/解析，重绑定未覆盖 |
| G14 | 上传内容嗅探 | UNTESTED | 仅按扩展名校验，未校验文件魔数/内容 |
| G15 | 接口限流 | UNTESTED | 未见限流实现/测试 |
| G16 | 密钥独立管理 | UNTESTED | 依赖 `SECRET_KEY` 轮换流程，无自动化验证 |
| G17 | 错误信息泄漏 | PARTIAL | 安全脚本覆盖部分错误体，未系统扫描 |
| G18 | 路径穿越 | COVERED | 安全脚本已覆盖（14/14 中的一项） |

## 四、性能、兼容与运维

| ID | 缺口 | 状态 | 说明 |
| --- | --- | --- | --- |
| G19 | 并发/压测 | UNTESTED | 单进程同步调用；无 QPS/并发数据 |
| G20 | 跨浏览器 | UNTESTED | E2E 仅 Edge/Chromium；未测 Firefox/Safari |
| G21 | 可访问性 | UNTESTED | 无 axe/键盘导航测试 |
| G22 | CI 实际执行 | NOT RUN | 仅本地执行；未触发 GitHub Actions |
| G23 | 生产部署 | NOT IMPLEMENTED | Nginx/TLS/多 worker/监控/备份未实现 |
| G24 | 备份与恢复 | UNTESTED | 仅有开发库重启持久性，无备份演练 |

## 五、本轮已补齐的测试缺口

| ID | 缺口 | 处理 | 结果 |
| --- | --- | --- | --- |
| T1 | 登录流程未覆盖 | 新增 `frontend/e2e/auth-flow.spec.ts` | 通过（3/3 轮） |
| T2 | 纪要生成未覆盖 | 新增 `frontend/e2e/minutes-flow.spec.ts` | 通过（3/3 轮） |
| T3 | `ai-flow` 条件 `test.skip` 可静默跳过 | 改为 `expect(access.ready).toBeTruthy()` | 通过（3/3 轮） |

## 六、结论

- 自动化可执行部分已全部通过；未通过项均为外部依赖/人工验收或性能评测，已分类标注。
- 在 G1–G7 完成前，不得宣称真实模型、真实 ASR、实时录音、本地工作区或 RAG 质量已验证。

## 七、待办状态

以上 G1–G24 均**仍为待办**，不因文档口径同步而关闭；真实服务、人工验收、安全残余与性能测试在获得凭据/设备/评测集后按 `manual-acceptance-checklist.md` 执行。

## 八、本轮更新（review2）

- E2E 覆盖已恢复：core（记录标记/知识库/记忆）、ai（准备/问答/纪要/行动项/问题）、audio（记录落库）、model-settings（LLM BYOK 边界）均已回归；最终 8/8 ×3。
- 技术文档已统一为项目测试成果，去除来源区分表述。
- G1–G7、G13–G24 仍为待办，未因文档更新而关闭。
