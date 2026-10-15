<template>
  <section class="tasks">
    <PageHeader title="个人任务" description="跟进由已确认行动项转换而成的个人任务。" />

    <div class="tasks__toolbar">
      <FormSelect
        id="task-status-filter"
        label="状态"
        :model-value="store.filters.status"
        :options="filterOptions"
        @update:model-value="onFilter"
      />
    </div>

    <LoadingSpinner v-if="store.loading && store.items.length === 0" class="tasks__state" />

    <ErrorMessage v-else-if="store.error" :error="store.error" retryable @retry="store.fetchList()" />

    <EmptyState
      v-else-if="store.items.length === 0"
      title="还没有任务"
      description="从已确认的行动项转成任务后，会出现在这里。"
    />

    <template v-else>
      <ul class="tasks__list">
        <li v-for="task in store.items" :key="task.task_id" class="task-item">
          <div class="task-item__head">
            <span class="task-item__title">{{ task.title }}</span>
            <StatusBadge :label="metaOf(task).label" :tone="metaOf(task).tone" />
          </div>

          <div class="task-item__controls">
            <FormSelect
              :id="`task-status-${task.task_id}`"
              label="状态"
              :model-value="task.status"
              :options="statusOptions"
              @update:model-value="(value) => changeStatus(task, value)"
            />
            <span v-if="task.due_date" class="task-item__due">截止 {{ dueOf(task) }}</span>
          </div>

          <div v-if="task.status !== 'cancelled' && task.status !== 'completed'" class="task-item__actions">
            <AppButton variant="ghost" @click="askCancel(task.task_id)">取消任务</AppButton>
          </div>
        </li>
      </ul>

      <AppPagination
        v-if="store.pagination.total_pages > 1"
        class="tasks__pagination"
        :page="store.pagination.page"
        :page-size="store.pagination.page_size"
        :total="store.pagination.total"
        @update:page="store.setPage"
      />
    </template>

    <ConfirmDialog
      :open="showCancel"
      title="取消任务"
      message="确定取消该任务吗？"
      confirm-text="取消任务"
      danger
      :loading="cancelling"
      @confirm="confirmCancel"
      @cancel="cancelCancel"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormSelect from '@/components/FormSelect.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useTasksStore, type TaskStatusFilter } from '@/stores/tasks'
import type { PersonalTask, TaskStatus } from '@/types/task'
import type { SelectOption } from '@/types/ui'
import { formatDate } from '@/utils/datetime'
import { taskStatusMeta } from '@/utils/statusLabels'

const store = useTasksStore()

const filterOptions: SelectOption[] = [
  { value: '', label: '全部' },
  { value: 'todo', label: '待办' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]

const statusOptions: SelectOption[] = [
  { value: 'todo', label: '待办' },
  { value: 'in_progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
]

const showCancel = ref(false)
const cancelling = ref(false)
const pendingCancelId = ref<string | null>(null)

function metaOf(task: PersonalTask) {
  return taskStatusMeta[task.status]
}

function dueOf(task: PersonalTask): string {
  return formatDate(task.due_date)
}

onMounted(() => {
  void store.fetchList()
})

function onFilter(value: string): void {
  void store.setStatusFilter(value as TaskStatusFilter)
}

function changeStatus(task: PersonalTask, value: string): void {
  void store.updateTask(task.task_id, { status: value as TaskStatus })
}

function askCancel(taskId: string): void {
  pendingCancelId.value = taskId
  showCancel.value = true
}

function cancelCancel(): void {
  showCancel.value = false
  pendingCancelId.value = null
}

async function confirmCancel(): Promise<void> {
  if (!pendingCancelId.value) {
    return
  }
  cancelling.value = true
  try {
    await store.cancelTask(pendingCancelId.value)
    showCancel.value = false
  } finally {
    cancelling.value = false
    pendingCancelId.value = null
  }
}
</script>

<style scoped>
.tasks__toolbar {
  margin-bottom: var(--space-4);
  max-width: 12rem;
}

.tasks__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

.tasks__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.task-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast);
}

.task-item:hover {
  border-color: var(--color-border-strong);
}

.task-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.task-item__title {
  font-weight: 600;
  overflow-wrap: anywhere;
}

.task-item__controls {
  display: flex;
  align-items: flex-end;
  gap: var(--space-3);
}

.task-item__controls :deep(.form-field) {
  min-width: 8rem;
}

.task-item__due {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  padding-bottom: var(--space-2);
}

.task-item__actions {
  display: flex;
  gap: var(--space-2);
}

.tasks__pagination {
  margin-top: var(--space-4);
}
</style>
