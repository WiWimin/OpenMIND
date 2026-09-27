# API 契约

本文件是前端、后端与 AI 模块的共同接口基线。正式编码前的接口以本文件为准，运行期以 FastAPI 自动生成的 OpenAPI 文档为准。

## 一、统一约定

| 项目 | 约定 |
| --- | --- |
| API 前缀 | `/api`，统一版本化 `/api/v1` |
| 数据格式 | JSON；文件上传 `multipart/form-data` |
| 身份认证 | 后端统一认证机制（当前用户由认证上下文确定） |
| 时间格式 | ISO 8601，统一时区策略 |
| ID | 由后端生成，前端不生成业务主键 |
| 错误响应 | 统一包含 `status`、`error_code`、`message`（可选 `retryable`） |
| 分页 | 列表接口统一使用分页参数与分页响应结构 |

### 成功响应示例

```json
{
  "status": "success",
  "data": { "id": "example_001" }
}
```

### 错误响应示例

```json
{
  "status": "error",
  "error_code": "MODEL_TIMEOUT",
  "message": "AI 服务暂时无法响应，请稍后重试。",
  "retryable": true
}
```

### 错误码

| 错误码 | 含义 |
| --- | --- |
| `AUTH_REQUIRED` | 用户未认证 |
| `PERMISSION_DENIED` | 无权访问该资源 |
| `RESOURCE_NOT_FOUND` | 资源不存在 |
| `VALIDATION_ERROR` | 请求字段校验失败 |
| `FILE_TYPE_NOT_SUPPORTED` | 文件格式不支持 |
| `FILE_PARSE_FAILED` | 文件解析失败 |
| `MODEL_TIMEOUT` | 模型调用超时 |
| `MODEL_OUTPUT_INVALID` | 模型输出不符合预期结构 |
| `BUSINESS_RULE_VIOLATION` | 业务规则不允许当前操作 |
| `INTERNAL_ERROR` | 未预期的服务端错误 |

## 二、用户认证（M01，A）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 用户登录 |
| POST | `/api/v1/auth/logout` | 用户退出 |
| GET | `/api/v1/auth/me` | 获取当前用户 |

## 三、会议管理（M02，A）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meetings` | 查询个人会议列表 |
| POST | `/api/v1/meetings` | 创建会议 |
| GET | `/api/v1/meetings/{meeting_id}` | 查询会议详情 |
| PATCH | `/api/v1/meetings/{meeting_id}` | 编辑会议 |
| DELETE | `/api/v1/meetings/{meeting_id}` | 删除会议及关联数据 |
| POST | `/api/v1/meetings/{meeting_id}/archive` | 归档会议 |

创建会议请求示例：

```json
{
  "title": "项目需求讨论会",
  "topic": "讨论项目范围和下一阶段工作",
  "meeting_time": "2026-10-01T14:00:00+08:00"
}
```

## 四、会议资料与会议记录（M03、M06，A、B）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/materials` | 上传会议材料 |
| GET | `/api/v1/materials/{material_id}` | 查看材料及处理状态 |
| DELETE | `/api/v1/materials/{material_id}` | 删除资料及关联索引 |
| POST | `/api/v1/meetings/{meeting_id}/records` | 新增会议记录或标记 |
| GET | `/api/v1/meetings/{meeting_id}/records` | 查询会议记录 |
| PATCH | `/api/v1/records/{record_id}` | 编辑会议记录 |
| POST | `/api/v1/materials/{material_id}/transcribe` | 发起音频转写（扩展） |

## 五、AI 应用（M04、M05、M06、M07，B）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/meetings/{meeting_id}/prepare` | 生成会前摘要和准备清单 |
| GET | `/api/v1/meetings/{meeting_id}/preparations` | 查询会前准备历史 |
| GET | `/api/v1/preparations/{preparation_id}` | 查看准备结果 |
| PATCH | `/api/v1/preparations/{preparation_id}` | 编辑和确认准备结果 |
| POST | `/api/v1/meetings/{meeting_id}/chat` | 会议相关问答与 RAG 检索 |
| POST | `/api/v1/meetings/{meeting_id}/organize` | 整理用户标记的个人信息 |
| POST | `/api/v1/meetings/{meeting_id}/minutes/generate` | 生成或更新会议纪要 |
| POST | `/api/v1/meetings/{meeting_id}/action-items/extract` | 提取候选行动项 |
| POST | `/api/v1/meetings/{meeting_id}/issues/extract` | 整理未解决问题 |

AI 问答请求示例：

```json
{
  "question": "上次会议确定了哪些需要我完成的事项？",
  "context_scope": "current_and_history",
  "include_sources": true
}
```

AI 问答响应示例：

```json
{
  "status": "success",
  "answer": "根据已导入的历史会议资料，存在以下待办事项……",
  "sources": [
    {
      "meeting_id": "meeting_001",
      "material_id": "material_001",
      "excerpt": "相关会议记录片段"
    }
  ],
  "insufficient_evidence": false
}
```

> `context_scope` 仅表示期望检索范围，实际范围必须由后端结合当前用户权限校验，不能由前端参数直接决定数据访问权限。

## 六、行动项与个人任务（M07、M08，A）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meetings/{meeting_id}/action-items` | 查询会议行动项 |
| PATCH | `/api/v1/action-items/{action_id}` | 编辑行动项 |
| POST | `/api/v1/action-items/{action_id}/confirm` | 确认行动项 |
| POST | `/api/v1/action-items/{action_id}/convert-to-task` | 转为个人任务 |
| GET | `/api/v1/tasks` | 查询个人任务清单 |
| GET | `/api/v1/tasks/{task_id}` | 查询任务详情 |
| PATCH | `/api/v1/tasks/{task_id}` | 修改任务信息和状态 |
| POST | `/api/v1/tasks/{task_id}/cancel` | 取消或撤销任务 |

行动项转任务请求示例：

```json
{
  "title": "整理本周项目进度并提交报告",
  "due_date": null
}
```

> 个人任务响应应包含 `task_id`、`meeting_id`、`action_id`、`title`、`status`、`due_date`，以保证任务可追溯至原始会议。

## 七、未解决问题（M09，A）

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/v1/meetings/{meeting_id}/issues` | 查询会议未解决问题 |
| PATCH | `/api/v1/issues/{issue_id}` | 修改问题状态和后续信息 |

## 八、接口联调顺序

| 批次 | 接口范围 | 参与成员 |
| --- | --- | --- |
| 第一批 | 认证、健康检查、会议 CRUD | A、C |
| 第二批 | 材料上传、材料状态、记录 CRUD | A、B、C |
| 第三批 | 模型调用、RAG、会前准备 | A、B、C |
| 第四批 | 会议问答、纪要生成、行动项提取 | A、B、C |
| 第五批 | 行动项确认、任务 CRUD、问题管理 | A、B、C |
| 第六批 | 异常、权限、部署和端到端测试 | 全员 |
