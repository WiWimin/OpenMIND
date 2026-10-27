<template>
  <div class="chat-panel">
    <form v-if="!readonly" class="chat-panel__ask" @submit.prevent="ask">
      <FormSelect
        id="chat-scope"
        v-model="scope"
        label="检索范围"
        :options="scopeOptions"
      />
      <FormTextarea
        id="chat-question"
        v-model="question"
        label="向会议提问"
        :rows="2"
        :error="formError"
      />
      <div class="chat-panel__actions">
        <AppButton type="submit" :loading="asking">提问</AppButton>
        <AppButton
          type="button"
          variant="ghost"
          :disabled="turns.length === 0 || asking"
          @click="refill"
        >
          重新提问
        </AppButton>
      </div>
    </form>

    <ErrorMessage v-if="error" :error="error" />

    <p v-if="turns.length === 0" class="chat-panel__hint">
      {{
        readonly
          ? '会议已归档，不能继续发起问答。'
          : '默认检索当前会议材料与最近记录；历史范围只扩展历史材料；个人知识库范围仅检索知识库。'
      }}
    </p>

    <ul class="chat-panel__turns">
      <li v-for="(turn, index) in turns" :key="index" class="chat-turn">
        <p class="chat-turn__question">{{ turn.question }}</p>
        <p class="chat-turn__answer">{{ turn.result.answer }}</p>
        <p v-if="turn.result.insufficient_evidence" class="chat-turn__flag">
          证据不足，回答仅供参考。
        </p>
        <div v-if="turn.result.sources.length" class="chat-turn__sources">
          <SourceRef
            v-for="(source, sourceIndex) in turn.result.sources"
            :key="sourceIndex"
            :excerpt="source.excerpt"
            :reference="sourceReference(source)"
          />
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'

import * as chatApi from '@/api/chat'
import AppButton from '@/components/AppButton.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormSelect from '@/components/FormSelect.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import SourceRef from '@/components/SourceRef.vue'
import type { ChatContextScope, ChatResult, ChatSource } from '@/types/chat'

interface ChatTurn {
  question: string
  result: ChatResult
}

const props = withDefaults(
  defineProps<{ meetingId: string; readonly?: boolean }>(),
  { readonly: false },
)

const scope = ref<ChatContextScope>('current_meeting')
const scopeOptions = [
  { value: 'current_meeting', label: '当前会议' },
  { value: 'current_and_history', label: '当前及历史' },
  { value: 'knowledge_base', label: '个人知识库' },
]
const question = ref('')
const formError = ref('')
const asking = ref(false)
const error = ref<unknown>(null)
const turns = ref<ChatTurn[]>([])

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

async function ask(): Promise<void> {
  const text = question.value.trim()
  if (!text) {
    formError.value = '请输入问题'
    return
  }
  formError.value = ''
  asking.value = true
  error.value = null
  try {
    const result = await chatApi.askMeeting(props.meetingId, {
      question: text,
      context_scope: scope.value,
      include_sources: true,
    })
    turns.value.push({ question: text, result })
    question.value = ''
  } catch (caught) {
    error.value = caught
  } finally {
    asking.value = false
  }
}

function refill(): void {
  const last = turns.value[turns.value.length - 1]
  if (!last) {
    return
  }
  formError.value = ''
  question.value = last.question
  void nextTick(() => {
    document.getElementById('chat-question')?.focus()
  })
}
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.chat-panel__ask {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: stretch;
}

.chat-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.chat-panel__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
}

.chat-panel__turns {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

/* 问答气泡 */
.chat-turn {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.chat-turn__question {
  align-self: flex-end;
  margin: 0;
  max-width: 88%;
  padding: var(--space-2) var(--space-3);
  background: linear-gradient(135deg, var(--color-primary), #4f83e0);
  border-radius: var(--radius-lg) var(--radius-lg) 4px var(--radius-lg);
  color: #ffffff;
  font-size: 0.9rem;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.chat-turn__answer {
  margin: 0;
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) 4px;
  color: var(--color-foreground);
  font-size: 0.9rem;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.chat-turn__flag {
  margin: 0;
  color: var(--color-checking);
  font-size: 0.8125rem;
}

.chat-turn__sources {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding-left: var(--space-1);
}
</style>
