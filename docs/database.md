# 共享数据层设计

本文件是前后端、AI 后端共同遵循的数据契约。字段、关系、状态和数据归属在业务开发前需达成一致。

## 一、数据设计原则

1. 个人数据隔离：用户只能访问自己拥有的会议、资料、记录、任务和问题。
2. 全流程可追溯：AI 结果能够关联来源会议、材料或会议记录。
3. 原始数据与 AI 结果分离：保留用户原始记录，不以 AI 生成结果覆盖原文。
4. 候选与确认分离：AI 提取的行动项和纪要必须允许用户编辑、确认。
5. 独立更新：纪要、行动项和任务可以分别更新，历史确认任务不因纪要修改而丢失来源关联。
6. 业务状态由后端控制：前端不能通过直接修改状态字段绕过权限或业务规则。

## 二、核心数据实体

| 实体 | 主要字段 | 关系与用途 |
| --- | --- | --- |
| User | `user_id`、`name`、`created_at` | 个人工作区及数据归属 |
| Meeting | `meeting_id`、`user_id`、`title`、`topic`、`meeting_time`、`status` | 用户拥有多场会议 |
| MeetingMaterial | `material_id`、`meeting_id`、`user_id`、`file_name`、`type`、`content`、`source` | 保存原始文件信息及提取文本 |
| MeetingRecord | `record_id`、`meeting_id`、`content`、`record_type`、`created_at` | 保存手动记录、重点标记和问题记录 |
| Preparation | `preparation_id`、`meeting_id`、`summary`、`checklist`、`version` | 保存会前摘要和个人准备清单 |
| MeetingMinutes | `minutes_id`、`meeting_id`、`content`、`version`、`created_at` | 保存 AI 生成及用户编辑后的纪要 |
| ActionItem | `action_id`、`meeting_id`、`content`、`assignee`、`due_date`、`status`、`source` | 保存候选或已确认行动项 |
| PersonalTask | `task_id`、`user_id`、`action_id`、`meeting_id`、`title`、`status`、`due_date` | 个人任务，能够追溯来源 |
| OpenIssue | `issue_id`、`meeting_id`、`description`、`status`、`follow_up` | 保存未解决问题和后续确认事项 |
| DocumentChunk | `chunk_id`、`material_id`、`content`、`chunk_index`、`embedding` | RAG 内部检索实体，保存分块、来源与向量 |

## 三、数据关系（E-R）

- User — Meeting：一对多
- User — PersonalTask：一对多
- Meeting — MeetingMaterial：一对多
- Meeting — MeetingRecord：一对多
- Meeting — Preparation：一对多
- Meeting — MeetingMinutes：一对多
- Meeting — ActionItem：一对多
- Meeting — OpenIssue：一对多
- ActionItem — PersonalTask：已确认行动项可转为个人任务
- Meeting — PersonalTask：个人任务可追溯来源会议
- MeetingMaterial — DocumentChunk：资料被切分为检索分块
- MeetingRecord — ActionItem：会议记录为行动项提取提供支撑

补充要求：

- DocumentChunk 每条分块必须能回溯到所属资料，不能只存向量而丢失原文来源。
- 个人任务必须同时保留用户、来源会议和可选行动项的关联。
- 纪要和准备结果应使用版本或更新时间字段，避免生成新版本时覆盖历史数据。
- AI 生成结果与用户确认结果应有明确区分，可通过状态字段或版本记录实现。

## 四、共享状态与枚举

| 对象 | 状态建议 | 说明 |
| --- | --- | --- |
| Meeting | `scheduled`、`in_progress`、`completed`、`archived` | 会议生命周期 |
| Material | `uploaded`、`processing`、`processed`、`failed` | 文件解析状态 |
| Preparation | `generating`、`draft`、`confirmed`、`failed` | 会前准备状态 |
| Minutes | `draft`、`confirmed` | 纪要是否经过用户确认 |
| ActionItem | `pending_confirmation`、`confirmed`、`converted`、`cancelled` | 行动项确认与转任务状态 |
| PersonalTask | `todo`、`in_progress`、`completed`、`cancelled` | 个人任务状态 |
| OpenIssue | `open`、`resolved`、`cancelled` | 未解决问题状态 |

> 状态流转由后端校验。不要将 AI 生成成功直接等同于用户确认成功。

## 五、数据库与迁移协作规范

1. A 负责主数据库结构和 Alembic 迁移合并。
2. B 在开发 RAG、纪要、行动项之前，先向 A 提交实体字段和关系需求。
3. C 通过 API 响应模型获取数据，不直接依赖数据库内部实现。
4. 每个涉及数据库结构的 PR，必须包含迁移文件或明确说明无需迁移。
5. 不允许多人同时基于同一个旧迁移创建冲突的 Alembic heads。
6. 删除会议、资料、纪要等关联数据时，应通过业务服务统一处理关联清理与文件删除。
7. 已应用（记录进 `alembic_version`）的迁移文件不可再修改，必须新增后续迁移。

## 六、基础设施：PostgreSQL 与 pgvector

| 项目 | 取值 | 说明 |
| --- | --- | --- |
| 镜像 | `pgvector/pgvector:pg16` | 已内置 pgvector 扩展二进制 |
| 持久化 | 具名卷 `pgdata` → `/var/lib/postgresql/data` | 容器重建不丢数据 |
| 容器内地址 | `db:5432` | 容器之间走 Docker 内部网络与服务名解析 |
| 宿主机直连 | `localhost:5432` | 仅用于宿主机直接运行后端，不用于容器间通信 |

pgvector 扩展**由 Alembic 统一管理**：迁移 `0002_enable_pgvector` 执行 `CREATE EXTENSION IF NOT EXISTS vector`。镜像只提供扩展二进制，扩展必须在目标库内启用后 `vector` 类型才可用，因此该迁移不可省略。

- 该迁移幂等，重复执行安全。
- `downgrade` 不做级联删除：若已有表/列依赖 `vector` 类型，降级会明确失败，而不是静默摧毁这些对象。
- 禁止使用 `docker-entrypoint-initdb.d` 之类的 initdb SQL 来启用扩展——initdb 脚本只在数据目录为空的首次启动时执行，不受版本控制，无法随代码演进。

验证方式见 `docs/development.md` 的「数据库启动验证」章节（`scripts/verify-db.ps1` / `scripts/verify-db.sh`）。
