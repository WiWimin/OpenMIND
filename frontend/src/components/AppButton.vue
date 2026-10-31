<template>
  <button
    class="app-button"
    :class="[`app-button--${variant}`, `app-button--${size}`, { 'app-button--block': block }]"
    :type="type"
    :disabled="disabled || loading"
  >
    <span v-if="loading" class="app-button__spinner" aria-hidden="true" />
    <span><slot /></span>
  </button>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: 'button' | 'submit' | 'reset'
    variant?: 'primary' | 'ghost' | 'danger'
    size?: 'sm' | 'md'
    disabled?: boolean
    loading?: boolean
    block?: boolean
  }>(),
  {
    type: 'button',
    variant: 'primary',
    size: 'md',
    disabled: false,
    loading: false,
    block: false,
  },
)
</script>

<style scoped>
.app-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  min-height: 2.4rem;
  padding: var(--space-2) var(--space-4);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    color var(--transition-fast),
    transform var(--transition-fast);
}

.app-button:not(:disabled):hover {
  transform: translateY(-1px);
}

.app-button:not(:disabled):active {
  transform: translateY(0);
}

.app-button--block {
  width: 100%;
}

.app-button--sm {
  min-height: 1.9rem;
  padding: 0 var(--space-3);
  font-size: 0.75rem;
  border-radius: var(--radius-sm);
}

.app-button--primary {
  color: var(--color-primary-contrast);
  background: var(--color-primary);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.app-button--primary:hover:not(:disabled) {
  background: var(--color-primary-strong);
  box-shadow: 0 6px 16px rgba(21, 94, 239, 0.24);
}

.app-button--ghost {
  background: var(--color-surface);
  border-color: var(--color-border);
  color: var(--color-foreground);
}

.app-button--ghost:hover:not(:disabled) {
  background: var(--color-surface-strong);
  border-color: var(--color-border-strong);
  color: var(--color-primary-strong);
}

.app-button--danger {
  color: #ffffff;
  background: #dc2626;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.app-button--danger:hover:not(:disabled) {
  background: #b91c1c;
  box-shadow: 0 6px 16px rgba(220, 38, 38, 0.24);
}

.app-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  box-shadow: none;
}

.app-button__spinner {
  width: 1rem;
  height: 1rem;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: app-button-spin 0.6s linear infinite;
}

@keyframes app-button-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .app-button {
    min-height: 2.75rem;
  }
}
</style>
