<template>
  <div class="brief-card">
    <p class="brief-card__eyebrow">会前速览</p>
    <p class="brief-card__headline">{{ model.headline }}</p>

    <ul v-if="model.key_points.length" class="brief-card__list">
      <li v-for="(item, index) in model.key_points" :key="`k-${index}`">{{ item }}</li>
    </ul>

    <div v-if="model.decisions_needed.length || model.risks.length" class="brief-card__split">
      <section v-if="model.decisions_needed.length" class="brief-card__section">
        <h4 class="brief-card__title">需会上确认</h4>
        <ul class="brief-card__list brief-card__list--compact">
          <li v-for="(item, index) in model.decisions_needed" :key="`d-${index}`">
            {{ item }}
          </li>
        </ul>
      </section>

      <section v-if="model.risks.length" class="brief-card__section">
        <h4 class="brief-card__title brief-card__title--risk">风险</h4>
        <ul class="brief-card__list brief-card__list--compact">
          <li v-for="(item, index) in model.risks" :key="`r-${index}`">{{ item }}</li>
        </ul>
      </section>
    </div>

    <p v-if="model.next_step" class="brief-card__next">
      <span class="brief-card__next-label">下一步</span>
      {{ model.next_step }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { MaterialBrief } from '@/types/chat'

const props = defineProps<{ data: MaterialBrief }>()

// 后端已做长度收口；这里只兜底字段缺失，避免卡片空白
const model = computed<MaterialBrief>(() => ({
  headline: props.data.headline ?? '',
  key_points: props.data.key_points ?? [],
  decisions_needed: props.data.decisions_needed ?? [],
  risks: props.data.risks ?? [],
  next_step: props.data.next_step ?? '',
}))
</script>

<style scoped>
.brief-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  font-size: 0.875rem;
}

.brief-card__eyebrow {
  margin: 0;
  color: var(--color-accent-strong);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.brief-card__headline {
  margin: 0;
  color: var(--color-foreground);
  font-size: 1rem;
  font-weight: 650;
  line-height: 1.55;
}

.brief-card__list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding-left: 1.1rem;
  line-height: 1.65;
}

.brief-card__list--compact {
  font-size: 0.8125rem;
}

.brief-card__list li::marker {
  color: var(--color-accent);
}

.brief-card__split {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
  gap: var(--space-3);
}

.brief-card__section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brief-card__title {
  margin: 0;
  color: var(--color-primary-strong);
  font-size: 0.75rem;
  font-weight: 650;
}

.brief-card__title--risk {
  color: var(--color-down);
}

.brief-card__next {
  margin: 0;
  padding: 0.5rem 0.7rem;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  line-height: 1.6;
  background: var(--color-surface-muted);
  border-radius: var(--radius-sm);
}

.brief-card__next-label {
  margin-right: 0.35rem;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.06em;
}
</style>
