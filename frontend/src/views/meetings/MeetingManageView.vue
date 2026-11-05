<template>
  <section class="meeting-manage">
    <PageHeader title="会议管理">
      <template #actions>
        <AppButton variant="ghost" @click="onWorkspaceButton">{{ workspaceButtonLabel }}</AppButton>
        <AppButton variant="ghost" @click="goTemplates">模板管理</AppButton>
      </template>
    </PageHeader>

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
            @import="openImport"
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
              :label="meetingBadgeMeta(activeMeeting?.status).label"
              :tone="meetingBadgeMeta(activeMeeting?.status).tone"
            />
            <div v-if="activeMeeting" class="meeting-files-view__actions">
              <AppButton
                variant="ghost"
                size="sm"
                :disabled="activeMeeting.status === 'archived' || busy"
                @click="openEdit"
              >
                编辑
              </AppButton>
              <AppButton
                variant="ghost"
                size="sm"
                :disabled="activeMeeting.status === 'archived' || busy"
                @click="askArchive"
              >
                归档
              </AppButton>
              <AppButton variant="danger" size="sm" :disabled="busy" @click="askDelete">
                删除
              </AppButton>
            </div>
          </div>
          <MeetingFilesPanel v-if="activeMeeting" :meeting-id="activeMeeting.meeting_id" />
        </div>
      </template>
    </section>

    <!-- 从本地文件夹导入资料到指定会议 -->
    <AppModal
      :open="importTarget !== null"
      :label="`导入资料 · ${importTarget?.title ?? ''}`"
      @close="importTarget = null"
    >
      <div v-if="importTarget" class="meeting-import">
        <p class="meeting-import__hint">
          从已授权的本地文件夹选择资料导入该会议；未连接时可先在此授权（与会议详情页同一份授权）。
        </p>
        <LocalWorkspacePanel
          :meeting-id="importTarget.meeting_id"
          :meeting-title="importTarget.title"
          :readonly="importTarget.status === 'archived'"
          :show-export="false"
          @imported="onImported"
        />
        <div class="meeting-import__actions">
          <AppButton variant="ghost" @click="importTarget = null">完成</AppButton>
        </div>
      </div>
    </AppModal>

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

    <!-- 编辑会议（自会议文件列表进入） -->
    <MeetingFormDialog
      :open="showEdit"
      :meeting="editTarget"
      :loading="savingEdit"
      :error="editError"
      :categories="categories"
      @submit="submitEdit"
      @cancel="showEdit = false"
    />

    <!-- 归档会议确认 -->
    <ConfirmDialog
      :open="showArchive"
      title="归档会议"
      :message="`归档后「${activeMeeting?.title ?? ''}」将变为只读，确定归档吗？`"
      confirm-text="归档"
      :loading="archiving"
      @confirm="confirmArchive"
      @cancel="showArchive = false"
    />

    <!-- 新建会议窗口 -->
    <CreateMeetingDialog ref="createDialog" />
  </section>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as meetingsApi from '@/api/meetings'
import AppBreadcrumb from '@/components/AppBreadcrumb.vue'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import CreateMeetingDialog from '@/components/CreateMeetingDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import LocalWorkspacePanel from '@/components/LocalWorkspacePanel.vue'
import MeetingFilesPanel from '@/components/MeetingFilesPanel.vue'
import MeetingFormDialog, { type MeetingFormPayload } from '@/components/MeetingFormDialog.vue'
import NavIcon from '@/components/NavIcon.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import type { Meeting, MeetingStatus } from '@/types/meeting'
import { formatDateTime } from '@/utils/datetime'
import { meetingStatusMeta, type StatusMeta } from '@/utils/statusLabels'
import {
  assignCategory,
  categoryOf,
  createCategory,
  deleteCategory,
  loadCategories,
  type MeetingCategory,
} from '@/utils/meetingCategories'

/** 会议行（本页内部组件）：文件夹图标 + 名称 + 元信息 + 打开/导入/删除 */
const MeetingRow = defineComponent({
  name: 'MeetingRow',
  props: {
    meeting: { type: Object as () => Meeting, required: true },
  },
  emits: ['open', 'import', 'delete'],
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
          label: meetingBadgeMeta(rowProps.meeting.status).label,
          tone: meetingBadgeMeta(rowProps.meeting.status).tone,
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
              class: 'meeting-row__action',
              onClick: () => emit('import', rowProps.meeting),
            },
            '导入',
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
const route = useRoute()
const ws = useLocalWorkspace()

const status = ref<StatusFilter>('')

const {
  items,
  pagination,
  loading,
  error,
  load: loadMeetings,
} = useAsyncList<Meeting>({
  fetcher: ({ page, page_size }) =>
    meetingsApi.listMeetings({
      page,
      page_size,
      status: status.value || undefined,
    }),
  pageSize: 100,
})

const categories = ref<MeetingCategory[]>([])

const view = ref<ExplorerView>('root')
const activeCategory = ref<MeetingCategory | null>(null)
const activeMeeting = ref<Meeting | null>(null)

const searchQuery = ref('')

const showDeleteMeeting = ref(false)
const deleteMeetingTarget = ref<Meeting | null>(null)
const deletingMeeting = ref(false)

const showDeleteCategory = ref(false)
const deleteCategoryTarget = ref<MeetingCategory | null>(null)

/* 编辑 / 归档：会议文件列表页内的会议操作（原会议详情页能力） */
const showEdit = ref(false)
const editTarget = ref<Meeting | null>(null)
const savingEdit = ref(false)
const editError = ref<unknown>(null)
const showArchive = ref(false)
const archiving = ref(false)

const busy = computed(() => savingEdit.value || archiving.value || deletingMeeting.value)

const creatingCategory = ref(false)
const newCategoryName = ref('')

function meetingBadgeMeta(status: MeetingStatus | undefined): StatusMeta {
  return meetingStatusMeta[status ?? 'scheduled']
}

const statusOptions: { value: StatusFilter; label: string }[] = [
  { value: '', label: '全部' },
  ...(Object.entries(meetingStatusMeta) as [MeetingStatus, StatusMeta][]).map(
    ([value, meta]) => ({ value, label: meta.label }),
  ),
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

/* ===== 会议操作（原会议详情页的编辑/归档/删除） ===== */
function openEdit(): void {
  if (!activeMeeting.value) {
    return
  }
  editTarget.value = activeMeeting.value
  editError.value = null
  showEdit.value = true
}

async function submitEdit(payload: MeetingFormPayload): Promise<void> {
  const target = editTarget.value
  if (!target) {
    return
  }
  savingEdit.value = true
  editError.value = null
  try {
    const updated = await meetingsApi.updateMeeting(target.meeting_id, {
      title: payload.title,
      topic: payload.topic,
      meeting_time: payload.meeting_time,
    })
    if (payload.categoryId !== undefined) {
      assignCategory(updated.meeting_id, payload.categoryId || null)
    }
    showEdit.value = false
    editTarget.value = null
    activeMeeting.value = updated
    toast.success('会议信息已更新')
    await load()
    refreshCategories()
  } catch (caught) {
    editError.value = caught
  } finally {
    savingEdit.value = false
  }
}

function askArchive(): void {
  if (activeMeeting.value) {
    showArchive.value = true
  }
}

async function confirmArchive(): Promise<void> {
  if (!activeMeeting.value) {
    return
  }
  archiving.value = true
  try {
    activeMeeting.value = await meetingsApi.archiveMeeting(activeMeeting.value.meeting_id)
    showArchive.value = false
    toast.success('会议已归档')
    await load()
  } catch (caught) {
    toast.error(caught instanceof Error ? caught.message : '归档失败，请稍后重试')
  } finally {
    archiving.value = false
  }
}

function askDelete(): void {
  if (activeMeeting.value) {
    askDeleteMeeting(activeMeeting.value)
  }
}

/**
 * 深链：/meetings?meeting=<id> 直接打开该会议的文件列表（主页「我的会议」、任务跳转用）。
 * 进入后补全所属分类，保证面包屑为 会议管理 > 分类 > 会议。
 */
async function openFromQuery(): Promise<void> {
  const meetingId = String(route.query.meeting ?? '')
  if (!meetingId) {
    return
  }
  try {
    const meeting = await meetingsApi.getMeeting(meetingId)
    const categoryId = categoryOf(meeting.meeting_id)
    activeCategory.value = categoryId
      ? (categories.value.find((item) => item.id === categoryId) ?? null)
      : null
    enterMeeting(meeting)
  } catch {
    toast.error('会议不存在或无权访问')
    goRoot()
  }
}

async function load(): Promise<void> {
  await loadMeetings(1)
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

const createDialog = ref<InstanceType<typeof CreateMeetingDialog> | null>(null)

function openCreate(): void {
  // 新建统一走创建会议窗口（弹窗），创建完成后进入会议流程页
  createDialog.value?.open()
}

function askDeleteMeeting(meeting: Meeting): void {
  deleteMeetingTarget.value = meeting
  showDeleteMeeting.value = true
}

/** 从会议管理页直接把本地文件夹资料导入指定会议 */
const importTarget = ref<Meeting | null>(null)

function openImport(meeting: Meeting): void {
  importTarget.value = meeting
}

function onImported(): void {
  if (importTarget.value) {
    toast.success(`已导入资料到「${importTarget.value.title}」`)
  }
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

// 未配置（或浏览器不支持）时展示「本地文件夹配置」，已配置后展示「修改文件夹配置」
const workspaceButtonLabel = computed(() =>
  ws.status.value === 'connected' || ws.status.value === 'needs-permission'
    ? '修改文件夹配置'
    : '本地文件夹配置',
)

async function onConnect(): Promise<void> {
  const connected = await ws.connect()
  // 连接成功不弹提示，页面顶部的工作区状态条已展示连接状态
  if (!connected && ws.status.value === 'unconfigured') {
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
  void load().then(() => openFromQuery())
})

// 深链：从主页「我的会议」/任务跳转过来时直接进入该会议的文件列表
watch(
  () => route.query.meeting,
  (value) => {
    if (value) {
      void openFromQuery()
    }
  },
)
</script>

<style scoped>
.meeting-manage {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
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

.meeting-files-view__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}

.meeting-panel__breadcrumb {
  margin-bottom: 0;
}

/* 会议管理页 · 本地文件夹导入对话框 */
.meeting-import {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5) var(--space-5);
  min-width: min(32rem, calc(100vw - 3rem));
}

.meeting-import__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.85rem;
}

.meeting-import__actions {
  display: flex;
  justify-content: flex-end;
}
</style>
