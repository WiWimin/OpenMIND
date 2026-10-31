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
      v-if="showWelcome && messages.length === 0 && (welcomeTitle || greeting || quickActions.length)"
      class="agent-welcome"
    >
      <div class="agent-welcome__intro">
        <h2 class="agent-welcome__title">{{ displayWelcomeTitle }}</h2>
        <MarkdownView v-if="greeting" class="agent-welcome__text" :content="greeting" />
      </div>

      <div v-if="quickActions.length" class="agent-welcome__starters">
        <button
          v-for="action in quickActions"
          :key="action.label"
          type="button"
          class="agent-starter"
          :disabled="disabled"
          @click="sendPrompt(action.prompt)"
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
                  v-if="message.regenerateText"
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

            <div
              v-if="!message.content && message.streaming"
              class="agent-typing"
              aria-label="Agent 正在思考"
            >
              <span />
              <span />
              <span />
            </div>
            <MarkdownView v-else class="agent-message__content" :content="message.content" />

            <p v-if="message.note" class="agent-message__note">{{ message.note }}</p>

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
        <textarea
          :id="inputId"
          ref="textareaEl"
          v-model="draft"
          class="agent-composer__input"
          rows="1"
          :placeholder="disabled ? '当前会议不可用' : placeholder"
          :disabled="disabled"
          :aria-label="`向 ${agentName} 发送消息`"
          @keydown="onKeydown"
          @input="adjustTextarea"
        />

        <div class="agent-composer__bar">
          <div v-if="$slots['composer-extra']" class="agent-composer__tools">
            <slot name="composer-extra" />
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
              :disabled="disabled || !draft.trim()"
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import MarkdownView from '@/components/MarkdownView.vue'
import type {
  AgentChatMessage,
  AgentQuickAction,
  AgentReply,
  AgentSendHandler,
} from '@/types/agent'

const props = withDefaults(
  defineProps<{
    agentName: string
    subtitle?: string
    welcomeTitle?: string
    greeting?: string
    quickActions?: AgentQuickAction[]
    onSend: AgentSendHandler
    placeholder?: string
    disabled?: boolean
    compact?: boolean
    inputId?: string
    contextText?: string
    /** 是否显示空态欢迎区（标题/问候语/快捷操作卡）；关闭后空态为纯空白 */
    showWelcome?: boolean
  }>(),
  {
    subtitle: '',
    welcomeTitle: '',
    greeting: '',
    quickActions: () => [],
    placeholder: '描述目标，或选中内容后提问…',
    disabled: false,
    compact: false,
    inputId: 'agent-chat-input',
    contextText: '',
    showWelcome: true,
  },
)

const emit = defineEmits<{ 'clear-context': [] }>()

const messages = ref<AgentChatMessage[]>([])
const draft = ref('')
const pending = ref(false)
const errorText = ref('')
const copiedId = ref<number | null>(null)
const listEl = ref<HTMLElement | null>(null)
const textareaEl = ref<HTMLTextAreaElement | null>(null)
const stickToBottom = ref(true)

let messageId = 0
let typingTarget: { message: AgentChatMessage; full: string } | null = null
let typingTimer: ReturnType<typeof setInterval> | null = null
let resolveTyping: (() => void) | null = null
let activeController: AbortController | null = null
let cancelled = false
let copyTimer: ReturnType<typeof setTimeout> | null = null

const isBusy = computed(() => pending.value || messages.value.some((message) => message.streaming))
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

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
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
  }
  finishTyping()
  const waiting = messages.value.find((message) => message.streaming)
  if (waiting) {
    waiting.streaming = false
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

async function runTurn(
  text: string,
  context: string | undefined,
  pushUser: boolean,
): Promise<void> {
  const value = text.trim()
  if (!value || props.disabled || isBusy.value) {
    return
  }

  cancelled = false
  errorText.value = ''

  if (pushUser) {
    messages.value.push({
      id: nextMessageId(),
      role: 'user',
      content: value,
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
    createdAt: Date.now(),
  })
  const assistant = messages.value[messages.value.length - 1] as AgentChatMessage
  stickToBottom.value = true
  void nextTick(() => scrollToBottom(true))
  pending.value = true

  const composed = context ? `${value}\n\n【引用选中内容】\n${context}` : value
  const controller = new AbortController()
  activeController = controller

  try {
    const reply: AgentReply | string = await props.onSend(composed, controller.signal)
    const normalized: AgentReply = typeof reply === 'string' ? { content: reply } : reply
    pending.value = false
    if (cancelled) {
      assistant.streaming = false
      assistant.content = '已停止生成。'
      return
    }
    await typeReply(assistant, normalized.content)
    if (cancelled) {
      return
    }
    assistant.sources = normalized.sources
    assistant.note = normalized.note
  } catch (caught) {
    pending.value = false
    assistant.streaming = false
    if (cancelled) {
      assistant.content = '已停止生成。'
      assistant.note = '输出已停止'
      return
    }
    assistant.error = true
    assistant.content = caught instanceof Error ? caught.message : '生成失败，请稍后重试。'
  } finally {
    if (activeController === controller) {
      activeController = null
    }
    pending.value = false
  }
}

async function send(): Promise<void> {
  const text = draft.value.trim()
  if (!text || isBusy.value || props.disabled) {
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

async function regenerate(index: number): Promise<void> {
  if (isBusy.value || props.disabled) {
    return
  }
  const target = messages.value[index]
  if (!target?.regenerateText) {
    return
  }
  const previousUser = [...messages.value.slice(0, index)]
    .reverse()
    .find((message) => message.role === 'user')
  messages.value.splice(index, 1)
  await runTurn(target.regenerateText, previousUser?.context, false)
}

onMounted(() => {
  adjustTextarea()
})

defineExpose({ sendPrompt, setDraft, focusInput, clear })
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

.agent-message__body--error :deep(.markdown-view) {
  color: var(--color-down);
}

.agent-message__note {
  margin: var(--space-2) 0 0;
  color: var(--color-checking);
  font-size: 0.75rem;
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

  .agent-composer__send,
  .agent-composer__stop {
    width: 2.5rem;
    height: 2.5rem;
  }
}
</style>
