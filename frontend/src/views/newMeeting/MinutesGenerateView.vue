<template>
  <StageShell
    stage="minutes"
    title="会后智能处理"
  >

    <template #default="{ meeting }">
      <div class="minutes-page">
        <AgentChat
          ref="chatRef"
          class="minutes-page__chat"
          agent-name="会后智能助手"
          welcome-title="你好，我是会后智能处理助手"
          :greeting="greeting"
          :on-send="handleSend"
          :disabled="!meeting.meeting_id"
          placeholder="生成纪要、拆解待办，或检索会议内容…"
        >
          <!-- 高频任务卡片（欢迎区内） -->
          <template #welcome-extra>
            <div class="task-cards">
              <button
                v-for="task in taskCards"
                :key="task.key"
                type="button"
                class="task-card"
                :disabled="!meeting.meeting_id"
                @click="runTask(task.prompt)"
              >
                <span
                  class="task-card__icon"
                  :class="`task-card__icon--${task.tone}`"
                  aria-hidden="true"
                  v-html="task.icon"
                />
                <span class="task-card__body">
                  <span class="task-card__title">{{ task.title }}</span>
                  <span class="task-card__desc">{{ task.desc }}</span>
                </span>
              </button>
            </div>
          </template>

          <!-- 输入框内：模板 / 模型快捷选择 -->
          <template #composer-extra>
            <TemplatePickerPopover
              :disabled="!meeting.meeting_id"
              :selected="selectedTemplateId"
              @select="onSelectTemplate"
            />
            <ModelPickerPopover
              :disabled="!meeting.meeting_id"
              :selected="selectedModel"
              @select="onSelectModel"
            />
          </template>
        </AgentChat>
      </div>
    </template>
  </StageShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import * as actionItemsApi from '@/api/actionItems'
import * as chatApi from '@/api/chat'
import * as minutesApi from '@/api/minutes'
import AgentChat from '@/components/AgentChat.vue'
import ModelPickerPopover from '@/components/ModelPickerPopover.vue'
import StageShell from '@/components/StageShell.vue'
import TemplatePickerPopover from '@/components/TemplatePickerPopover.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import type { AgentReply } from '@/types/agent'
import type { ActionItem } from '@/types/actionItem'
import type { ChatSource } from '@/types/chat'
import type { Minutes, MinutesTemplate } from '@/types/minutes'
import { resolveErrorMessage } from '@/utils/errors'
import { minutesTemplateMeta } from '@/utils/statusLabels'

const route = useRoute()
const toast = useToast()
const { mirrorMeetingFile } = useLocalWorkspace()

const meetingId = computed(() => String(route.query.meetingId ?? ''))
const lastMinutes = ref<Minutes | null>(null)
const chatRef = ref<InstanceType<typeof AgentChat> | null>(null)
const selectedModel = ref('')
const selectedTemplateId = ref('')

const greeting =
  '我会读取会前准备、转写文稿、用户标记和会议资料，帮你生成纪要、整理议程、拆解待办或检索内容。点击下方高频任务卡片快速开始，也可以在输入框左侧选择输出模板与对话模型。'

const ICON_MINUTES =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><rect x="4.5" y="3.5" width="15" height="17" rx="2" stroke="currentColor" stroke-width="1.7"/><path d="M8 8h8M8 12h8M8 16h5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
const ICON_AGENDA =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><rect x="4.5" y="4.5" width="15" height="15" rx="2" stroke="currentColor" stroke-width="1.7"/><path d="M4.5 9.5h15M8.5 3v3.5M15.5 3v3.5M8.5 13h2M13.5 13h2M8.5 16.5h2" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'
const ICON_TASKS =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="m4.5 7 1.8 1.8L9.5 5.6M4.5 16.5l1.8 1.8 3.2-3.2M12.5 8h7M12.5 17h7" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>'
const ICON_SEARCH =
  '<svg viewBox="0 0 24 24" width="20" height="20" fill="none"><path d="M10.8 17.6a6.8 6.8 0 1 0 0-13.6 6.8 6.8 0 0 0 0 13.6ZM16 16l4 4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>'

interface TaskCard {
  key: string
  title: string
  desc: string
  prompt: string
  tone: 'primary' | 'accent' | 'warning' | 'violet'
  icon: string
}

const taskCards: TaskCard[] = [
  {
    key: 'minutes',
    title: '会议纪要',
    desc: '生成结构化的正式会议纪要',
    prompt: '请生成会议纪要，并拆解待办任务。',
    tone: 'primary',
    icon: ICON_MINUTES,
  },
  {
    key: 'agenda',
    title: '会议议程',
    desc: '整理本次会议的议程与要点',
    prompt:
      '请基于会议记录整理本次会议的议程，按议题列出讨论要点与结论，并标注未讨论完的事项。',
    tone: 'accent',
    icon: ICON_AGENDA,
  },
  {
    key: 'tasks',
    title: '待办任务',
    desc: '提取行动项、责任人与截止时间',
    prompt: '请从会议记录中提取待办任务与行动项，标注责任人和截止时间。',
    tone: 'warning',
    icon: ICON_TASKS,
  },
  {
    key: 'search',
    title: '会议检索',
    desc: '检索会议内容，回答附带来源',
    prompt: '请检索本次会议的记录与资料，总结其中的关键信息，并给出对应来源。',
    tone: 'violet',
    icon: ICON_SEARCH,
  },
]

const minutesIntent = /纪要/
const actionsIntent = /待办|行动项/
const searchIntent = /检索|搜索|来源|出处|引用/

function templateLabel(value: MinutesTemplate): string {
  return minutesTemplateMeta[value].label
}

function inferTemplate(text: string): MinutesTemplate | undefined {
  if (/精简|简洁/.test(text)) {
    return 'concise'
  }
  if (/任务清单|待办|行动项/.test(text)) {
    return 'task_list'
  }
  if (/正式|标准|完整/.test(text)) {
    return 'standard'
  }
  return undefined
}

function onSelectModel(model: string): void {
  selectedModel.value = model
  toast.success(model ? `已选择模型：${model}` : '已恢复默认模型路由')
}

function onSelectTemplate(templateId: string): void {
  selectedTemplateId.value = templateId
  toast.success(templateId ? '已选择输出模板，生成纪要时将套用' : '已恢复默认纪要结构')
}

function runTask(prompt: string): void {
  void chatRef.value?.sendPrompt(prompt)
}

function sourceLabel(source: ChatSource): string {
  if (source.document_name) {
    return source.document_name
  }
  if (source.record_id) {
    return '会议记录'
  }
  if (source.material_id) {
    return '会议资料'
  }
  if (source.meeting_id) {
    return '会议上下文'
  }
  return '来源'
}

async function generateMinutesReply(text: string, signal: AbortSignal): Promise<AgentReply> {
  const minutes = await minutesApi.generateMinutes(
    meetingId.value,
    {
      record_ids: [],
      include_action_items: true,
      include_materials: true,
      template: inferTemplate(text),
      template_id: selectedTemplateId.value || undefined,
    },
    signal,
  )
  lastMinutes.value = minutes
  void mirrorMeetingFile({
    meetingId: meetingId.value,
    kind: 'minutes',
    fileName: `会议纪要_v${minutes.version}.md`,
    content: minutes.content,
  })
  return {
    content: minutes.content,
    note: `已生成${templateLabel(minutes.template)}草稿 v${minutes.version}，可在「会议详情 → 纪要」中编辑与确认。`,
  }
}

function formatActionItem(item: ActionItem): string {
  const assignee = item.assignee ? `责任人：${item.assignee}` : '责任人：待确认'
  const due = item.due_date ? `，截止：${item.due_date.slice(0, 10)}` : ''
  return `- ${item.content}（${assignee}${due}）`
}

async function extractActionsReply(): Promise<AgentReply> {
  const result = await actionItemsApi.extractActionItems(meetingId.value, { record_ids: [] })
  if (result.length === 0) {
    return {
      content: '当前会议记录中没有检测到明确的行动项。',
      note: '可以补充或整理会议记录后重试。',
    }
  }
  const lines = result.map((item) => formatActionItem(item)).join('\n')
  return {
    content: `## 提取到 ${result.length} 个行动项\n\n${lines}`,
    note: '已保存为行动项草稿，可在「会议详情 → 行动项」中确认并转为个人任务。',
  }
}

async function askReply(
  text: string,
  signal: AbortSignal,
  withSources: boolean,
): Promise<AgentReply> {
  const result = await chatApi.askMeeting(
    meetingId.value,
    {
      question: text,
      context_scope: 'current_meeting',
      include_sources: withSources,
      model: selectedModel.value || undefined,
    },
    signal,
  )
  return {
    content: result.answer,
    sources: withSources
      ? result.sources.slice(0, 3).map((source) => ({
          label: sourceLabel(source),
          detail: source.excerpt.replace(/\s+/g, ' ').slice(0, 64),
        }))
      : undefined,
    note: result.insufficient_evidence ? '证据不足，回答仅供参考。' : undefined,
  }
}

async function handleSend(text: string, signal: AbortSignal): Promise<AgentReply> {
  if (!meetingId.value) {
    throw new Error('请先选择一场会议。')
  }
  try {
    if (minutesIntent.test(text)) {
      return await generateMinutesReply(text, signal)
    }
    if (actionsIntent.test(text)) {
      return await extractActionsReply()
    }
    return await askReply(text, signal, searchIntent.test(text))
  } catch (caught) {
    if (signal.aborted) {
      throw new Error('已取消本次请求。')
    }
    throw new Error(resolveErrorMessage(caught, '处理失败，请稍后重试。'))
  }
}

async function loadLatestMinutes(): Promise<void> {
  if (!meetingId.value) {
    return
  }
  try {
    const result = await minutesApi.listMinutes(meetingId.value, { page: 1, page_size: 1 })
    lastMinutes.value = result.items[0] ?? null
  } catch {
    lastMinutes.value = null
  }
}

watch(
  meetingId,
  (id) => {
    lastMinutes.value = null
    if (!id) {
      return
    }
    void loadLatestMinutes()
  },
  { immediate: true },
)
</script>

<style scoped>
.minutes-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
}

/* 对话区占满页头以下空间 */
.minutes-page__chat {
  flex: 1;
  min-height: 0;
}

/* 高频任务卡片 */
.task-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.task-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4);
  text-align: left;
  font: inherit;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    background var(--transition-fast);
}

.task-card:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: rgba(21, 94, 239, 0.35);
  box-shadow: var(--shadow-md);
  background: var(--color-surface);
}

.task-card:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.task-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 2.35rem;
  height: 2.35rem;
  border-radius: var(--radius-md);
}

.task-card__icon--primary {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.task-card__icon--accent {
  color: var(--color-accent-strong);
  background: var(--color-accent-soft);
}

.task-card__icon--warning {
  color: #b45309;
  background: #fdf3e0;
}

.task-card__icon--violet {
  color: #6d28d9;
  background: #f1ecfd;
}

.task-card__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.task-card__title {
  color: var(--color-foreground);
  font-size: 0.9375rem;
  font-weight: 650;
}

.task-card__desc {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  line-height: 1.55;
}

@media (max-width: 1400px) {
  .task-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .minutes-page {
    height: auto;
  }

  .minutes-page__chat {
    min-height: 34rem;
  }
}

@media (max-width: 720px) {
  .task-cards {
    grid-template-columns: minmax(0, 1fr);
  }

  .minutes-page__chat {
    min-height: 28rem;
  }
}
</style>
