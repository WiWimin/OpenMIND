<template>
  <div ref="rootEl" class="mode-picker">
    <button
      type="button"
      class="mode-picker__trigger"
      :class="{ 'mode-picker__trigger--plan': modelValue === 'plan' }"
      :title="triggerTitle"
      :aria-label="triggerTitle"
      :aria-expanded="open"
      :disabled="disabled"
      @click="toggle"
    >
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
        <template v-if="modelValue === 'plan'">
          <rect
            x="5"
            y="3.5"
            width="14"
            height="17"
            rx="2"
            stroke="currentColor"
            stroke-width="1.5"
          />
          <path
            d="M8.5 8h7M8.5 12h7M8.5 16h4"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linecap="round"
          />
        </template>
        <template v-else>
          <path
            d="m14 6.5 3.5 3.5L7 20.5H3.5V17L14 6.5Z"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linejoin="round"
          />
          <path
            d="m12 8.5 3.5 3.5M16.5 4l3.5 3.5-1.8 1.8-3.5-3.5L16.5 4Z"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linejoin="round"
          />
        </template>
      </svg>
      <span class="mode-picker__label">{{ modeLabel }}</span>
      <svg
        class="mode-picker__chevron"
        :class="{ 'mode-picker__chevron--open': open }"
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

    <div v-if="open" class="mode-picker__panel" role="dialog" aria-label="选择对话模式">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="mode-picker__item"
        :class="{ 'mode-picker__item--selected': option.value === modelValue }"
        role="menuitemradio"
        :aria-checked="option.value === modelValue"
        @click="choose(option.value)"
      >
        <span class="mode-picker__item-main">
          <strong>{{ option.label }}</strong>
        </span>
        <svg
          v-if="option.value === modelValue"
          class="mode-picker__check"
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type { ChatMode } from '@/types/chat'

const props = withDefaults(defineProps<{ disabled?: boolean; modelValue?: ChatMode }>(), {
  disabled: false,
  modelValue: 'build',
})

const emit = defineEmits<{ 'update:modelValue': [mode: ChatMode] }>()

interface ModeOption {
  value: ChatMode
  label: string
}

const options: ModeOption[] = [
  { value: 'plan', label: 'Plan' },
  { value: 'build', label: 'Build' },
]

const rootEl = ref<HTMLElement | null>(null)
const open = ref(false)

const modeLabel = computed(() => (props.modelValue === 'plan' ? 'Plan' : 'Build'))
const triggerTitle = computed(() => `对话模式：${modeLabel.value}`)

function toggle(): void {
  if (props.disabled) {
    return
  }
  open.value = !open.value
}

function choose(value: ChatMode): void {
  emit('update:modelValue', value)
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
.mode-picker {
  position: relative;
  display: inline-flex;
}

.mode-picker__trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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

.mode-picker__trigger:hover:not(:disabled),
.mode-picker__trigger--plan {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.28);
}

.mode-picker__trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.mode-picker__label {
  font-weight: 600;
  white-space: nowrap;
}

.mode-picker__chevron {
  flex: 0 0 auto;
  transition: transform var(--transition-fast);
}

.mode-picker__chevron--open {
  transform: rotate(180deg);
}

.mode-picker__panel {
  position: absolute;
  bottom: calc(100% + 10px);
  left: 0;
  z-index: 60;
  display: flex;
  flex-direction: column;
  width: 16rem;
  padding: var(--space-2);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  animation: mode-picker-in var(--transition-fast);
}

@keyframes mode-picker-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.mode-picker__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  padding: 0.5rem var(--space-2);
  color: var(--color-foreground);
  font: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.mode-picker__item:hover {
  background: var(--color-surface-muted);
}

.mode-picker__item--selected {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.mode-picker__item-main {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.mode-picker__item-main strong {
  font-size: 0.8125rem;
  font-weight: 600;
}

.mode-picker__check {
  flex: 0 0 auto;
}
</style>
