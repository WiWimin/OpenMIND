# 共享数据层设计

本文件是前后端、AI 后端共同遵循的数据契约。字段、关系、状态和数据归属在业务开发前需达成一致。

> 状态：MVP 设计基线。字段类型为 PostgreSQL 建议类型；未决事项见 [`design-baseline.md`](design-baseline.md)。

## 一、数据设计原则

1. 个人数据隔离：用户只能访问自己拥有的会议、资料、记录、任务和问题。
2. 全流程可追溯：AI 结果能够关联来源会议、材料或会议记录。
3. 原始数据与 AI 结果分离：保留用户原始记录，不以 AI 生成结果覆盖原文。
4. 候选与确认分离：AI 提取的行动项和纪要必须允许用户编辑、确认。
5. 独立更新：纪要、行动项和任务可以分别更新，历史确认任务不因纪要修改而丢失来源关联。
6. 业务状态由后端控制：前端不能通过直接修改状态字段绕过权限或业务规则。
7. 来源约束：所有下级实体（材料、记录、准备、纪要、行动项、问题）必须能追溯到所属会议；查询时先校验会议归属当前用户。

## 二、主键与通用字段约定

### 2.1 主键格式（已定）

所有主键由后端生成，采用**带前缀字符串 ID**，类型 `VARCHAR(40)`：

| 实体 | 前缀 | 字段 |
| --- | --- | --- |
| users | `usr_` | `user_id` |
| meetings | `mtg_` | `meeting_id` |
| meeting_materials | `mat_` | `material_id` |
| meeting_records | `rec_` | `record_id` |
| preparations | `prep_` | `preparation_id` |
| meeting_minutes | `min_` | `minutes_id` |
| action_items | `act_` | `action_id` |
| personal_tasks | `tsk_` | `task_id` |
| open_issues | `iss_` | `issue_id` |
| document_chunks | `chk_` | `chunk_id` |

- 形如 `mtg_` + 32 位十六进制（如 `mtg_8f3a1c...`）。
- 外键字段必须与被引用主键类型一致（均 `VARCHAR(40)`）。
- 前端不得自行生成业务主键。

### 2.2 通用字段

- 时间：统一 `TIMESTAMPTZ`，以 **UTC** 存储；仅日期使用 `DATE`；`created_at`/`updated_at` 默认 `now()`，由后端维护。
- 结构化附加数据可用 `JSONB`，但核心状态和关联 ID 不藏在 JSON 中。
- 版本：`version` 从 1 开始，编辑后递增。

## 三、核心数据实体

> `PK` 主键；`NN` 非空；`UQ` 唯一；`FK` 外键；`IDX` 索引；`?` 可空。

### 3.1 `users` 用户

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `user_id` | VARCHAR(40) | PK | `usr_` 前缀 |
| `name` | VARCHAR(100) | NN, UQ | **唯一登录标识**（登录名兼显示名） |
| `password_hash` | TEXT | NN | 密码哈希，禁止明文 |
| `status` | VARCHAR(20) | NN, default `active` | `active` / `disabled` |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 登录标识为 `name`；**不设 email 字段**。
- 密码哈希算法由后端安全实现决定（成熟算法，禁止明文/可逆/普通 SHA）。
- API 不得返回 `password_hash`。

### 3.2 `meetings` 会议

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `meeting_id` | VARCHAR(40) | PK | `mtg_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 所属用户 |
| `title` | VARCHAR(200) | NN | 标题 |
| `topic` | TEXT | ? | 主题/背景 |
| `meeting_time` | TIMESTAMPTZ | ?, IDX | 计划时间 |
| `status` | VARCHAR(20) | NN, default `scheduled` | 见 §五 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |
| `archived_at` | TIMESTAMPTZ | ? | 归档时间 |

### 3.3 `meeting_materials` 会议材料

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `material_id` | VARCHAR(40) | PK | `mat_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 所属用户（便于过滤） |
| `file_name` | VARCHAR(255) | NN | 原始文件名 |
| `type` | VARCHAR(30) | NN | 标准化类型：`pdf` / `docx` / `txt` |
| `source` | VARCHAR(100) | ? | 来源说明 |
| `storage_key` | TEXT | NN | 存储定位键，不暴露前端 |
| `content` | TEXT | ? | 解析后文本（原文件独立存储） |
| `processing_status` | VARCHAR(20) | NN, default `uploaded` | 见 §五 |
| `parse_error` | TEXT | ? | 内部安全错误摘要 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- `meeting_materials.user_id` 必须与会议所属用户一致。
- 支持扩展名当前为 `.pdf` / `.docx` / `.txt`（对齐解析层 `SUPPORTED_EXTENSIONS`）。
- 删除材料须由业务服务同步清理 `document_chunks` 与文件对象。

### 3.4 `meeting_records` 会议记录

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `record_id` | VARCHAR(40) | PK | `rec_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `content` | TEXT | NN | 记录文本 |
| `record_type` | VARCHAR(20) | NN, default `manual` | `manual` / `transcript` / `imported` |
| `source_material_id` | VARCHAR(40) | FK→meeting_materials, ? | 转写/导入来源 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

### 3.5 `preparations` 会前准备稿

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `preparation_id` | VARCHAR(40) | PK | `prep_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `summary` | TEXT | NN, default '' | 会前摘要 |
| `checklist` | JSONB | NN, default `[]` | 字符串数组 |
| `status` | VARCHAR(20) | NN, default `draft` | 见 §五 |
| `version` | INTEGER | NN, default 1 | |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 版本：每次**生成**新增记录；对同一条记录的**编辑**原地更新并 `version` 递增（`ai-design.md 八.1`）。

### 3.6 `meeting_minutes` 会议纪要

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `minutes_id` | VARCHAR(40) | PK | `min_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `content` | TEXT | NN | 纪要正文 |
| `status` | VARCHAR(20) | NN, default `draft` | 见 §五 |
| `version` | INTEGER | NN, default 1 | |
| `source_record_ids` | JSONB | NN, default `[]` | 生成依据的记录 ID 快照 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- 版本：每次**生成**新增记录；编辑原地更新并 `version` 递增，确认置 `confirmed`（`ai-design.md 八.4`）。

### 3.7 `action_items` 行动项

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `action_id` | VARCHAR(40) | PK | `act_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `content` | TEXT | NN | 行动内容 |
| `assignee` | VARCHAR(100) | ? | 负责人文本，不一定关联系统用户 |
| `due_date` | DATE | ? | 截止日期 |
| `status` | VARCHAR(30) | NN, default `pending_confirmation` | 见 §五 |
| `source_record_id` | VARCHAR(40) | FK→meeting_records, ? | 主要来源记录 |
| `source_excerpt` | TEXT | ? | 支撑原文片段 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- `meeting_id` 非空；删除其所属会议前须检查是否存在已转换行动项（见 §七）。

### 3.8 `personal_tasks` 个人任务

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `task_id` | VARCHAR(40) | PK | `tsk_` 前缀 |
| `user_id` | VARCHAR(40) | FK→users, NN, IDX | 任务所属用户 |
| `meeting_id` | VARCHAR(40) | FK→meetings, ?, IDX | 来源会议 |
| `action_id` | VARCHAR(40) | FK→action_items, ?, UQ | 来源行动项（唯一） |
| `title` | VARCHAR(255) | NN | 标题 |
| `status` | VARCHAR(20) | NN, default `todo` | 见 §五 |
| `due_date` | DATE | ? | 截止日期 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

- `action_id` 唯一：保证同一行动项不重复生成任务（转任务幂等）。
- 转换任务的 `user_id` 必须为当前用户，不接受请求体指定。

### 3.9 `open_issues` 待跟进问题

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `issue_id` | VARCHAR(40) | PK | `iss_` 前缀 |
| `meeting_id` | VARCHAR(40) | FK→meetings, NN, IDX | 所属会议 |
| `description` | TEXT | NN | 问题描述 |
| `status` | VARCHAR(20) | NN, default `open` | 见 §五 |
| `follow_up` | TEXT | ? | 跟进内容 |
| `source_record_id` | VARCHAR(40) | FK→meeting_records, ? | 来源记录 |
| `created_at` | TIMESTAMPTZ | NN, default now() | |
| `updated_at` | TIMESTAMPTZ | NN, default now() | |

### 3.10 `document_chunks` 文档分块

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `chunk_id` | VARCHAR(40) | PK | `chk_` 前缀 |
| `material_id` | VARCHAR(40) | FK→meeting_materials, NN, IDX | 来源材料 |
| `content` | TEXT | NN | 分块文本 |
| `chunk_index` | INTEGER | NN | 顺序，从 0 开始 |
| `embedding` | `vector(1024)` | ? | 维度固定 **1024** |
| `created_at` | TIMESTAMPTZ | NN, default now() | |

- 唯一约束：`UNIQUE(material_id, chunk_index)`。
- 嵌入模型：阿里百炼 `text-embedding-v3`，维度 1024（依据 M00-08 验证）。
- 未生成 embedding 的分块可为空；检索不得把空向量当有效向量。
- 删除/重新解析材料时清理旧分块。

## 四、数据关系（E-R）

- User — Meeting：一对多
- User — PersonalTask：一对多
- Meeting — MeetingMaterial：一对多
- Meeting — MeetingRecord：一对多
- Meeting — Preparation：一对多
- Meeting — MeetingMinutes：一对多
- Meeting — ActionItem：一对多
- Meeting — OpenIssue：一对多
- MeetingMaterial — DocumentChunk：一对多
- MeetingRecord — ActionItem：一对多（`source_record_id`）
- MeetingRecord — OpenIssue：一对多（`source_record_id`）
- ActionItem — PersonalTask：0..1 对 0..1（`personal_tasks.action_id` 唯一）

补充要求：

- DocumentChunk 每条必须能回溯所属材料，不能只存向量丢失来源。
- 个人任务必须保留用户、来源会议与可选行动项关联。
- 纪要与准备结果用 `version`/`updated_at` 管理，避免覆盖历史。

## 五、共享状态与枚举

| 对象 | 字段 | 取值 | 说明 |
| --- | --- | --- | --- |
| Meeting | `status` | `scheduled`、`archived` | **MVP 仅两态**；预留 `in_progress`/`completed` 将来扩展 |
| Material | `processing_status` | `uploaded`、`processing`、`processed`、`failed` | 解析状态 |
| Preparation | `status` | `generating`、`draft`、`confirmed`、`failed` | |
| Minutes | `status` | `draft`、`confirmed` | |
| ActionItem | `status` | `pending_confirmation`、`confirmed`、`converted`、`cancelled` | |
| PersonalTask | `status` | `todo`、`in_progress`、`completed`、`cancelled` | |
| OpenIssue | `status` | `open`、`resolved`、`cancelled` | |

流转规则：

- Meeting：`scheduled` ↔ `archived`（归档只读，MVP 不提供开始/完成操作）。
- Material：`uploaded → processing → processed | failed`；重试允许 `failed → processing`。
- ActionItem：`pending_confirmation → confirmed → converted`；可由待确认/已确认进入 `cancelled`；**仅 `confirmed` 可转任务**。
- PersonalTask：`todo → in_progress → completed`；未完成可 `cancelled`。
- OpenIssue：`open → resolved | cancelled`。

> 状态流转由后端校验，前端不得直接改写。

## 六、索引与约束建议

- `users(name)`：唯一索引。
- `meetings(user_id, meeting_time)`。
- `meeting_materials(meeting_id)`、`meeting_materials(user_id)`。
- `meeting_records(meeting_id, created_at)`。
- `preparations(meeting_id, created_at)`。
- `meeting_minutes(meeting_id, created_at)`。
- `action_items(meeting_id, status)`。
- `personal_tasks(user_id, status, due_date)`。
- `open_issues(meeting_id, status)`。
- `document_chunks(material_id, chunk_index)`：唯一索引。
- `personal_tasks(action_id)`：唯一约束。
- 向量索引（HNSW/IVFFlat）待数据量确定后再选，不作为当前硬性要求。

## 七、删除与数据一致性策略

采用**受控级联**，由业务服务在事务中显式执行，不依赖隐式数据库行为。

- **删除会议**：
  - 若存在**已转换行动项**（`action_items.status = converted`）或**引用该会议的个人任务**（`personal_tasks.meeting_id`），**禁止删除**，业务层返回 `409 BUSINESS_RULE_VIOLATION`。
  - 否则在事务中删除该会议的材料、分块、记录、准备稿、纪要、行动项与问题。
- 删除材料：删除文件对象、`document_chunks` 与向量；`meeting_records.source_material_id` 引用该材料时置空，不删除原始记录。
- 删除行动项：已转换为任务的不允许直接删除（应取消状态或保留关联），避免任务失去来源。
- 用户删除：MVP 不提供。
- 文件存储不支持事务时，须设计失败补偿/清理机制。

## 八、数据库与迁移协作规范

1. A 负责主数据库结构和 Alembic 迁移合并。
2. B 在开发 RAG、纪要、行动项之前，先向 A 提交实体字段和关系需求。
3. C 通过 API 响应模型获取数据，不直接依赖数据库内部实现。
4. 每个涉及数据库结构的 PR，必须包含迁移文件或明确说明无需迁移。
5. 不允许多人同时基于同一个旧迁移创建冲突的 Alembic heads。
6. 删除会议、资料、纪要等关联数据时，应通过业务服务统一处理关联清理与文件删除。
7. 已应用（记录进 `alembic_version`）的迁移文件不可再修改，必须新增后续迁移。

## 九、基础设施：PostgreSQL 与 pgvector

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
