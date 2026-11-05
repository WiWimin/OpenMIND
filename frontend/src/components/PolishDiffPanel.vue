<template>
  <div class="polish-panel">
    <p v-if="suggestions.length === 0" class="polish-panel__empty">
      未发现需要修改的口误或识别错误。
    </p>

    <template v-else>
      <p v-if="dismissed" class="polish-panel__empty">已忽略全部修改建议。</p>
      <ul v-else class="polish-panel__list">
        <li v-for="(item, index) in suggestions" :key="index" class="polish-panel__row">
          <input
            v-if="!readonly"
            v-model="checked"
            type="checkbox"
            class="polish-panel__check"
            :value="index"
            :aria-label="`选择建议 ${index + 1}`"
          />
          <div class="polish-panel__body">
            <div class="polish-panel__diff">
              <span class="polish-panel__original">{{ item.original }}</span>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
                <path
                  d="M4 12h15m0 0-5-5m5 5-5 5"
                  stroke="currentColor"
                  stroke-width="1.7"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              <span class="polish-panel__suggested">{{ item.suggested }}</span>
            </div>
            <div class="polish-panel__meta">
              <span v-if="item.location" class="polish-panel__location">定位：{{ item.location }}…</span>
              <span class="polish-panel__reason">{{ item.reason }}</span>
              <span class="polish-panel__confidence" :class="`polish-panel__confidence--${item.confidence}`">
                {{ confidenceLabel(item.confidence) }}
              </span>
            </div>
          </div>
        </li>
      </ul>

      <div class="polish-panel__actions">
        <template v-if="!readonly">
          <AppButton
            size="sm"
            :loading="applying"
            :disabled="checked.length === 0"
            @click="emit('apply', selectedSuggestions)"
          >
            采纳选中（{{ checked.length }}）
          </AppButton>
          <AppButton size="sm" variant="ghost" @click="dismissed = true">忽略全部</AppButton>
        </template>
        <AppButton
          v-if="sourceText"
          size="sm"
          variant="ghost"
          @click="copyRevised"
        >
          复制修订稿
        </AppButton>
      </div>

      <p v-if="readonlyHint" class="polish-panel__hint">{{ readonlyHint }}</p>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import { useToast } from '@/composables/useToast'
import type { PolishSuggestion } from '@/types/chat'

const props = withDefaults(
  defineProps<{
    suggestions: PolishSuggestion[]
    /** 只读模式（录音中或音频不可编辑）：仅展示与复制 */
    readonly?: boolean
    applying?: boolean
    /** 原始转写全文，用于生成/复制修订稿 */
    sourceText?: string
    readonlyHint?: string
  }>(),
  {
    readonly: false,
    applying: false,
    sourceText: '',
    readonlyHint: '',
  },
)

const emit = defineEmits<{
  /** 采纳选中的建议（original → suggested 逐条替换由父级执行） */
  apply: [selected: PolishSuggestion[]]
}>()

const toast = useToast()
const dismissed = ref(false)
// 默认全部勾选，用户可取消
const checked = ref<number[]>(props.suggestions.map((_, index) => index))

const selectedSuggestions = computed(() =>
  props.suggestions.filter((_, index) => checked.value.includes(index)),
)

const CONFIDENCE_LABELS: Record<string, string> = {
  high: '高置信',
  medium: '中置信',
  low: '低置信',
}

function confidenceLabel(confidence: string): string {
  return CONFIDENCE_LABELS[confidence] ?? confidence
}

function revisedText(): string {
  let text = props.sourceText
  for (const item of props.suggestions) {
    if (item.original && item.suggested && text.includes(item.original)) {
      text = text.replace(item.original, item.suggested)
    }
  }
  return text
}

async function copyRevised(): Promise<void> {
  const text = revisedText()
  if (!text || text === props.sourceText) {
    toast.error('未能生成修订稿，请手动修改')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    toast.success('修订稿已复制到剪贴板')
  } catch {
    toast.error('复制失败，请手动选择文本复制')
  }
}
</script>

<style scoped>
.polish-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.polish-panel__empty {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.polish-panel__list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
}

.polish-panel__row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--color-border);
}

.polish-panel__row:last-child {
  border-bottom: 0;
}

.polish-panel__check {
  flex: 0 0 auto;
  width: 1rem;
  height: 1rem;
  margin-top: 0.2rem;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.polish-panel__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.polish-panel__diff {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  font-size: 0.8125rem;
}

.polish-panel__original {
  color: var(--color-muted-foreground);
  text-decoration: line-through;
  overflow-wrap: anywhere;
}

.polish-panel__diff svg {
  color: var(--color-muted-foreground);
  flex: 0 0 auto;
}

.polish-panel__suggested {
  color: #15803d;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.polish-panel__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  font-size: 0.6875rem;
  color: var(--color-muted-foreground);
}

.polish-panel__reason {
  flex: 1;
  min-width: 8rem;
}

.polish-panel__confidence {
  padding: 0.05rem 0.45rem;
  border-radius: var(--radius-pill);
  font-weight: 600;
  white-space: nowrap;
}

.polish-panel__confidence--high {
  color: #15803d;
  background: rgba(34, 197, 94, 0.12);
}

.polish-panel__confidence--medium {
  color: #b45309;
  background: rgba(250, 204, 21, 0.18);
}

.polish-panel__confidence--low {
  color: var(--color-muted-foreground);
  background: var(--color-surface-muted);
}

.polish-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.polish-panel__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}
</style>
