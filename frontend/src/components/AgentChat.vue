<template>
  <section class="agent-chat" :class="{ 'agent-chat--compact': compact }" aria-label="Agent 对话">
    <header class="agent-chat__header">
      <span class="agent-chat__avatar" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none">
          <path
            d="M12 3.2 13.8 8.6 19.2 10.4 13.8 12.2 12 17.6 10.2 12.2 4.8 10.4 10.2 8.6 12 3.2Z"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linejoin="round"
          />
          <path
            d="M18.6 15.2 19.4 17.6 21.8 18.4 19.4 19.2 18.6 21.6 17.8 19.2 15.4 18.4 17.8 17.6 18.6 15.2Z"
            fill="currentColor"
          />
        </svg>
      </span>
      <div class="agent-chat__identity">
        <p class="agent-chat__name">{{ agentName }}</p>
        <p v-if="subtitle" class="agent-chat__subtitle">{{ subtitle }}</p>
      </div>
      <div class="agent-chat__header-actions">
        <slot name="header-actions" />
        <button
          v-if="messages.length > 0"
          type="button"
          class="agent-chat__clear"
          title="清空当前对话"
          @click="clear"
        >
          清空
        </button>
      </div>
    </header>

    <div
      v-if="showWelcome && messages.length === 0 && (welcomeTitle || greeting || quickActions.length || $slots['welcome-extra'])"
      class="agent-welcome"
    >
      <div v-if="showWelcomeTitle || greeting" class="agent-welcome__intro">
        <h2 v-if="showWelcomeTitle" class="agent-welcome__title">{{ displayWelcomeTitle }}</h2>
        <MarkdownView v-if="greeting" class="agent-welcome__text" :content="greeting" />
      </div>

      <div v-if="quickActions.length" class="agent-welcome__starters">
        <button
          v-for="action in quickActions"
          :key="action.label"
          type="button"
          class="agent-starter"
          :disabled="disabled"
          @click="runStarter(action)"
        >
          <span class="agent-starter__head">
            <span class="agent-starter__label">{{ action.label }}</span>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
              <path
                d="M8 5.5 14.5 12 8 18.5"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </span>
          <span class="agent-starter__prompt">{{ action.prompt }}</span>
        </button>
      </div>

      <div v-if="$slots['welcome-extra']" class="agent-welcome__extra">
        <slot name="welcome-extra" />
      </div>
    </div>

    <div
      v-else
      ref="listEl"
      class="agent-chat__messages"
      role="log"
      :aria-busy="isBusy"
      @scroll="onScroll"
    >
      <template v-for="(message, index) in messages" :key="message.id">
        <article v-if="message.role === 'assistant'" class="agent-message agent-message--assistant">
          <div class="agent-rail" aria-hidden="true">
            <span class="agent-rail__dot" />
          </div>

          <div class="agent-message__body" :class="{ 'agent-message__body--error': message.error }">
            <header class="agent-message__meta">
              <span class="agent-message__name">{{ agentName }}</span>
              <time class="agent-message__time">{{ formatTime(message.createdAt) }}</time>
              <span v-if="message.streaming" class="agent-message__typing-label">正在输入</span>

              <div v-if="!message.streaming" class="agent-message__actions">
                <button
                  type="button"
                  class="agent-message__action"
                  :aria-label="copiedId === message.id ? '已复制' : '复制回复'"
                  @click="copy(message)"
                >
                  {{ copiedId === message.id ? '已复制' : '复制' }}
                </button>
                <button
                  v-if="message.regenerateText !== undefined && message.regenerateText !== null"
                  type="button"
                  class="agent-message__action"
                  :disabled="isBusy"
                  @click="regenerate(index)"
                >
                  重新生成
                </button>
                <slot name="message-actions" :message="message" />
              </div>
            </header>

            <!-- 思考过程（推理链）：原生推理 + 真实执行步骤，正文开始后自动折叠 -->
            <AgentReasoningPanel
              v-if="hasTrace(message)"
              :panel-id="`agent-reasoning-${message.id}`"
              :label="reasoningLabel(message)"
              :open="Boolean(message.reasoningOpen)"
              :stages="message.trace ?? []"
              :reasoning="message.reasoning ?? ''"
              :hint="reasoningHint(message)"
              :live="isReasoningLive(message)"
              @toggle="toggleReasoning(message)"
            />

            <div
              v-if="message.streaming && !message.content"
              class="agent-typing"
              aria-label="Agent 正在思考"
            >
              <span />
              <span />
              <span />
            </div>

            <!-- 会后产出：一句介绍 + 文件卡 + 下一步建议 -->
            <template v-else-if="isMinutesCard(message)">
              <MarkdownView class="agent-message__content" :content="message.content" />
              <AgentDocCard
                v-if="message.file && meetingId"
                :meeting-id="meetingId"
                :file="message.file"
                :meta="minutesMetaOf(message.structured)"
                @open="openDoc(message)"
              />
              <div class="agent-suggestions" role="group" aria-label="下一步建议">
                <button
                  v-for="suggestion in suggestionsFor(message)"
                  :key="suggestion.label"
                  type="button"
                  class="agent-suggestion"
                  @click="runSuggestion(message, suggestion)"
                >
                  {{ suggestion.label }}
                </button>
              </div>
            </template>

            <!-- 会后产出：一句介绍 + 行动项清单卡 + 下一步建议 -->
            <template v-else-if="isActionItemsCard(message)">
              <MarkdownView class="agent-message__content" :content="message.content" />
              <AgentActionItemsCard
                :items="actionItemsOf(message.structured)"
                @open="openDoc(message)"
              />
              <div class="agent-suggestions" role="group" aria-label="下一步建议">
                <button
                  v-for="suggestion in suggestionsFor(message)"
                  :key="suggestion.label"
                  type="button"
                  class="agent-suggestion"
                  @click="runSuggestion(message, suggestion)"
                >
                  {{ suggestion.label }}
                </button>
              </div>
            </template>

            <div v-else-if="message.structured" class="agent-message__structured">
              <slot name="structured" :message="message">
                <BriefCard
                  v-if="message.kind === 'brief' && isMaterialBrief(message.structured)"
                  :data="message.structured"
                />
                <SummaryCard
                  v-else-if="message.kind === 'summary' && isSummaryStructured(message.structured)"
                  :data="message.structured"
                />
                <PolishDiffPanel
                  v-else-if="message.kind === 'polish' && isPolishSuggestions(message.structured)"
                  :suggestions="message.structured"
                  readonly
                />
              </slot>
            </div>
            <MarkdownView v-else class="agent-message__content" :content="message.content" />

            <!-- 仅错误与手动停止时显示状态行，普通回复不再有额外提示文字 -->
            <p
              v-if="message.note && (message.error || message.stopped || message.statusNote)"
              class="agent-message__status"
              :class="{ 'agent-message__status--error': message.error || message.statusNote }"
            >
              {{ message.note }}
            </p>

            <div v-if="message.sources?.length" class="agent-message__sources">
              <span
                v-for="(source, sourceIndex) in message.sources"
                :key="sourceIndex"
                class="agent-source"
              >
                <strong>{{ source.label }}</strong>
                <span v-if="source.detail">{{ source.detail }}</span>
              </span>
            </div>

            <!-- 服务端确认门：AI 只给候选，联网等有副作用的动作需用户显式批准 -->
            <div
              v-if="message.pendingAction"
              class="agent-pending"
              role="group"
              aria-label="待确认操作"
            >
              <template v-if="message.pendingAction.status === 'pending'">
                <p class="agent-pending__label">需要你的确认</p>
                <div class="agent-pending__actions">
                  <button
                    type="button"
                    class="agent-pending__approve"
                    :disabled="message.pendingDeciding || isBusy"
                    @click="decidePending(message, true)"
                  >
                    {{ message.pendingDeciding ? '处理中…' : approveLabel(message.pendingAction) }}
                  </button>
                  <button
                    type="button"
                    class="agent-pending__reject"
                    :disabled="message.pendingDeciding || isBusy"
                    @click="decidePending(message, false)"
                  >
                    暂不处理
                  </button>
                </div>
              </template>
              <p v-else class="agent-pending__status">
                {{ pendingStatusText(message.pendingAction.status) }}
              </p>
            </div>

            <!-- Build 模式产出：下载 DOCX + 保存到会议资料 + 写入本地文件夹（各自独立重试） -->
            <ChatFileCard
              v-if="message.file && meetingId && !isMinutesCard(message)"
              :meeting-id="meetingId"
              :file="message.file"
            />
          </div>
        </article>

        <div v-else class="agent-message agent-message--user">
          <div class="agent-user">
            <blockquote v-if="message.context" class="agent-user__context">
              {{ message.context }}
            </blockquote>
            <p class="agent-user__text">{{ message.content }}</p>
          </div>
        </div>
      </template>

      <p v-if="errorText" class="agent-chat__error" role="alert">{{ errorText }}</p>
    </div>

    <form class="agent-chat__composer" @submit.prevent="send()">
      <div v-if="contextText" class="agent-context">
        <span class="agent-context__label">已引用选中内容</span>
        <span class="agent-context__text">{{ trimmedContext }}</span>
        <button
          type="button"
          class="agent-context__remove"
          aria-label="取消引用"
          @click="emit('clear-context')"
        >
          ×
        </button>
      </div>

      <div class="agent-composer">
        <img
          v-if="showMascot"
          :src="mascotSrc"
          :style="{ height: mascotSize }"
          class="agent-composer__mascot"
          alt=""
          aria-hidden="true"
          draggable="false"
        />
        <div class="agent-composer__field">
          <span v-if="pendingAction" ref="taskChipEl" class="agent-task-chip">
            <span class="agent-task-chip__tag">#{{ pendingAction.label }}</span>
            <button
              type="button"
              class="agent-task-chip__remove"
              aria-label="取消快捷任务"
              @click="pendingAction = null"
            >
              ×
            </button>
          </span>
          <textarea
            :id="inputId"
            ref="textareaEl"
            v-model="draft"
            class="agent-composer__input"
            rows="1"
            :placeholder="
              disabled
                ? '当前会议不可用'
                : pendingAction
                  ? '可补充要求后发送，或直接发送…'
                  : placeholder
            "
            :disabled="disabled"
            :style="chipIndentStyle"
            :aria-label="`向 ${agentName} 发送消息`"
            @keydown="onKeydown"
            @input="adjustTextarea"
          />
        </div>

        <div class="agent-composer__bar">
          <div class="agent-composer__tools">
            <button
              type="button"
              class="agent-thinking-toggle"
              :class="{ 'agent-thinking-toggle--on': thinking }"
              :aria-pressed="thinking"
              :disabled="disabled || isBusy"
              aria-label="显示 AI 思考过程"
              title="显示 AI 思考过程（部分模型会更慢、更贵）"
              @click="thinking = !thinking"
            >
              <svg
                viewBox="0 0 24 24"
                width="14"
                height="14"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M12 4.5c-3 0-5 2.1-5 4.7 0 1.4.6 2.4 1.4 3.2.5.5.8 1 .9 1.6h5.4c.1-.6.4-1.1.9-1.6.8-.8 1.4-1.8 1.4-3.2 0-2.6-2-4.7-5-4.7Z"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linejoin="round"
                />
                <path
                  d="M10 17.5h4M10.6 20h2.8"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linecap="round"
                />
              </svg>
              <span class="agent-thinking-toggle__text">思考</span>
            </button>
            <slot v-if="$slots['composer-extra']" name="composer-extra" />
          </div>
          <div class="agent-composer__actions">
            <button
              v-if="isBusy"
              type="button"
              class="agent-composer__stop"
              title="停止生成"
              aria-label="停止生成"
              @click="stop"
            >
              <span class="sr-only">停止生成</span>
              <svg
                viewBox="0 0 24 24"
                width="14"
                height="14"
                fill="currentColor"
                aria-hidden="true"
              >
                <rect x="7" y="7" width="10" height="10" rx="2" />
              </svg>
            </button>
            <button
              v-else
              type="submit"
              class="agent-composer__send"
              title="发送（Enter）"
              aria-label="发送消息"
              :disabled="disabled || (!draft.trim() && !pendingAction)"
            >
              <svg viewBox="0 0 24 24" width="17" height="17" fill="none" aria-hidden="true">
                <path
                  d="M4.5 12 19 5.5 14.8 19l-3.1-5.1L4.5 12Z"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linejoin="round"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <div v-if="$slots['composer-below']" class="agent-chat__composer-below">
        <slot name="composer-below" />
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import * as agentApi from '@/api/agent'
import assistantParrotUrl from '@/assets/ip/assistant-parrot.png'
import AgentActionItemsCard from '@/components/AgentActionItemsCard.vue'
import AgentDocCard from '@/components/AgentDocCard.vue'
import AgentReasoningPanel from '@/components/AgentReasoningPanel.vue'
import BriefCard from '@/components/BriefCard.vue'
import ChatFileCard from '@/components/ChatFileCard.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import PolishDiffPanel from '@/components/PolishDiffPanel.vue'
import SummaryCard from '@/components/SummaryCard.vue'
import { clearChatSession, loadChatSession, saveChatSession } from '@/utils/chatSession'
import { formatTime } from '@/utils/datetime'
import { resolveErrorMessage } from '@/utils/errors'
import type {
  ChatTrace,
  ChatTraceStage,
  MaterialBrief,
  PolishSuggestion,
  SummaryStructured,
} from '@/types/chat'
import type {
  AgentActionItemLite,
  AgentBackendMessage,
  AgentChatMessage,
  AgentDocOpenEvent,
  AgentIntentName,
  AgentPendingAction,
  AgentQuickAction,
  AgentQuickTaskHandler,
  AgentReply,
  AgentResultEvent,
  AgentScene,
  AgentSendHandler,
  AgentSendStreamHandler,
  AgentStreamDone,
  AgentTaskHandler,
  AgentTurnOptions,
  MinutesDocMeta,
  QuickTask,
} from '@/types/agent'

const props = withDefaults(
  defineProps<{
    agentName: string
    subtitle?: string
    welcomeTitle?: string
    greeting?: string
    /** 当前会议（Build 模式文件保存到会议资料/本地文件夹时必传） */
    meetingId?: string
    quickActions?: AgentQuickAction[]
    onSend: AgentSendHandler
    /** 快捷任务处理器：quickAction 带 task 时调用，走后端专用实现链 */
    onTask?: AgentTaskHandler
    /**
     * 简单文本任务处理器（quickTask）：页面未启用后端会话时由页面自行调用
     * `/agent/turns` 的 `quick_task` 通道；缺省时按普通对话发送。
     */
    onQuickTask?: AgentQuickTaskHandler
    /**
     * 流式发送处理器（SSE）：非任务对话走增量渲染（meta 来源先渲染、正文逐段追加、
     * 跳过打字动画）；缺省时全部走 onSend 同步链路。
     */
    onSendStream?: AgentSendStreamHandler
    placeholder?: string
    disabled?: boolean
    compact?: boolean
    inputId?: string
    contextText?: string
    /** 是否显示空态欢迎区（标题/问候语/快捷操作卡）；关闭后空态为纯空白 */
    showWelcome?: boolean
    /** 是否显示欢迎区大标题（关闭后仅保留快捷操作卡与问候语） */
    showWelcomeTitle?: boolean
    /** 输入框上方鹦鹉形象（默认内置图，可按页面替换） */
    mascotSrc?: string
    /** 鹦鹉趴在输入框上沿的高度 */
    mascotSize?: string
    /**
     * 本地持久化键（如 `preprocess:mtg_1`）：非空时对话与草稿按该键存取 localStorage，
     * 切页/刷新后恢复；为空则保持纯内存行为。
     */
    storageKey?: string
    /**
     * 后端会话模式：会话、消息与确认门持久化到服务端（`/agent/*`），
     * 加载失败或后端未启用时自动回退到 `storageKey` 的 localStorage 缓存。
     */
    backendSession?: boolean
    /** 后端会话场景（决定默认会话归属与页面先验） */
    agentScene?: AgentScene
    /** 透传给后端单轮的执行选项（模型/模板/模式/检索范围等） */
    agentOptions?: AgentTurnOptions
  }>(),
  {
    subtitle: '',
    welcomeTitle: '',
    greeting: '',
    meetingId: '',
    quickActions: () => [],
    onTask: undefined,
    onQuickTask: undefined,
    onSendStream: undefined,
    placeholder: '描述目标，或选中内容后提问…',
    disabled: false,
    compact: false,
    inputId: 'agent-chat-input',
    contextText: '',
    showWelcome: true,
    showWelcomeTitle: true,
    mascotSrc: assistantParrotUrl,
    mascotSize: '4.5rem',
    storageKey: '',
    backendSession: false,
    agentScene: 'minutes',
    agentOptions: () => ({}),
  },
)

/** 是否请求模型思考模式（推理链）：默认开启，输入框工具栏可手动关闭 */
const thinking = defineModel<boolean>('thinking', { default: true })

const emit = defineEmits<{
  'clear-context': []
  'agent-result': [payload: AgentResultEvent]
  /** 点击会后产出的文件卡/清单卡：由页面在右侧打开查看与编辑 */
  'open-doc': [payload: AgentDocOpenEvent]
}>()

const messages = ref<AgentChatMessage[]>([])
const draft = ref('')
const pending = ref(false)
const errorText = ref('')
const copiedId = ref<number | null>(null)
const listEl = ref<HTMLElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const stickToBottom = ref(true)
/** 待发送的快捷功能标记：点击快捷卡后挂到输入框，随用户输入一起发送 */
const pendingAction = ref<{
  label: string
  task?: string
  intent?: AgentIntentName
  mode?: 'plan' | 'build'
  quickTask?: QuickTask
  prompt: string
} | null>(null)

/* ---------- 后端会话（服务端持久化 + 确认门） ---------- */

/** 当前服务端会话 id；为空表示尚未建立或已回退本地模式 */
const backendSessionId = ref('')
/** 后端可用性：加载失败（未启用/网络异常）后回退 localStorage */
const backendActive = ref(false)
/** 挂载/切会议时的加载去重，避免并发 ensure */
let backendLoadPromise: Promise<void> | null = null

const isBackendMode = computed(() => props.backendSession && backendActive.value)

/* ---------- 输入框装饰：鹦鹉 IP 与快捷任务标记 ---------- */

// 未输入且对话未开始时显示；发送后隐藏，清空对话后恢复
const showMascot = computed(() => messages.value.length === 0 && !draft.value.trim())

const taskChipEl = ref<HTMLElement | null>(null)
const chipIndent = ref(0)
const chipIndentStyle = computed(() =>
  pendingAction.value ? { textIndent: `${chipIndent.value}px` } : undefined,
)

watch(pendingAction, async () => {
  await nextTick()
  // 首行文字按芯片实测宽度让位
  chipIndent.value = taskChipEl.value ? taskChipEl.value.offsetWidth + 6 : 0
})

let messageId = 0
let typingTarget: { message: AgentChatMessage; full: string } | null = null
let typingTimer: ReturnType<typeof setInterval> | null = null
let resolveTyping: (() => void) | null = null
let activeController: AbortController | null = null
let cancelled = false
let copyTimer: ReturnType<typeof setTimeout> | null = null

const isBusy = computed(() => pending.value || messages.value.some((message) => message.streaming))

// 组织化回复的类型守卫：kind 与 structured 独立存储，需要显式收窄
function isMaterialBrief(data: AgentChatMessage['structured']): data is MaterialBrief {
  return (
    data !== undefined &&
    !Array.isArray(data) &&
    typeof data === 'object' &&
    data !== null &&
    'headline' in data
  )
}

function isSummaryStructured(data: AgentChatMessage['structured']): data is SummaryStructured {
  return (
    data !== undefined &&
    !Array.isArray(data) &&
    typeof data === 'object' &&
    data !== null &&
    'conclusion' in data
  )
}

function isPolishSuggestions(data: AgentChatMessage['structured']): data is PolishSuggestion[] {
  return Array.isArray(data)
}

/* ---------- 会后产出：纪要文件卡 / 行动项清单卡 ---------- */

function isMinutesMeta(data: AgentChatMessage['structured']): data is MinutesDocMeta {
  return (
    data !== undefined &&
    !Array.isArray(data) &&
    typeof data === 'object' &&
    data !== null &&
    'minutes_id' in data
  )
}

function minutesMetaOf(data: AgentChatMessage['structured']): MinutesDocMeta | undefined {
  return isMinutesMeta(data) ? data : undefined
}

function isMinutesCard(message: AgentChatMessage): boolean {
  return message.kind === 'minutes' && Boolean(message.file) && isMinutesMeta(message.structured)
}

function actionItemsOf(data: AgentChatMessage['structured']): AgentActionItemLite[] {
  return Array.isArray(data) ? (data as AgentActionItemLite[]) : []
}

function isActionItemsCard(message: AgentChatMessage): boolean {
  return message.kind === 'action_items' && actionItemsOf(message.structured).length > 0
}

interface DocSuggestion {
  label: string
  /** 点击后直接发送的后续提示词 */
  prompt?: string
  /** 点击后在右侧打开产出 */
  open?: boolean
}

function suggestionsFor(message: AgentChatMessage): DocSuggestion[] {
  if (message.kind === 'minutes') {
    return [
      { label: '打开并编辑', open: true },
      {
        label: '提取行动项',
        prompt: '请从会议记录中提取待办任务与行动项，标注责任人和截止时间。',
      },
      { label: '再生成一版', prompt: '请重新生成会议纪要。' },
    ]
  }
  if (message.kind === 'action_items') {
    return [
      { label: '打开确认', open: true },
      { label: '再提取一次', prompt: '请重新提取待办任务与行动项。' },
    ]
  }
  return []
}

function openDoc(message: AgentChatMessage): void {
  emit('open-doc', {
    kind: message.kind === 'action_items' ? 'action_items' : 'minutes',
    meta: minutesMetaOf(message.structured),
  })
}

function runSuggestion(message: AgentChatMessage, suggestion: DocSuggestion): void {
  if (suggestion.open) {
    openDoc(message)
    return
  }
  if (suggestion.prompt) {
    void sendPrompt(suggestion.prompt)
  }
}
const displayWelcomeTitle = computed(
  () => props.welcomeTitle || `使用${props.agentName}处理这场会议`,
)
const trimmedContext = computed(() => {
  const text = props.contextText?.trim() ?? ''
  return text.length > 90 ? `${text.slice(0, 90)}…` : text
})

function nextMessageId(): number {
  return ++messageId
}

function onScroll(): void {
  const el = listEl.value
  if (!el) {
    return
  }
  stickToBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 96
}

function scrollToBottom(force = false): void {
  const el = listEl.value
  if (!el || (!force && !stickToBottom.value)) {
    return
  }
  el.scrollTop = el.scrollHeight
}

function adjustTextarea(): void {
  const el = textareaEl.value
  if (!el) {
    return
  }
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 180)}px`
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && pendingAction.value) {
    pendingAction.value = null
    return
  }
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) {
    return
  }
  event.preventDefault()
  void send()
}

function focusInput(): void {
  void nextTick(() => textareaEl.value?.focus())
}

function setDraft(text: string): void {
  draft.value = text
  void nextTick(() => {
    adjustTextarea()
    focusInput()
  })
}

function clear(): void {
  cancelled = true
  activeController?.abort()
  finishTyping()
  errorText.value = ''
  messages.value = []
  clearChatSession(props.storageKey)
  if (isBackendMode.value && backendSessionId.value) {
    const previous = backendSessionId.value
    backendSessionId.value = ''
    void agentApi
      .deleteSession(previous)
      .catch(() => undefined)
      .then(() => loadBackendSession())
  }
  void nextTick(focusInput)
}

onBeforeUnmount(() => {
  activeController?.abort()
  finishTyping()
})

async function copy(message: AgentChatMessage): Promise<void> {
  try {
    await navigator.clipboard.writeText(message.content)
    copiedId.value = message.id
    if (copyTimer) {
      clearTimeout(copyTimer)
    }
    copyTimer = setTimeout(() => {
      copiedId.value = null
    }, 1600)
  } catch {
    copiedId.value = null
  }
}

function finishTyping(): void {
  if (typingTimer) {
    clearInterval(typingTimer)
    typingTimer = null
  }
  typingTarget = null
  const resolve = resolveTyping
  resolveTyping = null
  resolve?.()
}

function stop(): void {
  cancelled = true
  activeController?.abort()
  if (typingTarget) {
    typingTarget.message.content = typingTarget.full
    typingTarget.message.streaming = false
    typingTarget.message.note = '输出已停止'
    typingTarget.message.stopped = true
    finalizeReasoning(typingTarget.message)
  }
  finishTyping()
  const waiting = messages.value.find((message) => message.streaming)
  if (waiting) {
    waiting.streaming = false
    finalizeReasoning(waiting)
    if (!waiting.content) {
      waiting.content = '正在停止生成…'
    }
  }
}

function typeReply(message: AgentChatMessage, full: string): Promise<void> {
  return new Promise((resolve) => {
    const reduceMotion =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches

    if (reduceMotion || full.length <= 60) {
      message.content = full
      message.streaming = false
      scrollToBottom()
      resolve()
      return
    }

    typingTarget = { message, full }
    resolveTyping = resolve
    const chunk = Math.max(1, Math.ceil(full.length / 50))
    let visible = 0

    const tick = (): void => {
      if (cancelled) {
        message.content = full
        message.streaming = false
        finishTyping()
        return
      }
      visible = Math.min(full.length, visible + chunk)
      message.content = full.slice(0, visible)
      scrollToBottom()
      if (visible < full.length) {
        return
      }
      message.streaming = false
      finishTyping()
    }

    typingTimer = setInterval(tick, 24)
    tick()
  })
}

/** 停止生成时的正文处理：保留已流出的部分正文，仅占位文本替换为「已停止生成。」 */
function applyStoppedContent(message: AgentChatMessage): void {
  if (!message.content || message.content.includes('正在停止生成')) {
    message.content = '已停止生成。'
  }
}

/** 结构化回复不做逐字动画，直接渲染卡片 */
function applyStructured(message: AgentChatMessage, reply: AgentReply): void {
  message.kind = reply.kind
  message.structured = reply.structured
  message.content = reply.content
  message.streaming = false
  scrollToBottom()
}

/* ---------- 思考过程（推理链）：原生推理 + 真实执行步骤 ---------- */

function hasTrace(message: AgentChatMessage): boolean {
  return Boolean(message.reasoning || (message.trace && message.trace.length > 0))
}

function isReasoningLive(message: AgentChatMessage): boolean {
  return Boolean(message.streaming && !message.reasoningDone)
}

/** 合并服务端下发的执行步骤（按 id 覆盖状态与细节） */
function upsertStage(message: AgentChatMessage, stage: ChatTraceStage): void {
  const trace = message.trace ?? (message.trace = [])
  const existing = trace.find((item) => item.id === stage.id)
  if (existing) {
    existing.status = stage.status
    if (stage.detail !== undefined) {
      existing.detail = stage.detail
    }
    if (stage.label) {
      existing.label = stage.label
    }
    return
  }
  trace.push({ ...stage })
}

/** 收敛执行步骤：running → done / error（done 帧与错误路径统一调用） */
function finishTrace(
  message: AgentChatMessage,
  status: 'done' | 'error' = 'done',
): void {
  for (const stage of message.trace ?? []) {
    if (stage.status === 'running') {
      stage.status = status
    }
  }
}

function applyTrace(message: AgentChatMessage, trace?: ChatTrace): void {
  if (!trace || !trace.stages?.length) {
    return
  }
  for (const stage of trace.stages) {
    upsertStage(message, stage)
  }
  message.nativeReasoning = trace.native_reasoning
  openReasoning(message)
}

function openReasoning(message: AgentChatMessage): void {
  if (!message.reasoningPinned) {
    message.reasoningOpen = true
  }
}

function closeReasoning(message: AgentChatMessage): void {
  if (!message.reasoningPinned) {
    message.reasoningOpen = false
  }
}

function toggleReasoning(message: AgentChatMessage): void {
  message.reasoningOpen = !message.reasoningOpen
  // 手动展开/折叠后不再被自动折叠覆盖
  message.reasoningPinned = true
}

function reasoningSeconds(message: AgentChatMessage): number {
  const ms =
    message.reasoningDurationMs ??
    (message.reasoningStartedAt ? Date.now() - message.reasoningStartedAt : 0)
  return Math.max(0, ms) / 1000
}

function reasoningLabel(message: AgentChatMessage): string {
  if (isReasoningLive(message)) {
    const seconds = reasoningSeconds(message)
    return seconds >= 1 ? `思考中 · ${seconds.toFixed(1)} 秒` : '思考中…'
  }
  if (message.reasoningDurationMs) {
    const prefix = message.reasoning ? '已思考' : '执行过程'
    const seconds = reasoningSeconds(message)
    const duration = seconds < 1 ? '不到 1 秒' : `${seconds.toFixed(1)} 秒`
    return `${prefix} ${duration}`
  }
  return '思考过程'
}

function reasoningHint(message: AgentChatMessage): string {
  if (message.reasoning) {
    return ''
  }
  if (message.nativeReasoning === false) {
    return '当前模型未返回内部推理，以上为本次回答的实际执行步骤。'
  }
  return '以上为本次回答的实际执行步骤。'
}

/** 收尾：标记思考完成、计算耗时、正文开始后折叠（手动展开过则保持） */
function finalizeReasoning(
  message: AgentChatMessage,
  status: 'done' | 'error' = 'done',
): void {
  message.reasoningDone = true
  finishTrace(message, status)
  if (!message.reasoningDurationMs && message.reasoningStartedAt) {
    message.reasoningDurationMs = Date.now() - message.reasoningStartedAt
  }
  if (status === 'done') {
    closeReasoning(message)
  }
}

/** 正文首个增量到达：思考阶段结束，执行步骤收敛、面板自动折叠 */
function onFirstContent(message: AgentChatMessage): void {
  message.reasoningDone = true
  if (!message.reasoningDurationMs && message.reasoningStartedAt) {
    message.reasoningDurationMs = Date.now() - message.reasoningStartedAt
  }
  finishTrace(message)
  closeReasoning(message)
}

/* ---------- 后端会话：映射、加载与单轮 ---------- */

function toAgentSource(source: {
  origin?: string
  title?: string | null
  document_name?: string | null
  material_id?: string | null
  record_id?: string | null
  meeting_id?: string | null
  excerpt?: string
}): { label: string; detail?: string } {
  let label = '来源'
  if (source.origin === 'web') {
    label = source.title ? `联网 · ${source.title}` : '联网检索'
  } else if (source.document_name) {
    label = source.document_name
  } else if (source.material_id) {
    label = '会议资料'
  } else if (source.record_id) {
    label = '会议记录'
  } else if (source.meeting_id) {
    label = '会议上下文'
  }
  const detail = source.excerpt?.replace(/\s+/g, ' ').slice(0, 64)
  return detail ? { label, detail } : { label }
}

function toChatMessage(message: AgentBackendMessage): AgentChatMessage {
  const role = message.role === 'user' ? 'user' : 'assistant'
  const meta = message.meta ?? {}
  const reasoning = typeof meta.reasoning === 'string' ? meta.reasoning : undefined
  const trace = Array.isArray(meta.trace)
    ? (meta.trace as ChatTraceStage[])
    : undefined
  return {
    id: nextMessageId(),
    role,
    content: message.content,
    createdAt: Date.parse(message.created_at) || Date.now(),
    streaming: false,
    sources: message.sources?.length ? message.sources.map(toAgentSource) : undefined,
    file: message.file ?? undefined,
    kind: message.kind ?? undefined,
    structured: (message.structured as AgentChatMessage['structured']) ?? undefined,
    error: message.status === 'failed' || undefined,
    // 历史消息：思考过程默认折叠，耗时与推理文本来自 meta
    reasoning,
    reasoningDone: role === 'assistant',
    reasoningDurationMs:
      typeof meta.reasoning_ms === 'number' ? meta.reasoning_ms : undefined,
    reasoningOpen: false,
    reasoningPinned: false,
    trace,
    nativeReasoning: reasoning ? true : undefined,
  }
}

/** 服务端历史 + 待确认动作 → 组件消息（确认门挂到对应助手消息） */
function applyBackendHistory(
  history: AgentBackendMessage[],
  actions: AgentPendingAction[],
): void {
  const pendingByMessage = new Map<AgentChatMessage, string>()
  const mapped = history.map((item) => {
    const message = toChatMessage(item)
    const pendingId = item.meta?.pending_action_id
    if (typeof pendingId === 'string') {
      pendingByMessage.set(message, pendingId)
    }
    return message
  })

  for (const action of actions) {
    const target = [...pendingByMessage.entries()].find(([, id]) => id === action.action_id)?.[0]
    if (target) {
      target.pendingAction = action
      continue
    }
    // 历史消息缺少关联（如运行中断）：补一条提示消息承载确认门
    mapped.push({
      id: nextMessageId(),
      role: 'assistant',
      content: action.question,
      createdAt: Date.parse(action.created_at) || Date.now(),
      streaming: false,
      pendingAction: action,
    })
  }

  messages.value = mapped
  stickToBottom.value = true
  void nextTick(() => scrollToBottom(true))
}

function isResourceNotFound(caught: unknown): boolean {
  return (
    typeof caught === 'object' &&
    caught !== null &&
    'error_code' in caught &&
    (caught as { error_code: unknown }).error_code === 'RESOURCE_NOT_FOUND'
  )
}

/** 建立/恢复服务端会话并加载历史与确认门；失败回退 localStorage 缓存 */
function loadBackendSession(): Promise<void> {
  if (!props.backendSession) {
    return Promise.resolve()
  }
  if (backendLoadPromise) {
    return backendLoadPromise
  }
  backendLoadPromise = (async () => {
    try {
      const session = await agentApi.ensureSession({
        scene: props.agentScene,
        meeting_id: props.meetingId || undefined,
      })
      backendSessionId.value = session.session_id
      const [history, actions] = await Promise.all([
        agentApi.listMessages(session.session_id),
        agentApi.listPendingActions(session.session_id),
      ])
      applyBackendHistory(history, actions)
      backendActive.value = true
      errorText.value = ''
    } catch (caught) {
      backendActive.value = false
      backendSessionId.value = ''
      restoreSession()
      if (!isResourceNotFound(caught)) {
        errorText.value = resolveErrorMessage(caught, '会话加载失败，已回退本地缓存。')
      }
    } finally {
      backendLoadPromise = null
    }
  })()
  return backendLoadPromise
}

/** 后端单轮：SSE 增量渲染 + 确认门/业务结果回传 */
async function runBackendTurn(
  text: string,
  signal: AbortSignal,
  assistant: AgentChatMessage,
  options?: {
    intent?: AgentIntentName
    mode?: 'plan' | 'build'
    quickTask?: QuickTask
  },
): Promise<{ reply: AgentReply; done: AgentStreamDone }> {
  if (!backendSessionId.value) {
    await loadBackendSession()
  }
  let streamed = ''
  let pendingFromStream: AgentPendingAction | undefined

  const turnOptions: AgentTurnOptions = { ...props.agentOptions, thinking: thinking.value }
  if (options?.mode) {
    turnOptions.mode = options.mode
  }
  if (options?.quickTask) {
    turnOptions.quick_task = options.quickTask
  }

  const done = await agentApi.streamAgentTurn(
    {
      session_id: backendSessionId.value || undefined,
      meeting_id: props.meetingId || undefined,
      scene: props.agentScene,
      message: text,
      intent: options?.intent,
      options: turnOptions,
    },
    {
      signal,
      onMeta: (meta) => {
        assistant.sources = meta.sources.map(toAgentSource)
        if (thinking.value) {
          applyTrace(assistant, meta.trace)
        }
      },
      onReasoning: (chunk) => {
        if (!thinking.value) {
          return
        }
        assistant.reasoning = (assistant.reasoning ?? '') + chunk
        openReasoning(assistant)
        scrollToBottom()
      },
      onDelta: (chunk) => {
        const first = streamed.length === 0
        streamed += chunk
        assistant.content = streamed
        if (first) {
          onFirstContent(assistant)
        }
        scrollToBottom()
      },
      onPendingAction: (action) => {
        pendingFromStream = action
      },
    },
  )

  backendSessionId.value = done.session_id
  if (pendingFromStream) {
    assistant.pendingAction = pendingFromStream
  }
  // done 兜底：推理增量丢失时补齐全文与耗时
  if (thinking.value) {
    if (!assistant.reasoning && done.reply.reasoning) {
      assistant.reasoning = done.reply.reasoning
    }
    if (done.reply.reasoning_ms) {
      assistant.reasoningDurationMs = done.reply.reasoning_ms
    }
  }
  const reply: AgentReply = {
    content: done.reply.content,
    kind: (done.reply.kind as AgentReply['kind']) ?? undefined,
    structured: (done.reply.structured as AgentReply['structured']) ?? undefined,
    sources: done.reply.sources.map(toAgentSource),
    note: done.reply.note ?? undefined,
    file: done.reply.file ?? undefined,
    reasoning: done.reply.reasoning ?? undefined,
    reasoningMs: done.reply.reasoning_ms ?? undefined,
    trace: done.reply.trace ?? undefined,
  }
  return { reply, done }
}

function approveLabel(action: AgentPendingAction): string {
  if (action.action_type === 'web_search') {
    return '联网检索'
  }
  return '允许执行'
}

function pendingStatusText(status: string): string {
  if (status === 'approved') {
    return '已批准，正在继续执行。'
  }
  if (status === 'rejected') {
    return '已取消该操作。'
  }
  return '该操作已过期，请重新发起。'
}

/** 确认门：批准继续工作流 / 拒绝取消；结果追加为新的助手消息 */
async function decidePending(message: AgentChatMessage, approve: boolean): Promise<void> {
  const action = message.pendingAction
  if (!action || action.status !== 'pending' || message.pendingDeciding) {
    return
  }
  message.pendingDeciding = true
  try {
    const result = approve
      ? await agentApi.approvePendingAction(action.action_id)
      : await agentApi.rejectPendingAction(action.action_id)
    message.pendingAction = {
      ...action,
      status: approve ? 'approved' : 'rejected',
      decided_at: new Date().toISOString(),
    }
    if (result.session_id) {
      backendSessionId.value = result.session_id
    }
    if (result.assistant_message) {
      messages.value.push(toChatMessage(result.assistant_message))
      stickToBottom.value = true
      void nextTick(() => scrollToBottom(true))
    }
    emit('agent-result', {
      sessionId: result.session_id,
      intent: result.intent,
      result: undefined,
    })
  } catch (caught) {
    message.note = resolveErrorMessage(caught, '处理确认失败，请重试。')
    message.statusNote = true
  } finally {
    message.pendingDeciding = false
  }
}

async function runTurn(
  text: string,
  context: string | undefined,
  pushUser: boolean,
  options?: {
    task?: string
    intent?: AgentIntentName
    mode?: 'plan' | 'build'
    quickTask?: QuickTask
    displayText?: string
  },
): Promise<void> {
  const value = text.trim()
  // 快捷任务允许空输入（仅按设计好的提示词执行）
  if (
    (!value && !options?.task && !options?.quickTask) ||
    props.disabled ||
    isBusy.value
  ) {
    return
  }

  cancelled = false
  errorText.value = ''

  if (pushUser) {
    messages.value.push({
      id: nextMessageId(),
      role: 'user',
      content: options?.displayText ?? value,
      context: context || undefined,
      streaming: false,
      createdAt: Date.now(),
    })
    stickToBottom.value = true
    void nextTick(() => scrollToBottom(true))
  }

  messages.value.push({
    id: nextMessageId(),
    role: 'assistant',
    content: '',
    streaming: true,
    regenerateText: value,
    task: options?.task,
    intent: options?.intent,
    mode: options?.mode,
    quickTask: options?.quickTask,
    createdAt: Date.now(),
    // 思考过程（推理链）：随流式回调逐步填充，正文开始后自动折叠
    reasoning: '',
    reasoningDone: false,
    reasoningOpen: false,
    reasoningPinned: false,
    reasoningStartedAt: Date.now(),
    trace: [],
  })
  const assistant = messages.value[messages.value.length - 1] as AgentChatMessage
  stickToBottom.value = true
  void nextTick(() => scrollToBottom(true))
  pending.value = true

  const composed = context ? `${value}\n\n【引用选中内容】\n${context}` : value
  const controller = new AbortController()
  activeController = controller

  try {
    // 快捷任务保持同步实现链；后端会话模式走 Agent SSE；否则沿用页面提供的流式/同步处理器
    const streamHandler = options?.task || options?.quickTask ? undefined : props.onSendStream
    const useBackend = isBackendMode.value && !options?.task
    let normalized: AgentReply | null = null

    if (useBackend) {
      const { reply, done } = await runBackendTurn(
        composed,
        controller.signal,
        assistant,
        options,
      )
      normalized = reply
      pending.value = false
      if (cancelled) {
        assistant.streaming = false
        applyStoppedContent(assistant)
        return
      }
      if (reply.structured) {
        applyStructured(assistant, reply)
      } else if (assistant.content) {
        // SSE 增量已直接写入：跳过打字动画
        assistant.streaming = false
        scrollToBottom()
      } else {
        await typeReply(assistant, reply.content)
      }
      emit('agent-result', {
        sessionId: done.session_id,
        intent: done.intent,
        result: done.reply.result,
      })
    } else if (streamHandler) {
      let streamed = ''
      normalized =
        (await streamHandler(composed, controller.signal, {
          thinking: thinking.value,
          onMeta: (sources, trace) => {
            // meta 先于正文到达：来源标签立即渲染
            assistant.sources = sources
            if (thinking.value) {
              applyTrace(assistant, trace)
            }
          },
          onReasoning: (chunk) => {
            if (!thinking.value) {
              return
            }
            assistant.reasoning = (assistant.reasoning ?? '') + chunk
            openReasoning(assistant)
            scrollToBottom()
          },
          onDelta: (chunk) => {
            const first = streamed.length === 0
            streamed += chunk
            assistant.content = streamed
            if (first) {
              onFirstContent(assistant)
            }
            scrollToBottom()
          },
        })) ?? null
      pending.value = false
      if (cancelled) {
        assistant.streaming = false
        applyStoppedContent(assistant)
        return
      }
      if (streamed) {
        // 增量已直接写入：跳过打字动画
        assistant.streaming = false
        scrollToBottom()
      } else if (normalized?.structured) {
        applyStructured(assistant, normalized)
      } else if (normalized) {
        await typeReply(assistant, normalized.content)
      } else {
        assistant.streaming = false
      }
    } else {
      const reply: AgentReply | string = await (options?.quickTask && props.onQuickTask
        ? props.onQuickTask(options.quickTask, value, controller.signal)
        : options?.task && props.onTask
          ? props.onTask(options.task, value, controller.signal)
          : props.onSend(composed, controller.signal))
      normalized = typeof reply === 'string' ? { content: reply } : reply
      pending.value = false
      if (cancelled) {
        assistant.streaming = false
        applyStoppedContent(assistant)
        return
      }
      if (normalized.structured) {
        applyStructured(assistant, normalized)
      } else {
        await typeReply(assistant, normalized.content)
      }
    }
    if (cancelled) {
      return
    }
    if (normalized) {
      if (normalized.sources !== undefined) {
        assistant.sources = normalized.sources
      }
      assistant.note = normalized.note
      assistant.file = normalized.file
      // done 兜底：增量丢失时补齐推理、耗时与执行步骤
      if (thinking.value && normalized.reasoning && !assistant.reasoning) {
        assistant.reasoning = normalized.reasoning
      }
      if (normalized.reasoningMs && !assistant.reasoningDurationMs) {
        assistant.reasoningDurationMs = normalized.reasoningMs
      }
      if (thinking.value && normalized.trace?.length && !assistant.trace?.length) {
        for (const stage of normalized.trace) {
          upsertStage(assistant, stage)
        }
      }
    }
  } catch (caught) {
    pending.value = false
    assistant.streaming = false
    if (cancelled) {
      applyStoppedContent(assistant)
      assistant.note = '输出已停止'
      assistant.stopped = true
      return
    }
    assistant.error = true
    finishTrace(assistant, 'error')
    const message = resolveErrorMessage(caught, '生成失败，请稍后重试。')
    if (assistant.content) {
      // 流式已输出部分正文：保留原文，错误改以备注提示
      assistant.note = message
    } else {
      assistant.content = message
    }
  } finally {
    // 所有分支（成功/失败/停止）统一收尾思考状态
    finalizeReasoning(assistant, assistant.error ? 'error' : 'done')
    if (activeController === controller) {
      activeController = null
    }
    pending.value = false
  }
}

async function send(): Promise<void> {
  if (props.disabled || isBusy.value) {
    return
  }
  const text = draft.value.trim()

  // 有快捷功能标记：任务模式走 onTask（用户补充作为 instruction）；
  // 提示词模式把设计好的完整提示词与用户补充自动组合后发送（允许空输入）
  if (pendingAction.value) {
    const action = pendingAction.value
    const context = props.contextText?.trim() || undefined
    // 简单文本任务：优先用输入框文字，其次用选中内容作为待处理文本
    if (action.quickTask && !text && !context) {
      errorText.value = '请先选中或输入要处理的文本。'
      return
    }
    pendingAction.value = null
    draft.value = ''
    await nextTick(adjustTextarea)
    if (context) {
      emit('clear-context')
    }
    const displayText = text ? `#${action.label} ${text}` : `#${action.label}`
    if (action.task && props.onTask) {
      await runTurn(text, context, true, { task: action.task, displayText })
    } else if (action.quickTask) {
      await runTurn(text || context || '', undefined, true, {
        quickTask: action.quickTask,
        intent: action.intent,
        mode: action.mode,
        displayText,
      })
    } else {
      const composed = text ? `${action.prompt}\n\n用户补充：${text}` : action.prompt
      await runTurn(composed, context, true, {
        displayText,
        intent: action.intent,
        mode: action.mode,
      })
    }
    return
  }

  if (!text) {
    return
  }
  const context = props.contextText?.trim() || undefined
  draft.value = ''
  await nextTick(adjustTextarea)
  if (context) {
    emit('clear-context')
  }
  await runTurn(text, context, true)
}

async function sendPrompt(prompt: string): Promise<void> {
  if (isBusy.value || props.disabled) {
    return
  }
  const context = props.contextText?.trim() || undefined
  if (context) {
    emit('clear-context')
  }
  await runTurn(prompt, context, true)
}

async function sendTask(task: string, prompt: string, displayText?: string): Promise<void> {
  if (isBusy.value || props.disabled) {
    return
  }
  const context = props.contextText?.trim() || undefined
  if (context) {
    emit('clear-context')
  }
  await runTurn(prompt, context, true, { task, displayText })
}

function runStarter(action: AgentQuickAction): void {
  // 有专用实现链或需要选中文本的动作：挂载标记，等用户补充/确认后发送
  if (action.quickTask || (action.task && props.onTask)) {
    pendingAction.value = action
    focusInput()
    return
  }
  const context = props.contextText?.trim() || undefined
  if (context) {
    emit('clear-context')
  }
  if (action.intent || action.mode) {
    void runTurn(action.prompt, context, true, {
      intent: action.intent,
      mode: action.mode,
      displayText: action.label,
    })
    return
  }
  void sendPrompt(action.prompt)
}

async function regenerate(index: number): Promise<void> {
  if (isBusy.value || props.disabled) {
    return
  }
  const target = messages.value[index]
  if (target?.regenerateText === undefined || target?.regenerateText === null) {
    return
  }
  const previousUser = [...messages.value.slice(0, index)]
    .reverse()
    .find((message) => message.role === 'user')
  messages.value.splice(index, 1)
  await runTurn(target.regenerateText, previousUser?.context, false, {
    task: target.task,
    intent: target.intent,
    mode: target.mode,
    quickTask: target.quickTask,
  })
}

/* ---------- 对话持久化（按 storageKey 存取 localStorage，切页/刷新后恢复） ---------- */

let saveTimer: ReturnType<typeof setTimeout> | null = null

/** 恢复会话；无存档时清空为新会话，消息 id 计数器抬到已恢复最大值之上，避免 :key 冲突 */
function restoreSession(): void {
  const session = props.storageKey ? loadChatSession(props.storageKey) : null
  if (!session) {
    messages.value = []
    draft.value = ''
    return
  }
  messages.value = session.messages
  draft.value = session.draft
  const maxId = session.messages.reduce((max, message) => Math.max(max, message.id), 0)
  if (maxId >= messageId) {
    messageId = maxId
  }
  stickToBottom.value = true
  void nextTick(() => scrollToBottom(true))
}

function persistSession(immediate = false): void {
  if (!props.storageKey) {
    return
  }
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  const writeNow = (): void => {
    saveTimer = null
    saveChatSession(props.storageKey, { draft: draft.value, messages: messages.value })
  }
  if (immediate) {
    writeNow()
  } else {
    saveTimer = setTimeout(writeNow, 300)
  }
}

// 换会议/换页面/切换模式：中断当前流式并切换到目标会话
watch(
  [() => props.storageKey, () => props.meetingId, () => props.backendSession],
  () => {
    cancelled = true
    activeController?.abort()
    finishTyping()
    pending.value = false
    errorText.value = ''
    backendSessionId.value = ''
    backendActive.value = false
    if (props.backendSession) {
      void loadBackendSession()
    } else if (props.storageKey) {
      restoreSession()
    }
  },
)

watch(
  [messages, draft],
  () => {
    persistSession()
  },
  { deep: true },
)

onMounted(() => {
  adjustTextarea()
  if (props.backendSession) {
    void loadBackendSession()
  } else {
    restoreSession()
  }
})

onBeforeUnmount(() => {
  // 离开页面前把最后一版对话落盘
  persistSession(true)
})

/** 挂载快捷功能标记（供外部快捷按钮调用）：task 模式走 onTask 专用链，否则按设计好的提示词组合发送 */
function setPendingQuickAction(action: {
  label: string
  task?: string
  intent?: AgentIntentName
  mode?: 'plan' | 'build'
  quickTask?: QuickTask
  prompt: string
}): void {
  pendingAction.value = action
  focusInput()
}

defineExpose({ sendPrompt, sendTask, setPendingQuickAction, setDraft, focusInput, clear })
</script>

<style scoped>
.agent-chat {
  display: flex;
  flex-direction: column;
  min-height: 32rem;
  height: 100%;
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.agent-chat--compact {
  min-height: 24rem;
}

.agent-chat__header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.agent-chat__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 2rem;
  height: 2rem;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: var(--radius-md);
}

.agent-chat__identity {
  flex: 1;
  min-width: 0;
}

.agent-chat__name {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 650;
}

.agent-chat__subtitle {
  margin: 1px 0 0;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-chat__header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.agent-chat__clear {
  padding: 4px 8px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.75rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.agent-chat__clear:hover {
  color: var(--color-foreground);
  background: var(--color-surface-muted);
  border-color: var(--color-border);
}

/* 空对话：用任务简报替代欢迎气泡 */
.agent-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--space-5);
  padding: var(--space-6);
  overflow-y: auto;
}

.agent-welcome__intro {
  max-width: 42rem;
}

.agent-welcome__title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.25;
}

.agent-welcome__text {
  margin-top: var(--space-2);
  max-width: 38rem;
  color: var(--color-muted-foreground);
}

.agent-welcome__text :deep(p) {
  margin: 0;
}

.agent-welcome__text :deep(ul),
.agent-welcome__text :deep(ol) {
  margin: var(--space-2) 0 0;
}

.agent-welcome__text :deep(li) {
  margin: 2px 0;
}

.agent-welcome__starters {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
  max-width: 42rem;
}

.agent-welcome__extra {
  width: 100%;
  max-width: 46rem;
}

.agent-starter {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-3);
  text-align: left;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    transform var(--transition-fast);
}

.agent-starter:hover:not(:disabled) {
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.28);
  transform: translateY(-1px);
}

.agent-starter:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.agent-starter:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.agent-starter__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.agent-starter__label {
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 650;
}

.agent-starter__head svg {
  flex: 0 0 auto;
  color: var(--color-primary-strong);
  opacity: 0.72;
}

.agent-starter__prompt {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.agent-chat--compact .agent-welcome {
  padding: var(--space-4);
}

.agent-chat--compact .agent-welcome__title {
  font-size: 1.25rem;
}

.agent-chat--compact .agent-welcome__starters {
  grid-template-columns: minmax(0, 1fr);
}

/* 对话：助手消息以会议记录式时间轴呈现，用户消息右侧对齐 */
.agent-chat__messages {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-5);
  overflow-y: auto;
  scroll-behavior: smooth;
}

.agent-message--assistant {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: var(--space-3);
}

.agent-rail {
  position: relative;
}

.agent-rail::before {
  content: '';
  position: absolute;
  top: 8px;
  bottom: calc(-1 * var(--space-5));
  left: 7px;
  width: 1px;
  background: var(--color-border);
}

.agent-rail__dot {
  position: absolute;
  top: 4px;
  left: 2px;
  width: 11px;
  height: 11px;
  background: var(--color-surface);
  border: 2px solid var(--color-primary);
  border-radius: 50%;
}

.agent-message__body {
  min-width: 0;
  max-width: 52rem;
}

.agent-message__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  min-height: 1.2rem;
  margin-bottom: 4px;
}

.agent-message__name {
  color: var(--color-foreground);
  font-size: 0.75rem;
  font-weight: 650;
}

.agent-message__time {
  color: var(--color-subtle-foreground);
  font-size: 0.6875rem;
  font-variant-numeric: tabular-nums;
}

.agent-message__typing-label {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.agent-message__actions {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.agent-message:hover .agent-message__actions,
.agent-message:focus-within .agent-message__actions {
  opacity: 1;
}

@media (hover: none) {
  .agent-message__actions {
    opacity: 1;
  }
}

.agent-message__action {
  padding: 2px 6px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.6875rem;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.agent-message__action:hover:not(:disabled) {
  color: var(--color-foreground);
  background: var(--color-surface-muted);
  border-color: var(--color-border);
}

.agent-message__action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.agent-message__content {
  color: var(--color-foreground);
}

.agent-message__structured {
  min-width: 0;
}

.agent-message__body--error :deep(.markdown-view) {
  color: var(--color-down);
}

.agent-message__status {
  margin: var(--space-2) 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.agent-message__status--error {
  color: var(--color-down);
}

.agent-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.agent-suggestion {
  height: 1.75rem;
  padding: 0 0.625rem;
  color: var(--color-foreground);
  font-size: 0.75rem;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  cursor: pointer;
}

.agent-suggestion:hover {
  color: var(--color-primary-strong);
  background: var(--color-surface-strong);
}

.agent-message__sources {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.agent-source {
  display: inline-flex;
  flex-direction: column;
  gap: 1px;
  padding: 5px 8px;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.agent-source strong {
  color: var(--color-foreground);
  font-weight: 600;
}

/* 服务端确认门：待批准动作卡片 */
.agent-pending {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px dashed var(--color-border-strong, var(--color-border));
  border-radius: var(--radius-md);
}

.agent-pending__label {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.75rem;
  font-weight: 600;
}

.agent-pending__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.agent-pending__approve,
.agent-pending__reject {
  padding: 5px 12px;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.agent-pending__approve {
  color: #ffffff;
  background: var(--color-primary);
  border: 1px solid var(--color-primary);
}

.agent-pending__reject {
  color: var(--color-muted-foreground);
  background: transparent;
  border: 1px solid var(--color-border);
}

.agent-pending__approve:disabled,
.agent-pending__reject:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.agent-pending__status {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.agent-message--user {
  display: flex;
  justify-content: flex-end;
}

.agent-user {
  max-width: min(36rem, 82%);
  padding: var(--space-2) var(--space-3);
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.16);
  border-radius: var(--radius-md) var(--radius-md) 4px var(--radius-md);
}

.agent-user__context {
  margin: 0 0 var(--space-2);
  padding: var(--space-2);
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  line-height: 1.55;
  background: rgba(255, 255, 255, 0.7);
  border-left: 2px solid var(--color-primary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.agent-user__text {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.875rem;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.agent-typing {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 1.4rem;
}

.agent-typing span {
  width: 6px;
  height: 6px;
  background: var(--color-primary);
  border-radius: 50%;
  opacity: 0.35;
  animation: agent-bounce 1.1s infinite ease-in-out;
}

.agent-typing span:nth-child(2) {
  animation-delay: 0.15s;
}

.agent-typing span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes agent-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.35;
  }
  30% {
    transform: translateY(-3px);
    opacity: 1;
  }
}

.agent-chat__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}

/* 输入区：一个输入框 + 一个主操作 */
.agent-chat__composer {
  padding: var(--space-3) var(--space-4) var(--space-4);
  border-top: 1px solid var(--color-border);
}

/* 输入框下方的气泡快捷操作行 */
.agent-chat__composer-below {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

/* 快捷任务标记：黄色短框，置于输入框内首行文字前 */
.agent-composer__field {
  position: relative;
  min-width: 0;
}

.agent-task-chip {
  position: absolute;
  top: 0.55rem;
  left: 0;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 1.3rem;
  padding: 0 3px 0 8px;
  background: rgba(250, 204, 21, 0.26);
  border: 1px solid rgba(202, 138, 4, 0.42);
  border-radius: var(--radius-pill);
  white-space: nowrap;
}

.agent-task-chip__tag {
  color: #854d0e;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1;
}

.agent-task-chip__remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 0.95rem;
  height: 0.95rem;
  color: #854d0e;
  font-size: 0.8rem;
  line-height: 1;
  background: transparent;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.agent-task-chip__remove:hover {
  background: rgba(202, 138, 4, 0.2);
}

/* 鹦鹉 IP：趴在输入框上边框中央，未输入时显示 */
.agent-composer__mascot {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  height: 4.5rem;
  width: auto;
  pointer-events: none;
  user-select: none;
}

.agent-context {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  padding: 6px 8px;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.agent-context__label {
  flex: 0 0 auto;
  color: var(--color-primary-strong);
  font-size: 0.6875rem;
  font-weight: 650;
}

.agent-context__text {
  flex: 1;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-context__remove {
  flex: 0 0 auto;
  width: 1.4rem;
  height: 1.4rem;
  color: var(--color-muted-foreground);
  font-size: 1rem;
  line-height: 1;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.agent-context__remove:hover {
  color: var(--color-foreground);
  background: var(--color-surface);
}

.agent-composer {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 6px 8px 6px 12px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.agent-composer:focus-within {
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.agent-composer__input {
  display: block;
  width: 100%;
  min-height: 2.2rem;
  max-height: 11.25rem;
  padding: var(--space-2) 0 var(--space-1);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.875rem;
  line-height: 1.6;
  background: transparent;
  border: 0;
  outline: none;
  resize: none;
}

.agent-composer__input::placeholder {
  color: var(--color-subtle-foreground);
}

.agent-composer__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding-top: 2px;
}

.agent-composer__tools {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

/* 思考过程开关：默认开启，生成中禁用（避免半途状态不一致） */
.agent-thinking-toggle {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 2rem;
  padding: 0 0.625rem;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.6875rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.agent-thinking-toggle:hover:not(:disabled) {
  color: var(--color-foreground);
  border-color: var(--color-border-strong);
}

.agent-thinking-toggle--on {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.35);
}

.agent-thinking-toggle:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.agent-thinking-toggle:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.agent-composer__actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-left: auto;
}

.agent-composer__send,
.agent-composer__stop {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    opacity var(--transition-fast);
}

.agent-composer__send {
  color: #ffffff;
  background: var(--color-primary);
  border: 0;
}

.agent-composer__send:hover:not(:disabled) {
  background: var(--color-primary-strong);
}

.agent-composer__send:disabled {
  color: var(--color-subtle-foreground);
  background: var(--color-surface-muted);
  cursor: not-allowed;
}

.agent-composer__stop {
  color: #b91c1c;
  background: #fff1f2;
  border: 1px solid rgba(220, 38, 38, 0.2);
}

.agent-composer__stop:hover {
  background: #ffe4e6;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 720px) {
  .agent-chat__header {
    padding: var(--space-3);
  }

  .agent-welcome {
    justify-content: flex-start;
    padding: var(--space-4);
  }

  .agent-welcome__title {
    font-size: 1.25rem;
  }

  .agent-welcome__starters {
    grid-template-columns: minmax(0, 1fr);
  }

  .agent-chat__messages {
    padding: var(--space-4) var(--space-3);
  }

  .agent-chat__composer {
    padding: var(--space-3);
  }

  .agent-user {
    max-width: 90%;
  }

  /* 窄屏只保留图标（按钮带 aria-label），为模式/模型选择器让出空间 */
  .agent-thinking-toggle__text {
    display: none;
  }

  .agent-thinking-toggle {
    width: 2.5rem;
    padding: 0;
  }

  .agent-composer__send,
  .agent-composer__stop {
    width: 2.5rem;
    height: 2.5rem;
  }
}
</style>
