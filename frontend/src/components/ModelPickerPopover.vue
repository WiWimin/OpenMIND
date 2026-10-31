<template>
  <div ref="rootEl" class="model-picker">
    <button
      type="button"
      class="model-picker__trigger"
      :class="{ 'model-picker__trigger--active': Boolean(selectedModel) }"
      :title="triggerTitle"
      :aria-label="triggerTitle"
      :aria-expanded="open"
      :disabled="disabled"
      @click="toggle"
    >
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
        <path
          d="m12 3 7.5 4.3v9.4L12 21l-7.5-4.3V7.3L12 3Z"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
        <path
          d="M12 12 4.7 7.8M12 12l7.3-4.2M12 12v8.6"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
      </svg>
      <span v-if="selectedModel" class="model-picker__dot" aria-hidden="true" />
    </button>

    <div v-if="open" class="model-picker__panel" role="menu" aria-label="选择对话模型">
      <p class="model-picker__head">对话模型</p>

      <p v-if="loading" class="model-picker__state">正在加载模型配置…</p>
      <p v-else-if="error" class="model-picker__state model-picker__state--error">{{ error }}</p>

      <template v-else>
        <button
          v-for="option in options"
          :key="option.value || 'default'"
          type="button"
          class="model-picker__item"
          :class="{ 'model-picker__item--selected': option.value === selectedModel }"
          role="menuitemradio"
          :aria-checked="option.value === selectedModel"
          @click="choose(option.value)"
        >
          <span class="model-picker__item-main">
            <strong>{{ option.label }}</strong>
            <span v-if="option.hint" class="model-picker__item-hint">{{ option.hint }}</span>
          </span>
          <svg
            v-if="option.value === selectedModel"
            viewBox="0 0 24 24"
            width="14"
            height="14"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M4.5 12.5 9.5 17.5 19.5 6.5"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>

        <p v-if="!hasConfiguredModel" class="model-picker__state">
          尚未配置模型，选择将继续跟随服务端默认路由。
        </p>
      </template>

      <button type="button" class="model-picker__manage" @click="emit('manage')">
        管理模型配置
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { getModelConfig } from '@/api/settings'
import { findPresetByApiBase } from '@/constants/modelProviders'
import type { ModelConfig, ModelPurpose } from '@/types/modelConfig'

const props = withDefaults(defineProps<{ disabled?: boolean; selected?: string }>(), {
  disabled: false,
  selected: '',
})

const emit = defineEmits<{ select: [model: string]; manage: [] }>()

const PURPOSE_LABELS: Record<ModelPurpose, string> = {
  preparation: '会前准备用途',
  chat: '会议问答用途',
  minutes: '纪要生成用途',
  extraction: '信息提取用途',
}

interface ModelOption {
  value: string
  label: string
  hint: string
}

const rootEl = ref<HTMLElement | null>(null)
const open = ref(false)
const loading = ref(false)
const error = ref('')
const config = ref<ModelConfig | null>(null)

const selectedModel = computed(() => props.selected)

const options = computed<ModelOption[]>(() => {
  const list: ModelOption[] = [
    { value: '', label: '默认（按用途路由）', hint: '跟随模型配置中的用途路由' },
  ]
  const seen = new Set<string>()
  const current = config.value
  if (current?.llm_api_base) {
    // 按已保存的 API 地址匹配提供商预设，列出该提供商的常用模型
    const preset = findPresetByApiBase(current.llm_api_base)
    if (preset) {
      for (const model of preset.models) {
        if (seen.has(model)) {
          continue
        }
        seen.add(model)
        list.push({ value: model, label: model, hint: `${preset.name} 推荐` })
      }
    }
  }
  if (current?.llm_model) {
    if (!seen.has(current.llm_model)) {
      list.push({ value: current.llm_model, label: current.llm_model, hint: '默认模型' })
    }
    seen.add(current.llm_model)
  }
  if (current) {
    for (const [purpose, model] of Object.entries(current.llm_purpose_models) as [
      ModelPurpose,
      string,
    ][]) {
      if (!model || seen.has(model)) {
        continue
      }
      seen.add(model)
      list.push({ value: model, label: model, hint: PURPOSE_LABELS[purpose] })
    }
  }
  return list
})

const hasConfiguredModel = computed(() => options.value.length > 1)

const triggerTitle = computed(() =>
  selectedModel.value ? `对话模型：${selectedModel.value}` : '选择对话模型',
)

async function loadConfig(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    config.value = await getModelConfig()
  } catch {
    error.value = '模型配置加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function toggle(): void {
  if (props.disabled) {
    return
  }
  open.value = !open.value
  if (open.value && !config.value && !loading.value) {
    void loadConfig()
  }
}

function choose(value: string): void {
  emit('select', value)
  open.value = false
}

function onDocumentClick(event: MouseEvent): void {
  if (open.value && rootEl.value && !rootEl.value.contains(event.target as Node)) {
    open.value = false
  }
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onDocumentKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onDocumentKeydown)
})
</script>

<style scoped>
.model-picker {
  position: relative;
  display: inline-flex;
}

.model-picker__trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: var(--color-muted-foreground);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: 50%;
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.model-picker__trigger:hover:not(:disabled),
.model-picker__trigger--active {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.28);
}

.model-picker__trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.model-picker__dot {
  position: absolute;
  top: -1px;
  right: -1px;
  width: 0.5rem;
  height: 0.5rem;
  background: var(--color-primary);
  border: 1.5px solid #ffffff;
  border-radius: 50%;
}

.model-picker__panel {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 17rem;
  padding: var(--space-2);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  animation: model-picker-in var(--transition-fast);
}

@keyframes model-picker-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.model-picker__head {
  margin: 0 0 var(--space-1);
  padding: var(--space-1) var(--space-2) 0;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.model-picker__state {
  margin: 0;
  padding: var(--space-2);
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.model-picker__state--error {
  color: var(--color-down);
}

.model-picker__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  padding: 0.45rem var(--space-2);
  color: var(--color-foreground);
  font: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.model-picker__item:hover {
  background: var(--color-surface-muted);
}

.model-picker__item--selected {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.model-picker__item-main {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.model-picker__item-main strong {
  overflow: hidden;
  font-size: 0.8125rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-picker__item-hint {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.model-picker__manage {
  margin-top: var(--space-1);
  padding: var(--space-2);
  color: var(--color-primary-strong);
  font-size: 0.75rem;
  font-weight: 600;
  text-decoration: none;
  border-top: 1px solid var(--color-border);
}

.model-picker__manage:hover {
  text-decoration: underline;
}
</style>
