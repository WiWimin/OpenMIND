<template>
  <section class="meeting-manage">
    <PageHeader title="会议管理">
      <template #actions>
        <AppButton variant="ghost" @click="onWorkspaceButton">本地文件夹配置</AppButton>
        <AppButton variant="ghost" @click="goTemplates">模板管理</AppButton>
      </template>
    </PageHeader>

    <!-- 本地工作区状态条 -->
    <div
      v-if="ws.status.value === 'connected' || ws.status.value === 'needs-permission'"
      class="workspace-bar"
      :class="{ 'workspace-bar--warn': ws.status.value === 'needs-permission' }"
      role="status"
    >
      <span class="workspace-bar__icon" aria-hidden="true"><NavIcon name="folder" :size="15" /></span>
      <template v-if="ws.status.value === 'connected'">
        <span class="workspace-bar__text">
          本地文件夹已连接：<strong>{{ ws.directoryName.value }}</strong
          >，上传的资料与生成的纪要将自动保存到对应会议文件夹。
        </span>
        <button type="button" class="workspace-bar__action" @click="ws.disconnect()">断开</button>
      </template>
      <template v-else>
        <span class="workspace-bar__text">
          本地文件夹「<strong>{{ ws.directoryName.value }}</strong
          >」需要恢复访问权限后才能自动保存。
        </span>
        <button type="button" class="workspace-bar__action workspace-bar__action--primary" @click="onRestore">
          恢复访问
        </button>
        <button type="button" class="workspace-bar__action" @click="ws.disconnect()">断开</button>
      </template>
    </div>

    <section class="meeting-panel">
      <header class="meeting-panel__head">
        <div>
          <h2 class="meeting-panel__title">会议列表</h2>
          <p class="meeting-panel__hint">共 {{ pagination.total }} 场会议</p>
        </div>
        <div class="meeting-panel__tools">
          <template v-if="view !== 'meeting'">
            <div class="status-chip-row" role="group" aria-label="会议状态筛选">
              <button
                v-for="option in statusOptions"
                :key="option.value"
                type="button"
                class="status-chip"
                :class="{ 'status-chip--active': status === option.value }"
                @click="setStatus(option.value)"
              >
                {{ option.label }}
              </button>
            </div>
            <div class="search-box">
              <span class="search-box__icon" aria-hidden="true"><NavIcon name="search" :size="15" /></span>
              <input
                v-model="searchQuery"
                class="search-box__input"
                type="search"
                placeholder="搜索会议名称或主题"
                aria-label="搜索会议"
              />
            </div>
          </template>
          <AppButton @click="openCreate">新建会议</AppButton>
        </div>
      </header>

      <AppBreadcrumb v-if="view !== 'root'" class="meeting-panel__breadcrumb" :items="breadcrumbItems" />

      <LoadingSpinner v-if="loading && items.length === 0" class="meeting-panel__state" />
      <ErrorMessage v-else-if="error" :error="error" retryable @retry="load()" />
      <EmptyState
        v-else-if="items.length === 0 && view === 'root'"
        title="还没有符合条件的会议"
        description="创建一场会议，开始资料预处理、录音转写与纪要生成。"
      >
        <AppButton @click="openCreate">新建会议</AppButton>
      </EmptyState>

      <template v-else>
        <p v-if="view === 'root' && pagination.total > items.length" class="meeting-panel__cap-hint">
          当前展示前 {{ items.length }} 场会议（共 {{ pagination.total }} 场）。
        </p>

        <!-- 根视图：分类文件夹 + 未分类文件夹 -->
        <div v-if="view === 'root'" class="folder-tree">
          <div v-for="folder in categoryFolders" :key="folder.id" class="folder-row">
            <button type="button" class="folder-row__expander" @click="enterCategory(folder)">
              <span class="folder-row__icon" aria-hidden="true"><NavIcon name="folder" :size="16" /></span>
              <span class="folder-row__name">{{ folder.name }}</span>
              <span class="folder-row__count">{{ folder.meetings.length }}</span>
            </button>
            <button
              type="button"
              class="folder-row__remove"
              :title="`删除分类「${folder.name}」，会议将归入未分类`"
              @click="askDeleteCategory(folder)"
            >
              删除分类
            </button>
          </div>

          <div class="folder-row">
            <button type="button" class="folder-row__expander" @click="enterCategory(null)">
              <span class="folder-row__icon" aria-hidden="true"><NavIcon name="folder" :size="16" /></span>
              <span class="folder-row__name">未分类</span>
              <span class="folder-row__count">{{ uncategorized.length }}</span>
            </button>
          </div>

          <!-- 新建分类 -->
          <div class="category-create">
            <template v-if="creatingCategory">
              <input
                v-model="newCategoryName"
                class="category-create__input"
                type="text"
                placeholder="输入分类名称，如：周会"
                maxlength="40"
                @keyup.enter="submitCategory"
              />
              <AppButton size="sm" :disabled="!newCategoryName.trim()" @click="submitCategory">
                创建
              </AppButton>
              <AppButton size="sm" variant="ghost" @click="cancelCreateCategory">取消</AppButton>
            </template>
            <button v-else type="button" class="category-create__toggle" @click="startCreateCategory">
              ＋ 新建分类
            </button>
          </div>
        </div>

        <!-- 分类视图：该分类下的会议文件夹 -->
        <div v-else-if="view === 'category'" class="folder-tree">
          <MeetingRow
            v-for="meeting in activeFolderMeetings"
            :key="meeting.meeting_id"
            :meeting="meeting"
            @open="enterMeeting"
            @delete="askDeleteMeeting"
          />
          <p v-if="activeFolderMeetings.length === 0" class="folder-empty-hint">
            {{ searchActive ? '没有匹配的会议' : '该分类下还没有会议' }}
          </p>
        </div>

        <!-- 会议视图：该会议的文件列表 -->
        <div v-else class="meeting-files-view">
          <div class="meeting-files-view__head">
            <h2 class="meeting-files-view__title">{{ activeMeeting?.title }}</h2>
            <StatusBadge
              :label="activeMeeting?.status === 'archived' ? '已归档' : '已安排'"
              :tone="activeMeeting?.status === 'archived' ? 'neutral' : 'info'"
            />
            <AppButton
              variant="ghost"
              size="sm"
              class="meeting-files-view__open"
              @click="openWorkspace"
            >
              打开会议工作台
            </AppButton>
          </div>
          <MeetingFilesPanel v-if="activeMeeting" :meeting-id="activeMeeting.meeting_id" />
        </div>
      </template>
    </section>

    <!-- 新建会议 -->
    <MeetingFormDialog
      :open="showCreate"
      :loading="creating"
      :error="createError"
      :categories="categories"
      @submit="createMeeting"
      @cancel="showCreate = false"
    />

    <!-- 删除会议确认 -->
    <ConfirmDialog
      :open="showDeleteMeeting"
      title="删除会议"
      :message="`删除后会议「${deleteMeetingTarget?.title ?? ''}」及其资料、录音、纪要将不可恢复，确定删除吗？`"
      confirm-text="删除"
      danger
      :loading="deletingMeeting"
      @confirm="confirmDeleteMeeting"
      @cancel="showDeleteMeeting = false"
    />

    <!-- 删除分类确认 -->
    <ConfirmDialog
      :open="showDeleteCategory"
      title="删除分类"
      :message="`删除分类「${deleteCategoryTarget?.name ?? ''}」后，其中的会议将归入未分类，确定删除吗？`"
      confirm-text="删除分类"
      danger
      @confirm="confirmDeleteCategory"
      @cancel="showDeleteCategory = false"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import * as meetingsApi from '@/api/meetings'
import AppBreadcrumb from '@/components/AppBreadcrumb.vue'
import AppButton from '@/components/AppButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MeetingFilesPanel from '@/components/MeetingFilesPanel.vue'
import MeetingFormDialog, { type MeetingFormPayload } from '@/components/MeetingFormDialog.vue'
import NavIcon from '@/components/NavIcon.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import type { Meeting, MeetingStatus } from '@/types/meeting'
import type { Pagination } from '@/types/pagination'
import { formatDateTime } from '@/utils/datetime'
import {
  assignCategory,
  categoryOf,
  createCategory,
  deleteCategory,
  loadCategories,
  type MeetingCategory,
} from '@/utils/meetingCategories'

/** 会议行（本页内部组件）：文件夹图标 + 名称 + 元信息 + 打开/删除 */
const MeetingRow = defineComponent({
  name: 'MeetingRow',
  props: {
    meeting: { type: Object as () => Meeting, required: true },
  },
  emits: ['open', 'delete'],
  setup(rowProps, { emit }) {
    return () =>
      h('div', { class: 'meeting-row' }, [
        h('span', { class: 'meeting-row__icon', 'aria-hidden': 'true' }, [
          h(NavIcon, { name: 'folder', size: 16 }),
        ]),
        h('div', { class: 'meeting-row__main' }, [
          h(
            'button',
            {
              type: 'button',
              class: 'meeting-row__name',
              onClick: () => emit('open', rowProps.meeting),
            },
            rowProps.meeting.title,
          ),
          h('p', { class: 'meeting-row__meta' }, [
            rowProps.meeting.topic || '未填写会议主题',
            ` · ${rowProps.meeting.meeting_time ? formatDateTime(rowProps.meeting.meeting_time) : '时间未设置'}`,
          ]),
        ]),
        h(StatusBadge, {
          label: rowProps.meeting.status === 'archived' ? '已归档' : '已安排',
          tone: rowProps.meeting.status === 'archived' ? 'neutral' : 'info',
        }),
        h('div', { class: 'meeting-row__actions' }, [
          h(
            'button',
            {
              type: 'button',
              class: 'meeting-row__action',
              onClick: () => emit('open', rowProps.meeting),
            },
            '查看',
          ),
          h(
            'button',
            {
              type: 'button',
              class: 'meeting-row__action meeting-row__action--danger',
              onClick: () => emit('delete', rowProps.meeting),
            },
            '删除',
          ),
        ]),
      ])
  },
})

type StatusFilter = MeetingStatus | ''
type ExplorerView = 'root' | 'category' | 'meeting'

const toast = useToast()
const router = useRouter()
const ws = useLocalWorkspace()

const items = ref<Meeting[]>([])
const pagination = ref<Pagination>({ page: 1, page_size: 100, total: 0, total_pages: 1 })
const loading = ref(false)
const error = ref<unknown>(null)
const status = ref<StatusFilter>('')

const categories = ref<MeetingCategory[]>([])

const view = ref<ExplorerView>('root')
const activeCategory = ref<MeetingCategory | null>(null)
const activeMeeting = ref<Meeting | null>(null)

const searchQuery = ref('')

const showCreate = ref(false)
const creating = ref(false)
const createError = ref<unknown>(null)

const showDeleteMeeting = ref(false)
const deleteMeetingTarget = ref<Meeting | null>(null)
const deletingMeeting = ref(false)

const showDeleteCategory = ref(false)
const deleteCategoryTarget = ref<MeetingCategory | null>(null)

const creatingCategory = ref(false)
const newCategoryName = ref('')

const statusOptions: { value: StatusFilter; label: string }[] = [
  { value: '', label: '全部' },
  { value: 'scheduled', label: '已安排' },
  { value: 'archived', label: '已归档' },
]

const searchActive = computed(() => searchQuery.value.trim().length > 0)

function matchesSearch(meeting: Meeting): boolean {
  const keyword = searchQuery.value.trim().toLowerCase()
  if (!keyword) {
    return true
  }
  return (
    meeting.title.toLowerCase().includes(keyword) ||
    (meeting.topic ?? '').toLowerCase().includes(keyword)
  )
}

const visibleMeetings = computed(() => items.value.filter(matchesSearch))

const uncategorized = computed(() =>
  visibleMeetings.value.filter((meeting) => !categoryOf(meeting.meeting_id)),
)

const categoryFolders = computed(() =>
  categories.value.map((category) => ({
    ...category,
    meetings: visibleMeetings.value.filter(
      (meeting) => categoryOf(meeting.meeting_id) === category.id,
    ),
  })),
)

/** 当前所在分类的名称（未分类文件夹为 null） */
const activeFolderMeetings = computed(() => {
  if (!activeCategory.value) {
    return uncategorized.value
  }
  return visibleMeetings.value.filter(
    (meeting) => categoryOf(meeting.meeting_id) === activeCategory.value?.id,
  )
})

const activeCategoryLabel = computed(() =>
  activeCategory.value?.name ?? '未分类',
)

const breadcrumbItems = computed(() => {
  if (view.value === 'category') {
    return [{ label: '会议管理', onClick: () => goRoot() }, { label: activeCategoryLabel.value }]
  }
  if (view.value === 'meeting') {
    return [
      { label: '会议管理', onClick: () => goRoot() },
      { label: activeCategoryLabel.value, onClick: () => goCategory() },
      { label: activeMeeting.value?.title ?? '' },
    ]
  }
  return []
})

/* ===== 视图导航 ===== */
function enterCategory(category: MeetingCategory | null): void {
  activeCategory.value = category
  activeMeeting.value = null
  view.value = 'category'
}

function enterMeeting(meeting: Meeting): void {
  activeMeeting.value = meeting
  view.value = 'meeting'
}

function goRoot(): void {
  view.value = 'root'
  activeCategory.value = null
  activeMeeting.value = null
}

function goCategory(): void {
  activeMeeting.value = null
  view.value = 'category'
}

function openWorkspace(): void {
  if (!activeMeeting.value) {
    return
  }
  void router.push({
    name: ROUTE_NAMES.meetingDetail,
    params: { meetingId: activeMeeting.value.meeting_id },
  })
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const result = await meetingsApi.listMeetings({
      page: 1,
      page_size: 100,
      status: status.value || undefined,
    })
    items.value = result.items
    pagination.value = result.pagination
  } catch (caught) {
    error.value = caught
  } finally {
    loading.value = false
  }
}

function refreshCategories(): void {
  categories.value = loadCategories()
}

function setStatus(next: StatusFilter): void {
  if (status.value === next) {
    return
  }
  status.value = next
  void load()
}

function openCreate(): void {
  createError.value = null
  showCreate.value = true
}

async function createMeeting(payload: MeetingFormPayload): Promise<void> {
  creating.value = true
  createError.value = null
  try {
    const created = await meetingsApi.createMeeting({
      title: payload.title,
      topic: payload.topic,
      meeting_time: payload.meeting_time,
    })
    if (payload.categoryId) {
      assignCategory(created.meeting_id, payload.categoryId)
    }
    showCreate.value = false
    toast.success('会议已创建')
    refreshCategories()
    await load()
  } catch (caught) {
    createError.value = caught
  } finally {
    creating.value = false
  }
}

function askDeleteMeeting(meeting: Meeting): void {
  deleteMeetingTarget.value = meeting
  showDeleteMeeting.value = true
}

async function confirmDeleteMeeting(): Promise<void> {
  const target = deleteMeetingTarget.value
  if (!target) {
    return
  }
  deletingMeeting.value = true
  try {
    await meetingsApi.deleteMeeting(target.meeting_id)
    assignCategory(target.meeting_id, null)
    showDeleteMeeting.value = false
    deleteMeetingTarget.value = null
    toast.success('会议已删除')
    // 若删除的是当前正在查看的会议，退回所在分类视图
    if (activeMeeting.value?.meeting_id === target.meeting_id) {
      goCategory()
    }
    await load()
  } catch (caught) {
    toast.error(caught instanceof Error ? caught.message : '删除失败，请稍后重试')
  } finally {
    deletingMeeting.value = false
  }
}

function askDeleteCategory(folder: { id: string; name: string }): void {
  deleteCategoryTarget.value = { id: folder.id, name: folder.name, createdAt: '' }
  showDeleteCategory.value = true
}

function confirmDeleteCategory(): void {
  const target = deleteCategoryTarget.value
  if (!target) {
    return
  }
  deleteCategory(target.id)
  // 若删除的是当前所在分类，退回根视图
  if (activeCategory.value?.id === target.id) {
    goRoot()
  }
  showDeleteCategory.value = false
  deleteCategoryTarget.value = null
  refreshCategories()
  toast.success('分类已删除，其中会议已归入未分类')
}

function startCreateCategory(): void {
  creatingCategory.value = true
  newCategoryName.value = ''
}

function cancelCreateCategory(): void {
  creatingCategory.value = false
  newCategoryName.value = ''
}

function submitCategory(): void {
  const name = newCategoryName.value.trim()
  if (!name) {
    return
  }
  const created = createCategory(name)
  refreshCategories()
  cancelCreateCategory()
  toast.success(`分类「${created.name}」已创建`)
}

function onWorkspaceButton(): void {
  if (ws.status.value === 'needs-permission') {
    void onRestore()
    return
  }
  void onConnect()
}

async function onConnect(): Promise<void> {
  const connected = await ws.connect()
  if (connected) {
    toast.success(`本地文件夹已连接：${ws.directoryName.value}`)
  } else if (ws.status.value === 'unconfigured') {
    toast.error('未选择文件夹')
  }
}

async function onRestore(): Promise<void> {
  const restored = await ws.restore()
  if (restored) {
    toast.success('本地文件夹访问已恢复')
  } else {
    toast.error('未能恢复访问权限')
  }
}

function goTemplates(): void {
  void router.push({ name: ROUTE_NAMES.templateManage })
}

onMounted(() => {
  refreshCategories()
  void load()
})
</script>

<style scoped>
.meeting-manage {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 本地工作区状态条 */
.workspace-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  color: var(--color-accent-strong);
  font-size: 0.75rem;
  background: var(--color-accent-soft);
  border: 1px solid rgba(13, 148, 136, 0.22);
  border-radius: var(--radius-lg);
}

.workspace-bar--warn {
  color: var(--color-checking);
  background: #fdf3e0;
  border-color: rgba(180, 83, 9, 0.22);
}

.workspace-bar__icon {
  display: inline-flex;
  flex: 0 0 auto;
}

.workspace-bar__text {
  flex: 1;
  min-width: 0;
}

.workspace-bar__text strong {
  font-weight: 650;
}

.workspace-bar__action {
  flex: 0 0 auto;
  padding: 3px 10px;
  color: inherit;
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid currentColor;
  border-radius: var(--radius-pill);
  cursor: pointer;
}

.workspace-bar__action--primary {
  color: #ffffff;
  background: var(--color-checking);
  border-color: var(--color-checking);
}

/* 面板 */
.meeting-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.meeting-panel__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.meeting-panel__tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.meeting-panel__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 650;
}

.meeting-panel__hint {
  margin: 2px 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.meeting-panel__state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
}

.meeting-panel__cap-hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

/* 状态筛选 */
.status-chip-row {
  display: flex;
  gap: 2px;
  padding: 2px;
  background: var(--color-surface-muted);
  border-radius: var(--radius-pill);
}

.status-chip {
  padding: 0.25rem 0.7rem;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 600;
  background: transparent;
  border: 0;
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.status-chip--active {
  color: var(--color-primary-strong);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

/* 搜索框 */
.search-box {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.search-box__icon {
  position: absolute;
  left: 0.65rem;
  display: inline-flex;
  color: var(--color-muted-foreground);
  pointer-events: none;
}

.search-box__input {
  width: 15rem;
  min-height: 2.1rem;
  padding: 0 var(--space-3) 0 2.2rem;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.8125rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
}

.search-box__input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

/* 文件夹树 */
.folder-tree {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.folder-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.folder-row__expander {
  display: flex;
  flex: 1;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
  padding: var(--space-2) var(--space-3);
  color: var(--color-foreground);
  font: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.folder-row__expander:hover {
  background: var(--color-surface-muted);
}

.folder-row__icon {
  display: inline-flex;
  flex: 0 0 auto;
  color: var(--color-checking);
}

.folder-row__name {
  flex: 0 1 auto;
  overflow: hidden;
  font-size: 0.875rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-row__count {
  flex: 0 0 auto;
  padding: 1px 8px;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-variant-numeric: tabular-nums;
  background: var(--color-surface-muted);
  border-radius: var(--radius-pill);
}

.folder-row__remove {
  flex: 0 0 auto;
  padding: 3px 8px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.6875rem;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.folder-row__remove:hover {
  color: var(--color-down);
}

.folder-empty-hint {
  margin: 0 0 var(--space-1);
  padding-left: 3.4rem;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

/* 会议行 */
:deep(.meeting-row) {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-fast);
}

:deep(.meeting-row:hover) {
  border-color: var(--color-border-strong);
}

:deep(.meeting-row__name) {
  padding: 0;
  font: inherit;
  text-align: left;
  background: none;
  border: 0;
  cursor: pointer;
}

:deep(.meeting-row__icon) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 2rem;
  height: 2rem;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
}

:deep(.meeting-row__main) {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

:deep(.meeting-row__name) {
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 650;
  text-decoration: none;
}

:deep(.meeting-row__name:hover) {
  color: var(--color-primary-strong);
}

:deep(.meeting-row__meta) {
  margin: 0;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.meeting-row__actions) {
  display: flex;
  flex: 0 0 auto;
  gap: var(--space-1);
}

:deep(.meeting-row__action) {
  padding: 3px 10px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 600;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    border-color var(--transition-fast);
}

:deep(.meeting-row__action:hover) {
  color: var(--color-primary-strong);
  border-color: rgba(21, 94, 239, 0.35);
}

:deep(.meeting-row__action--danger:hover) {
  color: var(--color-down);
  border-color: rgba(220, 38, 38, 0.35);
}

/* 新建分类 */
.category-create {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-top: 1px dashed var(--color-border);
}

.category-create__toggle {
  padding: 0.3rem 0.8rem;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  background: transparent;
  border: 1px dashed rgba(21, 94, 239, 0.4);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.category-create__toggle:hover {
  background: var(--color-primary-soft);
}

.category-create__input {
  flex: 0 1 16rem;
  min-height: 2rem;
  padding: 0 var(--space-3);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.8125rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.category-create__input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

@media (max-width: 640px) {
  .search-box__input {
    width: 100%;
  }
}

/* 会议文件视图 */
.meeting-files-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.meeting-files-view__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.meeting-files-view__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 650;
}

.meeting-files-view__open {
  margin-left: auto;
}

.meeting-panel__breadcrumb {
  margin-bottom: 0;
}
</style>
