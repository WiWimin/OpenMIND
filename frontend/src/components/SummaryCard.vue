<template>
  <div class="summary-card">
    <section v-if="model.conclusion.length" class="summary-card__section">
      <h4 class="summary-card__title">结论与决议</h4>
      <ul class="summary-card__list">
        <li v-for="(item, index) in model.conclusion" :key="`c-${index}`">{{ item }}</li>
      </ul>
    </section>

    <section v-if="model.key_discussions.length" class="summary-card__section">
      <h4 class="summary-card__title">关键讨论</h4>
      <div v-for="group in model.key_discussions" :key="group.topic" class="summary-card__topic">
        <p class="summary-card__topic-name">{{ group.topic }}</p>
        <ul class="summary-card__list">
          <li v-for="(point, index) in group.points" :key="`p-${index}`">{{ point }}</li>
        </ul>
      </div>
    </section>

    <section v-if="model.action_items.length" class="summary-card__section">
      <h4 class="summary-card__title">待办与责任</h4>
      <table class="summary-card__table">
        <thead>
          <tr>
            <th>任务</th>
            <th>负责人</th>
            <th>截止</th>
            <th>优先级</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(item, index) in model.action_items" :key="`a-${index}`">
            <td>
              {{ item.task }}
              <span v-if="item.source_quote" class="summary-card__quote">
                原文：{{ item.source_quote }}
              </span>
            </td>
            <td>{{ item.assignee ?? '未指定' }}</td>
            <td>{{ item.deadline ?? '未指定' }}</td>
            <td>
              <span class="summary-card__priority" :class="`summary-card__priority--${item.priority}`">
                {{ priorityLabel(item.priority) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="summary-card__hint">如需保存为行动项草稿，请使用「待办任务」功能。</p>
    </section>

    <section v-if="model.open_questions.length" class="summary-card__section">
      <h4 class="summary-card__title">待确认问题</h4>
      <ul class="summary-card__list">
        <li v-for="(item, index) in model.open_questions" :key="`q-${index}`">{{ item }}</li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { SummaryStructured } from '@/types/chat'

const props = defineProps<{ data: SummaryStructured }>()

// LLM 输出字段可能缺失，统一兜底为空数组
const model = computed<SummaryStructured>(() => ({
  conclusion: props.data.conclusion ?? [],
  key_discussions: props.data.key_discussions ?? [],
  action_items: props.data.action_items ?? [],
  open_questions: props.data.open_questions ?? [],
}))

const PRIORITY_LABELS: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

function priorityLabel(priority: string): string {
  return PRIORITY_LABELS[priority] ?? priority
}
</script>

<style scoped>
.summary-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  font-size: 0.875rem;
}

.summary-card__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.summary-card__title {
  margin: 0;
  font-size: 0.8125rem;
  font-weight: 650;
  color: var(--color-primary-strong);
}

.summary-card__list {
  margin: 0;
  padding-left: 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 4px;
  line-height: 1.65;
}

.summary-card__topic + .summary-card__topic {
  margin-top: var(--space-2);
}

.summary-card__topic-name {
  margin: 0 0 4px;
  font-weight: 600;
}

.summary-card__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.summary-card__table th,
.summary-card__table td {
  padding: 0.4rem 0.55rem;
  text-align: left;
  border: 1px solid var(--color-border);
  vertical-align: top;
}

.summary-card__table th {
  background: var(--color-surface-muted);
  font-weight: 600;
  white-space: nowrap;
}

.summary-card__quote {
  display: block;
  margin-top: 2px;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.summary-card__priority {
  padding: 0.05rem 0.45rem;
  border-radius: var(--radius-pill);
  font-size: 0.6875rem;
  font-weight: 600;
}

.summary-card__priority--high {
  color: var(--color-down);
  background: rgba(220, 38, 38, 0.1);
}

.summary-card__priority--medium {
  color: #b45309;
  background: rgba(250, 204, 21, 0.18);
}

.summary-card__priority--low {
  color: var(--color-muted-foreground);
  background: var(--color-surface-muted);
}

.summary-card__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}
</style>
