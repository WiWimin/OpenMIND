<template>
  <section class="info-card" :class="`info-card--${tone}`">
    <div class="info-card__head">
      <h2 class="info-card__label">{{ label }}</h2>
      <span v-if="tone !== 'neutral'" class="info-card__dot" aria-hidden="true">
        <svg viewBox="0 0 12 12" width="12" height="12" focusable="false">
          <circle cx="6" cy="6" r="5" fill="currentColor" />
        </svg>
      </span>
    </div>
    <p class="info-card__value">{{ value }}</p>
    <p v-if="description" class="info-card__description">{{ description }}</p>
  </section>
</template>

<script setup lang="ts">
import type { InfoCardTone } from '@/types/ui'

withDefaults(
  defineProps<{
    label: string
    value: string
    tone?: InfoCardTone
    description?: string
  }>(),
  {
    tone: 'neutral',
    description: '',
  },
)
</script>

<style scoped>
.info-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.info-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.info-card__label {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--color-muted-foreground);
}

.info-card__dot {
  display: inline-flex;
  color: var(--color-muted-foreground);
}

.info-card__value {
  margin: var(--space-2) 0 0;
  font-size: 1.5rem;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.info-card__description {
  margin: var(--space-2) 0 0;
  font-size: 0.8125rem;
  color: var(--color-muted-foreground);
}

.info-card--ok .info-card__dot {
  color: var(--color-ok);
}

.info-card--checking .info-card__dot {
  color: var(--color-checking);
}

.info-card--down .info-card__dot {
  color: var(--color-down);
}
</style>
