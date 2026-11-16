import type { AgentIntentName, AgentQuickAction, AgentScene, QuickTask } from '@/types/agent'

/**
 * 快捷功能注册表（单一事实来源）
 *
 * 设计约束（`docs/agent-framework.md 10.2`）：
 * - 每个动作声明 `intent` / `mode` / `outputKind` / `grounding`，页面不再硬编码提示词；
 * - 简单文本动作走 `quickTask`（单次 LLM，无检索/无落库/无确认门）；
 * - 结构化只读动作走 `pipeline`（如会前速览 `brief`）；
 * - 有副作用/确认门/多步的动作才走 `workflow`（纪要、待办、转写）。
 *
 * `rationale` / `sourceUrls` / `lastReviewed` 用于季度复核：
 * 说明「为什么提供这个动作」以及「依据哪个公开实践」，避免拍脑袋加功能。
 */

export type QuickActionOutputKind =
  | 'text'
  | 'brief_card'
  | 'summary_card'
  | 'polish_diff'
  | 'minutes'
  | 'checklist'
  | 'file'

export type QuickActionGrounding = 'materials_only' | 'materials_then_web' | 'web_first'

export interface QuickActionSpec extends AgentQuickAction {
  key: string
  scene: AgentScene
  outputKind: QuickActionOutputKind
  grounding: QuickActionGrounding
  rationale: string
  sourceUrls: string[]
  lastReviewed: string
  /** 仅用于快捷气泡/卡片装饰，不参与执行契约 */
  icon?: string
  desc?: string
  tone?: 'primary' | 'accent' | 'warning' | 'violet'
  quickTask?: QuickTask
}

const REVIEWED = '2026-11'

const SOURCES = {
  zapier: 'https://zapier.com/blog/best-ai-meeting-assistant/',
  atlassian: 'https://www.atlassian.com/software/confluence/templates/meeting-notes',
  ibabs: 'https://www.ibabs.com/en/meeting-management/agenda-management/',
  teams: 'https://learn.microsoft.com/en-us/microsoftteams/copilot-teams-transcription',
  meetingAi: 'https://meeting.ai/',
  lynkk: 'https://www.lynkk.ai/',
  promptzy: 'https://www.promptzy.com/',
  robertsRules: 'https://robertsrules.com/',
} as const

const ICON_BRIEF =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M5 5.5h14M5 10h14M5 14.5h9M5 19h6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
const ICON_AGENDA =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M5 5.5h14v15H5zM5 10h14M9 3v4M15 3v4M8.5 14h4M8.5 17h7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
const ICON_SPEECH =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M12 3.5a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0v-5a3 3 0 0 0-3-3ZM6.5 11.5v.5a5.5 5.5 0 0 0 11 0v-.5M12 17.5V21" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
const ICON_SEARCH =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M10.8 17.6a6.8 6.8 0 1 0 0-13.6 6.8 6.8 0 0 0 0 13.6ZM16 16l4 4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
const ICON_RISK =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M12 3.8 21 19.5H3L12 3.8Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M12 9.5v4.2M12 16.6v.4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'
const ICON_CHECKLIST =
  '<svg viewBox="0 0 24 24" width="13" height="13" fill="none"><path d="M4.5 4.5h15v15h-15zM8 12l2.2 2.2L16 8.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
const ICON_MINUTES =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="M6 3.5h9l3 3v14H6zM15 3.5v3h3M9 11h6M9 14.5h6M9 18h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
const ICON_RECORDS =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="M4.5 6.5h15M4.5 12h15M4.5 17.5h10" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
const ICON_TASKS =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="M4.5 5.5h15v13h-15zM8 10l1.8 1.8L13 8.6M8 15.5h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
const ICON_ISSUES =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6"/><path d="M12 7.5v5M12 16v.4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'

/* ------------------------------------------------------------------ 资料预处理 */

export const PREPROCESS_QUICK_ACTIONS: QuickActionSpec[] = [
  {
    key: 'preprocess.brief',
    scene: 'preprocess',
    label: '会前速览',
    prompt: '请基于本场会议资料，给出一份 60 秒可读完的会前速览。',
    intent: 'brief',
    mode: 'plan',
    outputKind: 'brief_card',
    grounding: 'materials_only',
    icon: ICON_BRIEF,
    rationale:
      '参会人最需要的是「这场会谈什么、我需要知道什么」，而不是长篇准备稿；速览只读本场资料，避免与准备清单重复。',
    sourceUrls: [SOURCES.zapier, SOURCES.teams, SOURCES.meetingAi],
    lastReviewed: REVIEWED,
  },
  {
    key: 'preprocess.agenda',
    scene: 'preprocess',
    label: '会议议程',
    prompt:
      '请基于本场会议资料，生成 3-6 个议题的会议议程；每个议题包含目标、建议时长、主讲人和讨论重点。',
    intent: 'chat',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_then_web',
    icon: ICON_AGENDA,
    rationale:
      '议程是多数参会人会前查看的第一份材料；按「目标/时长/主讲/讨论重点」组织，便于主持人控场。',
    sourceUrls: [SOURCES.ibabs, SOURCES.atlassian, SOURCES.robertsRules],
    lastReviewed: REVIEWED,
  },
  {
    key: 'preprocess.talking_points',
    scene: 'preprocess',
    label: '发言要点',
    prompt:
      '请基于本场会议资料，为我准备 3-5 条发言要点，并附 1 句开场白和 2 个可在会上提出的问题。',
    intent: 'chat',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_then_web',
    icon: ICON_SPEECH,
    rationale:
      '会前准备发言是高频需求；限制为 3-5 条观点 + 开场白 + 2 个问题，避免变成整篇发言稿。',
    sourceUrls: [SOURCES.promptzy, SOURCES.zapier],
    lastReviewed: REVIEWED,
  },
  {
    key: 'preprocess.lookup',
    scene: 'preprocess',
    label: '资料速查',
    prompt:
      '请从本场会议资料中查找最关键的信息，输出 3-5 条要点，并标注每条信息来自哪个文件。',
    intent: 'chat',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_then_web',
    icon: ICON_SEARCH,
    rationale:
      '会前快速定位资料中的关键数字与结论；要求标注来源文件名，便于参会人回查原文。',
    sourceUrls: [SOURCES.meetingAi, SOURCES.lynkk],
    lastReviewed: REVIEWED,
  },
  {
    key: 'preprocess.confirmations',
    scene: 'preprocess',
    label: '待确认事项',
    prompt:
      '请阅读本场会议资料，列出 3-5 个需要在会上确认的问题或风险，并说明为什么需要确认。',
    intent: 'chat',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_then_web',
    icon: ICON_RISK,
    rationale:
      '把「资料中的不确定点」提前暴露给参会人，减少会上反复澄清；与纪要阶段的未解决问题分开。',
    sourceUrls: [SOURCES.robertsRules, SOURCES.atlassian],
    lastReviewed: REVIEWED,
  },
  {
    key: 'preprocess.checklist',
    scene: 'preprocess',
    label: '准备清单',
    prompt:
      '请生成会前准备清单：梳理需要准备的材料、需要确认的信息，以及参会人需要提前了解的内容。',
    intent: 'prepare',
    mode: 'plan',
    outputKind: 'checklist',
    grounding: 'materials_only',
    icon: ICON_CHECKLIST,
    rationale:
      '清单是「我要做什么」的执行项，与速览的「是什么」分开；聊天区只展示条数与前 3 条，完整内容在左侧确认。',
    sourceUrls: [SOURCES.atlassian, SOURCES.promptzy],
    lastReviewed: REVIEWED,
  },
]

/* ------------------------------------------------------------------ 会中助手 */

export const ASR_QUICK_ACTIONS: QuickActionSpec[] = [
  {
    key: 'asr.summary',
    scene: 'asr',
    label: '提炼要点',
    prompt: '基于当前会议内容提炼要点，按结论与决议、关键讨论、待办与责任、待确认问题分节输出。',
    task: 'summary',
    intent: 'organize',
    mode: 'plan',
    outputKind: 'summary_card',
    grounding: 'materials_only',
    rationale: '会中需要快速对齐「已达成什么、还差什么」；结构化卡片比长段落更适合边听边看。',
    sourceUrls: [SOURCES.teams, SOURCES.zapier],
    lastReviewed: REVIEWED,
  },
  {
    key: 'asr.polish',
    scene: 'asr',
    label: '修正口误',
    prompt: '检查转写文本中的口误、识别错误与不通顺之处，逐条给出修改建议。',
    task: 'polish',
    intent: 'organize',
    mode: 'plan',
    outputKind: 'polish_diff',
    grounding: 'materials_only',
    rationale: 'ASR 转写难免有同音错字；逐条 diff 让用户确认后再改，避免 AI 直接覆盖原文。',
    sourceUrls: [SOURCES.teams, SOURCES.lynkk],
    lastReviewed: REVIEWED,
  },
  {
    key: 'asr.brief',
    scene: 'asr',
    label: '简短摘要',
    prompt: '用 3-5 句话概括当前会议进展。',
    task: 'brief',
    intent: 'organize',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_only',
    rationale: '中途加入或短暂离开的参会人需要 3-5 句话追赶进度，而不是完整纪要。',
    sourceUrls: [SOURCES.teams, SOURCES.meetingAi],
    lastReviewed: REVIEWED,
  },
  {
    key: 'asr.condense',
    scene: 'asr',
    label: '精简选中',
    prompt: '',
    quickTask: 'condense',
    intent: 'chat',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_only',
    rationale: '选中一段冗长转写后一键压缩，保留结论与数据；只处理选中文本，不写回原始记录。',
    sourceUrls: [SOURCES.promptzy],
    lastReviewed: REVIEWED,
  },
]

/* ------------------------------------------------------------------ 纪要生成 */

export const MINUTES_QUICK_ACTIONS: QuickActionSpec[] = [
  {
    key: 'minutes.minutes',
    scene: 'minutes',
    label: '会议纪要',
    prompt: '请生成会议纪要，并拆解待办任务。',
    intent: 'minutes_generate',
    mode: 'plan',
    outputKind: 'minutes',
    grounding: 'materials_only',
    icon: ICON_MINUTES,
    desc: '帮我生成一篇会议纪要',
    tone: 'primary',
    rationale: '纪要是会后第一交付物；生成 draft 后仍需用户编辑确认，AI 不直接定稿。',
    sourceUrls: [SOURCES.atlassian, SOURCES.zapier],
    lastReviewed: REVIEWED,
  },
  {
    key: 'minutes.records',
    scene: 'minutes',
    label: '会议记录',
    prompt: '请整理本次会议的会议记录，去除口语冗余，使逻辑清晰。',
    task: 'organize',
    intent: 'organize',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_only',
    icon: ICON_RECORDS,
    desc: '帮我整理一下会议记录',
    tone: 'accent',
    rationale: '原始记录保留口语；整理稿只作展示，不覆盖原文，便于会后阅读与检索。',
    sourceUrls: [SOURCES.teams],
    lastReviewed: REVIEWED,
  },
  {
    key: 'minutes.tasks',
    scene: 'minutes',
    label: '待办任务',
    prompt: '请从会议记录中提取待办任务与行动项，标注责任人和截止时间。',
    intent: 'action_items_extract',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_only',
    icon: ICON_TASKS,
    desc: '帮我提取待办任务',
    tone: 'warning',
    rationale: '行动项必须「唯一负责人 + 明确日期」；AI 只给候选，用户确认后才转为个人任务。',
    sourceUrls: [SOURCES.zapier, SOURCES.meetingAi],
    lastReviewed: REVIEWED,
  },
  {
    key: 'minutes.search',
    scene: 'minutes',
    label: '会议检索',
    prompt: '请检索本次会议的记录与资料，总结其中的关键信息，并给出对应来源。',
    intent: 'chat',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_then_web',
    icon: ICON_SEARCH,
    desc: '帮我检索会议内容',
    tone: 'accent',
    rationale: '会后回查「当时怎么说的」是高频需求；要求给出对应来源，便于定位原始记录。',
    sourceUrls: [SOURCES.meetingAi, SOURCES.lynkk],
    lastReviewed: REVIEWED,
  },
  {
    key: 'minutes.issues',
    scene: 'minutes',
    label: '未解决问题',
    prompt: '请从会议记录中提取讨论过但没有结论、需要下次继续的问题。',
    intent: 'issues_extract',
    mode: 'plan',
    outputKind: 'text',
    grounding: 'materials_only',
    icon: ICON_ISSUES,
    desc: '帮我梳理未解决问题',
    tone: 'violet',
    rationale: '把「没结论的问题」显式沉淀下来，避免会后失忆；与行动项分开管理。',
    sourceUrls: [SOURCES.robertsRules, SOURCES.atlassian],
    lastReviewed: REVIEWED,
  },
]

const REGISTRY: Record<AgentScene, QuickActionSpec[]> = {
  preprocess: PREPROCESS_QUICK_ACTIONS,
  asr: ASR_QUICK_ACTIONS,
  minutes: MINUTES_QUICK_ACTIONS,
}

export function quickActionsFor(scene: AgentScene): QuickActionSpec[] {
  return REGISTRY[scene]
}

/** 把注册表动作转换为 AgentChat 可消费的快捷操作（去掉审查字段） */
export function toAgentQuickAction(spec: QuickActionSpec): AgentQuickAction {
  return {
    label: spec.label,
    prompt: spec.prompt,
    task: spec.task,
    intent: spec.intent as AgentIntentName | undefined,
    mode: spec.mode,
    quickTask: spec.quickTask,
  }
}
