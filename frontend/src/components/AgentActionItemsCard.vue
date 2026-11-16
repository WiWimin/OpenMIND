<template>
  <div class="items-card" role="group" aria-label="行动项清单">
    <div class="items-card__head">
      <span class="items-card__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
          <path
            d="M4.5 5.5h15v13h-15zM8 10l1.8 1.8L13 8.6M8 15.5h6"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
      <div class="items-card__text">
        <p class="items-card__title">行动项清单</p>
        <p class="items-card__meta">共 {{ items.length }} 条，待逐条确认</p>
      </div>
      <button type="button" class="items-card__open" @click="emit('open')">
        打开确认
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" aria-hidden="true">
          <path
            d="M9 5.5 15.5 12 9 18.5"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </div>

    <ul class="items-card__list">
      <li v-for="(item, index) in visible" :key="item.action_id ?? index" class="items-card__item">
        <span class="items-card__index">{{ index + 1 }}</span>
        <span class="items-card__body">
          <span class="items-card__content">{{ item.content }}</span>
          <span class="items-card__sub">
            <span>责任人：{{ item.assignee || '待确认' }}</span>
            <span v-if="item.due_date">截止：{{ formatDate(item.due_date) }}</span>
          </span>
        </span>
      </li>
    </ul>

    <p v-if="items.length > maxVisible" class="items-card__more">
      另有 {{ items.length - maxVisible }} 条，打开清单查看全部
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { AgentActionItemLite } from '@/types/agent'
import { formatDate } from '@/utils/datetime'

const props = defineProps<{ items: AgentActionItemLite[] }>()
const emit = defineEmits<{ open: [] }>()

const maxVisible = 5
const visible = computed(() => props.items.slice(0, maxVisible))
</script>

<style scoped>
.items-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.items-card__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.items-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 2.25rem;
  height: 2.25rem;
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
  border-radius: var(--radius-sm);
}

.items-card__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.items-card__title {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.9375rem;
  font-weight: 650;
}

.items-card__meta {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.items-card__open {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex: none;
  height: 1.875rem;
  padding: 0 0.5rem;
  color: var(--color-primary-strong);
  font-size: 0.75rem;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.items-card__open:hover {
  background: var(--color-surface-muted);
}

.items-card__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.items-card__item {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--color-border);
}

.items-card__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 1.125rem;
  height: 1.125rem;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  background: var(--color-surface-muted);
  border-radius: 999px;
}

.items-card__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.items-card__content {
  color: var(--color-foreground);
  font-size: 0.8125rem;
  line-height: 1.6;
}

.items-card__sub {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.items-card__more {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}
</style>
