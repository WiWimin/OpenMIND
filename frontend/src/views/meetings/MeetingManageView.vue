<template>
  <section class="meeting-manage">
    <PageHeader title="会议管理">
      <template #actions>
        <AppButton variant="ghost" @click="onWorkspaceButton">{{ workspaceButtonLabel }}</AppButton>
        <AppButton variant="ghost" @click="goTemplates">模板管理</AppButton>
      </template>
    </PageHeader>

    <!-- 左右双栏：左＝文件夹树，右＝会议卡片列表 / 会议文件 -->
    <div class="meeting-split">
      <aside class="meeting-split__side">
        <CategoryTree
          :categories="treeCategories"
          :uncategorized="uncategorized"
          :total-count="items.length"
          :selected-key="selectedKey"
          :active-meeting-id="activeMeeting?.meeting_id ?? null"
          :expanded-ids="expandedIds"
          :search-active="searchActive"
          @select-all="goRoot"
          @select-category="enterCategory"
          @select-meeting="enterMeeting"
          @toggle="toggleCategory"
          @rename="renameTreeCategory"
          @remove="askDeleteCategory"
          @create="createTreeCategory"
        />
      </aside>

      <div class="meeting-split__main">
        <!-- 会议文件视图（点击卡片进入） -->
        <template v-if="view === 'meeting'">
          <div class="meeting-files-view__head">
            <h2 class="meeting-files-view__title">{{ activeMeeting?.title }}</h2>
            <StatusBadge
              :label="meetingBadgeMeta(activeMeeting?.status).label"
              :tone="meetingBadgeMeta(activeMeeting?.status).tone"
            />
            <div v-if="activeMeeting" class="meeting-files-view__actions">
              <AppButton variant="ghost" size="sm" @click="goWorkbench">会议工作台</AppButton>
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

          <AppBreadcrumb class="meeting-panel__breadcrumb" :items="breadcrumbItems" />

          <LoadingSpinner v-if="loading && items.length === 0" class="meeting-panel__state" />
          <ErrorMessage v-else-if="error" :error="error" retryable @retry="load()" />
          <div v-else class="meeting-files-view">
            <MeetingFilesPanel v-if="activeMeeting" :meeting-id="activeMeeting.meeting_id" />
          </div>
        </template>

        <!-- 卡片列表视图（全部 / 某分类） -->
        <template v-else>
          <header class="meeting-list__head">
            <div class="meeting-list__heading">
              <h2 class="meeting-list__title">{{ listTitle }}</h2>
              <p class="meeting-list__hint">共 {{ pagination.total }} 场会议</p>
            </div>
            <div class="meeting-list__tools">
              <div class="status-chip-row" role="group" aria-label="会议状态筛选">
                <button
                  v-for="option in statusOptions"
                  :key="option.value"
                  type="button"
                  class="status-chip"
                  :class="{ 'status-chip--active': status === option.value }"
                  :title="statusChipHint(option.value)"
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
              <AppButton @click="openCreate">新建会议</AppButton>
            </div>
          </header>

          <LoadingSpinner v-if="loading && items.length === 0" class="meeting-panel__state" />
          <ErrorMessage v-else-if="error" :error="error" retryable @retry="load()" />
          <EmptyState
            v-else-if="activeFolderMeetings.length === 0"
            :title="emptyTitle"
            :description="emptyDescription"
          >
            <AppButton @click="openCreate">新建会议</AppButton>
          </EmptyState>

          <template v-else>
            <div class="meeting-card-grid">
              <MeetingCard
                v-for="meeting in activeFolderMeetings"
                :key="meeting.meeting_id"
                :meeting="meeting"
                @open="enterMeeting"
              />
            </div>
            <p v-if="pagination.total > items.length" class="meeting-list__cap-hint">
              当前展示前 {{ items.length }} 场会议（共 {{ pagination.total }} 场）。
            </p>
          </template>
        </template>
      </div>
    </div>

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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as meetingsApi from '@/api/meetings'
import AppBreadcrumb from '@/components/AppBreadcrumb.vue'
import AppButton from '@/components/AppButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import CreateMeetingDialog from '@/components/CreateMeetingDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MeetingFilesPanel from '@/components/MeetingFilesPanel.vue'
import MeetingFormDialog, { type MeetingFormPayload } from '@/components/MeetingFormDialog.vue'
import CategoryTree, { type TreeCategory } from '@/components/meetings/CategoryTree.vue'
import MeetingCard from '@/components/meetings/MeetingCard.vue'
import NavIcon from '@/components/NavIcon.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import { resolveErrorMessage } from '@/utils/errors'
import { ROUTE_NAMES } from '@/constants/routeNames'
import type { Meeting, MeetingStatus } from '@/types/meeting'
import { meetingStatusMeta, type StatusMeta } from '@/utils/statusLabels'
import {
  assignCategory,
  categoryOf,
  createCategory,
  deleteCategory,
  loadCategories,
  renameCategory,
  type MeetingCategory,
} from '@/utils/meetingCategories'

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
/** 分类数据版本：增删改后自增，驱动依赖 categoryOf（localStorage，非响应式）的计算属性重算 */
const categoryVersion = ref(0)

const view = ref<ExplorerView>('root')
const activeCategory = ref<MeetingCategory | null>(null)
const activeMeeting = ref<Meeting | null>(null)
const expandedIds = ref<string[]>([])

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

function meetingBadgeMeta(status: MeetingStatus | undefined): StatusMeta {
  return meetingStatusMeta[status ?? 'scheduled']
}

/** 状态筛选说明：进行中 = 可编辑；已归档 = 只读 */
function statusChipHint(value: StatusFilter): string {
  if (value === 'archived') {
    return '已归档的会议为只读：不能导入资料、不能编辑，仅可查看与导出'
  }
  if (value === 'scheduled') {
    return '进行中的会议可正常编辑与导入资料'
  }
  return '查看全部会议'
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

const uncategorized = computed(() => {
  void categoryVersion.value
  return visibleMeetings.value.filter((meeting) => !categoryOf(meeting.meeting_id))
})

const treeCategories = computed<TreeCategory[]>(() =>
  categories.value.map((category) => ({
    ...category,
    meetings: visibleMeetings.value.filter(
      (meeting) => categoryOf(meeting.meeting_id) === category.id,
    ),
  })),
)

/** 当前所在分类的会议（未分类 = activeCategory 为 null） */
const activeFolderMeetings = computed(() => {
  if (view.value === 'root') {
    return visibleMeetings.value
  }
  if (!activeCategory.value) {
    return uncategorized.value
  }
  return visibleMeetings.value.filter(
    (meeting) => categoryOf(meeting.meeting_id) === activeCategory.value?.id,
  )
})

const listTitle = computed(() =>
  view.value === 'root' ? '全部会议' : activeCategory.value?.name ?? '未分类',
)

const activeCategoryLabel = computed(() =>
  activeCategory.value?.name ?? '未分类',
)

const selectedKey = computed(() => {
  if (view.value === 'root') {
    return 'all'
  }
  return activeCategory.value ? `cat:${activeCategory.value.id}` : 'cat:uncategorized'
})

const emptyTitle = computed(() => {
  if (searchActive.value) {
    return '没有匹配的会议'
  }
  return view.value === 'root' ? '还没有符合条件的会议' : '该分类下还没有会议'
})

const emptyDescription = computed(() => {
  if (searchActive.value) {
    return '换个关键词试试，或清空搜索查看全部会议。'
  }
  if (view.value === 'root') {
    return '创建一场会议，开始资料预处理、录音转写与纪要生成。'
  }
  return '新建一场会议，或把已有会议归入此分类。'
})

const breadcrumbItems = computed(() => {
  if (view.value === 'meeting') {
    return [
      { label: '会议管理', onClick: () => goRoot() },
      { label: activeCategoryLabel.value, onClick: () => goCategory() },
      { label: activeMeeting.value?.title ?? '' },
    ]
  }
  return []
})

/* ===== 树导航 ===== */
function ensureExpanded(id: string): void {
  if (!expandedIds.value.includes(id)) {
    expandedIds.value = [...expandedIds.value, id]
  }
}

function toggleCategory(id: string): void {
  expandedIds.value = expandedIds.value.includes(id)
    ? expandedIds.value.filter((item) => item !== id)
    : [...expandedIds.value, id]
}

/** 选中分类：右栏切换为该分类的会议卡片 */
function enterCategory(categoryId: string | null): void {
  activeMeeting.value = null
  activeCategory.value = categoryId
    ? (categories.value.find((item) => item.id === categoryId) ?? null)
    : null
  view.value = 'category'
  ensureExpanded(categoryId ?? 'uncategorized')
}

/** 点击会议（卡片或树子节点）：右栏切换为该会议的文件列表 */
function enterMeeting(meeting: Meeting): void {
  activeMeeting.value = meeting
  const categoryId = categoryOf(meeting.meeting_id)
  activeCategory.value = categoryId
    ? (categories.value.find((item) => item.id === categoryId) ?? null)
    : null
  view.value = 'meeting'
  ensureExpanded(categoryId ?? 'uncategorized')
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

/** 会议文件列表 → 会议工作台（资料预处理 / 录音转写 / 会后处理 3 卡片页） */
function goWorkbench(): void {
  if (!activeMeeting.value) {
    return
  }
  void router.push({
    name: ROUTE_NAMES.newMeeting,
    query: { meetingId: activeMeeting.value.meeting_id },
  })
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
    // 本地同步：改名/换分类时，本地会议文件夹随之迁移（未连接本地文件夹时静默跳过）
    void ws.syncMeetingLocal(
      updated.meeting_id,
      updated.title,
      payload.categoryId ?? categoryOf(updated.meeting_id),
    )
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
    toast.error(resolveErrorMessage(caught, '归档失败，请稍后重试'))
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
  categoryVersion.value += 1
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

async function confirmDeleteMeeting(): Promise<void> {
  const target = deleteMeetingTarget.value
  if (!target) {
    return
  }
  deletingMeeting.value = true
  try {
    await meetingsApi.deleteMeeting(target.meeting_id)
    // 本地同步：删除会议文件夹（未连接本地文件夹时静默跳过）
    void ws.deleteMeetingLocal(target.meeting_id, target.title)
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
    toast.error(resolveErrorMessage(caught, '删除失败，请稍后重试'))
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
  // 先收集该分类下的会议（删除后归属信息就没了），用于本地文件夹上移同步
  const meetingsInCategory = visibleMeetings.value
    .filter((meeting) => categoryOf(meeting.meeting_id) === target.id)
    .map((meeting) => ({ meetingId: meeting.meeting_id, title: meeting.title }))
  deleteCategory(target.id)
  // 本地同步：分类下会议文件夹上移一层 <分类>/<会议> → <会议>（与「归入未分类」一致）
  void ws.demoteCategoryLocal(target.name, meetingsInCategory)
  expandedIds.value = expandedIds.value.filter((id) => id !== target.id)
  // 若删除的是当前所在分类，退回根视图
  if (activeCategory.value?.id === target.id) {
    goRoot()
  }
  showDeleteCategory.value = false
  deleteCategoryTarget.value = null
  refreshCategories()
  toast.success('分类已删除，其中会议已归入未分类')
}

/** 树内重命名分类（更多菜单 → 重命名） */
function renameTreeCategory(categoryId: string, name: string): void {
  const renamed = renameCategory(categoryId, name)
  if (!renamed) {
    return
  }
  refreshCategories()
  // 本地同步：创建新命名的分类文件夹（FSA 无 rename，旧文件夹保留，下次同步按新名建）
  void ws.syncCategoryFolder(renamed.name)
  toast.success(`分类已重命名为「${renamed.name}」`)
}

/** 树底「＋ 新建分类」 */
function createTreeCategory(name: string): void {
  const created = createCategory(name)
  refreshCategories()
  ensureExpanded(created.id)
  // 本地同步：新建分类 → 本地授权目录创建同名文件夹（未连接时静默跳过）
  void ws.syncCategoryFolder(created.name)
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

/* ===== 左右双栏 ===== */
.meeting-split {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.meeting-split__side {
  flex: 0 0 15.5rem;
  max-height: calc(100vh - 13rem);
  padding-right: var(--space-3);
  overflow-y: auto;
  border-right: 1px solid var(--color-border);
}

.meeting-split__main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

/* ===== 卡片列表头部 ===== */
.meeting-list__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.meeting-list__heading {
  min-width: 0;
}

.meeting-list__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 650;
}

.meeting-list__hint {
  margin: 2px 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.meeting-list__tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.meeting-panel__state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
}

.meeting-list__cap-hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

/* 状态筛选胶囊 */
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
  width: 13rem;
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

/* 卡片网格 */
.meeting-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(19rem, 1fr));
  gap: var(--space-3);
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

/* ===== 响应式 ===== */
@media (max-width: 900px) {
  .meeting-split {
    flex-direction: column;
  }

  .meeting-split__side {
    flex: 1 1 auto;
    width: 100%;
    max-height: 16rem;
    padding-right: 0;
    padding-bottom: var(--space-3);
    overflow-y: auto;
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }
}

@media (max-width: 640px) {
  .search-box {
    flex: 1;
  }

  .search-box__input {
    width: 100%;
  }
}
</style>
