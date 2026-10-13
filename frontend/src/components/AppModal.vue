<template>
  <div v-if="open" class="modal" @click.self="emit('close')">
    <div class="modal__panel" role="dialog" aria-modal="true" :aria-label="title || undefined">
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
  }>(),
  {
    title: '',
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
  background: rgba(19, 78, 74, 0.35);
}

.modal__panel {
  width: 100%;
  max-width: 30rem;
  max-height: calc(100vh - 2 * var(--space-4));
  overflow: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: 0 10px 30px rgba(19, 78, 74, 0.18);
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
  font-size: 1.125rem;
  font-weight: 600;
}

.modal__close {
  border: none;
  background: transparent;
  color: var(--color-muted-foreground);
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
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
