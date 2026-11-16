<template>
  <section class="tasks-view">
    <PageHeader title="我的任务">
      <template #actions>
        <AppButton variant="ghost" @click="goArchive">已归档任务</AppButton>
      </template>
    </PageHeader>

    <!-- 状态筛选胶囊（原统计卡片） -->
    <div class="status-pill-row" role="group" aria-label="任务状态筛选">
      <button
        v-for="option in statusPills"
        :key="option.value"
        type="button"
        class="status-pill"
        :class="{ 'status-pill--active': store.filters.status === option.value }"
        @click="setStatusFilter(option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="tasks-view__panel">
      <TaskSection />
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import PageHeader from '@/components/PageHeader.vue'
import TaskSection from '@/components/TaskSection.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useTasksStore, type TaskStatusFilter } from '@/stores/tasks'

const router = useRouter()
const route = useRoute()
const store = useTasksStore()

const statusPills: { value: TaskStatusFilter; label: string }[] = [
  { value: '', label: '全部' },
  { value: 'todo', label: '待处理' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
]

const ALLOWED_STATUS: TaskStatusFilter[] = ['', 'todo', 'in_progress', 'completed']

function setStatusFilter(value: TaskStatusFilter): void {
  void store.setStatusFilter(value)
}

// 侧边栏按状态直达（如 /tasks?status=todo）时，预置对应筛选
function applyQueryStatus(): void {
  const next = String(route.query.status ?? '')
  if (ALLOWED_STATUS.includes(next as TaskStatusFilter) && next !== store.filters.status) {
    void store.setStatusFilter(next as TaskStatusFilter)
  }
}

onMounted(applyQueryStatus)
watch(() => route.query.status, applyQueryStatus)

function goArchive(): void {
  void router.push({ name: ROUTE_NAMES.taskArchive })
}
</script>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* 状态筛选胶囊：一行排开 */
.status-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.status-pill {
  padding: 0.3rem 0.95rem;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.8125rem;
  font-weight: 600;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.status-pill:hover {
  color: var(--color-foreground);
  border-color: var(--color-border-strong, var(--color-border));
}

.status-pill--active {
  color: #fff;
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.status-pill--active:hover {
  color: #fff;
  border-color: var(--color-primary);
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
</style>
