<template>
  <div class="markdown-view" v-html="html" />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ content: string }>()

const html = computed(() => renderMarkdown(props.content))
</script>

<style scoped>
.markdown-view {
  color: var(--color-foreground);
  font-size: 0.875rem;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.markdown-view :deep(> :first-child) {
  margin-top: 0;
}

.markdown-view :deep(> :last-child) {
  margin-bottom: 0;
}

.markdown-view :deep(h1) {
  margin: 1.1em 0 0.55em;
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.markdown-view :deep(h2) {
  margin: 1.05em 0 0.5em;
  padding-bottom: 0.3em;
  font-size: 1.0625rem;
  font-weight: 700;
  border-bottom: 1px solid var(--color-border);
}

.markdown-view :deep(h3) {
  margin: 1em 0 0.45em;
  font-size: 0.9375rem;
  font-weight: 650;
  color: var(--color-primary-strong);
}

.markdown-view :deep(h4) {
  margin: 0.9em 0 0.4em;
  font-size: 0.875rem;
  font-weight: 650;
}

.markdown-view :deep(p) {
  margin: 0.6em 0;
}

.markdown-view :deep(ul),
.markdown-view :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.35em;
}

.markdown-view :deep(li) {
  margin: 0.25em 0;
}

.markdown-view :deep(li::marker) {
  color: var(--color-primary);
}

.markdown-view :deep(strong) {
  font-weight: 650;
  color: var(--color-foreground);
}

.markdown-view :deep(a) {
  color: var(--color-primary-strong);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-view :deep(code) {
  padding: 0.1em 0.35em;
  font-family: var(--font-mono);
  font-size: 0.8125em;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.markdown-view :deep(.md-pre) {
  margin: 0.75em 0;
  padding: var(--space-3);
  overflow-x: auto;
  background: #0f172a;
  border-radius: var(--radius-md);
}

.markdown-view :deep(.md-pre code) {
  padding: 0;
  color: #e2e8f0;
  background: transparent;
  border: 0;
  font-size: 0.8125rem;
  line-height: 1.6;
}

.markdown-view :deep(blockquote) {
  margin: 0.75em 0;
  padding: var(--space-2) var(--space-3);
  color: var(--color-muted-foreground);
  background: var(--color-surface-strong);
  border-left: 3px solid var(--color-primary);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.markdown-view :deep(hr) {
  margin: 1em 0;
  border: 0;
  border-top: 1px solid var(--color-border);
}

.markdown-view :deep(.md-table-wrap) {
  margin: 0.75em 0;
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.markdown-view :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.markdown-view :deep(.md-table th),
.markdown-view :deep(.md-table td) {
  padding: 0.5rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border);
}

.markdown-view :deep(.md-table th) {
  color: var(--color-muted-foreground);
  font-weight: 650;
  background: var(--color-surface-muted);
  white-space: nowrap;
}

.markdown-view :deep(.md-table tr:last-child td) {
  border-bottom: 0;
}

.markdown-view :deep(.md-table tbody tr:hover) {
  background: var(--color-surface-strong);
}
</style>
