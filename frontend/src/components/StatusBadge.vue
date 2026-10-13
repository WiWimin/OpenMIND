<template>
  <span class="status-badge" :class="`status-badge--${tone}`">{{ label }}</span>
</template>

<script setup lang="ts">
import type { StatusTone } from '@/types/ui'

withDefaults(
  defineProps<{
    label: string
    tone?: StatusTone
  }>(),
  {
    tone: 'neutral',
  },
)
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 0 var(--space-2);
  border: 1px solid currentColor;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
  line-height: 1.5rem;
  white-space: nowrap;
}

.status-badge--neutral {
  color: var(--color-muted-foreground);
}

.status-badge--info {
  color: var(--color-primary-strong);
}

.status-badge--success {
  color: var(--color-ok);
}

.status-badge--warning {
  color: var(--color-checking);
}

.status-badge--danger {
  color: var(--color-down);
}
</style>
