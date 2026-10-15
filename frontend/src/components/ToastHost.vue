<template>
  <div class="toast-host" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="toast" tag="div" class="toast-host__stack">
      <p
        v-for="toast in toasts"
        :key="toast.id"
        class="toast"
        :class="`toast--${toast.tone}`"
        role="status"
      >
        <span class="toast__icon" aria-hidden="true">
          <svg v-if="toast.tone === 'success'" viewBox="0 0 24 24" width="14" height="14" fill="none">
            <path
              d="m6.5 12.5 3.5 3.4 7-7.3"
              stroke="currentColor"
              stroke-width="2.2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="none">
            <path d="M12 7.5v6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" />
            <circle cx="12" cy="16.8" r="1.2" fill="currentColor" />
          </svg>
        </span>
        <span class="toast__text">{{ toast.message }}</span>
      </p>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts } = useToast()
</script>

<style scoped>
.toast-host {
  position: fixed;
  right: var(--space-4);
  bottom: var(--space-4);
  z-index: 60;
  pointer-events: none;
}

.toast-host__stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: flex-end;
}

.toast {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  max-width: 22rem;
  margin: 0;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-md);
  font-size: 0.875rem;
  font-weight: 500;
}

.toast__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  color: #ffffff;
  flex: 0 0 auto;
}

.toast--success {
  border-color: rgba(5, 150, 105, 0.28);
}

.toast--success .toast__icon {
  background: linear-gradient(135deg, #059669, #34d399);
}

.toast--success .toast__text {
  color: #065f46;
}

.toast--error {
  border-color: rgba(225, 29, 72, 0.28);
}

.toast--error .toast__icon {
  background: linear-gradient(135deg, #e11d48, #fb7185);
}

.toast--error .toast__text {
  color: #9f1239;
}

.toast-enter-active,
.toast-leave-active {
  transition:
    opacity var(--transition) ease,
    transform var(--transition) ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.96);
}

.toast-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.98);
}

.toast-leave-active {
  position: absolute;
}
</style>
