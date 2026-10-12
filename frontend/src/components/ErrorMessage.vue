<template>
  <div v-if="message" class="error-message" role="alert">
    <p class="error-message__text">{{ message }}</p>
    <AppButton v-if="retryable" variant="ghost" @click="emit('retry')">重试</AppButton>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/AppButton.vue'
import { resolveErrorMessage } from '@/utils/errors'

const props = withDefaults(
  defineProps<{
    error?: unknown
    fallback?: string
    retryable?: boolean
  }>(),
  {
    fallback: '操作失败，请稍后重试。',
    retryable: false,
  },
)

const emit = defineEmits<{ retry: [] }>()

const message = computed(() =>
  props.error ? resolveErrorMessage(props.error, props.fallback) : '',
)
</script>

<style scoped>
.error-message {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-down);
  border-radius: var(--radius-sm);
}

.error-message__text {
  margin: 0;
  color: var(--color-down);
  font-size: 0.875rem;
}
</style>
