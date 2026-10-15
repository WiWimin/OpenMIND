<template>
  <figure class="source-ref">
    <figcaption class="source-ref__label">
      {{ label }}
      <span v-if="reference" class="source-ref__reference">（{{ reference }}）</span>
    </figcaption>
    <blockquote class="source-ref__excerpt">{{ excerpt }}</blockquote>
  </figure>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    excerpt: string
    label?: string
    reference?: string
  }>(),
  {
    label: '来源',
    reference: '',
  },
)
</script>

<style scoped>
.source-ref {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border-left: 3px solid var(--color-border-strong);
  border-radius: var(--radius-md);
}

.source-ref__label {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.source-ref__excerpt {
  margin: var(--space-1) 0 0;
  color: var(--color-foreground);
  font-size: 0.875rem;
}
</style>
