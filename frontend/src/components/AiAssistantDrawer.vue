<template>
  <div v-if="open" class="ai-drawer-root">
    <div class="ai-drawer-root__backdrop" @click="emit('close')" />

    <aside class="ai-drawer" role="dialog" aria-label="AI 助手">
      <header class="ai-drawer__header">
        <span class="ai-drawer__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
            <path
              d="M12 3.5 13.6 8.4 18.5 10 13.6 11.6 12 16.5 10.4 11.6 5.5 10 10.4 8.4 12 3.5Z"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linejoin="round"
            />
            <path
              d="M18.5 15.5 19.3 17.7 21.5 18.5 19.3 19.3 18.5 21.5 17.7 19.3 15.5 18.5 17.7 17.7 18.5 15.5Z"
              fill="currentColor"
            />
          </svg>
        </span>
        <div class="ai-drawer__heading">
          <p class="ai-drawer__title">AI 助手</p>
          <p class="ai-drawer__subtitle">随时提问，或让我生成纪要草稿</p>
        </div>
        <button type="button" class="ai-drawer__close" aria-label="关闭 AI 助手" @click="emit('close')">
          ×
        </button>
      </header>

      <div class="ai-drawer__capabilities">
        <button
          type="button"
          class="ai-drawer__chip"
          :disabled="generating || asking"
          @click="generateMinutes"
        >
          {{ generating ? '正在生成纪要…' : '生成会议纪要' }}
        </button>
        <p class="ai-drawer__hint">也可以直接输入问题，例如「帮我总结一下今天的讨论」。</p>
      </div>

      <ErrorMessage v-if="error" :error="error" />

      <ul class="ai-drawer__messages">
        <li
          v-for="(turn, index) in turns"
          :key="index"
          class="ai-drawer-message"
          :class="`ai-drawer-message--${turn.role}`"
        >
          <p class="ai-drawer-message__text">{{ turn.text }}</p>
          <p v-if="turn.insufficient" class="ai-drawer-message__flag">证据不足，回答仅供参考。</p>
          <div v-if="turn.sources?.length" class="ai-drawer-message__sources">
            <SourceRef
              v-for="(source, sourceIndex) in turn.sources"
              :key="sourceIndex"
              :excerpt="source.excerpt"
              :reference="sourceReference(source)"
            />
          </div>
        </li>
        <li v-if="asking" class="ai-drawer-message ai-drawer-message--assistant">
          <p class="ai-drawer-message__text ai-drawer-message__text--pending">正在思考…</p>
        </li>
      </ul>

      <form class="ai-drawer__form" @submit.prevent="ask">
        <FormTextarea
          id="ai-drawer-question"
          v-model="question"
          label="向 AI 助手提问"
          :rows="2"
          :error="formError"
          placeholder="例如：帮我生成一下会议纪要"
        />
        <AppButton type="submit" :loading="asking || generating">发送</AppButton>
      </form>
    </aside>

    <AppModal :open="resultOpen" title="AI 生成的纪要草稿" @close="resultOpen = false">
      <RichTextEditor id="ai-drawer-result" v-model="resultDraft" label="纪要内容" />
      <p class="ai-drawer__result-note">
        这是 AI 生成的候选草稿，可直接修改后保存；保存后仍可在「纪要」小节继续编辑或确认。
      </p>
      <ErrorMessage v-if="saveError" :error="saveError" />
      <template #footer>
        <AppButton variant="ghost" @click="resultOpen = false">关闭</AppButton>
        <AppButton :loading="saving" @click="saveDraft">保存草稿</AppButton>
      </template>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

import * as chatApi from '@/api/chat'
import * as minutesApi from '@/api/minutes'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import SourceRef from '@/components/SourceRef.vue'
import { useToast } from '@/composables/useToast'
import type { ChatSource } from '@/types/chat'
import type { Minutes } from '@/types/minutes'
import { isRequestCancelled } from '@/utils/requests'

const props = defineProps<{ open: boolean; meetingId: string }>()
const emit = defineEmits<{ close: []; 'minutes-saved': []; navigate: [tab: string] }>()

const toast = useToast()

interface DrawerTurn {
  role: 'user' | 'assistant'
  text: string
  sources?: ChatSource[]
  insufficient?: boolean
}

const question = ref('')
const formError = ref('')
const asking = ref(false)
const generating = ref(false)
const error = ref<unknown>(null)
const turns = ref<DrawerTurn[]>([])

const resultOpen = ref(false)
const resultDraft = ref('')
const resultMinutes = ref<Minutes | null>(null)
const saving = ref(false)
const saveError = ref<unknown>(null)

function sourceReference(source: ChatSource): string {
  return (
    source.document_name ||
    source.document_id ||
    source.material_id ||
    source.record_id ||
    source.meeting_id ||
    ''
  )
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && !resultOpen.value) {
    emit('close')
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))

const minutesIntent = /纪要/

interface NavIntent {
  test: RegExp
  tab: string
  guide: string
}

const navIntents: NavIntent[] = [
  {
    test: /整理|归纳/,
    tab: 'records',
    guide: '请切到「记录」小节，勾选要整理的讨论记录后点击「AI 整理所选」，结果可修改并另存为记录。',
  },
  {
    test: /行动项|待办/,
    tab: 'minutes',
    guide: '请切到「纪要」小节，在下方「行动项」区域点击「提取行动项」，确认后可转为个人任务。',
  },
  {
    test: /问题|疑问|待确认事项/,
    tab: 'issues',
    guide: '请切到「问题」小节，点击「提取问题」，AI 会从纪要与记录中列出待确认事项。',
  },
  {
    test: /材料|上传|文档/,
    tab: 'materials',
    guide: '请切到「材料」小节，可上传会议相关文档，供会前准备与问答引用。',
  },
  {
    test: /准备|会前/,
    tab: 'preparation',
    guide: '请切到「会前准备」小节，点击「生成会前准备」，AI 会基于已上传材料整理要点。',
  },
  {
    test: /收尾|归档|检查/,
    tab: 'checklist',
    guide: '请切到「收尾」小节，可查看纪要、行动项与问题的处理状态，全部处理完即完成收尾。',
  },
  {
    test: /任务/,
    tab: 'checklist',
    guide: '行动项确认后可在「纪要」小节转为个人任务；个人任务请在左侧导航打开「我的任务」页面查看跟进。',
  },
]

async function ask(): Promise<void> {
  const text = question.value.trim()
  if (!text) {
    formError.value = '请输入问题'
    return
  }
  formError.value = ''
  question.value = ''
  turns.value.push({ role: 'user', text })

  if (minutesIntent.test(text)) {
    await generateMinutes()
    return
  }

  const navIntent = navIntents.find((intent) => intent.test.test(text))
  if (navIntent) {
    turns.value.push({ role: 'assistant', text: navIntent.guide })
    emit('navigate', navIntent.tab)
    return
  }

  asking.value = true
  error.value = null
  try {
    const result = await chatApi.askMeeting(props.meetingId, {
      question: text,
      include_sources: true,
    })
    turns.value.push({
      role: 'assistant',
      text: result.answer,
      sources: result.sources,
      insufficient: result.insufficient_evidence,
    })
  } catch (caught) {
    error.value = caught
  } finally {
    asking.value = false
  }
}

async function generateMinutes(): Promise<void> {
  generating.value = true
  error.value = null
  try {
    const minutes = await minutesApi.generateMinutes(props.meetingId, {
      record_ids: [],
      include_action_items: true,
    })
    resultMinutes.value = minutes
    resultDraft.value = minutes.content
    resultOpen.value = true
    turns.value.push({
      role: 'assistant',
      text: '已生成纪要候选草稿，请在中间面板中查看并修改，保存后可在「纪要」小节继续处理。',
    })
  } catch (caught) {
    if (isRequestCancelled(caught)) {
      turns.value.push({ role: 'assistant', text: '已取消生成。' })
    } else {
      error.value = caught
    }
  } finally {
    generating.value = false
  }
}

async function saveDraft(): Promise<void> {
  if (!resultMinutes.value) {
    return
  }
  saving.value = true
  saveError.value = null
  try {
    await minutesApi.updateMinutes(resultMinutes.value.minutes_id, { content: resultDraft.value })
    resultOpen.value = false
    toast.success('纪要草稿已保存')
    emit('minutes-saved')
  } catch (caught) {
    saveError.value = caught
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.ai-drawer-root {
  position: fixed;
  inset: 0;
  z-index: 90;
}

.ai-drawer-root__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.28);
}

.ai-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  width: min(24rem, 100vw);
  padding: var(--space-4);
  background: rgba(255, 255, 255, 0.92);
  border-left: 1px solid var(--color-border);
  box-shadow: var(--shadow-md);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  animation: ai-drawer-in var(--transition);
}

@keyframes ai-drawer-in {
  from {
    transform: translateX(24px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.ai-drawer__header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
}

.ai-drawer__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.85rem;
  height: 1.85rem;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: var(--radius-sm);
}

.ai-drawer__heading {
  flex: 1;
  min-width: 0;
}

.ai-drawer__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--color-foreground);
}

.ai-drawer__subtitle {
  margin: 2px 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.ai-drawer__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--color-muted-foreground);
  font-size: 1.375rem;
  line-height: 1;
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.ai-drawer__close:hover {
  background: var(--color-surface-strong);
  color: var(--color-foreground);
}

.ai-drawer__capabilities {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: linear-gradient(135deg, rgba(21, 94, 239, 0.07), rgba(20, 184, 166, 0.07));
  border: 1px solid rgba(21, 94, 239, 0.18);
  border-radius: var(--radius-md);
}

.ai-drawer__chip {
  align-self: flex-start;
  padding: 0.4rem 0.9rem;
  color: var(--color-primary-strong);
  font-size: 0.8125rem;
  font-weight: 600;
  font: inherit;
  background: #ffffff;
  border: 1px solid rgba(21, 94, 239, 0.28);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.ai-drawer__chip:hover:not(:disabled) {
  background: rgba(21, 94, 239, 0.08);
}

.ai-drawer__chip:disabled {
  opacity: 0.6;
  cursor: default;
}

.ai-drawer__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.ai-drawer__messages {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.ai-drawer-message {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.ai-drawer-message__text {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  font-size: 0.9rem;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.ai-drawer-message--user {
  align-items: flex-end;
}

.ai-drawer-message--user .ai-drawer-message__text {
  max-width: 88%;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-primary), #155eef);
  border-radius: var(--radius-lg) var(--radius-lg) 4px var(--radius-lg);
  font-weight: 500;
}

.ai-drawer-message--assistant .ai-drawer-message__text {
  color: var(--color-foreground);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px;
}

.ai-drawer-message__text--pending {
  color: var(--color-muted-foreground);
  font-style: italic;
}

.ai-drawer-message__flag {
  margin: 0;
  color: var(--color-checking);
  font-size: 0.8125rem;
}

.ai-drawer-message__sources {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-left: var(--space-1);
}

.ai-drawer__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: stretch;
}

.ai-drawer__result-note {
  margin: var(--space-2) 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

@media (max-width: 600px) {
  .ai-drawer {
    width: 100vw;
  }
}
</style>
