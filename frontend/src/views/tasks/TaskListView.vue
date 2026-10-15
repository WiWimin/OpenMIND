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

          <form
            v-if="editId === task.task_id"
            class="task-item__edit"
            @submit.prevent="saveEdit"
          >
            <FormField
              :id="`task-edit-title-${task.task_id}`"
              v-model="editTitle"
              label="任务标题"
              required
              :error="editFormError"
            />
            <FormField
              :id="`task-edit-due-${task.task_id}`"
              v-model="editDue"
              label="截止日期"
              type="date"
            />
            <ErrorMessage v-if="editError" :error="editError" />
            <div class="task-item__edit-actions">
              <AppButton type="button" variant="ghost" :disabled="editSaving" @click="cancelEdit">
                取消
              </AppButton>
              <AppButton type="submit" :loading="editSaving">保存修改</AppButton>
            </div>
          </form>

          <template v-else>
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

            <div class="task-item__actions">
              <AppButton variant="ghost" @click="openDetail(task)">查看详情</AppButton>
              <AppButton variant="ghost" @click="startEdit(task)">编辑任务</AppButton>
              <AppButton
                v-if="task.status !== 'cancelled' && task.status !== 'completed'"
                variant="ghost"
                @click="askCancel(task.task_id)"
              >
                取消任务
              </AppButton>
            </div>
          </template>
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

    <AppModal :open="detailTask !== null" title="任务详情" @close="detailTask = null">
      <dl v-if="detailTask" class="task-detail">
        <div class="task-detail__row">
          <dt>任务标题</dt>
          <dd>{{ detailTask.title }}</dd>
        </div>
        <div class="task-detail__row">
          <dt>状态</dt>
          <dd>{{ metaOf(detailTask).label }}</dd>
        </div>
        <div class="task-detail__row">
          <dt>截止日期</dt>
          <dd>{{ dueOf(detailTask) }}</dd>
        </div>
        <div class="task-detail__row">
          <dt>创建时间</dt>
          <dd>{{ createdOf(detailTask) }}</dd>
        </div>
        <div class="task-detail__row">
          <dt>来源会议</dt>
          <dd>{{ detailTask.meeting_id ?? '无关联会议' }}</dd>
        </div>
      </dl>
      <template #footer>
        <AppButton v-if="detailTask?.meeting_id" variant="ghost" @click="goToMeeting">
          跳转来源会议
        </AppButton>
        <AppButton v-if="detailTask" @click="editFromDetail">编辑任务</AppButton>
        <AppButton variant="ghost" @click="detailTask = null">关闭</AppButton>
      </template>
    </AppModal>

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
import { useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import FormSelect from '@/components/FormSelect.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useTasksStore, type TaskStatusFilter } from '@/stores/tasks'
import type { PersonalTask, TaskStatus } from '@/types/task'
import type { SelectOption } from '@/types/ui'
import { formatDate, formatDateTime } from '@/utils/datetime'
import { taskStatusMeta } from '@/utils/statusLabels'

const store = useTasksStore()
const router = useRouter()
const toast = useToast()

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

const detailTask = ref<PersonalTask | null>(null)
const editId = ref<string | null>(null)
const editTitle = ref('')
const editDue = ref('')
const editFormError = ref('')
const editError = ref<unknown>(null)
const editSaving = ref(false)

function metaOf(task: PersonalTask) {
  return taskStatusMeta[task.status]
}

function dueOf(task: PersonalTask): string {
  return formatDate(task.due_date)
}

function createdOf(task: PersonalTask): string {
  return formatDateTime(task.created_at)
}

function openDetail(task: PersonalTask): void {
  detailTask.value = task
}

function editFromDetail(): void {
  const task = detailTask.value
  detailTask.value = null
  if (task) {
    startEdit(task)
  }
}

function startEdit(task: PersonalTask): void {
  editId.value = task.task_id
  editTitle.value = task.title
  editDue.value = task.due_date ?? ''
  editFormError.value = ''
  editError.value = null
}

function cancelEdit(): void {
  editId.value = null
}

async function saveEdit(): Promise<void> {
  if (!editId.value) {
    return
  }
  const title = editTitle.value.trim()
  if (!title) {
    editFormError.value = '请输入任务标题'
    return
  }
  editFormError.value = ''
  editSaving.value = true
  editError.value = null
  try {
    await store.updateTask(editId.value, {
      title,
      due_date: editDue.value || undefined,
    })
    editId.value = null
    toast.success('任务已更新')
  } catch (caught) {
    editError.value = caught
  } finally {
    editSaving.value = false
  }
}

function goToMeeting(): void {
  const meetingId = detailTask.value?.meeting_id
  if (!meetingId) {
    return
  }
  void router.push({ name: ROUTE_NAMES.meetingDetail, params: { meetingId } })
}

onMounted(() => {
  void store.fetchList()
})

function onFilter(value: string): void {
  void store.setStatusFilter(value as TaskStatusFilter)
}

function changeStatus(task: PersonalTask, value: string): void {
  void store.updateTask(task.task_id, { status: value as TaskStatus })
  toast.success('任务状态已更新')
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
    toast.success('任务已取消')
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
  flex-wrap: wrap;
  gap: var(--space-2);
}

.task-item__edit {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.task-item__edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.task-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
}

.task-detail__row {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr);
  gap: var(--space-3);
  align-items: baseline;
}

.task-detail__row dt {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
}

.task-detail__row dd {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.875rem;
  overflow-wrap: anywhere;
}

.tasks__pagination {
  margin-top: var(--space-4);
}
</style>
