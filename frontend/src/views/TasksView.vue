<template>
  <section class="tasks-view">
    <PageHeader title="我的任务">
      <template #actions>
        <AppButton variant="ghost" @click="goArchive">已归档任务</AppButton>
      </template>
    </PageHeader>

    <div class="task-overview">
      <article v-for="card in overviewCards" :key="card.key" class="task-stat">
        <span class="task-stat__icon" :class="`task-stat__icon--${card.tone}`" aria-hidden="true">
          <NavIcon :name="card.icon" :size="20" />
        </span>
        <div class="task-stat__text">
          <span class="task-stat__label">{{ card.label }}</span>
          <strong class="task-stat__value">{{ card.value }}</strong>
        </div>
      </article>
    </div>

    <div class="tasks-view__panel">
      <TaskSection />
    </div>

    <aside class="task-suggestion">
      <header class="task-suggestion__head">
        <span class="task-suggestion__mark" aria-hidden="true">
          <NavIcon name="sparkle" :size="17" />
        </span>
        <div>
          <h2 class="task-suggestion__title">AI 任务建议</h2>
          <p class="task-suggestion__hint">根据待办任务的截止时间整理</p>
        </div>
      </header>

      <ul class="task-suggestion__list">
        <li v-if="stats.overdue > 0" class="task-suggestion__item task-suggestion__item--danger">
          <span class="task-suggestion__dot" aria-hidden="true" />
          有 {{ stats.overdue }} 项待办已逾期，建议优先处理。
        </li>
        <li v-if="stats.dueSoon > 0" class="task-suggestion__item">
          <span class="task-suggestion__dot" aria-hidden="true" />
          {{ stats.dueSoon }} 项任务将在 7 天内到期。
        </li>
        <li v-if="stats.todo > 0" class="task-suggestion__item">
          <span class="task-suggestion__dot" aria-hidden="true" />
          还有 {{ stats.todo }} 项待办尚未完成，保持跟进。
        </li>
        <li
          v-if="!stats.overdue && !stats.dueSoon && stats.todo === 0"
          class="task-suggestion__item"
        >
          <span class="task-suggestion__dot" aria-hidden="true" />
          当前没有紧急任务，保持现有节奏即可。
        </li>
      </ul>

      <AppButton size="sm" variant="ghost" @click="showTodo">查看待办</AppButton>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listTasks } from '@/api/tasks'
import AppButton from '@/components/AppButton.vue'
import NavIcon from '@/components/NavIcon.vue'
import PageHeader from '@/components/PageHeader.vue'
import TaskSection from '@/components/TaskSection.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useTasksStore } from '@/stores/tasks'
import type { PersonalTask } from '@/types/task'

const router = useRouter()
const store = useTasksStore()

const stats = reactive({
  total: 0,
  todo: 0,
  inProgress: 0,
  completed: 0,
  overdue: 0,
  dueSoon: 0,
})

const todoItems = ref<PersonalTask[]>([])

const overviewCards = computed(() => [
  { key: 'total', label: '全部任务', value: stats.total, icon: 'tasks', tone: 'blue' },
  { key: 'todo', label: '待处理', value: stats.todo, icon: 'clock', tone: 'amber' },
  { key: 'progress', label: '进行中', value: stats.inProgress, icon: 'list', tone: 'teal' },
  { key: 'completed', label: '已完成', value: stats.completed, icon: 'check', tone: 'green' },
])

function daysFromToday(dateText: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(`${dateText}T23:59:59`)
  if (Number.isNaN(target.getTime())) {
    return Number.POSITIVE_INFINITY
  }
  return Math.ceil((target.getTime() - today.getTime()) / 86_400_000)
}

async function loadOverview(): Promise<void> {
  try {
    const [all, todo, inProgress, completed, todoList] = await Promise.all([
      listTasks({ page: 1, page_size: 1 }),
      listTasks({ status: 'todo', page: 1, page_size: 1 }),
      listTasks({ status: 'in_progress', page: 1, page_size: 1 }),
      listTasks({ status: 'completed', page: 1, page_size: 1 }),
      listTasks({ status: 'todo', page: 1, page_size: 100 }),
    ])

    stats.total = all.pagination.total
    stats.todo = todo.pagination.total
    stats.inProgress = inProgress.pagination.total
    stats.completed = completed.pagination.total
    todoItems.value = todoList.items
    stats.overdue = todoList.items.filter(
      (task) => task.due_date && daysFromToday(task.due_date) < 0,
    ).length
    stats.dueSoon = todoList.items.filter((task) => {
      if (!task.due_date) return false
      const days = daysFromToday(task.due_date)
      return days >= 0 && days <= 7
    }).length
  } catch {
    stats.overdue = 0
    stats.dueSoon = 0
  }
}

function showTodo(): void {
  void store.setStatusFilter('todo')
}

function goArchive(): void {
  void router.push({ name: ROUTE_NAMES.taskArchive })
}

onMounted(() => {
  void loadOverview()
})
</script>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.task-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.task-stat {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.task-stat__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 2.6rem;
  height: 2.6rem;
  border-radius: var(--radius-md);
}

.task-stat__icon--blue {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.task-stat__icon--amber {
  color: #b45309;
  background: #fef3c7;
}

.task-stat__icon--teal {
  color: var(--color-accent-strong);
  background: var(--color-accent-soft);
}

.task-stat__icon--green {
  color: #047857;
  background: #d1fae5;
}

.task-stat__text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.task-stat__label {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.task-stat__value {
  color: var(--color-foreground);
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.tasks-view__panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.task-suggestion {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background:
    radial-gradient(420px 180px at 100% 0%, rgba(21, 94, 239, 0.08), transparent 65%),
    var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.task-suggestion > :deep(.app-button) {
  align-self: flex-start;
}

.task-suggestion__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.task-suggestion__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.2rem;
  height: 2.2rem;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: var(--radius-md);
}

.task-suggestion__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 650;
}

.task-suggestion__hint {
  margin: 1px 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.task-suggestion__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.task-suggestion__item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  line-height: 1.55;
}

.task-suggestion__item--danger {
  color: var(--color-down);
}

.task-suggestion__dot {
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
  margin-top: 0.5rem;
  background: currentColor;
  border-radius: 50%;
  opacity: 0.6;
}

@media (max-width: 900px) {
  .task-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .task-stat {
    padding: var(--space-3);
  }

  .task-stat__value {
    font-size: 1.25rem;
  }
}
</style>
