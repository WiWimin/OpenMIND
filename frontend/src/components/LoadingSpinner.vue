<template>
  <span
    class="loading-spinner"
    :class="`loading-spinner--${size}`"
    role="status"
    :aria-label="label"
  >
    <span class="loading-spinner__circle" aria-hidden="true" />
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    size?: 'sm' | 'md'
    label?: string
  }>(),
  {
    size: 'md',
    label: '加载中',
  },
)
</script>

<style scoped>
.loading-spinner {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.loading-spinner__circle {
  display: block;
  width: 1.25rem;
  height: 1.25rem;
  border: 2px solid rgba(21, 94, 239, 0.25);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: loading-spinner-spin 0.6s linear infinite;
}

.loading-spinner--sm .loading-spinner__circle {
  width: 0.875rem;
  height: 0.875rem;
}

@keyframes loading-spinner-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
