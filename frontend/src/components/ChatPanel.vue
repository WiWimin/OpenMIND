<template>
  <div class="chat-panel">
    <form class="chat-panel__ask" @submit.prevent="ask">
      <FormTextarea
        id="chat-question"
        v-model="question"
        label="向会议提问"
        :rows="2"
        :error="formError"
      />
      <AppButton type="submit" :loading="asking">提问</AppButton>
    </form>

    <ErrorMessage v-if="error" :error="error" />

    <p v-if="turns.length === 0" class="chat-panel__hint">
      基于本会议的材料与记录进行问答，回答会附来源。
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
import { ref } from 'vue'

import * as chatApi from '@/api/chat'
import AppButton from '@/components/AppButton.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import SourceRef from '@/components/SourceRef.vue'
import type { ChatResult, ChatSource } from '@/types/chat'

interface ChatTurn {
  question: string
  result: ChatResult
}

const props = defineProps<{ meetingId: string }>()

const question = ref('')
const formError = ref('')
const asking = ref(false)
const error = ref<unknown>(null)
const turns = ref<ChatTurn[]>([])

function sourceReference(source: ChatSource): string {
  return source.material_id || source.record_id || source.meeting_id
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
  align-items: flex-start;
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

.chat-turn {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.chat-turn__question {
  margin: 0;
  padding-left: var(--space-3);
  border-left: 3px solid var(--color-border-strong);
  font-weight: 600;
}

.chat-turn__answer {
  margin: 0;
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
}
</style>
