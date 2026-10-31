<template>
  <section class="stage-shell">
    <div class="stage-shell__card">
      <div class="stage-shell__head">
        <div class="stage-shell__intro">
          <h1 class="stage-shell__title">{{ title }}</h1>
          <p v-if="description" class="stage-shell__description">{{ description }}</p>
        </div>

        <div class="stage-shell__meeting">
          <label class="stage-bar__select">
            <span class="stage-bar__sr">选择会议</span>
            <select
              :value="meetingId"
              :disabled="meetingsLoading || meetings.length === 0"
              @change="onSelect"
            >
              <option v-if="meetings.length === 0" value="">暂无会议</option>
              <option v-for="item in meetings" :key="item.meeting_id" :value="item.meeting_id">
                {{ item.title }}（{{ statusLabel(item.status) }}）
              </option>
            </select>
          </label>
          <button type="button" class="stage-bar__create" @click="openCreate">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
              <path
                d="M12 5.5v13M5.5 12h13"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
              />
            </svg>
            新建会议
          </button>
          <slot name="actions" />
        </div>
      </div>

      <nav class="stage-steps" aria-label="会议流程">
        <RouterLink
          v-for="(step, index) in steps"
          :key="step.key"
          class="stage-step"
          :class="{
            'stage-step--active': step.key === stage,
            'stage-step--done': index < activeIndex,
          }"
          :to="step.to"
        >
          <span class="stage-step__index">{{ index + 1 }}</span>
          <span class="stage-step__label">{{ step.label }}</span>
          <svg
            v-if="index < steps.length - 1"
            class="stage-step__divider"
            viewBox="0 0 24 24"
            width="12"
            height="12"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M9 5.5 15.5 12 9 18.5"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </RouterLink>
      </nav>
    </div>

    <ErrorMessage v-if="error" :error="error" retryable @retry="loadMeeting" />

    <div class="stage-shell__body">
      <LoadingSpinner v-if="loading" class="stage-shell__state" />

      <EmptyState
        v-else-if="!meeting"
        title="先选择一场会议"
        description="选择已有会议或新建一场会议，Agent 会基于该会议的上下文继续处理。"
      >
        <AppButton @click="openCreate">新建会议</AppButton>
      </EmptyState>

      <template v-else>
        <slot :meeting="meeting" :meeting-id="meeting.meeting_id" />
      </template>
    </div>

    <MeetingFormDialog
      :open="showCreate"
      :loading="creating"
      :error="createError"
      @submit="createMeeting"
      @cancel="showCreate = false"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as meetingsApi from '@/api/meetings'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MeetingFormDialog from '@/components/MeetingFormDialog.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import type { CreateMeetingPayload, Meeting, MeetingStatus } from '@/types/meeting'

type StageKey = 'preprocess' | 'asr' | 'minutes'

const props = defineProps<{
  stage: StageKey
  title: string
  description?: string
}>()

const route = useRoute()
const router = useRouter()
const toast = useToast()

const meetings = ref<Meeting[]>([])
const meetingsLoading = ref(false)
const meetingId = ref(String(route.query.meetingId ?? ''))
const meeting = ref<Meeting | null>(null)
const loading = ref(false)
const error = ref<unknown>(null)

const showCreate = ref(false)
const creating = ref(false)
const createError = ref<unknown>(null)

const steps = computed(() => {
  const query = meetingId.value ? { meetingId: meetingId.value } : {}
  return [
    {
      key: 'preprocess' as const,
      label: '资料预处理',
      to: { name: ROUTE_NAMES.preprocess, query },
    },
    { key: 'asr' as const, label: '实时录音转写', to: { name: ROUTE_NAMES.asr, query } },
    {
      key: 'minutes' as const,
      label: '会后智能处理',
      to: { name: ROUTE_NAMES.minutesGenerate, query },
    },
  ]
})

const activeIndex = computed(() => steps.value.findIndex((step) => step.key === props.stage))

function statusLabel(status: MeetingStatus): string {
  return status === 'archived' ? '已归档' : '已安排'
}

function syncQuery(): void {
  const current = String(route.query.meetingId ?? '')
  if (current === meetingId.value) {
    return
  }
  const query = { ...route.query }
  if (meetingId.value) {
    query.meetingId = meetingId.value
  } else {
    delete query.meetingId
  }
  void router.replace({ query })
}

async function loadMeeting(): Promise<void> {
  if (!meetingId.value) {
    meeting.value = null
    return
  }
  loading.value = true
  error.value = null
  try {
    meeting.value = await meetingsApi.getMeeting(meetingId.value)
  } catch (caught) {
    meeting.value = null
    error.value = caught
  } finally {
    loading.value = false
  }
}

async function loadMeetings(): Promise<void> {
  meetingsLoading.value = true
  try {
    const result = await meetingsApi.listMeetings({ page: 1, page_size: 50 })
    meetings.value = result.items
    if (!meetingId.value && result.items.length > 0) {
      const preferred = result.items.find((item) => item.status === 'scheduled') ?? result.items[0]
      select(preferred.meeting_id)
    }
  } catch {
    meetings.value = []
  } finally {
    meetingsLoading.value = false
  }
}

function select(id: string): void {
  meetingId.value = id
  syncQuery()
  void loadMeeting()
}

function onSelect(event: Event): void {
  const target = event.target as HTMLSelectElement
  if (target.value) {
    select(target.value)
  }
}

function openCreate(): void {
  createError.value = null
  showCreate.value = true
}

async function createMeeting(payload: CreateMeetingPayload): Promise<void> {
  creating.value = true
  createError.value = null
  try {
    const created = await meetingsApi.createMeeting(payload)
    showCreate.value = false
    toast.success('会议已创建')
    await loadMeetings()
    select(created.meeting_id)
  } catch (caught) {
    createError.value = caught
  } finally {
    creating.value = false
  }
}

watch(
  () => route.query.meetingId,
  (value) => {
    const next = String(value ?? '')
    if (next && next !== meetingId.value) {
      meetingId.value = next
      void loadMeeting()
    }
  },
)

onMounted(() => {
  void loadMeetings()
  if (meetingId.value) {
    void loadMeeting()
  }
})
</script>

<style scoped>
.stage-shell {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
}

/* 页头卡片：左侧标题与会议选择，右侧三步流程 */
.stage-shell__card {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

/* 内容区：撑满剩余高度，内部滚动交给各页面 */
.stage-shell__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.stage-shell__body > :deep(.stage-shell__state) {
  flex: 1;
}

.stage-shell__body > :deep(.empty-state) {
  flex: 1;
}

.stage-shell__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.stage-shell__intro {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.stage-shell__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.stage-shell__description {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  line-height: 1.6;
}

.stage-shell__meeting {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.stage-bar__select {
  position: relative;
  display: inline-flex;
}

.stage-bar__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.stage-bar__select select {
  max-width: 15rem;
  min-height: 2rem;
  padding: 0 1.75rem 0 var(--space-2);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.8125rem;
  font-weight: 550;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.stage-bar__select select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.stage-bar__create {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 2rem;
  padding: 0 var(--space-2);
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.stage-bar__create:hover {
  background: var(--color-primary-soft);
}

.stage-steps {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  padding-top: var(--space-2);
  border-top: 1px solid var(--color-border);
}

.stage-step {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.35rem 0.65rem;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  font-weight: 550;
  text-decoration: none;
  border-radius: var(--radius-md);
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.stage-step:hover {
  color: var(--color-foreground);
  background: var(--color-surface-muted);
}

.stage-step__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.1rem;
  height: 1.1rem;
  font-size: 0.6875rem;
  font-variant-numeric: tabular-nums;
  background: var(--color-surface-muted);
  border: 1px solid var(--color-border);
  border-radius: 50%;
}

.stage-step--active {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.stage-step--active .stage-step__index {
  color: #ffffff;
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.stage-step--done .stage-step__index {
  color: var(--color-accent-strong);
  background: var(--color-accent-soft);
  border-color: rgba(13, 148, 136, 0.2);
}

.stage-step__divider {
  flex: 0 0 auto;
  margin-left: 2px;
  color: var(--color-border-strong);
}

.stage-shell__state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
}

@media (max-width: 900px) {
  .stage-shell__card {
    padding: var(--space-3) var(--space-3);
  }

  .stage-step {
    padding: 0.3rem 0.5rem;
  }

  .stage-step__label {
    font-size: 0.6875rem;
  }
}
</style>
