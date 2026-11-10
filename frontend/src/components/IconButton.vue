<template>
  <button
    class="icon-button"
    :class="[`icon-button--${tone}`, { 'icon-button--large': large }]"
    type="button"
    :title="label"
    :aria-label="label"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="icon-button__spinner" aria-hidden="true" />
    <NavIcon v-else :name="icon" :size="large ? 18 : size" />
  </button>
</template>

<script setup lang="ts">
import NavIcon from '@/components/NavIcon.vue'

withDefaults(
  defineProps<{
    /** 按钮语义（同时用于 title 提示与 aria-label） */
    icon: string
    label: string
    tone?: 'default' | 'danger' | 'primary'
    size?: number
    /** 与状态选择框同高（2.6rem）的显眼尺寸 */
    large?: boolean
    disabled?: boolean
    loading?: boolean
  }>(),
  {
    tone: 'default',
    size: 16,
    large: false,
    disabled: false,
    loading: false,
  },
)
</script>

<style scoped>
.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  color: var(--color-muted-foreground);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.icon-button--large {
  width: 2.6rem;
  height: 2.6rem;
  border-radius: var(--radius-md);
}

.icon-button:hover:not(:disabled) {
  color: var(--color-primary-strong);
  background: var(--color-surface-strong);
  border-color: var(--color-border);
}

.icon-button:focus-visible {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.icon-button--danger:hover:not(:disabled) {
  color: var(--color-down);
  background: rgba(225, 29, 72, 0.08);
  border-color: rgba(225, 29, 72, 0.24);
}

/* 蓝底显眼变体（新增任务入口） */
.icon-button--primary {
  color: #ffffff;
  background: var(--color-primary);
  border-color: var(--color-primary);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.icon-button--primary:hover:not(:disabled) {
  color: #ffffff;
  background: var(--color-primary-strong);
  border-color: var(--color-primary-strong);
  box-shadow: 0 6px 16px rgba(21, 94, 239, 0.24);
}

.icon-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.icon-button__spinner {
  width: 0.9rem;
  height: 0.9rem;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: icon-button-spin 0.6s linear infinite;
}

@keyframes icon-button-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
