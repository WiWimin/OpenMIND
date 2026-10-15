<template>
  <button
    class="app-button"
    :class="[`app-button--${variant}`, { 'app-button--block': block }]"
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
    disabled?: boolean
    loading?: boolean
    block?: boolean
  }>(),
  {
    type: 'button',
    variant: 'primary',
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
  min-height: 2.5rem;
  padding: var(--space-2) var(--space-4);
  border: 1px solid transparent;
  border-radius: var(--radius-pill);
  font: inherit;
  font-size: 0.9375rem;
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

.app-button--primary {
  color: var(--color-primary-contrast);
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  box-shadow: 0 8px 20px rgba(79, 70, 229, 0.26);
}

.app-button--primary:hover:not(:disabled) {
  box-shadow: 0 12px 26px rgba(79, 70, 229, 0.34);
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
  background: linear-gradient(135deg, #fb7185, #e11d48);
  box-shadow: 0 8px 20px rgba(225, 29, 72, 0.22);
}

.app-button--danger:hover:not(:disabled) {
  box-shadow: 0 12px 26px rgba(225, 29, 72, 0.3);
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
</style>
