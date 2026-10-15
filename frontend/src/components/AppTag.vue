<template>
  <span class="app-tag" :title="title">
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string
    title?: string
  }>(),
  {
    label: '',
    title: '',
  },
)
</script>

<style scoped>
.app-tag {
  display: inline-flex;
  align-items: center;
  padding: 0 0.6rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  font-weight: 500;
  line-height: 1.5rem;
  white-space: nowrap;
}
</style>
