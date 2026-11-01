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
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
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
      <span class="model-picker__label">{{ triggerLabel }}</span>
      <svg
        class="model-picker__chevron"
        :class="{ 'model-picker__chevron--open': open }"
        viewBox="0 0 24 24"
        width="12"
        height="12"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="m6 9 6 6 6-6"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>

    <div v-if="open" class="model-picker__panel" role="dialog" aria-label="选择对话模型">
      <div class="model-picker__toolbar">
        <div class="model-picker__search">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.6" />
            <path
              d="m16 16 4.5 4.5"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
            />
          </svg>
          <input
            ref="searchInputEl"
            v-model="query"
            type="text"
            class="model-picker__search-input"
            placeholder="搜索模型"
            aria-label="搜索模型"
          />
        </div>
        <button
          type="button"
          class="model-picker__add"
          title="添加模型配置"
          aria-label="添加模型配置"
          @click="openConfig"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
            <path
              d="M12 5v14M5 12h14"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            />
          </svg>
        </button>
      </div>

      <div class="model-picker__list">
        <p v-if="loading" class="model-picker__state">正在获取模型列表…</p>
        <p v-else-if="error" class="model-picker__state model-picker__state--error">
          {{ error }}
        </p>
        <template v-else>
          <p v-if="providerError" class="model-picker__state model-picker__state--error">
            {{ providerError }}
          </p>

          <template v-if="providerItems.length">
            <p class="model-picker__group">全部模型</p>
            <button
              v-for="option in providerItems"
              :key="`provider-${option.value}`"
              type="button"
              class="model-picker__item"
              :class="{ 'model-picker__item--selected': option.value === effectiveSelected }"
              role="menuitemradio"
              :aria-checked="option.value === effectiveSelected"
              @click="choose(option.value)"
            >
              <span class="model-picker__item-main">
                <strong>{{ option.label }}</strong>
              </span>
              <svg
                v-if="option.value === effectiveSelected"
                class="model-picker__check"
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
          </template>

          <p v-if="showEmpty" class="model-picker__state">未找到匹配的模型</p>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { getModelConfig, getProviderModels } from '@/api/settings'
import type { ModelConfig } from '@/types/modelConfig'

const props = withDefaults(defineProps<{ disabled?: boolean; selected?: string }>(), {
  disabled: false,
  selected: '',
})

const emit = defineEmits<{ select: [model: string]; manage: [] }>()

interface ModelOption {
  value: string
  label: string
  hint: string
}

const rootEl = ref<HTMLElement | null>(null)
const searchInputEl = ref<HTMLInputElement | null>(null)
const open = ref(false)
const loading = ref(false)
const error = ref('')
const query = ref('')
const config = ref<ModelConfig | null>(null)
const providerModels = ref<string[]>([])
const providerLoading = ref(false)
const providerLoaded = ref(false)
const providerError = ref('')

const selectedModel = computed(() => props.selected)

// 无会话内选择时，默认选中「全部模型」的第一个模型
const effectiveSelected = computed(() => selectedModel.value || providerModels.value[0] || '')

// 触发器展示当前生效模型
const triggerLabel = computed(() => {
  if (effectiveSelected.value) {
    return effectiveSelected.value
  }
  return config.value?.llm_model || '默认模型'
})

const triggerTitle = computed(() => `对话模型：${triggerLabel.value}`)

function matchesQuery(label: string): boolean {
  const q = query.value.trim().toLowerCase()
  return !q || label.toLowerCase().includes(q)
}

const providerItems = computed<ModelOption[]>(() =>
  providerModels.value.filter((model) => matchesQuery(model)).map((model) => ({
    value: model,
    label: model,
    hint: '',
  })),
)

const showEmpty = computed(
  () => !loading.value && !providerItems.value.length,
)

async function loadConfig(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    config.value = await getModelConfig()
    void loadProviderModels()
  } catch {
    error.value = '模型配置加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function loadProviderModels(): Promise<void> {
  if (providerLoading.value || providerLoaded.value) {
    return
  }
  const current = config.value
  if (!current || current.llm_source === 'none' || !current.llm_api_base) {
    return
  }
  providerLoading.value = true
  providerError.value = ''
  try {
    const result = await getProviderModels()
    providerModels.value = result.models
    // 未手动选择过时，默认选中清单第一个模型，保证展示与实际请求一致
    if (!props.selected && result.models.length) {
      emit('select', result.models[0])
    }
  } catch {
    providerError.value = '获取服务商模型列表失败，仅显示项目预设'
  } finally {
    providerLoading.value = false
    providerLoaded.value = true
  }
}

function toggle(): void {
  if (props.disabled) {
    return
  }
  open.value = !open.value
  if (open.value) {
    if (!config.value && !loading.value) {
      void loadConfig()
    }
    void nextTick(() => searchInputEl.value?.focus())
  }
}

function choose(value: string): void {
  emit('select', value)
  open.value = false
}

function openConfig(): void {
  open.value = false
  emit('manage')
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
  // 挂载即加载配置，让选择框直接显示当前默认模型名
  void loadConfig()
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
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 16rem;
  height: 2rem;
  padding: 0 var(--space-2);
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.75rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
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

.model-picker__label {
  overflow: hidden;
  font-weight: 600;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.model-picker__chevron {
  flex: 0 0 auto;
  transition: transform var(--transition-fast);
}

.model-picker__chevron--open {
  transform: rotate(180deg);
}

.model-picker__panel {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  z-index: 60;
  display: flex;
  flex-direction: column;
  width: 22rem;
  max-height: 23rem;
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

.model-picker__toolbar {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-border);
}

.model-picker__search {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 6px;
  min-height: 2.1rem;
  padding: 0 var(--space-2);
  color: var(--color-muted-foreground);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.model-picker__search:focus-within {
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.model-picker__search-input {
  flex: 1;
  min-width: 0;
  min-height: 100%;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.8125rem;
  background: transparent;
  border: 0;
}

.model-picker__search-input:focus {
  outline: none;
}

.model-picker__add {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 2.1rem;
  height: 2.1rem;
  color: var(--color-primary-strong);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.model-picker__add:hover {
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.28);
}

.model-picker__list {
  flex: 1 1 auto;
  overflow-y: auto;
  margin-top: var(--space-1);
}

.model-picker__group {
  margin: var(--space-2) 0 2px;
  padding: 0 var(--space-2);
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

.model-picker__check {
  flex: 0 0 auto;
}
</style>
