<template>
  <section class="dashboard">
    <section class="dashboard__hero">
      <div class="dashboard__hero-body">
        <p class="dashboard__eyebrow">仪表盘</p>
        <h1 class="dashboard__greeting">{{ greeting }}，{{ userName }}</h1>
        <p class="dashboard__meta">
          <span>{{ todayLabel }}</span>
          <span class="dashboard__meta-dot" aria-hidden="true">·</span>
          <span>{{ summaryLabel }}</span>
        </p>
      </div>

      <div class="dashboard__hero-actions">
        <RouterLink class="hero-btn hero-btn--ghost" :to="{ name: ROUTE_NAMES.tasks }">
          我的任务
        </RouterLink>
        <RouterLink
          class="hero-btn hero-btn--primary"
          :to="{ name: ROUTE_NAMES.meetings, query: { create: '1' } }"
        >
          新建会议
        </RouterLink>
      </div>

      <span class="dashboard__hero-glow" aria-hidden="true" />
      <span class="dashboard__hero-grid" aria-hidden="true" />
    </section>

    <ErrorMessage
      v-if="!loading && loadError"
      :error="loadError"
      fallback="仪表盘数据加载失败。"
      retryable
      @retry="load"
    />

    <div
      v-if="loading"
      class="dashboard__stats"
      aria-busy="true"
      aria-label="正在加载统计数据"
    >
      <span v-for="index in 4" :key="index" class="stat-card stat-card--skeleton" />
    </div>

    <div v-else class="dashboard__stats">
      <article class="stat-card">
        <header class="stat-card__head">
          <span class="stat-card__label">会议总数</span>
          <span class="stat-card__icon stat-card__icon--indigo" aria-hidden="true">
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
          <span class="stat-card__label">待办任务</span>
          <span class="stat-card__icon stat-card__icon--violet" aria-hidden="true">
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
          <span class="stat-card__label">进行中任务</span>
          <span class="stat-card__icon stat-card__icon--blue" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
              <path d="M4.5 12h11" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
              <path d="m12.5 7.5 5 4.5-5 4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
              <circle cx="19" cy="12" r="1.6" fill="currentColor" />
            </svg>
          </span>
        </header>
        <p class="stat-card__value">{{ stats.inProgress }}</p>
        <p class="stat-card__hint">正在推进中</p>
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

    <div v-if="loading" class="dashboard__grid" aria-busy="true">
      <span class="panel panel--skeleton" />
      <span class="panel panel--skeleton" />
    </div>

    <div v-else class="dashboard__grid">
      <section class="panel">
        <header class="panel__head">
          <h2 class="panel__title">会议概览</h2>
          <RouterLink class="panel__link" :to="{ name: ROUTE_NAMES.meetings }">全部会议</RouterLink>
        </header>

        <div class="split">
          <div class="split__row">
            <span class="split__label"><span class="split__dot split__dot--indigo" aria-hidden="true" />已安排</span>
            <span class="split__bar" aria-hidden="true"><span class="split__fill" :style="{ width: meetingShare }" /></span>
            <span class="split__value">{{ stats.scheduled }}</span>
          </div>
          <div class="split__row">
            <span class="split__label"><span class="split__dot split__dot--slate" aria-hidden="true" />已归档</span>
            <span class="split__bar" aria-hidden="true"><span class="split__fill split__fill--muted" :style="{ width: archivedShare }" /></span>
            <span class="split__value">{{ stats.archived }}</span>
          </div>
        </div>

        <div class="panel__divider" aria-hidden="true" />

        <h3 class="panel__subtitle">最近会议</h3>
        <ul v-if="recentMeetings.length" class="feed">
          <li v-for="meeting in recentMeetings" :key="meeting.meeting_id" class="feed__item">
            <RouterLink
              class="feed__link"
              :to="{ name: ROUTE_NAMES.meetingDetail, params: { meetingId: meeting.meeting_id } }"
            >
              <span class="feed__main">
                <span class="feed__title">{{ meeting.title }}</span>
                <span class="feed__sub">
                  {{ meeting.topic ?? '未填写主题' }} · {{ formatDateTime(meeting.meeting_time) }}
                </span>
              </span>
              <StatusBadge :label="meetingMeta(meeting).label" :tone="meetingMeta(meeting).tone" />
            </RouterLink>
          </li>
        </ul>
        <p v-else class="panel__empty">
          还没有会议，点击右上角「新建会议」创建第一场会议。
        </p>
      </section>

      <section class="panel">
        <header class="panel__head">
          <h2 class="panel__title">待办任务</h2>
          <RouterLink class="panel__link" :to="{ name: ROUTE_NAMES.tasks }">全部任务</RouterLink>
        </header>

        <ul v-if="recentTasks.length" class="feed">
          <li v-for="task in recentTasks" :key="task.task_id" class="feed__item">
            <span class="feed__link feed__link--static">
              <span class="feed__main">
                <span class="feed__title">{{ task.title }}</span>
                <span class="feed__sub">截止 {{ formatDate(task.due_date) }}</span>
              </span>
              <StatusBadge :label="taskMeta(task).label" :tone="taskMeta(task).tone" />
            </span>
          </li>
        </ul>
        <p v-else class="panel__empty">
          还没有个人任务。在会议纪要中把已确认的行动项「转为我的个人任务」即可出现。
        </p>

        <div class="panel__divider" aria-hidden="true" />

        <h3 class="panel__subtitle">AI 生成的结论都需要你确认</h3>
        <p class="panel__note">
          纪要、行动项、待确认问题均为候选草稿，点击【确认】后才会成为正式数据。
        </p>
      </section>
    </div>

    <section class="panel panel--flow">
      <header class="panel__head">
        <h2 class="panel__title">工作流程</h2>
        <span class="panel__hint">从会议到个人任务的闭环</span>
      </header>
      <ol class="flow">
        <li
          v-for="(step, index) in flowSteps"
          :key="step.title"
          class="flow__step"
          :style="{ animationDelay: `${index * 60}ms` }"
        >
          <span class="flow__index" aria-hidden="true">{{ index + 1 }}</span>
          <span class="flow__title">{{ step.title }}</span>
          <span class="flow__desc">{{ step.description }}</span>
        </li>
      </ol>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { listMeetings } from '@/api/meetings'
import { listTasks } from '@/api/tasks'
import ErrorMessage from '@/components/ErrorMessage.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'
import type { Meeting, MeetingStatus } from '@/types/meeting'
import type { PersonalTask, TaskStatus } from '@/types/task'
import { formatDate, formatDateTime } from '@/utils/datetime'
import {
  meetingStatusMeta,
  resolveStatusMeta,
  taskStatusMeta,
} from '@/utils/statusLabels'

interface DashboardStats {
  meetingTotal: number
  scheduled: number
  archived: number
  taskTotal: number
  todo: number
  inProgress: number
  completed: number }

const EMPTY_STATS: DashboardStats = {
  meetingTotal: 0,
  scheduled: 0,
  archived: 0,
  taskTotal: 0,
  todo: 0,
  inProgress: 0,
  completed: 0,
}

const flowSteps = [
  { title: '创建会议', description: '填写主题与时间' },
  { title: '导入资料', description: 'PDF / DOCX / TXT' },
  { title: '会前准备', description: '摘要、清单与问题' },
  { title: '会中记录', description: '记录、重点与问答' },
  { title: '纪要行动项', description: '生成并确认候选' },
  { title: '任务跟进', description: '转任务并跟进状态' },
] as const

const auth = useAuthStore()

const loading = ref(true)
const loadError = ref<unknown>(null)
const stats = ref<DashboardStats>({ ...EMPTY_STATS })
const recentMeetings = ref<Meeting[]>([])
const recentTasks = ref<PersonalTask[]>([])

const userName = computed(() => auth.user?.name ?? '访客')

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const todayLabel = computed(() => {
  const now = new Date()
  const week = ['日', '一', '二', '三', '四', '五', '六'][now.getDay()] ?? ''
  return `${formatDate(now.toISOString())} 星期${week}`
})

const summaryLabel = computed(() =>
  stats.value.meetingTotal > 0
    ? `共 ${stats.value.meetingTotal} 场会议 · ${stats.value.todo} 项待办`
    : '创建第一场会议，开始你的 AI 会议工作流',
)

const completionRate = computed(() => {
  const { taskTotal, completed } = stats.value
  if (taskTotal <= 0) return 0
  return Math.round((completed / taskTotal) * 100)
})

const meetingShare = computed(() => shareLabel(stats.value.scheduled, stats.value.meetingTotal))
const archivedShare = computed(() => shareLabel(stats.value.archived, stats.value.meetingTotal))

function shareLabel(value: number, total: number): string {
  if (total <= 0) return '0%'
  return `${Math.max(Math.round((value / total) * 100), 4)}%`
}

function meetingMeta(meeting: Meeting) {
  return resolveStatusMeta<MeetingStatus>(meetingStatusMeta, meeting.status)
}

function taskMeta(task: PersonalTask) {
  return resolveStatusMeta<TaskStatus>(taskStatusMeta, task.status)
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const [meetings, scheduled, tasks, todo, inProgress, completed] = await Promise.all([
      listMeetings({ page: 1, page_size: 5 }),
      listMeetings({ status: 'scheduled', page: 1, page_size: 1 }),
      listTasks({ page: 1, page_size: 5 }),
      listTasks({ status: 'todo', page: 1, page_size: 1 }),
      listTasks({ status: 'in_progress', page: 1, page_size: 1 }),
      listTasks({ status: 'completed', page: 1, page_size: 1 }),
    ])

    recentMeetings.value = meetings.items
    recentTasks.value = tasks.items
    stats.value = {
      meetingTotal: meetings.pagination.total,
      scheduled: scheduled.pagination.total,
      archived: Math.max(meetings.pagination.total - scheduled.pagination.total, 0),
      taskTotal: tasks.pagination.total,
      todo: todo.pagination.total,
      inProgress: inProgress.pagination.total,
      completed: completed.pagination.total,
    }
  } catch (error) {
    loadError.value = error
    stats.value = { ...EMPTY_STATS }
    recentMeetings.value = []
    recentTasks.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 顶部横幅 */
.dashboard__hero {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5);
  color: #e2e8f0;
  background: linear-gradient(135deg, #111a2e 0%, #131c33 55%, #1a1440 100%);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.dashboard__hero-body {
  position: relative;
  z-index: 1;
}

.dashboard__eyebrow {
  margin: 0 0 var(--space-2);
  color: rgba(165, 180, 252, 0.95);
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

.dashboard__meta-dot {
  color: rgba(148, 163, 184, 0.7);
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
  box-shadow: 0 10px 24px rgba(79, 70, 229, 0.45);
}

.hero-btn--primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(79, 70, 229, 0.55);
}

.dashboard__hero-glow {
  position: absolute;
  top: -60%;
  right: -8%;
  width: 22rem;
  height: 22rem;
  border-radius: 50%;
  background: radial-gradient(closest-side, rgba(139, 92, 246, 0.5), transparent 70%);
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
  border-radius: 10px;
  color: #ffffff;
}

.stat-card__icon--indigo {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
}

.stat-card__icon--violet {
  background: linear-gradient(135deg, #7c3aed, #a78bfa);
}

.stat-card__icon--blue {
  background: linear-gradient(135deg, #2563eb, #38bdf8);
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

.stat-card--skeleton,
.panel--skeleton {
  position: relative;
  overflow: hidden;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  min-height: 8.5rem;
  border-radius: var(--radius-lg);
}

.panel--skeleton {
  min-height: 16rem;
}

.stat-card--skeleton::after,
.panel--skeleton::after {
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

/* 主体双栏 */
.dashboard__grid {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
  align-items: start;
}

.panel {
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.panel__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.panel__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.panel__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.panel__link {
  font-size: 0.875rem;
  font-weight: 600;
  text-decoration: none;
}

.panel__subtitle {
  margin: 0 0 var(--space-2);
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-muted-foreground);
}

.panel__divider {
  height: 1px;
  margin: var(--space-3) 0;
  background: var(--color-border);
}

.panel__note {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.panel__empty {
  margin: 0;
  padding: var(--space-3);
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
  text-align: center;
  background: var(--color-surface-strong);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
}

/* 状态分布条 */
.split {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.split__row {
  display: grid;
  grid-template-columns: 5.5rem minmax(0, 1fr) 2rem;
  align-items: center;
  gap: var(--space-2);
}

.split__label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.split__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.split__dot--indigo {
  background: var(--color-primary);
}

.split__dot--slate {
  background: #94a3b8;
}

.split__bar {
  display: block;
  height: 8px;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  overflow: hidden;
}

.split__fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
  border-radius: var(--radius-pill);
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}

.split__fill--muted {
  background: linear-gradient(90deg, #94a3b8, #cbd5f5);
}

.split__value {
  font-family: var(--font-display);
  font-size: 0.875rem;
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* 列表 */
.feed {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.feed__item {
  margin: 0;
}

.feed__link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2);
  border-radius: var(--radius-md);
  text-decoration: none;
  transition: background var(--transition-fast);
}

.feed__link:hover {
  background: var(--color-surface-strong);
}

.feed__link--static {
  cursor: default;
}

.feed__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.feed__title {
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.9375rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed__sub {
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 工作流程 */
.panel--flow {
  padding-bottom: var(--space-3);
}

.flow {
  display: grid;
  gap: var(--space-2);
  grid-template-columns: repeat(6, minmax(0, 1fr));
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: step;
}

.flow__step {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-3) var(--space-2);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  animation: stat-rise 0.4s cubic-bezier(0.22, 1, 0.36, 1) backwards;
  transition:
    border-color var(--transition-fast),
    transform var(--transition-fast);
}

.flow__step:hover {
  border-color: var(--color-border-strong);
  transform: translateY(-2px);
}

.flow__step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -8px;
  z-index: 1;
  width: 8px;
  height: 2px;
  background: var(--color-border-strong);
}

.flow__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  color: #ffffff;
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 700;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: 50%;
  box-shadow: 0 6px 14px rgba(79, 70, 229, 0.3);
}

.flow__title {
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 600;
}

.flow__desc {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  line-height: 1.45;
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

@media (max-width: 1100px) {
  .dashboard__grid {
    grid-template-columns: 1fr;
  }

  .flow {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .flow__step:nth-child(3n)::after {
    display: none;
  }
}

@media (max-width: 640px) {
  .dashboard__greeting {
    font-size: 1.375rem;
  }

  .flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .flow__step:nth-child(3n)::after {
    display: block;
  }

  .flow__step:nth-child(2n)::after {
    display: none;
  }
}
</style>
