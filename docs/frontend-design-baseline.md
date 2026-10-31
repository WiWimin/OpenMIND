# OpenMIND 前端设计现状与优化基线

> **文档目的**：以当前 `develop` 工作区代码为事实依据，梳理项目定位、功能现状、前端实现、后端契约、Agent 能力与技术约束，并给出基于参考设计图的页面优化方案。
>
> **文档定位**：本文件负责「前端设计现状与优化决策」，不替代 `requirements.md`（产品范围）、`api.md`（接口契约）、`database.md`（数据契约）、`ai-design.md`（AI 实现）。发生冲突时，以上述权威文档和运行期 OpenAPI 为准。
>
> **参考材料**：8 张「智会 AI 助手」界面参考图。仅用于布局、信息层级、组件形态与交互节奏参考；不复制其品牌、Logo、文案、人物头像、插画与第三方产品名称。参考图中大量文字为 AI 生成占位内容，不作为需求依据。
>
> **更新时间**：2026-10-27

---

## 0. 结论摘要

1. **能力基础已经具备**：MVP 闭环 M00–M10 已实现，并扩展了纪要模板、按用途模型路由、个人知识库、记忆中心、本地会议工作区、音频上传转写。参考图中的核心页面，大多数可以在现有接口上完成视觉与信息架构升级。
2. **真正缺的是「信息组织」而不是「功能数量」**：当前前端已覆盖闭环，但页面结构偏工程化、表格与筛选能力不足、状态语义不统一，导致用户需要多点几次才能看到「这场会议走到哪一步」。
3. **设计优化应分三层**：
   - **P0 无后端改动**：统一外壳、设计令牌、表格/标签页/统计卡等基础组件，重排现有页面信息层级。
   - **P1 小后端改动**：会议搜索与聚合、任务筛选与来源会议名、知识库分块统计/重新索引、导出设置。
   - **P2 大能力**：实时 ASR、流式输出、扬声器分离、会议沉淀知识库、通知中心、全局搜索、组织权限。
4. **不可伪造的能力**：实时录音转写、说话人分离、逐句时间戳、通知中心、AI 自动建任务、会议完成状态、知识库全局检索开关、独立「测试连接」接口，当前后端均未提供。参考图中的这些元素必须降级为「上传音频转写」「按请求选择知识库范围」「保存时探测」等真实能力，或明确标注「规划中」。
5. **最重要的产品约束不变**：AI 只产出草稿/候选；纪要、行动项、问题必须经用户确认；任务只能由已确认行动项转换；状态由后端控制；密钥不下发前端。

---

## 1. 项目定位

### 1.1 一句话定位

OpenMIND 是面向**个人参会者**的「AI 会议个人助理」，围绕**会前准备 → 会中记录 → 会后纪要 → 个人任务跟进**，把一场会议的资料、讨论、结论和待办串成可追溯的个人工作流。

### 1.2 目标用户

| 维度 | 描述 |
| --- | --- |
| 核心用户 | 产品经理、项目经理、研发负责人、咨询顾问、销售等高频参会者 |
| 使用形态 | 个人使用，一人一账号；不是团队协作空间 |
| 主要诉求 | 会前快速读懂资料、会中不漏重点、会后快速出纪要、待办不丢 |
| 使用设备 | 桌面浏览器为主；参考图为 16:9 桌面工作台 |
| 能力水平 | 不要求用户理解 Prompt、向量、模型参数；高级配置放在系统设置 |

### 1.3 核心使用场景

1. **会前 30 分钟**：上传项目背景、参会人、议程草案，让 AI 提炼议题、风险与准备清单。
2. **会中**：记录讨论、标记重点/决议/疑问；随时基于资料和当前记录提问。
3. **会后 10 分钟**：生成纪要草稿，确认结论，提取行动项与未解决问题。
4. **次日跟进**：把已确认行动项转为个人任务，按截止时间推进、完成或取消。
5. **长期积累**：把个人文档放入知识库，在会议问答中按需引用；维护个人角色与表达偏好。

### 1.4 产品目标与闭环判定

```text
创建会议 → 导入资料 → AI 理解与检索 → 会前准备
   → 会中记录与问答 → 生成纪要 → 提取行动项 → 个人任务跟进
```

闭环成立的标准：

- 一次真实会议能从「建会」走到「行动项转为个人任务并被跟进」。
- 全程数据可追溯：任务能回到行动项，行动项能回到来源记录，纪要能回到记录与材料。
- 状态由后端控制，前端不能直接改状态绕过规则。
- AI 结果作为草稿/候选，关键结果经用户确认。

### 1.5 明确不做（第一版）

- 多人实时协作、共享会议空间、组织/团队权限体系。
- 会议主持、议程编排、投票、云端录制。
- 移动端 App、离线模式、浏览器插件。
- 多语言界面。
- 自动化部署流水线（CI 只做检查）。
- 实时流式 ASR、说话人分离、逐句时间戳（当前仅支持上传音频后同步转写）。

### 1.6 设计原则（由业务约束推导）

| 原则 | 对界面的要求 |
| --- | --- |
| 候选与确认分离 | 所有 AI 产出显示「草稿 / 待确认 / 已确认」；确认按钮是明确的主操作 |
| 原始数据不被覆盖 | 编辑 AI 结果时保留来源；重新生成新增版本，不静默覆盖已确认纪要 |
| 可追溯 | 问答显示来源片段；行动项显示来源记录；任务显示来源会议 |
| 个人数据隔离 | 不出现团队空间、成员管理、共享入口 |
| 状态由后端控制 | 前端只提供合法动作，不提供「直接改状态」的下拉捷径 |
| 密钥安全 | 系统设置只显示脱敏密钥；不提供「查看明文」 |
| 长耗时透明 | AI 生成、音频转写显示进行中、可取消、失败可重试，不伪造进度百分比 |
| 低认知负担 | 一场会议一条主线；会前、会中、会后三个阶段始终可见 |

---

## 2. 功能现状

### 2.1 已实现功能

| 模块 | 能力 | 状态 | 主要入口 |
| --- | --- | --- | --- |
| M00 基础工程 | 前后端骨架、数据库迁移、Docker Compose、CI、协作规范 | 已实现 | — |
| M01 用户认证 | 注册、登录、退出、当前用户；HS256 JWT；无 refresh | 已实现 | `/login`、`/register` |
| M02 会议管理 | 列表、创建、详情、编辑、删除、归档；仅 `scheduled` / `archived` | 已实现 | `/meetings`、`/meetings/:id` |
| M03 会议资料 | PDF/DOCX/TXT 上传、解析、分块、向量索引、状态、删除 | 已实现 | 会议详情「材料」、资料预处理 |
| M04 模型与检索 | BYOK、Embedding、向量检索、模型探测、按用途模型路由 | 已实现 | `/settings` |
| M05 会前准备 | 生成摘要与准备清单、编辑、确认、版本递增 | 已实现 | `/new-meeting/preprocess` |
| M06 会议记录 | 记录增删改查、重点/决议/疑问标记、问答、整理记录 | 已实现 | 会议详情「记录」、录音转写页 |
| M06 扩展 | 音频上传、同步 ASR、转写修订、确认转记录、失败重试 | 已实现 | 会议详情「音频」、录音转写页 |
| M07 纪要与行动项 | 纪要生成/编辑/确认/模板、行动项提取/确认/转任务 | 已实现 | `/new-meeting/minutes`、会议详情「纪要」 |
| M08 个人任务 | 任务列表、详情、编辑、状态流转、取消；仅由行动项转换 | 已实现 | `/tasks`、`/tasks/archive` |
| M09 未解决问题 | 问题提取、列表、编辑、跟进、状态 | 已实现 | 会议详情「问题」 |
| M10 测试部署 | 异常处理、权限、Playwright E2E、Docker 部署 | 已实现 | — |
| 扩展：知识库 | 个人知识库上传、解析、分块、索引、语义检索、删除 | 已实现 | `/knowledge`、`/knowledge/search` |
| 扩展：记忆中心 | 角色、工作场景、表达偏好、默认纪要模板 | 已实现 | `/memory` |
| 扩展：本地工作区 | 浏览器授权本地目录，导入资料、导出最新纪要 DOCX | 已实现（仅 Chromium） | `/meetings/folder`、会议详情「材料」 |

### 2.2 未实现 / 范围外能力

#### A. 产品范围外

- 多人协作、共享空间、组织与角色权限。
- 会议主持、议程投票、云端录制。
- 移动端 App、离线模式、浏览器插件。
- 多语言。
- 实时流式 ASR、说话人分离、逐字时间戳。
- 自动把会议内容沉淀进个人知识库。

#### B. 参考图有、当前后端暂无的能力

> 这些不是 MVP 缺陷，而是「设计图领先于后端」的部分。前端不能直接做成可用按钮，否则会形成假功能。

| 参考图元素 | 当前真实情况 | 处理建议 |
| --- | --- | --- |
| 顶栏全局搜索 | 无搜索接口，仅会议列表有状态筛选 | P1 增加 `keyword` 后开放；此前可做「页面内搜索」或隐藏 |
| 通知中心 / 红点 | 无通知模型与接口 | P2；当前不要放红点 |
| 参会人列 / 头像组 | `meetings` 无参会人字段 | 不展示；或放入 `topic` 文本 |
| 会议状态「已完成 / 进行中 / 待整理」 | 后端只有 `scheduled` / `archived` | 用「处理进度」派生展示，不写成会议状态 |
| 任务优先级「高/中/低」 | `personal_tasks` 无 priority | 不展示；需后端迁移后开放 |
| 任务负责人 | `personal_tasks` 无 assignee | 不展示；行动项有 `assignee`，但任务没有 |
| 新建任务 | 无 `POST /tasks`；任务只能由行动项转换 | 隐藏「新建任务」，改为「从行动项转入」 |
| 任务来源会议名称 | 任务只返回 `meeting_id` | P1 增加 `meeting_title`，或前端批量解析 |
| 知识库分类 / 分类目录 | 无分类表与接口 | P2；当前用文件名与搜索 |
| 文档分块数量 / 索引中 | 知识库文档只返回 `processing_status`，无分块数 | P1 增加 `chunk_count` / `indexed` |
| 重新索引 | 无 reindex 接口 | P1 增加；此前只支持重新上传 |
| 「启用检索」全局开关 | 只有问答请求参数 `context_scope` | 做成「本次问答范围」选择器；全局偏好需新接口 |
| 导出设置 | 无导出配置接口；仅前端 DOCX 导出 | 先做本地偏好；需多格式再建接口 |
| 模块权限 | 仅资源归属校验，无角色权限 | P2；当前不展示权限矩阵 |
| 账号设置 | 只有用户名与退出 | 可展示只读账号信息；改密/头像需新接口 |
| 模型「测试连接」 | 保存时 probe；无独立测试接口 | 按钮改为「保存并测试」；失败按错误码提示 |
| 会后处理进度 | 无流水线/任务模型 | 用已有状态派生「待生成/已生成/待确认/已完成」 |
| AI 自动建任务 / 自动完成 | 明确禁止 | 保持人工确认与转换 |
| 实时录音 / 说话人区分 | 仅上传音频同步转写 | 改为「上传音频转写」；实时能力另立项目 |

### 2.3 完整业务流程

```text
① 注册/登录
   └─ JWT 存入前端，后续请求 Bearer

② 创建会议（title 必填，topic/meeting_time 可选）
   └─ 进入会前资料预处理

③ 上传会议资料
   └─ 后端同步解析 → 分块 → Embedding → document_chunks
   └─ 状态：uploaded → processing → processed / failed

④ 生成会前准备
   └─ 读取会议信息 + 当前材料（可选有限历史）
   └─ 产出 summary + checklist，status=draft
   └─ 用户编辑/确认 → confirmed

⑤ 会中记录
   ├─ 手动新增记录（manual）
   ├─ 上传音频 → 同步 ASR → transcribed → 用户修订 → 确认生成 transcript 记录
   ├─ 记录打标：highlight / decision / question
   └─ 会议问答：current_meeting / current_and_history / knowledge_base

⑥ 生成纪要
   └─ 读取记录 + 材料 + 标记 + 记忆偏好
   └─ 模板：standard / concise / task_list
   └─ 产出 draft，可编辑、确认、导出 DOCX

⑦ 提取行动项 / 问题
   └─ 行动项 pending_confirmation；问题 open
   └─ 用户确认行动项 → confirmed

⑧ 行动项转个人任务
   └─ 仅 confirmed 可转；action_id 唯一保证幂等
   └─ 行动项变 converted，任务 status=todo

⑨ 任务跟进
   └─ todo → in_progress → completed
   └─ 未完成可 cancelled；终态不可回退

⑩ 归档会议
   └─ 会议只读；不允许编辑或触发 AI 生成
```

### 2.4 状态机与界面呈现

| 对象 | 状态 | 界面建议 |
| --- | --- | --- |
| 会议 | `scheduled` / `archived` | 只显示「已安排 / 已归档」；处理进度另行派生 |
| 材料 | `uploaded` / `processing` / `processed` / `failed` | 已上传 / 解析中 / 已解析 / 解析失败 |
| 准备稿 | `generating` / `draft` / `confirmed` / `failed` | 生成中 / 草稿 / 已确认 / 生成失败 |
| 纪要 | `draft` / `confirmed` | 草稿 / 已确认；不要显示后端不存在的「生成中」 |
| 行动项 | `pending_confirmation` / `confirmed` / `converted` / `cancelled` | 待确认 / 已确认 / 已转任务 / 已取消 |
| 个人任务 | `todo` / `in_progress` / `completed` / `cancelled` | 待办 / 进行中 / 已完成 / 已取消 |
| 问题 | `open` / `resolved` / `cancelled` | 待处理 / 已解决 / 已取消 |
| 音频 | `uploaded` / `processing` / `transcribed` / `failed` / `confirmed` | 已上传 / 转写中 / 已转写 / 转写失败 / 已保存 |
| 知识库文档 | `uploaded` / `processing` / `processed` / `failed` | 已上传 / 解析中 / 已索引 / 解析失败 |

> 设计规范：状态徽标统一使用 `StatusBadge` 的 5 种语义色；不要为同一状态在不同页面使用不同颜色。

---

## 3. 前端现状

### 3.1 技术栈与框架

| 项 | 现状 |
| --- | --- |
| 框架 | Vue 3.5 + TypeScript + Vite 5 |
| 路由 | Vue Router 4，`createWebHistory`，路由守卫按登录态重定向 |
| 状态 | Pinia 2；仅 `auth` / `meetings` / `tasks` / `modelConfig` 四个 store |
| HTTP | axios；`src/api/client.ts` 统一 baseURL、Bearer 注入、错误规范化 |
| UI 框架 | **无** Element Plus / Ant Design / Tailwind；全部为手写组件 + 全局 CSS 令牌 + scoped CSS |
| 富文本 | Tiptap 3（加粗、颜色、字体、高亮、图片等） |
| 文档导出 | `docx` 9，浏览器端生成 DOCX Blob |
| 图标 | 自绘 `NavIcon.vue`（21 个线性图标），无图标库 |
| 字体 | Google Fonts：Inter + Space Grotesk；中文回退 PingFang SC / 微软雅黑 |
| 图表 | 无图表库；进度用 CSS 进度条 |
| 实时能力 | 无 SSE / WebSocket；Agent 回复为一次性响应 + 前端打字机效果 |
| 主题 | 仅浅色；`color-scheme: light`；无暗色模式 |

### 3.2 目录结构

```text
frontend/src/
├── api/            # 14 个领域 API 模块 + client.ts + timeouts.ts
├── assets/         # main.css（全局设计令牌与共享原语）
├── components/     # 42 个可复用组件
├── composables/    # useAsyncList、useToast 等
├── constants/      # routeNames.ts、navigation.ts、upload.ts
├── layouts/        # WorkspaceLayout.vue（全局外壳）
├── router/         # 路由表与登录守卫
├── stores/         # auth / meetings / tasks / modelConfig
├── types/          # 领域类型
├── utils/          # 时间、错误、状态文案、DOCX、Markdown、上传校验
└── views/          # 16 个页面级组件
```

### 3.3 路由与页面清单

| 路由 | 页面 | 导航位置 | 主要能力 | 现状评价 |
| --- | --- | --- | --- | --- |
| `/login` | `auth/LoginView.vue` | 访客 | 登录 | 双栏品牌页，完成度高 |
| `/register` | `auth/RegisterView.vue` | 访客 | 注册 | 与登录同构 |
| `/dashboard` | `DashboardView.vue` | 主页 → 仪表盘 | 统计、最近会议、AI 建议、今日待办 | 已接近参考图 8，但会议表为卡片列表 |
| `/new-meeting` | `newMeeting/NewMeetingView.vue` | 新建会议 → 会议总入口 | 三阶段入口 | 信息偏少，像导航页 |
| `/new-meeting/preprocess` | `newMeeting/PreprocessView.vue` | 新建会议 → 资料预处理 | 资料、准备稿、Agent 对话 | 结构接近参考图 2，但左右栏顺序与视觉需重排 |
| `/new-meeting/asr` | `newMeeting/AsrView.vue` | 新建会议 → 录音转写 | 音频、记录、AI 辅助 | 仅上传音频；无实时录音/说话人分离 |
| `/new-meeting/minutes` | `newMeeting/MinutesGenerateView.vue` | 新建会议 → 纪要生成 | 素材信号、Agent、纪要编辑/确认/导出 | 接近参考图 5，但缺「四张处理卡」与进度侧栏 |
| `/meetings` | `meetings/MeetingManageView.vue` | 会议管理 → 历史会议列表 | 统计、状态筛选、会议表、分页 | 缺搜索、参会人、资料/纪要/待办列 |
| `/meetings/folder` | `meetings/FolderConfigView.vue` | 会议管理 → 本地文件夹配置 | 目录授权、导入/导出说明 | 独立页面，参考图无对应 |
| `/meetings/:meetingId` | `meetings/MeetingDetailView.vue` | 会议管理 → 详情 | 材料/准备/记录/音频/纪要/问题/收尾 | 功能全但信息密度高，适合作为「详情」而非主工作台 |
| `/tasks` | `TasksView.vue` | 任务管理 → 任务总览 | 统计、任务列表、AI 建议 | 缺优先级/负责人/来源会议名/新建任务 |
| `/tasks/archive` | `tasks/TaskArchiveView.vue` | 任务管理 → 已归档任务 | 已完成任务 | 简单复用 |
| `/knowledge` | `KnowledgeView.vue` | 知识库 → 文档管理 | 上传、检索、文档列表、删除 | 缺分类、分块数、重新索引、卡片视图 |
| `/knowledge/search` | `knowledge/KnowledgeSearchView.vue` | 知识库 → 向量检索测试 | TopK、相似度结果 | 偏调试工具，普通用户入口可合并 |
| `/memory` | `MemoryView.vue` | 系统设置 → 用户记忆中心 | 角色/场景/偏好/默认模板 | 参考图无对应，保留为高级设置 |
| `/settings` | `settings/ModelSettingsView.vue` | 系统设置 → 模型配置 | LLM/Embedding BYOK、用途模型 | 参考图 1 有「模型/导出/权限/账号」，当前只有模型 |

### 3.4 布局与导航

当前 `WorkspaceLayout.vue`：

- **顶栏 56px**：品牌 → 一级导航（6 个模块）→ 账户菜单。
- **左侧栏 232px**：当前模块标题 + 二级导航（带 `hint` 说明），激活项为实心蓝底。
- **主内容**：面包屑 + 路由过渡动画；最大宽度 82rem。
- **响应式**：≤1080px 左栏 208px；≤960px 左栏变顶部横向滚动；≤640px 隐藏品牌文字与用户名。

现状问题：

1. 顶栏没有全局搜索、通知、帮助入口；参考图中的搜索框是明显的效率入口。
2. 左侧二级导航每项都带一行 `hint`，信息量偏大；参考图使用分组标题 + 简洁条目。
3. 系统设置模块的 `routeName` 指向 `/memory`，而「模型配置」在二级导航；面包屑会把记忆中心当作模块首页，语义略绕。
4. 页面级 `PageHeader` 与 `StageShell` 两套头部并存，标题层级不统一。
5. 详情页 7 个 Tab 平铺，缺少「当前进行到哪一步」的进度感。

### 3.5 设计系统现状

全局令牌位于 `assets/main.css`：

| 类别 | 现有值 |
| --- | --- |
| 主色 | `#155eef`，深色 `#0f4bd1`，浅底 `#ebf1ff` |
| 辅助色 | 青绿 `#0d9488`，浅底 `#e6f7f4` |
| 背景 | `#f4f8ff`，带两层径向光晕 |
| 文本 | 前景 `#10203a`，次级 `#5f6f86`，弱化 `#66768d` |
| 描边 | `#e3ebf7` / `#cad9f0` |
| 圆角 | 8 / 10 / 14 / 18 / pill |
| 阴影 | 轻量蓝灰阴影 + 玻璃高光 |
| 间距 | 4 / 8 / 12 / 16 / 24 / 32 / 48 |
| 动效 | 140ms / 200ms / 320ms，支持 `prefers-reduced-motion` |
| 字体 | Inter / Space Grotesk / 中文系统字体 |

共享原语：`.ds-card`、`.ds-card--padded`、`.ds-section-head`、`.ds-title`、`.ds-subtitle`、`.ds-chip`、`.ds-kbd`、`.ds-divider`。

优点：

- 已有统一色彩、圆角、阴影、间距，视觉基础不差。
- 支持键盘焦点、`aria-*`、减少动效。
- 组件普遍有 loading / empty / error / retry 状态。

不足：

- 部分组件内仍有硬编码色值（如 `#155eef`、`#b45309`、`#fef3c7`），未完全走令牌。
- 缺少表格、标签页、统计卡、筛选栏、抽屉、搜索框等「后台页面级」原语。
- 字体依赖 Google Fonts，国内网络可能加载失败；Space Grotesk 对中文无意义。
- 阴影与渐变使用较多，参考图更扁平、更克制；需要在「品牌感」与「企业后台密度」之间收敛。

### 3.6 组件清单（42 个）

| 分组 | 组件 |
| --- | --- |
| 外壳与导航 | `WorkspaceLayout`、`AppBreadcrumb`、`NavIcon`、`PageHeader`、`StageShell`、`ToastHost` |
| 基础原语 | `AppButton`、`AppModal`、`AppPagination`、`AppTag`、`ConfirmDialog`、`EmptyState`、`ErrorMessage`、`FormField`、`FormSelect`、`FormTextarea`、`LoadingSpinner`、`StatusBadge`、`MarkdownView`、`SourceRef`、`RichTextEditor` |
| 会议 | `MeetingList`、`MeetingCard`、`MeetingFormDialog` |
| 资料/记录/音频 | `MaterialSection`、`MaterialList`、`MaterialItem`、`MaterialUploader`、`RecordSection`、`RecordItem`、`AudioSection`、`LocalWorkspacePanel` |
| AI 与产出 | `AgentChat`、`ChatPanel`、`AiAssistantDrawer`、`AiAssistantEntry`、`PreparationSection`、`MinutesSection`、`ActionItemSection`、`IssuesSection`、`PostMeetingChecklist` |
| 知识库 | `KnowledgeUploader` |

### 3.7 状态管理与 API 层

- `auth`：token、当前用户、登录/注册/退出。
- `meetings`：列表、分页、筛选、当前会议、创建。
- `tasks`：列表、分页、筛选、编辑、取消。
- `modelConfig`：读取/保存/恢复默认/用途模型。
- 知识库、纪要、准备稿、记录、音频、问题等使用组件内局部状态 + `useAsyncList`，没有全局缓存。
- `useAsyncList` 统一处理 page/page_size、items、pagination、loading、error、load/loadMore。
- `client.ts` 默认 30s 超时；AI 生成、音频转写、解析/向量化上传使用 `LONG_REQUEST_TIMEOUT_MS = 240_000`。
- 错误统一为 `{ status, error_code, message, retryable, details? }`；前端按 `error_code` 分支。
- 取消：`AgentChat`、纪要生成、行动项/问题提取使用 `AbortController`；取消只中断浏览器请求，后端可能继续完成。

### 3.8 交互现状

- **加载**：`LoadingSpinner` + 骨架屏（仅仪表盘统计卡）。
- **空状态**：`EmptyState`，多数页面有主操作。
- **错误**：`ErrorMessage` + `retryable` 重试。
- **危险操作**：删除会议/材料/记录/知识库、归档、取消任务均二次确认。
- **反馈**：`ToastHost` + `useToast`。
- **AI 对话**：`AgentChat` 支持快捷提示、引用选中文本、复制、重新生成、停止、来源标签；但「流式」是前端逐字动画，不是真实 SSE。
- **AI 入口**：资料预处理页内嵌聊天、录音转写页右侧聊天、会议详情浮动按钮 + 抽屉、纪要页聊天。
- **可访问性**：表单 label、`aria-label`、`role="log"`、`aria-busy`、焦点环、减少动效已具备；表格/标签页语义仍可加强。

### 3.9 测试与质量

- Vitest：`frontend/tests` 覆盖页面与主要组件（仪表盘、会议、材料、记录、音频、纪要、行动项、问题、知识库、设置、Agent 等）。
- Playwright：`core-flow`、`ai-flow`、`audio-flow`、`local-workspace`、`model-settings`、`support`。
- 质量门禁：`npm run typecheck`、`npm run lint`、`npm run test`；E2E 需真实后端与模型/ASR 配置。

### 3.10 现有 UI 问题清单

| 问题 | 影响 | 优先级 |
| --- | --- | --- |
| 页面头部不统一（PageHeader / StageShell / Dashboard hero） | 视觉节奏不一致 | P0 |
| 缺少表格原语，列表多为卡片或 div 网格 | 会议/任务/知识库信息密度低 | P0 |
| 筛选能力弱：会议仅状态，任务仅状态 | 找不到会议/任务 | P1 |
| 会议列表没有「资料/纪要/待办」进度 | 用户不知道下一步做什么 | P1 |
| 状态语义混用（会议状态 vs 处理进度） | 误以为后端支持「进行中/已完成」 | P0 |
| 知识库文档卡片信息少 | 无法判断是否可检索 | P1 |
| 系统设置只有模型配置 | 与参考图的「系统设置」心智不符 | P1 |
| 左侧 hint 过多、分组不清 | 导航扫描成本高 | P0 |
| 字体依赖外网 | 弱网下字体回退，品牌感下降 | P1 |
| 渐变/阴影偏多 | 与参考图的清爽后台感有差距 | P1 |
| 移动端表格直接压缩 | 小屏可读性差 | P1 |
| Agent「流式」是假动画 | 用户可能误解为真实流式 | P0（文案/交互纠正） |

### 3.11 与参考图的差异总表

| 参考图 | 对应现有页面 | 保留 | 需重做/补齐 | 依赖后端 |
| --- | --- | --- | --- | --- |
| 1 系统设置 | `/settings` + `/memory` | BYOK 表单、用途模型 | 标签页、模块绑定表、导出设置、账号设置 | 导出设置、账号、权限、独立测试连接 |
| 2 会前资料预处理 | `/new-meeting/preprocess` | 上传、准备稿、Agent | 三栏/两栏布局、步骤条、底部动作、文件状态卡 | 无（文件状态已有） |
| 3 任务管理 | `/tasks` | 统计卡、任务列表、AI 建议 | 筛选栏、表格列、优先级/负责人/来源会议 | 任务字段、创建接口、筛选参数 |
| 4 知识库 | `/knowledge` | 上传、检索、文档列表 | 卡片网格、分块数、索引状态、分类、检索开关 | 分块统计、reindex、分类、全局开关 |
| 5 会后 AI 处理中心 | `/new-meeting/minutes` | 纪要生成、模板、导出 | 四张处理卡、进度侧栏、底部动作 | 沉淀知识库、流水线状态 |
| 6 会议管理 | `/meetings` | 统计、状态筛选、表格 | 搜索、更多筛选、参会人/资料/纪要/待办列 | keyword、聚合统计、参会人 |
| 7 实时录音转写 | `/new-meeting/asr` | 音频、记录、AI 辅助 | 会议信息栏、转写视图、标记 | 实时 ASR、说话人分离、时间戳 |
| 8 会议工作台 | `/dashboard` | Hero、统计、最近会议、AI 建议、今日待办 | 表格化、快捷动作、真实进度 | 聚合统计、任务来源名 |

---

## 4. 后端接口

### 4.1 基本约定

| 项 | 约定 |
| --- | --- |
| 前缀 | `/api/v1` |
| 格式 | JSON；文件上传 `multipart/form-data` |
| 鉴权 | `Authorization: Bearer <JWT>`；HS256；默认 1440 分钟；无 refresh |
| 登录标识 | 唯一 `name` + `password`，无 email |
| 成功信封 | `{ "status": "success", "data": ... }` |
| 错误信封 | `{ "status": "error", "error_code", "message", "retryable", "details"? }` |
| 分页 | `page` 从 1 开始，`page_size` 默认 20、最大 100；`data.items` + `data.pagination` |
| 时间 | 库内 UTC；接口返回带时区 ISO 8601；日期用 `YYYY-MM-DD` |
| 主键 | 后端生成，带前缀（`usr_` / `mtg_` / `mat_` / `rec_` / `prep_` / `min_` / `act_` / `tsk_` / `iss_` / `aud_` / `kdoc_`） |
| 权限 | 所有资源按当前用户过滤；越权统一 `404 RESOURCE_NOT_FOUND` |
| 健康检查 | `/health`、`/api/v1/health/db` 不使用信封 |

### 4.2 接口清单

> 说明：`api.md` 中标注 `[提案]` 的接口（材料列表、纪要读取/编辑/确认、记录删除、行动项详情/删除）在当前后端代码中**均已实现**；契约仍需团队确认后从提案转正式。以运行期 OpenAPI 为准。

#### 认证与健康

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/register` | 注册，201 返回用户 + token |
| POST | `/auth/login` | 登录，200 返回用户 + token |
| POST | `/auth/logout` | 无状态退出 |
| GET | `/auth/me` | 当前用户 |
| GET | `/health` | 服务探针 |
| GET | `/health/db` | 数据库探针 |

#### 会议

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/meetings` | 列表；`page`、`page_size`、`status` |
| POST | `/meetings` | 创建 |
| GET | `/meetings/{meeting_id}` | 详情 |
| PATCH | `/meetings/{meeting_id}` | 编辑 title/topic/meeting_time |
| DELETE | `/meetings/{meeting_id}` | 删除；存在已转换行动项/任务时 409 |
| POST | `/meetings/{meeting_id}/archive` | 归档，之后只读 |

#### 材料、记录、音频

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/meetings/{meeting_id}/materials` | 上传 PDF/DOCX/TXT；同步解析/索引 |
| GET | `/meetings/{meeting_id}/materials` | 材料分页列表 |
| GET | `/materials/{material_id}` | 材料详情（含 parse_error） |
| DELETE | `/materials/{material_id}` | 删除材料与分块 |
| POST | `/meetings/{meeting_id}/records` | 新增记录 |
| GET | `/meetings/{meeting_id}/records` | 记录分页列表 |
| PATCH | `/records/{record_id}` | 编辑 content/marker_type |
| DELETE | `/records/{record_id}` | 删除；被行动项/问题引用时 409 |
| POST | `/meetings/{meeting_id}/audio` | 上传 MP3/WAV/M4A/WEBM，同步转写 |
| GET | `/meetings/{meeting_id}/audio` | 音频分页列表 |
| GET | `/audio/{audio_id}` | 音频详情 |
| PATCH | `/audio/{audio_id}` | 修改转写文本 |
| POST | `/audio/{audio_id}/retry` | 失败重试 |
| POST | `/audio/{audio_id}/confirm` | 确认并创建 transcript 记录 |
| DELETE | `/audio/{audio_id}` | 删除未确认音频 |

#### AI 应用

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/meetings/{meeting_id}/prepare` | 生成会前准备稿；`include_history`、`user_goal` |
| POST | `/meetings/{meeting_id}/chat` | 会议问答；`context_scope`、`include_sources` |
| POST | `/meetings/{meeting_id}/organize` | 整理记录；`record_ids`、`style`；不落库 |
| POST | `/meetings/{meeting_id}/minutes/generate` | 生成纪要；201；模板/资料/行动项开关 |
| GET | `/meetings/{meeting_id}/minutes` | 纪要分页列表 |
| GET | `/minutes/{minutes_id}` | 纪要详情 |
| PATCH | `/minutes/{minutes_id}` | 编辑正文，version 递增 |
| POST | `/minutes/{minutes_id}/confirm` | 确认纪要 |
| POST | `/meetings/{meeting_id}/action-items/extract` | 提取行动项，候选落库 |
| POST | `/meetings/{meeting_id}/issues/extract` | 提取问题，落库 open |
| POST | `/meetings/{meeting_id}/records` 等 | 记录 CRUD 见上 |

#### 准备稿、行动项、任务、问题

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/meetings/{meeting_id}/preparations` | 准备稿列表 |
| GET | `/preparations/{preparation_id}` | 准备稿详情 |
| PATCH | `/preparations/{preparation_id}` | 编辑 summary/checklist |
| POST | `/preparations/{preparation_id}/confirm` | 确认，幂等 |
| GET | `/meetings/{meeting_id}/action-items` | 行动项列表 |
| GET | `/action-items/{action_id}` | 行动项详情 |
| PATCH | `/action-items/{action_id}` | 编辑 content/assignee/due_date |
| DELETE | `/action-items/{action_id}` | 删除；已转任务 409 |
| POST | `/action-items/{action_id}/confirm` | 确认，幂等 |
| POST | `/action-items/{action_id}/convert-to-task` | 转任务；仅 confirmed；幂等 |
| GET | `/tasks` | 任务列表；`status` |
| GET | `/tasks/{task_id}` | 任务详情 |
| PATCH | `/tasks/{task_id}` | 修改 title/due_date/status |
| POST | `/tasks/{task_id}/cancel` | 取消，幂等 |
| GET | `/meetings/{meeting_id}/issues` | 问题列表 |
| PATCH | `/issues/{issue_id}` | 编辑 description/status/follow_up |

#### 知识库、记忆、模型配置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/knowledge/documents` | 上传文档，解析/分块/索引 |
| GET | `/knowledge/documents` | 文档分页列表 |
| GET | `/knowledge/documents/{document_id}` | 文档详情 |
| DELETE | `/knowledge/documents/{document_id}` | 删除文档、分块、向量 |
| POST | `/knowledge/search` | 语义检索；`query`、`top_k`、`min_score` |
| GET | `/me/memory` | 读取记忆 |
| PUT | `/me/memory` | 保存/替换记忆 |
| DELETE | `/me/memory` | 清除记忆 |
| GET | `/me/settings/model` | 读取模型配置（脱敏） |
| PUT | `/me/settings/model` | 保存并 probe；整体替换提供方 |
| PUT | `/me/settings/model/purposes` | 保存用途模型覆盖 |
| DELETE | `/me/settings/model` | 清除自备配置，回退全局 |

### 4.3 关键数据结构（UI 相关字段）

```ts
// 会议
{ meeting_id, title, topic, meeting_time, status, created_at, updated_at, archived_at }

// 材料
{ material_id, meeting_id, file_name, type, source, processing_status, parse_error, created_at }

// 记录
{ record_id, meeting_id, content, record_type, marker_type, source_material_id, created_at, updated_at }

// 准备稿
{ preparation_id, meeting_id, summary, checklist: string[], status, version, created_at, updated_at }

// 纪要
{ minutes_id, meeting_id, content, status, version, template,
  source_record_ids: string[], source_material_ids: string[], created_at, updated_at }

// 行动项
{ action_id, meeting_id, content, assignee, due_date, status,
  source: { record_id, excerpt }, created_at, updated_at }

// 个人任务
{ task_id, user_id, meeting_id, action_id, title, status, due_date, created_at, updated_at }

// 问题
{ issue_id, meeting_id, description, status, follow_up,
  source: { record_id }, created_at, updated_at }

// 音频
{ audio_id, meeting_id, file_name, type, status, transcript, error, record_id, created_at, updated_at }

// 知识库文档 / 检索命中
{ document_id, file_name, type, processing_status, parse_error, created_at }
{ document_id, file_name, excerpt, score }

// 问答
{ answer, sources: [{ meeting_id, material_id, record_id, document_id, document_name, excerpt }],
  insufficient_evidence }

// 模型配置（读取）
{ llm_api_base, llm_model, llm_api_key_masked, llm_source, llm_purpose_models,
  embedding_api_base, embedding_model, embedding_api_key_masked, embedding_source, embedding_dim }

// 记忆
{ role, work_scenarios, communication_style, preferred_minutes_template, updated_at }
```

### 4.4 列表查询能力边界

| 列表 | 现有参数 | 尚不支持 |
| --- | --- | --- |
| 会议 | `page`、`page_size`、`status` | `keyword`、`start_time`、`end_time`、聚合进度 |
| 材料 | `page`、`page_size` | 类型/状态筛选、搜索 |
| 记录 | `page`、`page_size` | 标记筛选、搜索 |
| 音频 | `page`、`page_size` | 状态筛选、搜索 |
| 准备稿 | `page`、`page_size` | 状态筛选 |
| 纪要 | `page`、`page_size` | 模板/状态筛选 |
| 行动项 | `page`、`page_size` | 状态/负责人筛选 |
| 任务 | `page`、`page_size`、`status` | `keyword`、`due_before`、`due_after`、`meeting_id`、负责人/优先级 |
| 问题 | `page`、`page_size` | 状态筛选 |
| 知识库 | `page`、`page_size` | 类型/状态筛选、搜索、分类 |
| 检索 | `query`、`top_k`、`min_score` | 跨库混合范围 |

### 4.5 实现状态与设计落地结论

- **可以直接做**：外壳与导航、仪表盘、会议详情、准备稿、纪要、行动项、问题、任务状态流转、知识库上传/检索、模型设置、记忆中心、本地工作区。
- **可以前端派生但要注意准确性**：会议「处理进度」、任务「逾期/即将到期」、工作台「AI 建议」。派生只能基于已加载数据；跨分页统计必须后端聚合，否则数字会不准。
- **必须后端新增**：全局搜索、会议关键词/时间筛选、任务来源会议名、任务优先级/负责人/新建、知识库分块数/重新索引/分类、导出设置、账号设置、通知、会后流水线、实时 ASR/说话人分离、会议沉淀知识库。

---

## 5. Agent 能力

### 5.1 定义与边界

OpenMIND 当前的「Agent」不是自主规划、工具调用型的 Agent Runtime，而是：

```text
前端 Agent 交互层（意图识别 + 快捷提示 + 对话 UI）
        ↓
后端 AI 能力层（Prompt + RAG + LLM + 结构化输出）
        ↓
业务 Service（权限、状态、落库、确认）
```

因此：

- Agent **不能**自行创建任务、完成任务、修改会议状态。
- Agent **不能**跨会话记住对话；只有用户显式维护的「记忆中心」会按用途注入 Prompt。
- Agent **不能**保证实时流式；当前是一次性返回，前端做逐字展示。
- Agent 的输出是**草稿/候选**，必须由用户确认或转换。

### 5.2 能力矩阵

| 能力 | 接口 | 输入 | 输出 | 是否落库 | 状态 | 主要 UI |
| --- | --- | --- | --- | --- | --- | --- |
| 会前准备 | `POST /meetings/{id}/prepare` | `include_history`、`user_goal` | `summary`、`checklist` | 是，`draft` | generating/draft/confirmed/failed | 资料预处理、会议详情「会前准备」 |
| 会议问答 | `POST /meetings/{id}/chat` | `question`、`context_scope`、`include_sources` | `answer`、`sources[]`、`insufficient_evidence` | 否 | 一次性 | 资料预处理、录音转写、详情抽屉、ChatPanel |
| 整理记录 | `POST /meetings/{id}/organize` | `record_ids`、`style` | `organized_content`、`source_record_ids` | 否（可另存为记录） | 一次性 | 记录区「AI 整理所选」 |
| 纪要生成 | `POST /meetings/{id}/minutes/generate` | `record_ids`、`include_action_items`、`include_materials`、`template` | `content`、模板、来源快照 | 是，`draft` | draft/confirmed | 纪要生成、会议详情「纪要」 |
| 行动项提取 | `POST /meetings/{id}/action-items/extract` | `record_ids` | `items[]` | 是，`pending_confirmation` | 待确认/已确认/已转任务/已取消 | 会议详情「纪要」下方行动项区 |
| 问题提取 | `POST /meetings/{id}/issues/extract` | `record_ids` | `items[]` | 是，`open` | open/resolved/cancelled | 会议详情「问题」 |
| 音频转写 | `POST /meetings/{id}/audio` | 音频文件 | `transcript`、`status` | 是 | uploaded/processing/transcribed/failed/confirmed | 录音转写、会议详情「音频」 |
| 知识库检索 | `POST /knowledge/search` | `query`、`top_k`、`min_score` | `items[{document_id, file_name, excerpt, score}]` | 否 | 一次性 | 知识库、检索测试页 |
| 纪要导出 | 前端 `buildMinutesDocxBlob` | 纪要 Markdown/HTML | DOCX Blob | 否 | 一次性 | 纪要页、详情纪要区、本地工作区 |

> 「AI 建议」在工作台与任务页是**规则计算**（基于会议数、待办数、逾期数、截止日期），不是模型调用。设计文案应写「基于当前数据」而非暗示 LLM 推理。

### 5.3 调用链与模型路由

```text
AgentChat / 页面按钮
  → src/api/*.ts（240s 超时、AbortSignal）
  → FastAPI 路由（鉴权、归属校验）
  → services/*（业务状态、幂等、落库）
  → ai/*（Prompt、RAG、LLM、结构化校验）
  → PostgreSQL / pgvector / storage
```

- 按用途路由：`preparation` / `chat` / `minutes` / `extraction`，仅覆盖模型名，API 地址与密钥沿用 LLM 配置。
- 未覆盖用途回退 `llm_model`。
- Embedding 独立配置，维度固定 1024。
- 默认要求 BYOK；`ALLOW_GLOBAL_FALLBACK=false` 时未配置用户返回 `MODEL_CONFIG_REQUIRED`。
- 保存模型配置时 probe：Embedding 必须返回 1024 维；LLM 必须能生成。

### 5.4 输入输出示例

**会前准备**

```json
// 请求
{ "include_history": true, "user_goal": "确认本周里程碑和待解决风险" }

// 响应 data
{
  "preparation_id": "prep_xxx",
  "meeting_id": "mtg_xxx",
  "summary": "会议背景摘要……",
  "checklist": ["确认本周里程碑", "询问接口联调风险"],
  "status": "draft",
  "version": 1,
  "created_at": "2026-10-01T09:20:00+08:00",
  "updated_at": "2026-10-01T09:20:00+08:00"
}
```

**会议问答**

```json
// 请求
{ "question": "上次会议决定了什么？", "context_scope": "current_meeting", "include_sources": true }

// 响应 data
{
  "answer": "根据已有会议材料，上次会议决定……",
  "sources": [
    { "meeting_id": "mtg_xxx", "material_id": "mat_xxx", "record_id": null,
      "document_id": null, "document_name": null, "excerpt": "相关原文片段" }
  ],
  "insufficient_evidence": false
}
```

**纪要生成**

```json
// 请求
{ "record_ids": ["rec_xxx"], "include_action_items": true,
  "include_materials": true, "template": "standard" }

// 响应 data（201）
{
  "minutes_id": "min_xxx",
  "meeting_id": "mtg_xxx",
  "content": "会议纪要草稿……",
  "status": "draft",
  "version": 1,
  "template": "standard",
  "source_record_ids": ["rec_xxx"],
  "source_material_ids": ["mat_xxx"],
  "created_at": "2026-10-01T10:00:00+08:00",
  "updated_at": "2026-10-01T10:00:00+08:00"
}
```

### 5.5 执行状态与交互现状

| 维度 | 现状 | 设计含义 |
| --- | --- | --- |
| 调用方式 | 同步 HTTP | 前端必须显示「生成中」，并允许取消 |
| 流式 | 无 SSE/WebSocket | 不要写「实时流式输出」；逐字动画只是展示效果 |
| 进度 | 无百分比/阶段回调 | 不要伪造「检索 30% / 生成 70%」 |
| 取消 | `AbortController` 中断请求 | 文案写「已停止等待」，不要承诺后端已停止 |
| 失败 | 统一错误码 + `retryable` | 按错误码给出重试/去设置/换范围 |
| 会话 | 组件内存，不持久化 | 切页即丢；不要暗示长期记忆 |
| 产出 | 草稿/候选落库 | 必须显示「草稿/待确认」，确认后才成为正式结果 |
| 来源 | 问答返回 sources；纪要记录来源 ID | UI 显示来源 chips / 片段，不伪造引用 |
| 幂等 | 转任务幂等；生成非幂等 | 重复点击生成会产生多条草稿，按钮需防重复提交 |

### 5.6 RAG 与记忆

- 会议问答范围：
  - `current_meeting`：当前会议材料 + 当前会议最近记录（有限条数/长度）。
  - `current_and_history`：当前用户全部会议材料 + 当前会议最近记录。
  - `knowledge_base`：仅个人知识库，不读取会议材料/记录。
- 检索：应用层余弦相似度，`top_k` 默认 5，`min_score` 默认 0.3；低于阈值丢弃。
- 来源不得伪造：`excerpt` 必须来自命中分块或记录原文；无结果时 `insufficient_evidence=true`。
- 记忆按用途注入：
  - 会前准备：角色、工作场景、表达偏好。
  - 纪要：表达偏好、默认模板。
  - 问答：表达偏好。
  - 行动项/问题提取：不使用记忆。

### 5.7 错误码与重试语义

| 错误码 | 典型 HTTP | 含义 | 前端动作 |
| --- | --- | --- | --- |
| `AUTH_REQUIRED` | 401 | 未登录/失效 | 跳登录 |
| `RESOURCE_NOT_FOUND` | 404 | 不存在或越权 | 返回列表/提示 |
| `VALIDATION_ERROR` | 422 | 参数不合法 | 字段级提示 |
| `FILE_TYPE_NOT_SUPPORTED` | 415 | 文件类型不支持 | 说明支持格式 |
| `FILE_TOO_LARGE` | 413 | 超过大小 | 说明 20MB 限制 |
| `FILE_PARSE_FAILED` | 422 | 解析失败 | 显示 `details.reason` |
| `MODEL_TIMEOUT` | 504 | 模型超时 | 可重试 |
| `MODEL_OUTPUT_INVALID` | 502 | 输出无法解析 | 可重试/换模板 |
| `MODEL_CONFIG_INVALID` | 400 | 密钥/维度/配置错误 | 去模型设置 |
| `MODEL_CONFIG_REQUIRED` | 400 | 未配置 BYOK | 去模型设置 |
| `MODEL_QUOTA_EXCEEDED` | 402 | 额度不足 | 提示充值/换 Key |
| `RATE_LIMITED` | 429 | 限流 | 可重试 |
| `BUSINESS_RULE_VIOLATION` | 409 | 当前状态不允许 | 解释规则 |
| `INTERNAL_ERROR` | 500 | 未预期 | 可重试/反馈 |

### 5.8 Agent 体验设计建议

1. **把「流式」改成「生成中」**：真实能力是同步返回；显示计时、取消、重试，比假流式更可信。
2. **运行卡而不是聊天气泡**：对纪要、准备稿、提取这类长任务，使用「任务卡 + 状态 + 来源 + 结果」结构；只有问答保持对话流。
3. **来源可见**：每条回答下方显示来源类型（会议资料/会议记录/知识库）和片段；纪要显示参与记录数与材料数。
4. **范围选择器**：问答输入框上方提供「当前会议 / 历史会议 / 知识库」；默认当前会议，切换时解释影响。
5. **确认门槛**：草稿/候选使用醒目徽标；「转任务」只在 `confirmed` 后可用；批量操作前二次确认。
6. **失败可恢复**：`MODEL_CONFIG_REQUIRED` 直接给「去配置模型」；`MODEL_TIMEOUT` 给「重试」并保留输入。
7. **不承诺记忆**：对话区标注「本次会话临时对话」；长期偏好引导到「记忆中心」。
8. **不要自动执行**：任何「Agent 已为你创建任务/完成纪要」的文案都不符合当前业务约束。

---

## 6. 技术约束

### 6.1 技术栈与版本

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3.5、TypeScript 5.6、Vite 5、Pinia 2、Vue Router 4、Tiptap 3、docx 9、axios 1.7 |
| 后端 | Python 3.11+（验证于 3.13）、FastAPI、Pydantic、SQLAlchemy、Alembic |
| 数据库 | PostgreSQL 16 + pgvector |
| AI | 云端 LLM + Embedding（OpenAI 兼容）；可选 FunASR |
| 文件 | 本地 `storage/` |
| 开发 | Docker Compose |
| 测试 | pytest、Vitest、Playwright、ruff、ESLint、Prettier |

### 6.2 项目结构与边界

```text
OpenMIND/
├── backend/app/
│   ├── api/v1/        # HTTP 路由、依赖注入、响应
│   ├── services/      # 业务规则、状态流转、权限
│   ├── repositories/  # 数据库访问
│   ├── models/        # ORM
│   ├── schemas/       # Pydantic
│   └── ai/            # LLM、Embedding、RAG、Prompt、解析
├── frontend/src/      # 见 3.2
├── docker/            # Compose 与 .env.example
├── docs/              # 契约与设计文档
├── storage/           # 运行时文件（不提交真实资料）
└── scripts/           # 开发/测试/数据库校验
```

边界：

- 前端不直接访问数据库，不持有模型密钥。
- 后端负责身份、权限、持久化、业务状态。
- AI 层只生成候选、检索、整理，不决定任务/状态流转。
- 数据库结构变更必须附 Alembic 迁移。

### 6.3 环境与启动

后端（`backend/`）：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
ruff check .
pytest
alembic upgrade head
```

前端（`frontend/`）：

```bash
npm install
npm run dev          # http://localhost:5173
npm run typecheck
npm run lint
npm run test
npm run build
npm run test:e2e     # 需真实后端 + 模型/ASR 配置
```

Docker：

```bash
docker compose -f docker/compose.dev.yml up --build
```

- 前端 5173（strictPort），后端 8000，数据库 5432。
- Vite `/api` 代理到 `http://localhost:8000`。
- OpenAPI：`http://localhost:8000/docs`。

### 6.4 环境变量与安全

关键变量：

- `SECRET_KEY`：非开发环境至少 32 字符；轮换用 `SECRET_KEY_PREVIOUS`。
- `ACCESS_TOKEN_EXPIRE_MINUTES`：默认 1440。
- `DATABASE_URL`、`POSTGRES_*`。
- `STORAGE_DIR`、`MAX_UPLOAD_MB`（默认 20）。
- `LLM_*` / `EMBEDDING_*`：服务端全局配置。
- `ALLOW_GLOBAL_FALLBACK`：默认 `false`。
- `ALLOW_PRIVATE_MODEL_ENDPOINTS`：默认 `false`，仅自建本地模型开启。
- `ASR_API_BASE` / `ASR_API_KEY` / `ASR_MODEL`。
- `CORS_ORIGINS`。
- 前端：`VITE_API_BASE_URL`、`VITE_DEV_PROXY_TARGET`。

安全约束：

- 模型密钥 Fernet 加密存库，接口只返回 `_masked`。
- 来源为 `global` / `none` 时 `_masked` 为空。
- `api_base` 默认只允许 HTTPS 公网，拒绝本机/私有 IP/URL 内嵌凭证。
- 任何接口不得返回明文密钥、堆栈、SQL、Prompt。
- 本地目录只通过浏览器 File System Access API 授权，后端不读用户绝对路径。

### 6.5 前端实现约束

1. **不要引入 UI 框架**（Element Plus / Ant Design / Tailwind）除非团队明确决策；当前视觉依赖手写组件与 CSS 令牌，混入框架会破坏一致性并增大包体。
2. **复用现有组件与令牌**：新增页面级原语放入 `components/`，样式优先引用 `main.css` 变量，避免硬编码色值。
3. **路由名与路径唯一来源**：`constants/routeNames.ts`；导航结构唯一来源 `constants/navigation.ts`。新增页面必须同步两处。
4. **API 契约唯一来源**：`api.md`；前端类型放 `types/`，请求封装放 `api/`。
5. **错误按 `error_code` 分支**，不依赖 `message` 文案。
6. **长耗时请求**使用 `LONG_REQUEST_TIMEOUT_MS`，并提供取消/重试。
7. **不要伪造后端能力**：无接口的按钮要么隐藏、要么标注「规划中」、要么降级为真实可用的替代动作。
8. **保留测试可用性**：现有 Playwright 依赖角色名、标签文本、`#id`（如 `#knowledge-file`、`#memory-role`、`#knowledge-query`）；重构时尽量保留可访问名称与关键 ID。
9. **浏览器支持**：本地工作区仅 Chromium；其他浏览器显示明确提示，不影响其他功能。
10. **中文优先**：界面文案中文；日期/数字用 `zh-CN` 格式；不要直接复制参考图中的 AI 占位文案。

### 6.6 质量门禁

提交前必须通过：

```bash
# 后端
cd backend && ruff check . && pytest

# 前端
cd frontend && npm run typecheck && npm run lint && npm run test
```

E2E 在具备模型/ASR 配置时执行；验收报告需区分真实服务、Mock 与未执行项。

---

## 7. 基于参考图的设计优化方案

### 7.1 总体视觉方向

**目标**：保留 OpenMIND 现有蓝绿品牌，收敛为「清爽、可信、有进度感」的个人 AI 工作台。

| 维度 | 建议 |
| --- | --- |
| 背景 | 保留极浅蓝底与顶部弱光晕；页面主体更多留白，减少大面积渐变 |
| 主色 | 继续使用 `#155eef`；主按钮、激活导航、关键数字使用主色 |
| 辅助色 | 青绿用于「已完成/健康」；琥珀用于「待确认/风险」；红色仅用于失败/逾期/删除 |
| 卡片 | 12–16px 圆角、1px 边框、轻阴影；不要每张卡都发光 |
| 表格 | 表头浅灰蓝、行高 44–52px、hover 浅蓝；移动端转卡片 |
| 字体 | 中文优先：`Inter, "PingFang SC", "Microsoft YaHei", system-ui`；Space Grotesk 仅用于数字/英文品牌字 |
| 图标 | 扩展 `NavIcon` 到 30+ 个；统一 1.5–1.7px 线宽 |
| 密度 | 企业后台密度：页面标题 24–28px，区块标题 16px，正文 13–14px |
| 动效 | 仅用于页面切换、卡片入场、状态变化；不超过 200ms |

### 7.2 信息架构与导航

参考图采用「顶栏一级导航 + 左侧分组二级导航」，与当前结构一致，建议：

1. **顶栏**：
   - 品牌 `OpenMIND` + 「AI 会议助理」标签。
   - 一级导航：主页、新建会议、会议管理、任务管理、知识库、系统设置。
   - 右侧：搜索（P1，先做禁用/页面内搜索）、帮助、账户菜单。
   - 通知中心在无接口前不放红点。
2. **左侧栏**：
   - 使用分组标题（如「会议」「任务」「知识」「系统」），减少每项 `hint`。
   - 激活项实心蓝底 + 白字；hover 浅蓝。
   - 支持折叠分组（P1），默认展开当前模块。
3. **系统设置**：
   - 左侧二级：模型配置、记忆中心、导出设置（P1）、账号设置（P1）、模块权限（P2）。
   - 当前 `/memory` 与 `/settings` 都是独立页面，可合并为「系统设置」下的标签页或子路由，保留旧路由重定向。
4. **页面头部**：
   - 统一为「标题 + 一句话说明 + 右侧主操作 + 可选步骤条」。
   - `StageShell` 的三步条保留，但视觉上移到标题下方，作为会议主线。

### 7.3 页面级方案

#### 7.3.1 会议工作台（参考图 8）

**参考要点**：顶部四个快捷动作、最近会议表、右侧 AI 建议、底部今日待办。

**保留**：Hero 标题、统计卡、最近会议、AI 建议、今日待办。

**改造**：

- 快捷动作从「阶段入口」改为「任务动作」：
  - 新建会议（打开弹窗）。
  - 上传音频（先选会议 → 跳转录音转写）。
  - 上传资料（先选会议 → 跳转资料预处理）。
  - 查看纪要（跳转会议管理/纪要列表）。
- 最近会议改为表格：会议名称、时间、状态、处理进度、操作。
  - 处理进度 = 资料/记录/纪要/行动项四段的派生进度；需 P1 聚合接口，短期只显示「资料已就绪 / 已有纪要」等布尔标签。
- AI 建议卡片：文案改为「基于当前数据」，列出可点击的真实待办；不要显示未实现的「检测到 3 份未处理资料」除非能准确计算。
- 今日待办：保留，增加「逾期」「今天」「本周」分组；点击进入任务页对应筛选。

**依赖**：会议聚合统计（P1）、任务来源会议名（P1）；无后端时用现有列表统计。

#### 7.3.2 会议管理（参考图 6）

**参考要点**：搜索框、状态/时间/纪要筛选 chips、会议表、参会人、资料状态、纪要状态、待办数量。

**保留**：统计卡、状态 chips、表格、分页、新建会议。

**改造**：

- 顶部工具栏：搜索框（P1 后端 `keyword`）+ 筛选 chips（全部/本周/已生成纪要/待处理）+ 新建会议。
- 表格列：会议名称（含主题）、时间、状态、处理进度、操作。
  - 「参会人」当前无字段，暂不展示；如需展示，先放 `topic` 或新增字段。
  - 「资料状态/纪要状态/待办数量」需要聚合接口；短期用「材料数/记录数/纪要数」派生，且只对当前页准确。
- 行操作：查看详情、资料预处理、录音转写、纪要生成；用主次按钮区分，避免一行 4 个蓝链接。
- 空状态：区分「没有会议」与「筛选无结果」。

**依赖**：`keyword`、`start_time`/`end_time`、聚合统计、参会人字段（P1/P2）。

#### 7.3.3 任务管理（参考图 3）

**参考要点**：四张统计卡、四组筛选、任务表（来源会议/负责人/截止/优先级/状态/操作）、AI 任务建议。

**保留**：统计卡、任务列表、状态流转、AI 建议。

**改造**：

- 统计卡：全部/待办/进行中/已完成；数值来自现有 `listTasks` 分页 total。
- 筛选栏：来源会议、负责人、状态、截止时间。
  - 当前只支持状态；来源会议/负责人/截止范围需后端参数。
  - 短期可做「状态 + 截止时间预设」但必须只对已加载页生效，或在 UI 标注「当前页」。
- 表格列：任务内容、来源会议、负责人、截止时间、优先级、状态、操作。
  - 负责人/优先级无字段，**不要显示假值**；可先隐藏，待迁移后开放。
  - 来源会议：用 `meeting_id` 批量换标题（P1 后端返回 `meeting_title` 更稳）。
- 行操作：编辑、标记完成（`PATCH status=completed`）、取消；不要放「删除」除非后端支持。
- 「新建任务」：当前只能从行动项转换；按钮改为「从行动项转入」，跳转会议详情纪要区。
- AI 建议：保留规则计算；增加「查看建议」跳转到逾期/即将到期筛选。

**依赖**：任务创建/删除、assignee、priority、meeting_title、due 范围筛选（P1/P2）。

#### 7.3.4 知识库（参考图 4）

**参考要点**：上传文档/新建分类/搜索、文档卡片（分块数/索引状态/操作）、知识来源侧栏、问答检索开关。

**保留**：上传、语义检索、文档列表、删除。

**改造**：

- 顶部工具栏：上传文档、新建分类（P2）、搜索文档（P1）。
- 文档展示：卡片网格（桌面 3–4 列，移动 1 列），字段：
  - 文件名、类型、创建时间。
  - 处理状态（已上传/解析中/已索引/失败）。
  - 分块数（P1）、是否可检索（由 `processed` 派生）。
  - 操作：查看详情（P1 分块列表）、重新索引（P1）、删除。
- 右侧「知识来源」：当前无来源聚合；可先展示最近上传的文档或隐藏。
- 「启用检索」：不要做全局开关；改为「在会议问答中使用知识库」说明 + 跳转问答范围选择器；如要做偏好，存 `localStorage` 并明确仅本机。
- 检索测试页 `/knowledge/search` 保留为高级工具，普通用户从知识库顶部搜索即可。

**依赖**：`chunk_count`、`indexed`、reindex、分类、文档搜索（P1/P2）。

#### 7.3.5 系统设置（参考图 1）

**参考要点**：模型配置/导出设置标签页、表单网格、业务模块绑定表、保存/恢复默认。

**保留**：LLM/Embedding 两张配置卡、用途模型、保存/恢复默认。

**改造**：

- 顶部标签页：模型配置、导出设置、账号设置（P1）、模块权限（P2）。
- 模型配置：
  - 表单两列：API 地址、模型名、密钥（password）、上下文窗口（当前无字段，隐藏）。
  - Temperature：当前后端不支持，隐藏或标注「规划中」。
  - 用途模型：会前准备/会议问答/纪要生成/行动项与问题提取。
  - 业务模块绑定表：用用途模型映射「资料预处理/录音转写/纪要生成/知识库检索」，状态显示「已配置/继承默认/未配置」。
  - 「测试连接」：改为「保存并测试」；保存时 probe 已实现，无需独立接口。
- 导出设置：当前只有 DOCX 前端导出；可做本地偏好（默认模板、是否包含来源），需持久化再建接口。
- 账号设置：展示用户名、注册时间、退出；改密/头像需 P2。
- 保存/恢复默认：保留确认弹窗；恢复默认会清除 BYOK，文案明确。

**依赖**：导出设置、账号、权限、独立探测（P1/P2）。

#### 7.3.6 会前资料预处理（参考图 2）

**参考要点**：三步条、左侧上传资料 + 文件状态、右侧 AI 会议助手、底部保存/跳转。

**保留**：资料上传、解析状态、准备稿、Agent 对话、确认。

**改造**：

- 布局：桌面 `320px 上传栏 + 自适应聊天区`；参考图为「左上传、右聊天」，当前 `PreprocessView` 是「左产出、右聊天」，需调整 DOM 顺序。
- 顶部步骤条：资料预处理（当前）→ 录音转写 → 纪要生成；使用 `StageShell` 现有步骤，但视觉加粗当前步骤。
- 左侧：
  - 拖拽上传区（PDF/DOCX/TXT）。
  - 文件列表：图标、文件名、状态（已解析/解析中/失败）、删除。
  - Agent 能力说明/最近准备稿摘要。
- 右侧：
  - Agent 欢迎语 + 快捷提示（提炼议题、生成议程、准备清单、生成准备稿）。
  - 对话消息：Markdown、来源 chips、生成中、停止、重试。
  - 输入框 + 「上传文件」「生成建议」「保存预处理结果」。
- 底部动作：
  - 保存结果 → 确认准备稿（`POST /preparations/{id}/confirm`）。
  - 跳转录音转写 → `/new-meeting/asr?meetingId=...`。
- 不要显示参考图中的「已切片/已向量化」双状态，除非后端返回分块/索引信息；当前只显示 `processing_status`。

**依赖**：无（现有接口足够）；分块数展示需 P1。

#### 7.3.7 录音转写（参考图 7）

**参考要点**：左侧会议信息、中间实时录音与转写、右侧 AI 助手与实时摘要。

**保留**：音频上传、转写修订、确认转记录、记录标记、AI 问答。

**改造**：

- **明确降级**：把「开始实时录音」改为「上传音频并转写」；不做麦克风采集、不做实时流。
- 三栏布局：
  - 左：会议信息（名称、时间、状态、资料数、记录数）+ 转写设置（只读说明）。
  - 中：音频上传卡、音频列表、转写文本编辑器（保存修订/重新转写/确认生成记录）。
  - 右：AI 助手（基于当前会议问答）、快捷提示、来源。
- 说话人区分/重点标记开关：**不要显示**；当前无说话人字段，标记作用于「记录」而非逐句转写。
- 转写视图：当前是纯文本 textarea；可增加「按段落」展示，但不要伪造时间戳/说话人。
- 底部动作：保存转写（已有）、导出 TXT（可前端新增，成本低）、跳转纪要生成（已有）。
- 实时摘要/待办提取/问题追踪：不要放在转写页作为实时面板；改为「生成纪要」「提取行动项」「提取问题」按钮，跳转对应流程。

**依赖**：实时 ASR、说话人分离、时间戳（P2/范围外）。

#### 7.3.8 会后 AI 处理中心（参考图 5）

**参考要点**：Agent 已完成分析、四张处理卡（纪要/待办/风险决议/知识沉淀）、右侧处理进度、底部补充要求与动作。

**保留**：纪要生成、模板、编辑/确认/导出、行动项提取、问题提取。

**改造**：

- 四张处理卡映射真实能力：
  1. 生成会议纪要 → `POST /minutes/generate`。
  2. 提取待办任务 → `POST /action-items/extract`，确认后转任务。
  3. 确认风险与决议 → 从记录标记（decision/question）与问题提取派生；没有独立「风险」实体，文案改为「确认决议与待确认事项」。
  4. 沉淀到知识库 → **当前无接口**，标注「规划中」或隐藏。
- 右侧处理进度：用已有数据派生：
  - 纪要草稿：有无 `draft`。
  - 待办提取：行动项数量/待确认数量。
  - 任务同步：已转任务数量。
  - 知识沉淀：无接口 → 不显示或标「未开始」。
  - 不要显示百分比进度条，除非后端提供任务状态。
- 底部输入：补充要求（作为生成 Prompt 的 `user_goal` 或模板说明）；上传附件（材料上传）；生成纪要；同步任务（客户端批量转换 confirmed 行动项）；导出结果（DOCX）。
- 同步任务要逐条调用 `convert-to-task`，失败要显示部分成功，不要假装全部成功。

**依赖**：会议→知识库沉淀、流水线状态（P2）；其余可现有接口实现。

### 7.4 组件与设计系统增量

| 新组件 | 用途 | 优先级 |
| --- | --- | --- |
| `AppTable` | 会议/任务/知识库统一表格；支持 sticky header、hover、空状态、移动卡片降级 | P0 |
| `AppTabs` | 系统设置、会议详情、知识库视图切换 | P0 |
| `AppStatCard` | 工作台/任务/会议统计卡，统一图标、数值、提示 | P0 |
| `AppFilterBar` | 搜索 + 下拉 + chips + 右侧主操作 | P0 |
| `AppSearchInput` | 顶栏/列表搜索，支持清空、快捷键 | P1 |
| `AppDrawer` | 会议详情 AI 助手、移动端筛选 | P1 |
| `AgentRunCard` | 长任务运行卡：状态、计时、取消、重试、来源、结果 | P1 |
| `StepRail` | 会前/会中/会后步骤条 | P1 |
| `DocumentCard` | 知识库文档卡片 | P1 |
| `ProgressRing/Bar` | 会议处理进度 | P1 |
| `AppTooltip` | 解释不可用能力/字段 | P1 |
| `AppSkeleton` | 列表/表格骨架屏 | P1 |

设计令牌补充：

```css
--color-info: #155eef;
--color-success: #0f766e;
--color-warning: #b45309;
--color-danger: #dc2626;
--color-surface-hover: #f2f7ff;
--color-table-head: #f6f9ff;
--shadow-card: 0 1px 2px rgba(16, 32, 58, 0.04), 0 8px 24px rgba(35, 76, 160, 0.06);
--radius-card: 14px;
--radius-control: 10px;
```

### 7.5 交互与状态规范

1. **加载**：列表首屏用 skeleton；按钮内 loading；长任务显示计时与取消。
2. **空状态**：说明「为什么空」+ 一个主操作；筛选无结果提供「清除筛选」。
3. **错误**：显示可读文案 + 错误码（可折叠）+ 重试；`MODEL_CONFIG_REQUIRED` 直接给设置入口。
4. **确认**：删除、归档、恢复默认、转任务、批量同步必须二次确认；确认文案说明后果。
5. **防重复**：生成/提取/转任务按钮在请求中禁用；避免重复草稿/重复候选。
6. **来源**：问答来源 chips 可展开片段；纪要显示参与记录/材料数量；任务显示来源会议。
7. **状态一致性**：同一状态全站同一颜色/文案；不要用「已完成」表示会议状态。
8. **键盘**：`Cmd/Ctrl+K` 搜索（P1）；`Esc` 关闭弹窗/抽屉；表单 Enter 提交，Shift+Enter 换行。
9. **可访问性**：表格 `scope`、Tabs `role=tablist`/`aria-selected`、抽屉焦点陷阱、图标按钮 `aria-label`、对比度 ≥ 4.5:1。
10. **响应式**：≤960px 左栏横向滚动；≤720px 表格转卡片；≤640px 主操作全宽；触控目标 ≥ 44px。

### 7.6 后端配套需求清单

#### P0（前端可独立完成）

- 统一外壳、设计令牌、表格/标签页/统计卡/筛选栏。
- 工作台、会议管理、任务、知识库、设置页的视觉重排。
- 会议详情处理进度派生（仅当前会议，数据量可控）。
- 纪要 DOCX 导出、转写 TXT 导出（前端）。
- Agent 运行卡、来源展示、确认门槛、错误恢复。
- 页面内搜索（仅当前已加载列表，明确标注）。

#### P1（小后端改动，建议优先）

1. 会议列表：`keyword`、`start_time`、`end_time`。
2. 会议聚合：`material_count`、`record_count`、`minutes_count`、`pending_action_count`、`issue_count`，可放在列表项或 `/meetings/{id}/summary`。
3. 任务：`meeting_title`、`keyword`、`due_before`、`due_after`、`meeting_id` 筛选；`POST /tasks`（手动任务）与 `DELETE` 需产品确认（当前业务要求任务必须来自行动项）。
4. 知识库：文档 `chunk_count`、`indexed`；`POST /knowledge/documents/{id}/reindex`；文档搜索。
5. 导出设置：`GET/PUT /me/settings/export`（默认模板、是否含来源、文件命名）。
6. 账号设置：`GET /me` 已够只读；改密/显示名需新接口。
7. 会议详情聚合：一次返回材料/记录/纪要/行动项/问题计数，减少 N+1。

#### P2（较大能力）

- 通知中心与未读状态。
- 全局搜索（跨会议/任务/知识库）。
- 知识库分类/目录、来源聚合。
- 会议沉淀知识库。
- 会后处理流水线（异步任务、阶段状态、失败补偿）。
- SSE/流式输出、聊天历史持久化。
- 实时 ASR、说话人分离、逐句时间戳。
- 组织/角色权限、共享空间。

### 7.7 实施路线

| 阶段 | 范围 | 不改后端 | 验收 |
| --- | --- | --- | --- |
| Phase 0 | 设计令牌、外壳、`AppTable`/`AppTabs`/`AppStatCard`/`AppFilterBar`、页面头部统一 | 是 | 全站视觉一致；现有测试通过 |
| Phase 1 | 工作台、会议管理、任务、知识库、设置页重排 | 是 | 信息层级接近参考图；无假功能；响应式可用 |
| Phase 2 | 资料预处理、录音转写、会后处理中心；Agent 运行卡/来源/确认/取消 | 是 | 闭环可用；长任务状态清晰；来源可追溯 |
| Phase 3 | 搜索、聚合、任务来源名、知识库元数据/reindex、导出设置 | 部分 | 列表筛选准确；数字不跨页失真 |
| Phase 4 | 通知、分类、沉淀知识库、流水线、SSE、实时 ASR | 否 | 单独立项与验收 |

### 7.8 验收清单

- [ ] 8 个参考页均有对应真实页面或明确降级，不存在「点了没反应」的按钮。
- [ ] 会议/任务/知识库列表有搜索或明确说明筛选范围。
- [ ] 所有 AI 产出显示草稿/候选/已确认状态，确认前不能转任务。
- [ ] 问答来源可展开，无来源时明确「证据不足」。
- [ ] 长任务显示生成中、可取消、失败可重试；不伪造进度。
- [ ] 会议状态只显示 `scheduled`/`archived`；处理进度单独标识。
- [ ] 任务页不显示后端不存在的负责人/优先级/新建任务。
- [ ] 知识库不显示后端不存在的分块数/分类/全局检索开关，除非已实现。
- [ ] 录音转写页不宣称实时录音/说话人分离。
- [ ] 设置页密钥只显示脱敏；恢复默认有确认。
- [ ] 桌面/平板/手机三档布局可用；表格有小屏降级。
- [ ] 键盘可达、焦点可见、图标按钮有 `aria-label`。
- [ ] `npm run typecheck`、`npm run lint`、`npm run test` 通过；后端 `ruff`、`pytest` 通过。
- [ ] 未提交用户已有改动；新增文件与文档路径清晰。

### 7.9 风险与取舍

| 风险 | 说明 | 应对 |
| --- | --- | --- |
| 照搬参考图导致假功能 | 图中大量能力后端没有 | 每个模块标注「真实/派生/规划中」 |
| 引入 UI 框架破坏一致性 | 现有手写组件与令牌已成型 | 不引入；扩展自有原语 |
| 跨页统计不准 | 前端只能拿到当前页 | 用聚合接口；否则只显示当前页/布尔状态 |
| N+1 请求 | 会议列表逐行取材料/纪要 | P1 聚合；短期限制在当前页 |
| 长任务体验差 | 同步 AI 可能 1–3 分钟 | 计时、取消、重试、禁止重复提交 |
| 字体加载失败 | Google Fonts 国内不稳定 | 自托管或系统字体优先 |
| 未提交改动冲突 | 工作区有大量前端修改 | 新建设计文档与组件，不覆盖现有文件 |
| 测试选择器失效 | E2E 依赖文本/ID | 重构保留可访问名称与关键 ID |

---

## 8. 附录

### 8.1 参考图与页面映射

| 图 | 主题 | 现有页面 | 设计结论 |
| --- | --- | --- | --- |
| 1 | 系统设置 | `/settings`、`/memory` | 保留表单，补标签页/绑定表/导出设置 |
| 2 | 会前资料预处理 | `/new-meeting/preprocess` | 调整左右栏，补步骤条与底部动作 |
| 3 | 任务管理 | `/tasks` | 补表格/筛选；隐藏无字段列 |
| 4 | 知识库 | `/knowledge` | 卡片化；补元数据与检索说明 |
| 5 | 会后 AI 处理中心 | `/new-meeting/minutes` | 四卡映射真实能力；进度派生 |
| 6 | 会议管理 | `/meetings` | 补搜索/筛选/进度列 |
| 7 | 实时录音转写 | `/new-meeting/asr` | 降级为上传音频转写；三栏重排 |
| 8 | 会议工作台 | `/dashboard` | 表格化最近会议；真实快捷动作 |

### 8.2 术语

| 术语 | 含义 |
| --- | --- |
| 准备稿 | 会前摘要 + 准备清单，`preparations` |
| 纪要 | 会议纪要草稿/确认稿，`meeting_minutes` |
| 行动项 | 从记录提取的候选待办，`action_items` |
| 个人任务 | 由已确认行动项转换的任务，`personal_tasks` |
| 未解决问题 | 从记录提取的待跟进问题，`open_issues` |
| 记忆 | 用户显式维护的角色/场景/表达偏好/默认模板 |
| 知识库 | 用户个人文档库，独立于会议材料 |
| BYOK | 用户自备模型 API Key |
| 用途模型 | `preparation` / `chat` / `minutes` / `extraction` 的模型名覆盖 |

### 8.3 依据文件

- `AGENTS.md`
- `docs/requirements.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/database.md`
- `docs/ai-design.md`
- `docs/design-baseline.md`
- `docs/module-development-spec.md`
- `frontend/src/router/index.ts`
- `frontend/src/constants/navigation.ts`
- `frontend/src/layouts/WorkspaceLayout.vue`
- `frontend/src/assets/main.css`
- `frontend/src/components/*`
- `frontend/src/views/*`
- `backend/app/api/v1/*`
- `backend/app/services/*`
- `backend/app/ai/*`
- `backend/app/schemas/*`

### 8.4 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-10-27 | 建立前端设计现状与优化基线：六维调研、参考图映射、P0–P2 路线与验收清单 |
