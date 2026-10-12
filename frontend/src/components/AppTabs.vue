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
  display: flex;
  gap: var(--space-1);
  overflow-x: auto;
  border-bottom: 1px solid var(--color-border);
}

.tabs__tab {
  padding: var(--space-2) var(--space-3);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-muted-foreground);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.tabs__tab:hover {
  color: var(--color-primary-strong);
}

.tabs__tab--active {
  color: var(--color-primary-strong);
  border-bottom-color: var(--color-primary);
}
</style>
