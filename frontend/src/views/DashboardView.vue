<template>
  <section class="dashboard">
    <section id="section-overview" class="dashboard__hero">
      <div class="dashboard__hero-body">
        <p class="dashboard__eyebrow">仪表盘</p>
        <h1 class="dashboard__greeting">OpenMIND</h1>
        <p class="dashboard__meta">
          <span>智能会议记录、纪要生成与任务跟踪</span>
        </p>
      </div>

      <div class="dashboard__hero-actions">
        <button class="hero-btn hero-btn--ghost" type="button" @click="scrollToTasks">
          我的任务
        </button>
        <button class="hero-btn hero-btn--primary" type="button" @click="openCreate">
          新建会议
        </button>
      </div>

      <span class="dashboard__hero-glow" aria-hidden="true" />
      <span class="dashboard__hero-grid" aria-hidden="true" />
    </section>

    <ErrorMessage
      v-if="statsError"
      :error="statsError"
      fallback="统计数据加载失败。"
      retryable
      @retry="loadStats"
    />

    <div
      v-if="statsLoading"
      class="dashboard__stats"
      aria-busy="true"
      aria-label="正在加载统计数据"
    >
      <span v-for="index in 4" :key="index" class="stat-card stat-card--skeleton" />
    </div>

    <div v-else class="dashboard__stats">
      <article class="stat-card">
        <header class="stat-card__head">
          <span class="stat-card__label">总会议</span>
          <span class="stat-card__icon stat-card__icon--blue" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
              <rect x="3.5" y="5.5" width="17" height="13" rx="2.5" stroke="currentColor" stroke-width="1.7" />
              <path d="M8 3.5v3M16 3.5v3M3.5 10.5h17" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
            </svg>
          </span>
        </header>
        <p class="stat-card__value">{{ stats.meetingTotal }}</p>
        <p class="stat-card__hint">
          已安排 {{ stats.scheduled }} · 已归档 {{ stats.archived }}
        </p>
      </article>

      <article class="stat-card">
        <header class="stat-card__head">
          <span class="stat-card__label">已安排</span>
          <span class="stat-card__icon stat-card__icon--teal" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
              <circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.7" />
              <path d="M12 8v4.5l3 1.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
            </svg>
          </span>
        </header>
        <p class="stat-card__value">{{ stats.scheduled }}</p>
        <p class="stat-card__hint">待进行的会议</p>
      </article>

      <article class="stat-card">
        <header class="stat-card__head">
          <span class="stat-card__label">待办任务</span>
          <span class="stat-card__icon stat-card__icon--indigo" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
              <rect x="4.5" y="4.5" width="15" height="15" rx="3" stroke="currentColor" stroke-width="1.7" />
              <path d="M8.5 10.5h7M8.5 14.5h4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
            </svg>
          </span>
        </header>
        <p class="stat-card__value">{{ stats.todo }}</p>
        <p class="stat-card__hint">共 {{ stats.taskTotal }} 项个人任务</p>
      </article>

      <article class="stat-card">
        <header class="stat-card__head">
          <span class="stat-card__label">已完成任务</span>
          <span class="stat-card__icon stat-card__icon--green" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
              <circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="1.7" />
              <path d="m8.6 12.2 2.3 2.3 4.5-4.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
        </header>
        <p class="stat-card__value">{{ stats.completed }}</p>
        <p class="stat-card__hint">完成率 {{ completionRate }}%</p>
      </article>
    </div>

    <section id="section-meetings" class="dashboard__meetings">
      <header class="dashboard__meetings-head">
        <h2 class="dashboard__meetings-title">我的会议</h2>
        <div class="dashboard__meetings-tools">
          <FormSelect
            id="meeting-status-filter"
            label="状态"
            :model-value="store.filters.status"
            :options="statusOptions"
            @update:model-value="onFilterChange"
          />
          <AppButton @click="openCreate">新建会议</AppButton>
        </div>
      </header>

      <LoadingSpinner v-if="store.loading && store.items.length === 0" class="dashboard__state" />

      <ErrorMessage
        v-else-if="store.error"
        :error="store.error"
        retryable
        @retry="store.fetchList()"
      />

      <EmptyState
        v-else-if="store.items.length === 0"
        title="还没有会议"
        description="创建一个会议，开始会前准备、会中记录与会后整理。"
      >
        <AppButton @click="openCreate">新建会议</AppButton>
      </EmptyState>

      <template v-else>
        <MeetingList :items="store.items" @select="openDetail" />
        <AppButton
          v-if="store.pagination.page < store.pagination.total_pages"
          class="dashboard__more"
          variant="ghost"
          :loading="store.loading"
          @click="store.loadMore()"
        >
          加载更多
        </AppButton>
      </template>
    </section>

    <section id="section-tasks" class="dashboard__tasks">
      <header class="dashboard__tasks-head">
        <h2 class="dashboard__tasks-title">我的任务</h2>
        <p class="dashboard__tasks-hint">跟进由已确认行动项转换而成的个人任务。</p>
      </header>
      <TaskSection />
    </section>

    <MeetingFormDialog
      :open="showForm"
      :loading="saving"
      :error="saveError"
      @submit="createMeeting"
      @cancel="closeForm"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listMeetings } from '@/api/meetings'
import { listTasks } from '@/api/tasks'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormSelect from '@/components/FormSelect.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MeetingFormDialog from '@/components/MeetingFormDialog.vue'
import MeetingList from '@/components/MeetingList.vue'
import TaskSection from '@/components/TaskSection.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useMeetingsStore, type MeetingStatusFilter } from '@/stores/meetings'
import { useTasksStore, type TaskStatusFilter } from '@/stores/tasks'
import type { CreateMeetingPayload } from '@/types/meeting'
import type { SelectOption } from '@/types/ui'

interface DashboardStats {
  meetingTotal: number
  scheduled: number
  archived: number
  taskTotal: number
  todo: number
  completed: number
}

const EMPTY_STATS: DashboardStats = {
  meetingTotal: 0,
  scheduled: 0,
  archived: 0,
  taskTotal: 0,
  todo: 0,
  completed: 0,
}

const statusOptions: SelectOption[] = [
  { value: '', label: '全部' },
  { value: 'scheduled', label: '已安排' },
  { value: 'archived', label: '已归档' },
]

const store = useMeetingsStore()
const tasksStore = useTasksStore()
const route = useRoute()
const router = useRouter()
const toast = useToast()

const TASK_STATUSES = ['todo', 'in_progress', 'completed', 'cancelled']

function parseTaskStatus(raw: unknown): TaskStatusFilter | undefined {
  if (typeof raw !== 'string' || !TASK_STATUSES.includes(raw)) {
    return undefined
  }
  return raw as TaskStatusFilter
}

// 页面进入（含 /tasks 复用同一组件）时按 ?status 同步任务筛选
function syncTasksFromRoute(): void {
  if (route.name !== ROUTE_NAMES.tasks) {
    return
  }
  const status = parseTaskStatus(route.query.status) ?? ''
  if (status !== tasksStore.filters.status) {
    void tasksStore.setStatusFilter(status)
  }
}

// /tasks 首次进入：直接按 ?status 复位筛选，由 TaskSection 挂载后拉取
if (route.name === ROUTE_NAMES.tasks) {
  tasksStore.filters.status = parseTaskStatus(route.query.status) ?? ''
}

function scrollToTarget(target: string, attempts = 30): void {
  const node = document.querySelector(target)
  if (node instanceof HTMLElement) {
    node.scrollIntoView({ block: 'start' })
    return
  }
  if (attempts > 0) {
    requestAnimationFrame(() => scrollToTarget(target, attempts - 1))
  }
}

function scrollFromRoute(): void {
  const target =
    route.hash || (route.name === ROUTE_NAMES.tasks ? '#section-tasks' : '')
  if (target) {
    scrollToTarget(target)
  }
}

const statsLoading = ref(true)
const statsError = ref<unknown>(null)
const stats = ref<DashboardStats>({ ...EMPTY_STATS })

const showForm = ref(false)
const saving = ref(false)
const saveError = ref<unknown>(null)

const completionRate = computed(() => {
  const { taskTotal, completed } = stats.value
  if (taskTotal <= 0) return 0
  return Math.round((completed / taskTotal) * 100)
})

async function loadStats(): Promise<void> {
  statsLoading.value = true
  statsError.value = null
  try {
    const [meetings, scheduled, tasks, todo, completed] = await Promise.all([
      listMeetings({ page: 1, page_size: 1 }),
      listMeetings({ status: 'scheduled', page: 1, page_size: 1 }),
      listTasks({ page: 1, page_size: 1 }),
      listTasks({ status: 'todo', page: 1, page_size: 1 }),
      listTasks({ status: 'completed', page: 1, page_size: 1 }),
    ])

    stats.value = {
      meetingTotal: meetings.pagination.total,
      scheduled: scheduled.pagination.total,
      archived: Math.max(meetings.pagination.total - scheduled.pagination.total, 0),
      taskTotal: tasks.pagination.total,
      todo: todo.pagination.total,
      completed: completed.pagination.total,
    }
  } catch (error) {
    statsError.value = error
    stats.value = { ...EMPTY_STATS }
  } finally {
    statsLoading.value = false
  }
}

function openCreate(): void {
  saveError.value = null
  showForm.value = true
}

function closeForm(): void {
  showForm.value = false
}

function onFilterChange(value: string): void {
  void store.setStatusFilter(value as MeetingStatusFilter)
}

function openDetail(meetingId: string): void {
  void router.push({ name: ROUTE_NAMES.meetingDetail, params: { meetingId } })
}

function scrollToTasks(): void {
  document
    .getElementById('section-tasks')
    ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function createMeeting(payload: CreateMeetingPayload): Promise<void> {
  saving.value = true
  saveError.value = null
  try {
    await store.createMeeting(payload)
    showForm.value = false
    toast.success('会议已创建')
    void loadStats()
  } catch (caught) {
    saveError.value = caught
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadStats()
  void store.fetchList()
  syncTasksFromRoute()
  if (route.query.create === '1') {
    openCreate()
    void router.replace({ query: {} })
  }
  scrollFromRoute()
})

// /dashboard、/meetings、/tasks 复用同一组件实例，路由变化在这里联动
watch(
  () => route.fullPath,
  () => {
    if (route.query.create === '1') {
      openCreate()
      void router.replace({ query: {} })
    }
    syncTasksFromRoute()
    scrollFromRoute()
  },
)
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 顶部横幅 */
.dashboard__hero {
  scroll-margin-top: 5.5rem;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5);
  color: #e2e8f0;
  background: linear-gradient(135deg, #0f2744 0%, #12304f 55%, #0e2a47 100%);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.dashboard__hero-body {
  position: relative;
  z-index: 1;
}

.dashboard__eyebrow {
  margin: 0 0 var(--space-2);
  color: rgba(148, 197, 255, 0.95);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.dashboard__greeting {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
  color: #ffffff;
}

.dashboard__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: var(--space-2) 0 0;
  color: rgba(203, 213, 225, 0.85);
  font-size: 0.875rem;
}

.dashboard__hero-actions {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.hero-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 2.5rem;
  padding: 0 var(--space-4);
  border-radius: var(--radius-pill);
  font-size: 0.9375rem;
  font-weight: 600;
  text-decoration: none;
  font: inherit;
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    background var(--transition-fast);
}

.hero-btn--ghost {
  color: #e2e8f0;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.hero-btn--ghost:hover {
  background: rgba(255, 255, 255, 0.14);
  transform: translateY(-1px);
}

.hero-btn--primary {
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border: none;
  box-shadow: 0 10px 24px rgba(59, 111, 212, 0.45);
}

.hero-btn--primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(59, 111, 212, 0.55);
}

.dashboard__hero-glow {
  position: absolute;
  top: -60%;
  right: -8%;
  width: 22rem;
  height: 22rem;
  border-radius: 50%;
  background: radial-gradient(closest-side, rgba(20, 184, 166, 0.5), transparent 70%);
  pointer-events: none;
}

.dashboard__hero-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 36px 36px;
  mask-image: radial-gradient(120% 100% at 100% 0%, #000 10%, transparent 75%);
  pointer-events: none;
}

/* 统计卡 */
.dashboard__stats {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fit, minmax(13.5rem, 1fr));
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
  animation: stat-rise 0.45s cubic-bezier(0.22, 1, 0.36, 1) backwards;
  transition:
    transform var(--transition),
    box-shadow var(--transition);
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-glow);
}

.stat-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.stat-card__label {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
}

.stat-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: var(--radius-md);
  color: #ffffff;
}

.stat-card__icon--blue {
  background: linear-gradient(135deg, #3b6fd4, #3b82f6);
}

.stat-card__icon--teal {
  background: linear-gradient(135deg, #0d9488, #2dd4bf);
}

.stat-card__icon--indigo {
  background: linear-gradient(135deg, #6366f1, #818cf8);
}

.stat-card__icon--green {
  background: linear-gradient(135deg, #059669, #34d399);
}

.stat-card__value {
  margin: 0;
  font-family: var(--font-display);
  font-size: 2.25rem;
  font-weight: 700;
  line-height: 1.1;
  color: var(--color-foreground);
  font-variant-numeric: tabular-nums;
}

.stat-card__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.stat-card--skeleton {
  position: relative;
  overflow: hidden;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  min-height: 8.5rem;
  border-radius: var(--radius-lg);
}

.stat-card--skeleton::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    100deg,
    transparent 20%,
    rgba(255, 255, 255, 0.75) 50%,
    transparent 80%
  );
  animation: shimmer 1.3s infinite;
}

/* 会议区 */
.dashboard__meetings {
  scroll-margin-top: 5.5rem;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
}

.dashboard__meetings-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.dashboard__meetings-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.dashboard__meetings-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: var(--space-3);
}

.dashboard__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

.dashboard__more {
  align-self: center;
  margin-top: var(--space-2);
}

/* 任务区 */
.dashboard__tasks {
  scroll-margin-top: 5.5rem;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
}

.dashboard__tasks-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.dashboard__tasks-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.dashboard__tasks-hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

@keyframes stat-rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes shimmer {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(100%);
  }
}

@media (max-width: 640px) {
  .dashboard__greeting {
    font-size: 1.375rem;
  }

  .dashboard__meetings-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
