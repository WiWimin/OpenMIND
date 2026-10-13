<template>
  <div class="empty-state">
    <p class="empty-state__title">{{ title }}</p>
    <p v-if="description" class="empty-state__description">{{ description }}</p>
    <div v-if="$slots.default" class="empty-state__actions">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    description?: string
  }>(),
  {
    description: '',
  },
)
</script>

<style scoped>
.empty-state {
  padding: var(--space-5) var(--space-4);
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  text-align: center;
}

.empty-state__title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
}

.empty-state__description {
  margin: var(--space-2) auto 0;
  max-width: 32rem;
  color: var(--color-muted-foreground);
}

.empty-state__actions {
  margin-top: var(--space-4);
  display: flex;
  justify-content: center;
  gap: var(--space-2);
}
</style>
