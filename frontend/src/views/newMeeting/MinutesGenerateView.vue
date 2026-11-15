<template>
  <StageShell
    stage="minutes"
    title="会后智能处理"
  >

    <template #default="{ meeting }">
      <div class="minutes-page">
        <AgentChat
          ref="chatRef"
          v-model:thinking="thinking"
          class="minutes-page__chat"
          agent-name="纪要萃取，一羽搞定"
          :show-welcome-title="false"
          :mascot-src="mascotUrl"
          mascot-size="8rem"
          :meeting-id="meeting.meeting_id"
          :storage-key="meeting.meeting_id ? `minutes:${meeting.meeting_id}` : ''"
          :on-send="handleSend"
          :on-send-stream="handleSend"
          :on-task="handleAgentTask"
          :backend-session="agentEnabled && !!meeting.meeting_id"
          agent-scene="minutes"
          :agent-options="agentOptions"
          :disabled="!meeting.meeting_id"
          placeholder="生成纪要、整理记录、拆解待办，或检索会议内容…"
          @open-doc="onOpenDoc"
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
                @click="runTask(task)"
              >
                <span
                  class="task-card__icon"
                  :class="`task-card__icon--${task.tone ?? 'primary'}`"
                  aria-hidden="true"
                  v-html="task.icon"
                />
                <span class="task-card__body">
                  <span class="task-card__title">{{ task.label }}</span>
                  <span class="task-card__desc">{{ task.desc }}</span>
                </span>
              </button>
            </div>
          </template>

          <!-- 输入框内：模式 / 模型 / 模板选择 -->
          <template #composer-extra>
            <ModePicker v-model="chatMode" :disabled="!meeting.meeting_id" />
            <ModelPickerPopover
              :disabled="!meeting.meeting_id"
              :selected="selectedModel"
              @select="onSelectModel"
              @manage="openPanel('model')"
            />
            <TemplatePickerPopover
              :disabled="!meeting.meeting_id"
              :selected="selectedTemplateId"
              :meeting-id="meeting.meeting_id"
              return-to="minutes"
            />
          </template>
        </AgentChat>

        <!-- 点击聊天里的文件卡/清单卡：右侧打开查看与编辑 -->
        <AgentDocDrawer
          :open="drawerOpen"
          :meeting-id="meeting.meeting_id"
          :kind="drawerKind"
          :meta="drawerMeta"
          @close="drawerOpen = false"
        />
      </div>
    </template>
  </StageShell>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

import * as chatApi from '@/api/chat'
import mascotUrl from '@/assets/ip/functionthree.jpeg'
import AgentChat from '@/components/AgentChat.vue'
import AgentDocDrawer from '@/components/AgentDocDrawer.vue'
import ModePicker from '@/components/ModePicker.vue'
import ModelPickerPopover from '@/components/ModelPickerPopover.vue'
import StageShell from '@/components/StageShell.vue'
import TemplatePickerPopover from '@/components/TemplatePickerPopover.vue'
import { useSettingsPanels } from '@/composables/useSettingsPanels'
import { useToast } from '@/composables/useToast'
import { agentEnabled } from '@/config/flags'
import { MINUTES_QUICK_ACTIONS, type QuickActionSpec } from '@/config/quickActions'
import type {
  AgentDocOpenEvent,
  AgentReply,
  AgentSource,
  AgentStreamHandlers,
  AgentTurnOptions,
  MinutesDocMeta,
} from '@/types/agent'
import type { ChatMode, ChatPayload, ChatSource, OrganizeTask } from '@/types/chat'
import { resolveErrorMessage } from '@/utils/errors'

const route = useRoute()
const toast = useToast()
const { openPanel } = useSettingsPanels()

const meetingId = computed(() => String(route.query.meetingId ?? ''))
const chatRef = ref<InstanceType<typeof AgentChat> | null>(null)
const selectedModel = ref('')
const selectedTemplateId = ref('')

// 点击聊天里的文件卡/清单卡 → 右侧文件页（头部卡片 + 文档编辑区）查看与编辑
const drawerOpen = ref(false)
const drawerKind = ref<'minutes' | 'action_items'>('minutes')
const drawerMeta = ref<MinutesDocMeta | undefined>(undefined)

function onOpenDoc(event: AgentDocOpenEvent): void {
  drawerKind.value = event.kind
  drawerMeta.value = event.meta
  drawerOpen.value = true
}

// 支持「模板管理页 → 使用」跳转时通过路由参数预选模板
const routeTemplateId = String(route.query.templateId ?? '')
if (routeTemplateId) {
  selectedTemplateId.value = routeTemplateId
}

const chatMode = ref<ChatMode>('build')
/** 思考过程（推理链）开关：默认开启，可按次关闭（关闭后不请求思考模式） */
const thinking = ref(true)

/** 后端 Agent 单轮执行选项：页面选择随消息透传，后端按意图消费 */
const agentOptions = computed<AgentTurnOptions>(() => ({
  model: selectedModel.value || undefined,
  template_id: selectedTemplateId.value || undefined,
  mode: chatMode.value,
  context_scope: 'current_meeting',
  include_sources: true,
  include_history: true,
  include_action_items: true,
  include_materials: true,
}))

// 高频任务卡来自注册表：minutes/records/tasks/issues/search 各自声明意图与输出形态
const taskCards: QuickActionSpec[] = MINUTES_QUICK_ACTIONS

function onSelectModel(model: string): void {
  selectedModel.value = model
  toast.success(model ? `已选择模型：${model}` : '已恢复默认模型路由')
}

function runTask(card: QuickActionSpec): void {
  // 挂载注册表动作：发送时透传 intent/mode/task，由后端按通道执行
  chatRef.value?.setPendingQuickAction({
    label: card.label,
    prompt: card.prompt,
    intent: card.intent,
    mode: card.mode,
    task: card.task,
    quickTask: card.quickTask,
  })
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

function mapSources(sources: ChatSource[]): AgentSource[] {
  return sources.slice(0, 3).map((source) => ({
    label: sourceLabel(source),
    detail: source.excerpt.replace(/\s+/g, ' ').slice(0, 64),
  }))
}

async function askReply(
  text: string,
  signal: AbortSignal,
  withSources: boolean,
  stream?: AgentStreamHandlers,
): Promise<AgentReply> {
  const payload: ChatPayload = {
    question: text,
    context_scope: 'current_meeting',
    include_sources: withSources,
    model: selectedModel.value || undefined,
    mode: chatMode.value,
    thinking: thinking.value,
  }
  // Build 模式走同步（流式端点仅支持 plan，api.md 5.7a）；否则走 SSE 增量
  const result =
    stream && chatMode.value !== 'build'
      ? await chatApi.askMeetingStream(
          meetingId.value,
          payload,
          {
            onMeta: (meta) => stream.onMeta?.(mapSources(meta.sources), meta.trace),
            onDelta: stream.onDelta,
            onReasoning: stream.onReasoning,
          },
          signal,
        )
      : await chatApi.askMeeting(meetingId.value, payload, signal)
  return {
    content: result.answer,
    file: result.file ?? undefined,
    sources: withSources ? mapSources(result.sources) : undefined,
    reasoning: result.reasoning,
    note: result.insufficient_evidence ? '证据不足，回答仅供参考。' : undefined,
  }
}

async function handleAgentTask(
  task: string,
  prompt: string,
  signal: AbortSignal,
): Promise<AgentReply> {
  if (!meetingId.value) {
    throw new Error('请先选择一场会议。')
  }
  try {
    const result = await chatApi.organizeRecords(
      meetingId.value,
      {
        task: task as OrganizeTask,
        model: selectedModel.value || undefined,
        ...(prompt.trim() ? { instruction: prompt.trim().slice(0, 2000) } : {}),
      },
      signal,
    )
    if (result.task === 'summary' && result.structured && !Array.isArray(result.structured)) {
      return { content: '', kind: 'summary', structured: result.structured }
    }
    if (result.task === 'polish' && Array.isArray(result.structured)) {
      return {
        content: '',
        kind: 'polish',
        structured: result.structured,
        note: '请逐条确认修改建议（当前页面仅支持只读预览）。',
      }
    }
    return { content: result.organized_content, note: '整理稿仅作展示，不会覆盖原始记录。' }
  } catch (caught) {
    if (signal.aborted) {
      throw new Error('已取消本次请求。')
    }
    throw new Error(resolveErrorMessage(caught, '处理失败，请稍后重试。'))
  }
}

async function handleSend(
  text: string,
  signal: AbortSignal,
  stream?: AgentStreamHandlers,
): Promise<AgentReply> {
  if (!meetingId.value) {
    throw new Error('请先选择一场会议。')
  }
  try {
    return await askReply(text, signal, true, stream)
  } catch (caught) {
    if (signal.aborted) {
      throw new Error('已取消本次请求。')
    }
    throw new Error(resolveErrorMessage(caught, '处理失败，请稍后重试。'))
  }
}
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

/* 高频任务卡片：宽屏 5 张一行均分 */
.task-cards {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-3);
}

.task-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 5.75rem;
  padding: var(--space-4) var(--space-3);
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
  width: 2.1rem;
  height: 2.1rem;
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
  /* 小字固定一行，超长省略号截断 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (max-width: 1180px) {
  .task-cards {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .minutes-page {
    height: auto;
  }

  .minutes-page__chat {
    min-height: 34rem;
  }
}

@media (max-width: 860px) {
  .task-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 600px) {
  .task-cards {
    grid-template-columns: minmax(0, 1fr);
  }

  .minutes-page__chat {
    min-height: 28rem;
  }
}
</style>
