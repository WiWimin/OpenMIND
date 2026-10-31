<template>
  <div ref="rootEl" class="template-picker">
    <button
      type="button"
      class="template-picker__trigger"
      :class="{ 'template-picker__trigger--active': Boolean(selectedTemplateId) }"
      :title="triggerTitle"
      :aria-label="triggerTitle"
      :aria-expanded="open"
      :disabled="disabled"
      @click="toggle"
    >
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
        <path
          d="M8 4.5h8M8 4.5A1.5 1.5 0 0 0 6.5 6v13A1.5 1.5 0 0 0 8 20.5h8a1.5 1.5 0 0 0 1.5-1.5V6A1.5 1.5 0 0 0 16 4.5"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
        />
        <path
          d="M9 9.5h6M9 13h6M9 16.5h3.5"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
        />
      </svg>
      <span v-if="selectedTemplateId" class="template-picker__dot" aria-hidden="true" />
    </button>

    <div v-if="open" class="template-picker__panel" role="menu" aria-label="选择输出模板">
      <p class="template-picker__head">输出模板</p>

      <p v-if="loading" class="template-picker__state">正在加载模板…</p>
      <p v-else-if="error" class="template-picker__state template-picker__state--error">
        {{ error }}
      </p>

      <template v-else>
        <button
          v-for="option in options"
          :key="option.template_id"
          type="button"
          class="template-picker__item"
          :class="{ 'template-picker__item--selected': option.template_id === selectedTemplateId }"
          role="menuitemradio"
          :aria-checked="option.template_id === selectedTemplateId"
          @click="choose(option.template_id)"
        >
          <span class="template-picker__item-main">
            <strong>{{ option.name }}</strong>
            <span v-if="option.description" class="template-picker__item-hint">
              {{ option.description }}
            </span>
          </span>
          <span class="template-picker__badge" :class="`template-picker__badge--${option.source}`">
            {{ option.source === 'builtin' ? '内置' : '自定义' }}
          </span>
        </button>

        <button
          type="button"
          class="template-picker__item template-picker__item--default"
          role="menuitemradio"
          :aria-checked="selectedTemplateId === ''"
          @click="choose('')"
        >
          <span class="template-picker__item-main">
            <strong>默认结构</strong>
            <span class="template-picker__item-hint">不套用模板，按默认结构生成</span>
          </span>
          <svg
            v-if="selectedTemplateId === ''"
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

      <RouterLink class="template-picker__manage" :to="{ name: ROUTE_NAMES.templateManage }">
        管理模板
      </RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { listTemplates } from '@/api/templates'
import { ROUTE_NAMES } from '@/constants/routeNames'
import type { MeetingTemplate } from '@/types/template'

const props = withDefaults(defineProps<{ disabled?: boolean; selected?: string }>(), {
  disabled: false,
  selected: '',
})

const emit = defineEmits<{ select: [templateId: string] }>()

const rootEl = ref<HTMLElement | null>(null)
const open = ref(false)
const loading = ref(false)
const error = ref('')
const templates = ref<MeetingTemplate[]>([])

const selectedTemplateId = computed(() => props.selected)

const options = computed<MeetingTemplate[]>(() => templates.value)

const triggerTitle = computed(() => {
  if (!selectedTemplateId.value) {
    return '选择输出模板'
  }
  const found = templates.value.find((item) => item.template_id === selectedTemplateId.value)
  return found ? `输出模板：${found.name}` : '选择输出模板'
})

function toggle(): void {
  if (props.disabled) {
    return
  }
  open.value = !open.value
  if (open.value && templates.value.length === 0 && !loading.value) {
    void loadTemplates()
  }
}

async function loadTemplates(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    templates.value = await listTemplates()
  } catch {
    error.value = '模板加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function choose(templateId: string): void {
  emit('select', templateId)
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
.template-picker {
  position: relative;
  display: inline-flex;
}

.template-picker__trigger {
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

.template-picker__trigger:hover:not(:disabled),
.template-picker__trigger--active {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.28);
}

.template-picker__trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.template-picker__dot {
  position: absolute;
  top: -1px;
  right: -1px;
  width: 0.5rem;
  height: 0.5rem;
  background: var(--color-primary);
  border: 1.5px solid #ffffff;
  border-radius: 50%;
}

.template-picker__panel {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  z-index: 40;
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 18rem;
  max-height: 22rem;
  padding: var(--space-2);
  overflow-y: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  animation: template-picker-in var(--transition-fast);
}

@keyframes template-picker-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.template-picker__head {
  margin: 0 0 var(--space-1);
  padding: var(--space-1) var(--space-2) 0;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.template-picker__state {
  margin: 0;
  padding: var(--space-2);
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.template-picker__state--error {
  color: var(--color-down);
}

.template-picker__item {
  display: flex;
  align-items: flex-start;
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

.template-picker__item:hover {
  background: var(--color-surface-muted);
}

.template-picker__item--selected {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.template-picker__item--default {
  border-top: 1px dashed var(--color-border);
  border-radius: 0 0 var(--radius-sm) var(--radius-sm);
}

.template-picker__item-main {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.template-picker__item-main strong {
  font-size: 0.8125rem;
  font-weight: 600;
}

.template-picker__item-hint {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.template-picker__badge {
  flex: 0 0 auto;
  padding: 1px 7px;
  font-size: 0.625rem;
  font-weight: 650;
  border-radius: var(--radius-pill);
}

.template-picker__badge--builtin {
  color: var(--color-accent-strong);
  background: var(--color-accent-soft);
}

.template-picker__badge--custom {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.template-picker__manage {
  margin-top: var(--space-1);
  padding: var(--space-2);
  color: var(--color-primary-strong);
  font-size: 0.75rem;
  font-weight: 600;
  text-decoration: none;
  border-top: 1px solid var(--color-border);
}

.template-picker__manage:hover {
  text-decoration: underline;
}
</style>
