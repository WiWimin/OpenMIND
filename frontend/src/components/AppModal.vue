<template>
  <div v-if="open" class="modal" @click.self="emit('close')">
    <div
      class="modal__panel"
      :class="{ 'modal__panel--overflow-visible': overflowVisible }"
      role="dialog"
      aria-modal="true"
      :aria-label="label || title || undefined"
    >
      <slot name="top" />
      <header v-if="title" class="modal__header">
        <h2 class="modal__title">{{ title }}</h2>
        <button class="modal__close" type="button" aria-label="关闭" @click="emit('close')">
          ×
        </button>
      </header>

      <div class="modal__body">
        <slot />
      </div>

      <footer v-if="$slots.footer" class="modal__footer">
        <slot name="footer" />
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    open: boolean
    title?: string
    /** 无默认头部时的无障碍名称 */
    label?: string
    /** 面板不裁剪溢出内容（用于顶部装饰性内容探出面板的场景） */
    overflowVisible?: boolean
  }>(),
  {
    title: '',
    label: '',
    overflowVisible: false,
  },
)

const emit = defineEmits<{ close: [] }>()

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    emit('close')
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
    } else {
      document.removeEventListener('keydown', onKeydown)
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-4);
  background: rgba(15, 23, 42, 0.42);
  -webkit-backdrop-filter: blur(6px);
  backdrop-filter: blur(6px);
}

.modal__panel {
  position: relative;
  width: 100%;
  max-width: 30rem;
  max-height: calc(100vh - 2 * var(--space-4));
  overflow: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  animation: modal-rise var(--transition);
}

.modal__panel--overflow-visible {
  overflow: visible;
  max-height: none;
}

@keyframes modal-rise {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.modal__title {
  margin: 0;
  font-size: 1.0625rem;
  font-weight: 600;
}

.modal__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--color-muted-foreground);
  font-size: 1.375rem;
  line-height: 1;
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.modal__close:hover {
  background: var(--color-surface-strong);
  color: var(--color-foreground);
}

.modal__body {
  padding: var(--space-4);
}

.modal__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
}
</style>
