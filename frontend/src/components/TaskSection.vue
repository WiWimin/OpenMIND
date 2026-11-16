<template>
  <div class="task-section">
    <div v-if="showFilter" class="task-section__toolbar">
      <div class="task-section__toolbar-title">
        <strong>任务列表</strong>
        <span>共 {{ store.pagination.total }} 项</span>
      </div>
      <div class="task-section__toolbar-actions">
        <IconButton
          v-if="!readonly"
          icon="plus"
          label="新增任务"
          tone="primary"
          large
          @click="toggleCreate"
        />
      </div>
    </div>

    <form v-if="showCreate && !readonly" class="task-create" @submit.prevent="saveNew">
      <FormField
        id="task-create-title"
        v-model="newTitle"
        label="任务标题"
        required
        :error="newFormError"
        placeholder="要做的一件事…"
      />
      <div class="task-create__row">
        <FormField
          id="task-create-due"
          v-model="newDue"
          label="截止日期"
          type="date"
        />
        <FormSelect
          id="task-create-priority"
          v-model="newPriority"
          label="优先级"
          :options="priorityOptions"
        />
      </div>
      <ErrorMessage v-if="newError" :error="newError" />
      <div class="task-create__actions">
        <AppButton type="button" variant="ghost" :disabled="newSaving" @click="cancelCreate">
          取消
        </AppButton>
        <AppButton type="submit" :loading="newSaving">创建任务</AppButton>
      </div>
    </form>

    <LoadingSpinner v-if="store.loading && store.items.length === 0" class="task-section__state" />

    <ErrorMessage
      v-else-if="store.error"
      :error="store.error"
      retryable
      @retry="store.fetchList()"
    />

    <EmptyState v-else-if="store.items.length === 0" title="还没有任务">
      <img
        class="task-section__empty-img"
        :src="taskEmptyUrl"
        alt=""
        aria-hidden="true"
        draggable="false"
      />
    </EmptyState>

    <template v-else>
      <div class="task-section__table">
        <div class="task-section__head" aria-hidden="true">
          <span>任务</span>
          <span>关联会议</span>
          <span>截止时间与状态</span>
          <span>操作</span>
        </div>

        <ul class="task-section__list">
          <li v-for="task in store.items" :key="task.task_id" class="task-item">
            <form v-if="editId === task.task_id" class="task-item__edit" @submit.prevent="saveEdit">
              <FormField
                :id="`task-edit-title-${task.task_id}`"
                v-model="editTitle"
                label="任务标题"
                required
                :error="editFormError"
              />
              <div class="task-item__edit-row">
                <FormField
                  :id="`task-edit-due-${task.task_id}`"
                  v-model="editDue"
                  label="截止日期"
                  type="date"
                />
                <FormSelect
                  :id="`task-edit-priority-${task.task_id}`"
                  v-model="editPriority"
                  label="优先级"
                  :options="priorityOptions"
                />
              </div>
              <ErrorMessage v-if="editError" :error="editError" />
              <div class="task-item__edit-actions">
                <AppButton type="button" variant="ghost" :disabled="editSaving" @click="cancelEdit">
                  取消
                </AppButton>
                <AppButton type="submit" :loading="editSaving">保存修改</AppButton>
              </div>
            </form>

            <template v-else>
              <div class="task-item__head">
                <button
                  type="button"
                  class="task-item__title"
                  :title="`${task.title}（点击查看任务详情）`"
                  @click="openDetail(task)"
                >
                  {{ task.title }}
                </button>
              </div>

              <!-- 关联会议：点击跳转会议管理 -->
              <div class="task-item__meeting">
                <button
                  v-if="task.meeting_id"
                  type="button"
                  class="task-item__meeting-link"
                  :title="`跳转到会议「${task.meeting_title ?? task.meeting_id}」`"
                  @click="goMeeting(task)"
                >
                  {{ task.meeting_title || '来源会议' }}
                </button>
                <span v-else class="task-item__meeting-none">—</span>
              </div>

              <div class="task-item__controls">
                <select
                  v-if="!readonly"
                  :id="`task-status-${task.task_id}`"
                  class="task-item__status-select"
                  :value="task.status"
                  aria-label="任务状态"
                  @change="onStatusChange(task, $event)"
                >
                  <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
                <StatusBadge v-else :label="metaOf(task).label" :tone="metaOf(task).tone" />

                <span
                  v-if="task.due_date"
                  class="task-item__due"
                  :class="{ 'task-item__due--overdue': isOverdue(task) }"
                >
                  截止 {{ dueOf(task) }}
                  <StatusBadge
                    v-if="isOverdue(task)"
                    class="task-item__overdue"
                    label="已逾期"
                    tone="danger"
                  />
                </span>
                <span v-else class="task-item__due">未设置截止时间</span>
              </div>

              <div class="task-item__actions">
                <IconButton
                  v-if="readonly && task.status === 'completed'"
                  icon="undo"
                  label="撤回到待办"
                  :loading="revertingId === task.task_id"
                  @click="revert(task)"
                />
                <template v-else-if="!readonly">
                  <IconButton icon="edit" label="编辑任务" @click="startEdit(task)" />
                  <IconButton
                    v-if="task.status !== 'cancelled' && task.status !== 'completed'"
                    icon="trash"
                    label="删除任务"
                    tone="danger"
                    @click="askCancel(task.task_id)"
                  />
                </template>
              </div>
            </template>
          </li>
        </ul>
      </div>

      <AppButton
        v-if="hasMore"
        class="task-section__more"
        variant="ghost"
        :loading="store.loading"
        @click="loadMore"
      >
        加载更多
      </AppButton>
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
          <dt>优先级</dt>
          <dd>
            <StatusBadge :label="priorityMeta(detailTask).label" :tone="priorityMeta(detailTask).tone" />
          </dd>
        </div>
        <div class="task-detail__row">
          <dt>截止日期</dt>
          <dd>
            {{ dueOf(detailTask) }}
            <StatusBadge v-if="isOverdue(detailTask)" label="已逾期" tone="danger" />
          </dd>
        </div>
        <div class="task-detail__row">
          <dt>创建时间</dt>
          <dd>{{ createdOf(detailTask) }}</dd>
        </div>
        <div class="task-detail__row">
          <dt>来源会议</dt>
          <dd>{{ detailTask.meeting_title || detailTask.meeting_id || '无关联会议' }}</dd>
        </div>
      </dl>
      <template #footer>
        <AppButton v-if="detailTask?.meeting_id" variant="ghost" @click="goToMeeting">
          跳转来源会议
        </AppButton>
        <AppButton v-if="detailTask && !readonly" @click="editFromDetail">编辑任务</AppButton>
        <AppButton variant="ghost" @click="detailTask = null">关闭</AppButton>
      </template>
    </AppModal>

    <ConfirmDialog
      :open="showCancel"
      title="删除任务"
      message="确定删除该任务吗？删除后任务将标记为已取消并从当前列表移除。"
      confirm-text="删除"
      danger
      :loading="cancelling"
      @confirm="confirmCancel"
      @cancel="cancelCancel"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import taskEmptyUrl from '@/assets/task-empty.jpeg'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import FormSelect from '@/components/FormSelect.vue'
import IconButton from '@/components/IconButton.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useTasksStore, type TaskStatusFilter } from '@/stores/tasks'
import type { PersonalTask, TaskPriority, TaskStatus } from '@/types/task'
import type { SelectOption, StatusTone } from '@/types/ui'
import { formatDate, formatDateTime } from '@/utils/datetime'
import { resolveErrorMessage } from '@/utils/errors'
import { taskStatusMeta, type StatusMeta } from '@/utils/statusLabels'

const store = useTasksStore()
const router = useRouter()
const props = withDefaults(
  defineProps<{
    defaultStatus?: TaskStatusFilter
    showFilter?: boolean
    autoLoad?: boolean
    readonly?: boolean
  }>(),
  {
    defaultStatus: '',
    showFilter: true,
    autoLoad: true,
    readonly: false,
  },
)

store.filters.status = props.defaultStatus

const toast = useToast()

const taskStatusOptions = (
  Object.entries(taskStatusMeta) as [TaskStatus, StatusMeta][]
).map(([value, meta]) => ({ value, label: meta.label }))

const statusOptions: SelectOption[] = taskStatusOptions

/** 优先级三色：高＝红、中＝橙、低＝灰 */
const PRIORITY_META: Record<TaskPriority, { label: string; tone: StatusTone }> = {
  high: { label: '高', tone: 'danger' },
  medium: { label: '中', tone: 'warning' },
  low: { label: '低', tone: 'neutral' },
}

const priorityOptions: SelectOption[] = [
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]

function priorityMeta(task: PersonalTask): { label: string; tone: StatusTone } {
  return PRIORITY_META[task.priority ?? 'medium']
}

const showCancel = ref(false)
const cancelling = ref(false)
const pendingCancelId = ref<string | null>(null)

const detailTask = ref<PersonalTask | null>(null)
const editId = ref<string | null>(null)
const editTitle = ref('')
const editDue = ref('')
const editPriority = ref<TaskPriority>('medium')
const editFormError = ref('')
const editError = ref<unknown>(null)
const editSaving = ref(false)

// 新增任务
const showCreate = ref(false)
const newTitle = ref('')
const newDue = ref('')
const newPriority = ref<TaskPriority>('medium')
const newFormError = ref('')
const newError = ref<unknown>(null)
const newSaving = ref(false)

// 归档撤回
const revertingId = ref<string | null>(null)

const hasMore = computed(() => store.pagination.page < store.pagination.total_pages)

function metaOf(task: PersonalTask) {
  return taskStatusMeta[task.status]
}

function dueOf(task: PersonalTask): string {
  return formatDate(task.due_date)
}

function isOverdue(task: PersonalTask): boolean {
  if (!task.due_date || task.status === 'completed' || task.status === 'cancelled') {
    return false
  }
  const due = new Date(`${task.due_date}T23:59:59`)
  if (Number.isNaN(due.getTime())) {
    return false
  }
  return due.getTime() < Date.now()
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
  editPriority.value = task.priority ?? 'medium'
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
      priority: editPriority.value,
    })
    editId.value = null
    toast.success('任务已更新')
  } catch (caught) {
    editError.value = caught
  } finally {
    editSaving.value = false
  }
}

function toggleCreate(): void {
  showCreate.value = !showCreate.value
  if (showCreate.value) {
    newTitle.value = ''
    newDue.value = ''
    newPriority.value = 'medium'
    newFormError.value = ''
    newError.value = null
  }
}

function cancelCreate(): void {
  showCreate.value = false
  newFormError.value = ''
  newError.value = null
}

async function saveNew(): Promise<void> {
  const title = newTitle.value.trim()
  if (!title) {
    newFormError.value = '请输入任务标题'
    return
  }
  newFormError.value = ''
  newSaving.value = true
  newError.value = null
  try {
    await store.createTask({
      title,
      due_date: newDue.value || undefined,
      priority: newPriority.value,
    })
    showCreate.value = false
    toast.success('任务已创建')
  } catch (caught) {
    newError.value = caught
  } finally {
    newSaving.value = false
  }
}

async function revert(task: PersonalTask): Promise<void> {
  if (revertingId.value) {
    return
  }
  revertingId.value = task.task_id
  try {
    await store.revertTask(task.task_id)
    toast.success('已撤回到待办任务')
  } catch (error) {
    toast.error(resolveErrorMessage(error, '撤回失败'))
  } finally {
    revertingId.value = null
  }
}

function goToMeeting(): void {
  const task = detailTask.value
  detailTask.value = null
  if (task) {
    goMeeting(task)
  }
}

/** 行内「关联会议」链接与详情弹窗共用：跳到会议管理该会议的文件列表 */
function goMeeting(task: PersonalTask): void {
  if (!task.meeting_id) {
    return
  }
  // 跳到会议管理中该会议的文件列表（原会议详情页已删除）
  void router.push({ name: ROUTE_NAMES.meetings, query: { meeting: task.meeting_id } })
}

onMounted(() => {
  if (props.autoLoad) {
    void store.fetchList()
  }
})

function onStatusChange(task: PersonalTask, event: Event): void {
  const target = event.target as HTMLSelectElement
  void changeStatus(task, target.value)
}

async function changeStatus(task: PersonalTask, value: string): Promise<void> {
  try {
    await store.updateTask(task.task_id, { status: value as TaskStatus })
    toast.success('任务状态已更新')
  } catch (error) {
    toast.error(resolveErrorMessage(error, '任务状态更新失败'))
  }
}

function loadMore(): void {
  void store.loadMore()
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
    toast.success('任务已删除')
  } finally {
    cancelling.value = false
  }
}
</script>

<style scoped>
.task-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.task-section__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
}

.task-section__toolbar-title {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.task-section__toolbar-title strong {
  font-size: 0.9375rem;
  font-weight: 650;
}

.task-section__toolbar-title span {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.task-section__toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3);
}

.task-create {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

/* 截止日期 + 优先级并排 */
.task-create__row,
.task-item__edit-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.task-create__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.task-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

/* 空态插画：放在「还没有任务」文字下方 */
.task-section__empty-img {
  display: block;
  width: min(220px, 70%);
  height: auto;
  margin: 0 auto;
}

.task-section__table {
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.task-section__head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 9.5rem 12.5rem auto;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--color-surface-strong);
  border-bottom: 1px solid var(--color-border);
}

.task-section__head span:last-child {
  text-align: right;
}

.task-section__list {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.task-section__more {
  align-self: center;
}

.task-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 9.5rem 12.5rem auto;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
  transition: background var(--transition-fast);
}

.task-item:last-child {
  border-bottom: 0;
}

.task-item:hover {
  background: var(--color-surface-muted);
}

.task-item__head {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 0;
}

.task-item__title {
  padding: 0;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 650;
  text-align: left;
  overflow-wrap: anywhere;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.task-item__title:hover {
  color: var(--color-primary-strong);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.task-item__title:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
  border-radius: 2px;
}

/* 关联会议跳转链接 */
.task-item__meeting {
  min-width: 0;
}

.task-item__meeting-link {
  display: block;
  max-width: 100%;
  padding: 0;
  overflow: hidden;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.75rem;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  background: transparent;
  border: 0;
  cursor: pointer;
  text-decoration: none;
}

.task-item__meeting-link:hover {
  text-decoration: underline;
  text-underline-offset: 2px;
}

.task-item__meeting-link:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
  border-radius: 2px;
}

.task-item__meeting-none {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  opacity: 0.6;
}

.task-item__controls {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.task-item__status-select {
  min-height: 1.9rem;
  padding: 0 1.5rem 0 8px;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.75rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.task-item__status-select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.task-item__due {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

/* 逾期：截止日期文字标红 */
.task-item__due--overdue {
  color: var(--color-down);
  font-weight: 600;
}

/* 操作按钮：默认收起，hover / 键盘聚焦时显现 */
.task-item__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.task-item:hover .task-item__actions,
.task-item:focus-within .task-item__actions {
  opacity: 1;
}

.task-item__edit {
  grid-column: 1 / -1;
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

@media (max-width: 900px) {
  .task-section__head {
    display: none;
  }

  .task-item {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-2);
  }

  .task-item__controls {
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
  }

  .task-item__actions {
    justify-content: flex-start;
    /* 触屏无 hover：操作常驻可见 */
    opacity: 1;
  }

  .task-create__row,
  .task-item__edit-row {
    grid-template-columns: minmax(0, 1fr);
  }
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
</style>
