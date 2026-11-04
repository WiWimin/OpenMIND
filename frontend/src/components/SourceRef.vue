<template>
  <figure class="source-ref">
    <figcaption class="source-ref__label">
      {{ label }}
      <a
        v-if="url"
        class="source-ref__link"
        :href="url"
        target="_blank"
        rel="noopener noreferrer"
      >{{ reference || url }}</a>
      <span v-else-if="reference" class="source-ref__reference">（{{ reference }}）</span>
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
    /** 联网来源：提供后渲染为可点击链接 */
    url?: string | null
  }>(),
  {
    label: '来源',
    reference: '',
    url: null,
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

.source-ref__link {
  color: var(--color-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
  word-break: break-all;
}

.source-ref__excerpt {
  margin: var(--space-1) 0 0;
  color: var(--color-foreground);
  font-size: 0.875rem;
}
</style>
