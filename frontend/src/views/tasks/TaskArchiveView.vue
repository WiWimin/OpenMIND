<template>
  <section class="task-archive">
    <PageHeader
      title="已归档任务"
      description="查看已完成并归档的个人任务，可导出当前记录用于复盘或交接。"
    >
      <template #actions>
        <AppButton variant="ghost" :disabled="store.items.length === 0" @click="exportCsv">
          导出 CSV
        </AppButton>
        <AppButton variant="ghost" @click="goTasks">返回任务总览</AppButton>
      </template>
    </PageHeader>

    <div class="task-archive__strip">
      <span class="task-archive__pill">已完成 {{ store.pagination.total }} 项</span>
      <span class="task-archive__hint">
        归档任务只读展示，如需继续跟进，请在任务总览中调整状态或重新创建任务。
      </span>
    </div>

    <div class="task-archive__panel">
      <TaskSection default-status="completed" :show-filter="false" readonly />
    </div>
  </section>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import PageHeader from '@/components/PageHeader.vue'
import TaskSection from '@/components/TaskSection.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useTasksStore } from '@/stores/tasks'
import { taskStatusMeta } from '@/utils/statusLabels'

const router = useRouter()
const toast = useToast()
const store = useTasksStore()

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`
}

function exportCsv(): void {
  if (store.items.length === 0) {
    return
  }
  const header = ['任务内容', '来源会议', '截止日期', '状态', '创建时间']
  const rows = store.items.map((task) => [
    task.title,
    task.meeting_id ?? '',
    task.due_date ?? '',
    taskStatusMeta[task.status].label,
    task.created_at,
  ])
  const csv = [header, ...rows].map((row) => row.map(csvCell).join(',')).join('\r\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = '已归档任务.csv'
  link.click()
  URL.revokeObjectURL(url)
  toast.success('已导出当前页任务')
}

function goTasks(): void {
  void router.push({ name: ROUTE_NAMES.tasks })
}
</script>

<style scoped>
.task-archive {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.task-archive__strip {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.task-archive__pill {
  padding: 2px 9px;
  color: var(--color-accent-strong);
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--color-accent-soft);
  border-radius: var(--radius-pill);
}

.task-archive__hint {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.task-archive__panel {
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
