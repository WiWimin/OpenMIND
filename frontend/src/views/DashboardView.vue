<template>
  <section class="home">
    <!-- 欢迎横幅：问好 + 项目介绍 + IP 形象 -->
    <section class="home__hero">
      <div class="home__hero-copy">
        <h1 class="home__greeting">{{ greeting }}，{{ userName }} <span aria-hidden="true">👋</span></h1>
        <p class="home__summary">
          今天有 <strong>{{ stats.scheduled }}</strong> 场会议和
          <strong>{{ stats.todo }}</strong> 项待办任务
        </p>
      </div>
      <img
        class="home__mascot"
        :src="mascotUrl"
        alt="OpenMIND 助手：我已整理今日日程"
      />
    </section>

    <section class="home__intro">
      <div class="home__intro-copy">
        <h2 class="home__intro-title">OpenMIND 智能会议助手</h2>
        <p class="home__intro-desc">基于 AI 的会议纪要、日程与任务协作平台</p>
      </div>
      <button class="home__cta" type="button" @click="openCreate">新建会议</button>
    </section>

    <ErrorMessage
      v-if="statsError"
      :error="statsError"
      fallback="统计数据加载失败。"
      retryable
      @retry="loadStats"
    />

    <!-- 我的会议 -->
    <section class="home__panel">
      <header class="home__panel-head">
        <h2 class="home__panel-title">我的会议</h2>
        <RouterLink class="home__panel-link" :to="{ name: ROUTE_NAMES.meetings }">
          查看全部
        </RouterLink>
      </header>

      <LoadingSpinner
        v-if="store.loading && store.items.length === 0"
        class="home__state"
      />

      <ErrorMessage
        v-else-if="store.error"
        :error="store.error"
        retryable
        @retry="store.fetchList()"
      />

      <EmptyState
        v-else-if="recentMeetings.length === 0"
        title="还没有会议"
        description="创建一个会议，开始会前准备、会中记录与会后整理。"
      >
        <AppButton @click="openCreate">新建会议</AppButton>
      </EmptyState>

      <ul v-else class="home__meetings">
        <li v-for="meeting in recentMeetings" :key="meeting.meeting_id">
          <button
            type="button"
            class="home__meeting"
            @click="openDetail(meeting.meeting_id)"
          >
            <span class="home__meeting-title">{{ meeting.title }}</span>
            <span class="home__meeting-time">{{ formatMeetingTime(meeting.meeting_time) }}</span>
            <StatusBadge
              :label="meetingStatusMeta[meeting.status].label"
              :tone="meetingStatusMeta[meeting.status].tone"
            />
          </button>
        </li>
      </ul>
    </section>

    <!-- 待办任务 -->
    <section class="home__panel">
      <header class="home__panel-head">
        <h2 class="home__panel-title">待办任务</h2>
        <RouterLink class="home__panel-link" :to="{ name: ROUTE_NAMES.tasks }">
          查看全部
        </RouterLink>
      </header>

      <LoadingSpinner
        v-if="tasksLoading && tasks.length === 0"
        class="home__state"
      />

      <ErrorMessage
        v-else-if="tasksError"
        :error="tasksError"
        retryable
        @retry="loadTasks"
      />

      <p v-else-if="tasks.length === 0" class="home__tasks-empty">
        今天没有待办任务，保持当前的会议节奏即可。
      </p>

      <ul v-else class="home__tasks">
        <li v-for="task in tasks" :key="task.task_id">
          <label class="home__task">
            <input
              type="checkbox"
              class="home__task-check"
              :checked="task.status === 'completed'"
              :disabled="savingTaskId === task.task_id"
              :aria-label="`完成任务：${task.title}`"
              @change="completeTask(task)"
            />
            <span class="home__task-title">{{ task.title }}</span>
            <span class="home__task-due">
              <NavIcon name="clock" :size="14" />
              {{ task.due_date ? formatDate(task.due_date) : '未设置截止时间' }}
            </span>
          </label>
        </li>
      </ul>
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
import { listTasks, updateTask } from '@/api/tasks'
import mascotUrl from '@/assets/homepage-ip.png'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MeetingFormDialog from '@/components/MeetingFormDialog.vue'
import NavIcon from '@/components/NavIcon.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'
import { useMeetingsStore } from '@/stores/meetings'
import type { CreateMeetingPayload } from '@/types/meeting'
import type { PersonalTask } from '@/types/task'
import { formatDate } from '@/utils/datetime'
import { meetingStatusMeta } from '@/utils/statusLabels'

const MEETING_LIMIT = 5
const TASK_LIMIT = 5

const store = useMeetingsStore()
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const toast = useToast()

const stats = ref({ scheduled: 0, todo: 0 })
const statsLoading = ref(true)
const statsError = ref<unknown>(null)

const tasks = ref<PersonalTask[]>([])
const tasksLoading = ref(true)
const tasksError = ref<unknown>(null)
const savingTaskId = ref<string | null>(null)

const showForm = ref(false)
const saving = ref(false)
const saveError = ref<unknown>(null)

const userName = computed(() => auth.user?.name ?? '朋友')

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const recentMeetings = computed(() => store.items.slice(0, MEETING_LIMIT))

function formatMeetingTime(value: string | null): string {
  const date = new Date(value ?? '')
  if (!value || Number.isNaN(date.getTime())) {
    return '未安排时间'
  }
  const startOfDay = (input: Date): number =>
    new Date(input.getFullYear(), input.getMonth(), input.getDate()).getTime()
  const dayOffset = Math.round((startOfDay(date) - startOfDay(new Date())) / 86_400_000)
  const time = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  if (dayOffset === 0) return `今天 ${time}`
  if (dayOffset === 1) return `明天 ${time}`
  if (dayOffset === -1) return `昨天 ${time}`
  return `${date.getMonth() + 1} 月 ${date.getDate()} 日 ${time}`
}

async function loadStats(): Promise<void> {
  statsLoading.value = true
  statsError.value = null
  try {
    const [scheduled, todo] = await Promise.all([
      listMeetings({ status: 'scheduled', page: 1, page_size: 1 }),
      listTasks({ status: 'todo', page: 1, page_size: 1 }),
    ])
    stats.value = {
      scheduled: scheduled.pagination.total,
      todo: todo.pagination.total,
    }
  } catch (error) {
    statsError.value = error
  } finally {
    statsLoading.value = false
  }
}

async function loadTasks(): Promise<void> {
  tasksLoading.value = true
  tasksError.value = null
  try {
    const result = await listTasks({ status: 'todo', page: 1, page_size: TASK_LIMIT })
    tasks.value = result.items
  } catch (error) {
    tasksError.value = error
  } finally {
    tasksLoading.value = false
  }
}

async function completeTask(task: PersonalTask): Promise<void> {
  if (savingTaskId.value) {
    return
  }
  savingTaskId.value = task.task_id
  try {
    await updateTask(task.task_id, { status: 'completed' })
    toast.success('任务已完成')
    tasks.value = tasks.value.filter((item) => item.task_id !== task.task_id)
    stats.value = { ...stats.value, todo: Math.max(stats.value.todo - 1, 0) }
  } catch (error) {
    tasksError.value = error
  } finally {
    savingTaskId.value = null
  }
}

function openCreate(): void {
  saveError.value = null
  showForm.value = true
}

function closeForm(): void {
  showForm.value = false
}

function openDetail(meetingId: string): void {
  void router.push({ name: ROUTE_NAMES.meetingDetail, params: { meetingId } })
}

async function createMeeting(payload: CreateMeetingPayload): Promise<void> {
  saving.value = true
  saveError.value = null
  try {
    const created = await store.createMeeting(payload)
    showForm.value = false
    toast.success('会议已创建，进入会议流程')
    await router.push({
      name: ROUTE_NAMES.newMeeting,
      query: { meetingId: created.meeting_id },
    })
    void loadStats()
  } catch (caught) {
    saveError.value = caught
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadStats()
  void loadTasks()
  void store.fetchList()
  if (route.query.create === '1') {
    openCreate()
    void router.replace({ query: {} })
  }
})

// /dashboard 与 /meetings 复用同一组件实例，路由变化在这里联动
watch(
  () => route.fullPath,
  () => {
    if (route.query.create === '1') {
      openCreate()
      void router.replace({ query: {} })
    }
  },
)
</script>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 欢迎横幅 */
.home__hero {
  position: relative;
  overflow: hidden;
  padding: 2.75rem 2.5rem 5.25rem;
  background: linear-gradient(118deg, #e3edff 0%, #eaf0fe 48%, #f2effe 100%);
  border: 1px solid rgba(21, 94, 239, 0.1);
  border-radius: var(--radius-xl);
}

.home__hero-copy {
  position: relative;
  z-index: 1;
  max-width: 60%;
}

.home__greeting {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 2.6vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-foreground);
}

.home__summary {
  margin: var(--space-2) 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.9375rem;
}

.home__summary strong {
  padding: 0 2px;
  color: var(--color-primary-strong);
  font-size: 1.05rem;
  font-weight: 700;
}

.home__mascot {
  position: absolute;
  right: 4%;
  bottom: 0;
  height: 100%;
  max-height: 15rem;
  filter: drop-shadow(0 12px 20px rgba(21, 94, 239, 0.16));
  user-select: none;
  pointer-events: none;
}

/* 项目介绍卡（压在横幅下缘） */
.home__intro {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin: -2.9rem 1.5rem 0;
  padding: var(--space-5) var(--space-6);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
}

.home__intro-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.375rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-foreground);
}

.home__intro-desc {
  margin: var(--space-1) 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
}

.home__cta {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.8rem 2.1rem;
  color: #ffffff;
  font: inherit;
  font-size: 0.9375rem;
  font-weight: 650;
  background: var(--color-primary);
  border: 0;
  border-radius: var(--radius-pill);
  box-shadow: 0 10px 22px rgba(21, 94, 239, 0.32);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    transform var(--transition-fast),
    box-shadow var(--transition-fast);
}

.home__cta:hover {
  background: var(--color-primary-strong);
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(21, 94, 239, 0.36);
}

.home__cta:active {
  transform: translateY(0);
}

/* 列表面板 */
.home__panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.home__panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--color-border);
}

.home__panel-title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 650;
  color: var(--color-foreground);
}

.home__panel-link {
  color: var(--color-primary-strong);
  font-size: 0.8125rem;
  font-weight: 600;
  text-decoration: none;
}

.home__panel-link:hover {
  text-decoration: underline;
  text-underline-offset: 2px;
}

.home__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

/* 我的会议 */
.home__meetings {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.home__meetings li + li .home__meeting {
  border-top: 1px dashed var(--color-border);
}

.home__meeting {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-3) var(--space-2);
  color: inherit;
  font: inherit;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.home__meeting:hover {
  background: var(--color-surface-muted);
}

.home__meeting-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-foreground);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home__meeting-time {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  white-space: nowrap;
}

/* 待办任务 */
.home__tasks {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.home__tasks li + li .home__task {
  border-top: 1px dashed var(--color-border);
}

.home__task {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.home__task:hover {
  background: var(--color-surface-muted);
}

.home__task-check {
  flex: 0 0 auto;
  width: 1.05rem;
  height: 1.05rem;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.home__task-check:disabled {
  cursor: progress;
}

.home__task-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-size: 0.875rem;
  color: var(--color-foreground);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home__task-due {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  white-space: nowrap;
}

.home__tasks-empty {
  margin: 0;
  padding: var(--space-3);
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  background: var(--color-surface-strong);
  border-radius: var(--radius-md);
}

@media (max-width: 900px) {
  .home__hero {
    padding: 2.25rem 2rem 4.5rem;
  }

  .home__hero-copy {
    max-width: 55%;
  }

  .home__mascot {
    right: 0;
    height: 9.5rem;
  }

  .home__intro {
    margin: -2.5rem 0.75rem 0;
    padding: var(--space-4) var(--space-5);
  }
}

@media (max-width: 640px) {
  .home__mascot {
    display: none;
  }

  .home__hero {
    padding: 2rem 1.5rem 4.25rem;
  }

  .home__hero-copy {
    max-width: 100%;
  }

  .home__intro {
    flex-direction: column;
    align-items: flex-start;
    margin: -2.5rem 0.25rem 0;
  }

  .home__cta {
    width: 100%;
  }

  .home__meeting,
  .home__task {
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .home__meeting-title,
  .home__task-title {
    flex-basis: 100%;
    white-space: normal;
  }
}
</style>
