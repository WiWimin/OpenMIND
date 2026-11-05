# 00 代码基线（code-baseline）

> 审计日期：2026-11-02；仓库：`https://github.com/WiWimin/OpenMIND`

## 一、最新提交确认

| 项 | 值 |
| --- | --- |
| 远端 | `origin` → `https://github.com/WiWimin/OpenMIND` |
| 分支 | `main`（本地已切换并快进） |
| 完整 SHA | `ff426413ef239e7f23133de206c402cab0b1d2a6` |
| 短 SHA | `ff42641` |
| 提交日期 | 2026-11-01 20:14:03 +0800 |
| 提交标题 | Merge pull request #56 from WiWimin/feature/meeting-workspace-redesign |
| 与远端同步 | `main...origin/main` = 0 / 0 |

`git fetch --all --prune` 已执行（exit 0），`origin/main` 与 `origin/develop` 均无更新于 ff42641 / 7454a20 之外的新提交。

## 二、分支关系

| 分支 | 短 SHA | 日期 | 说明 |
| --- | --- | --- | --- |
| `origin/main` | `ff42641` | 2026-11-01 20:14 | **5.0 采用基线**（最新） |
| `origin/develop` | `7454a20` | 2026-10-31 16:00 | 4.1 使用的基线；比 main 落后 6 个提交 |

`main` 与 `develop` 已分叉：`develop` 独有 1 个提交（`7454a20` 合并 PR #55），`main` 独有 6 个提交（见下）。main 为最新集成结果。

## 三、4.1 基线与 5.0 基线的差异（7454a20..ff42641）

`git diff --stat 7454a20..ff42641`：**96 个文件，+7305 / -2102**。按目录：后端 39、前端 47、docker 2、docs 4、其他（resources/scripts）。

提交列表（时间顺序）：

| commit | 内容 |
| --- | --- |
| `0ce5bec` | Merge PR #54 from develop |
| `3c93569` | feat(m08): chunked live transcription with segment-level transcript |
| `47de6a8` | feat(ai): multi-task organize chain with structured summary and polish |
| `2c82a9d` | feat(settings): model connectivity probe, provider model list and template management |
| `f4240fc` | feat(new-meeting): quick-action task chips, parrot mascot and transcript stream UI |
| `ff42641` | Merge PR #56 |

后端关键变更文件：

- 迁移：`0020_drop_user_embedding_config.py`、`0021_template_category_default.py`、`0022_audio_segments.py`。
- 音频：`models/audio.py`、`schemas/audio.py`、`api/v1/audio.py`、`services/audio_service.py`、`repositories/audio_repository.py`。
- 模型配置：`models/model_config.py`、`schemas/model_config.py`、`services/model_config_service.py`、`api/v1/settings.py`。
- 整理链：`services/ai_chat_service.py`、`ai/prompts/organize.py`、`schemas/chat.py`、`api/v1/ai_chat.py`。
- 模板：`models/meeting_template.py`、`schemas/meeting_template.py`、`services/meeting_template_service.py`、`api/v1/templates.py`。
- 存储：`utils/storage.py`（新增 `read_bytes` / `remove_tree` 等用于分片合并）。

## 四、5.0 唯一代码基线

**结论：5.0 采用 `main` @ `ff426413ef239e7f23133de206c402cab0b1d2a6`（2026-11-01 20:14:03 +0800）作为唯一代码基线。**

理由：
1. 该提交为当前 `main` 与远端最新提交，包含 4.1 之后全部 6 个提交（含音频实时分片转写、多任务整理链、模型连通性探测、模板分类等）。
2. `develop`（7454a20）缺少上述 6 个提交，不代表当前最新功能状态。
3. 文档封面与摘要将标注：版本 5.0、分支 `main`、短 SHA `ff42641`、编制日期、文档状态。

## 五、工作区状态说明

当前工作区为 `main` @ ff42641，**无已跟踪文件改动**；存在大量历史未跟踪文件（`docs/`、zip、解压目录等），本次审计与写作不清理、不覆盖原始 4.1 文件。
