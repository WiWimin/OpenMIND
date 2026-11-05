# OpenMIND 人工验收与真实服务检查清单

> 基线：`ff426413ef239e7f23133de206c402cab0b1d2a6`。
> 本轮所有项目均为 **NOT RUN / BLOCKED**；完成前不得在文档或汇报中写“已通过”。
> 凭据只写入本地 `docker/.env`，不得提交、不得打印到日志。

## 1. 真实 LLM 调用

**前置**：可用供应商密钥；`docker/.env` 设置 `LLM_API_BASE`、`LLM_API_KEY`、`LLM_MODEL`；`ALLOW_GLOBAL_FALLBACK=false`；`ALLOW_PRIVATE_MODEL_ENDPOINTS=false`（公网地址）。

**步骤**
1. 重启后端：`docker compose -f docker/compose.dev.yml up -d --force-recreate backend`。
2. 登录后进入“设置 → 模型配置”，保存自定义 LLM（或使用全局配置）。
3. 打开任一会议，进入“纪要”页发起一次问答。
4. 再次发起一次“提取待办”。
5. 查询模型配置接口，确认 `llm_source` 与 `llm_probe_verified`。

**预期**：两次真实调用返回 200；回答带 sources（有材料时）；`llm_source=user` 或 `global`；不出现 `MODEL_CONFIG_REQUIRED`。

**留存**：请求时间、模型名、响应状态、`llm_probe_verified`、调用截图（不含密钥）。

**状态**：BLOCKED（本环境 `LLM_API_BASE=http://mock-ai:9000/v1`）。

## 2. 真实 Embedding 调用

**前置**：`EMBEDDING_API_BASE/KEY/MODEL` 指向真实服务；`EMBEDDING_DIM=1024`。

**步骤**
1. 重启后端。
2. 上传一份 PDF/DOCX/TXT 材料，等待“已解析”。
3. 检查 `document_chunks` 行数与 `embedding` 非空。
4. 发起一次材料问答，确认命中来源。

**预期**：Embedding 返回 1024 维；分块入库；无 `MODEL_TIMEOUT`/`RATE_LIMITED`；问答引用材料片段。

**留存**：入库行数、维度、耗时、错误码（若有）。

**状态**：BLOCKED（本环境为 Mock；文档 B 组记录为 RATE_LIMITED×2，未能成功）。

## 3. 本地 FunASR 实际转写

**前置**：`scripts/asr.ps1` 可运行；镜像/模型已下载（约 1.5GB+，CPU 首次预热约 15 分钟）。

**步骤**
1. `powershell -ExecutionPolicy Bypass -File scripts/asr.ps1 up`。
2. `powershell -ExecutionPolicy Bypass -File scripts/asr.ps1 smoke`。
3. `docker compose -f docker/compose.dev.yml --profile asr up -d backend`。
4. 上传一段 30–60s 的真实语音（mp3/wav/m4a/webm）。
5. 等待状态 `transcribed`，检查分段文本。
6. 编辑文稿 → “确认并保存为记录”。

**预期**：`smoke` 通过；转写非空；分段带 `offset_seconds`；确认后生成 `RecordType.transcript` 会议记录。

**留存**：smoke 日志、转写文本、分段 JSON、确认后的记录截图。

**状态**：NOT RUN（无 asr 镜像/容器/模型）。

## 4. 外部 ASR（如有凭据）

**前置**：`ASR_API_BASE/KEY/MODEL` 指向外部服务。

**步骤**：同第 3 节步骤 4–6，改为外部 ASR。

**预期**：与第 3 节一致；错误路径需验证 401/429/超时映射。

**状态**：BLOCKED（无外部凭据）。

## 5. 浏览器真实麦克风录音（MediaRecorder）

**前置**：Chrome/Edge；可授权麦克风；后端与测试前端已启动。

**步骤**
1. 打开会议 → “实时录音转写”。
2. 授权麦克风，录制 30s（包含 2–3 句清晰语音）。
3. 观察分片上传请求（`audio/{id}/live/chunk`）。
4. 结束录音（`live/finish`），等待转写。
5. 编辑文稿并确认生成记录。

**预期**：分片持续上传；结束后文本合并；单片失败可重试且不中断；确认生成记录。

**留存**：Network 面板分片请求、最终文稿、记录截图。

**状态**：NOT RUN（需人工授权设备）。

## 6. 本地工作区真实目录读写

**前置**：Chrome/Edge；支持 File System Access API。

**步骤**
1. 打开会议 → “纪要” → 生成并确认纪要。
2. 首次确认时选择本地目录并授权读写。
3. 检查目录内生成的文件（纪要）。
4. 刷新/重开页面，再次确认可复用授权并写入。
5. 撤销授权后再次确认，观察降级提示。

**预期**：授权后写入成功；重开可复用；拒绝授权时给出明确提示且不阻塞主流程。

**留存**：目录文件列表、文件内容截图、降级提示截图。

**状态**：NOT RUN（需人工选择目录）。

## 7. RAG 质量评测（无黄金集则不得报指标）

**前置**：建立 20–50 条“问题—标准答案—应引用材料”的标注集。

**步骤**
1. 固定材料与分块参数（800/120）。
2. 对每条问题执行检索问答，记录 Top-5 命中的材料/分块。
3. 计算 Recall@5、引用正确率、无证据拒答正确率。
4. 记录失败样例并归类。

**预期**：输出可复现的评测表；未建立标注集前只列“未评测”。

**状态**：NOT EVALUATED（无标注集）。

## 8. 安全残余项人工复核

| 项 | 步骤 | 预期 |
| --- | --- | --- |
| DNS 重绑定 | 使用可控 DNS 指向私网，保存/探测模型地址 | 保存时解析与请求时均拦截私网 |
| 上传内容嗅探 | 将可执行内容改名为 `.txt` 上传 | 解析失败并拒绝，不落库/不索引 |
| 限流 | 高频登录/问答 | 返回 429 或明确限流错误 |
| 密钥轮换 | 设置 `SECRET_KEY_PREVIOUS` 后轮换 | 旧密文仍可解密，新密文使用新密钥 |

**状态**：UNTESTED（无自动化覆盖）。

## 9. 当前完成状态（2026-11-03）

| 项目 | 状态 |
| --- | --- |
| 真实 LLM（GLM-4-Flash） | 已有成功记录；原始日志未归档，人工复核仍待执行 |
| 真实 Embedding | 未成功（限流） |
| 本地 FunASR | 已有流程成功记录；原始日志未归档，复测需本地模型 |
| 外部 ASR | BLOCKED（无凭据） |
| 浏览器实时录音 | NOT RUN |
| 本地目录真实读写 | NOT RUN（E2E 仅覆盖降级提示） |
| RAG 质量评测 | NOT EVALUATED |
| 压力/并发 | NOT RUN |
| 生产部署 | NOT RUN |

> 本节状态不改变上文人工验收步骤；在获得凭据、设备与评测集后按步骤执行并留存日志。
