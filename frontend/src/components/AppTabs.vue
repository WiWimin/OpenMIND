<template>
  <div class="tabs" role="tablist">
    <button
      v-for="tab in tabs"
      :key="tab.value"
      class="tabs__tab"
      :class="{ 'tabs__tab--active': tab.value === modelValue }"
      type="button"
      role="tab"
      :aria-selected="tab.value === modelValue"
      @click="emit('update:modelValue', tab.value)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { TabItem } from '@/types/ui'

defineProps<{
  tabs: TabItem[]
  modelValue: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<style scoped>
.tabs {
  display: inline-flex;
  gap: 4px;
  max-width: 100%;
  padding: 4px;
  overflow-x: auto;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
}

.tabs__tab {
  padding: 0.45rem 0.95rem;
  border: none;
  border-radius: var(--radius-pill);
  background: transparent;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.tabs__tab:hover {
  color: var(--color-primary-strong);
}

.tabs__tab--active {
  color: var(--color-primary-contrast);
  font-weight: 600;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  box-shadow: 0 6px 16px rgba(59, 111, 212, 0.26);
}
</style>
