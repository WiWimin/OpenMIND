<template>
  <span class="status-badge" :class="`status-badge--${tone}`">
    <span class="status-badge__dot" aria-hidden="true" />
    {{ label }}
  </span>
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
  gap: 6px;
  padding: 0 0.6rem;
  border: 1px solid transparent;
  border-radius: var(--radius-pill);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.5rem;
  white-space: nowrap;
}

.status-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 18%, transparent);
}

.status-badge--neutral {
  color: var(--color-muted-foreground);
  background: var(--color-surface-strong);
  border-color: var(--color-border);
}

.status-badge--info {
  color: var(--color-primary-strong);
  background: rgba(59, 111, 212, 0.1);
  border-color: rgba(59, 111, 212, 0.22);
}

.status-badge--success {
  color: var(--color-ok);
  background: rgba(5, 150, 105, 0.1);
  border-color: rgba(5, 150, 105, 0.22);
}

.status-badge--warning {
  color: var(--color-checking);
  background: rgba(217, 119, 6, 0.1);
  border-color: rgba(217, 119, 6, 0.24);
}

.status-badge--danger {
  color: var(--color-down);
  background: rgba(225, 29, 72, 0.1);
  border-color: rgba(225, 29, 72, 0.22);
}
</style>
