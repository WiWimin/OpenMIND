<template>
  <div class="post-checklist">
    <LoadingSpinner v-if="loading" class="post-checklist__state" />

    <ErrorMessage
      v-else-if="error"
      class="post-checklist__state"
      :error="error"
      retryable
      @retry="load()"
    />

    <template v-else>
      <p v-if="finished" class="post-checklist__done">本次会议已收尾，纪要已确认且没有待处理事项。</p>

      <ul class="post-checklist__list">
        <li class="post-checklist__item">
          <div class="post-checklist__body">
            <span class="post-checklist__label">会议纪要</span>
            <StatusBadge :tone="minutesTone" :label="minutesLabel" />
          </div>
          <AppButton variant="ghost" @click="emit('go-to-tab', 'minutes')">
            {{ minutesActionLabel }}
          </AppButton>
        </li>

        <li class="post-checklist__item">
          <div class="post-checklist__body">
            <span class="post-checklist__label">待确认行动项</span>
            <StatusBadge :tone="pendingActionItems > 0 ? 'warning' : 'success'" :label="`${pendingActionItems} 项`" />
          </div>
          <AppButton variant="ghost" @click="emit('go-to-tab', 'minutes')">去确认</AppButton>
        </li>

        <li class="post-checklist__item">
          <div class="post-checklist__body">
            <span class="post-checklist__label">待处理问题</span>
            <StatusBadge :tone="openIssues > 0 ? 'warning' : 'success'" :label="`${openIssues} 项`" />
          </div>
          <AppButton variant="ghost" @click="emit('go-to-tab', 'issues')">去处理</AppButton>
        </li>

        <li class="post-checklist__item">
          <div class="post-checklist__body">
            <span class="post-checklist__label">已转个人任务</span>
            <StatusBadge tone="info" :label="`${convertedActionItems} 项`" />
          </div>
          <RouterLink class="post-checklist__link" :to="{ name: ROUTE_NAMES.tasks }">
            查看我的任务
          </RouterLink>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import * as actionItemsApi from '@/api/actionItems'
import * as issuesApi from '@/api/issues'
import * as minutesApi from '@/api/minutes'
import AppButton from '@/components/AppButton.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import type { MinutesStatus } from '@/types/minutes'
import type { StatusTone } from '@/types/ui'

const props = defineProps<{ meetingId: string }>()
const emit = defineEmits<{ 'go-to-tab': [tab: string] }>()

const loading = ref(true)
const error = ref<unknown>(null)

const latestMinutesStatus = ref<MinutesStatus | null>(null)
const hasMinutes = ref(false)
const pendingActionItems = ref(0)
const convertedActionItems = ref(0)
const openIssues = ref(0)

const minutesLabel = computed(() => {
  if (!hasMinutes.value) {
    return '未生成'
  }
  return latestMinutesStatus.value === 'confirmed' ? '已确认' : '草稿待确认'
})

const minutesTone = computed<StatusTone>(() => {
  if (!hasMinutes.value) {
    return 'danger'
  }
  return latestMinutesStatus.value === 'confirmed' ? 'success' : 'warning'
})

const minutesActionLabel = computed(() => (hasMinutes.value ? '查看纪要' : '生成纪要'))

const finished = computed(
  () =>
    hasMinutes.value &&
    latestMinutesStatus.value === 'confirmed' &&
    pendingActionItems.value === 0 &&
    openIssues.value === 0,
)

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [minutes, actionItems, issues] = await Promise.all([
      minutesApi.listMinutes(props.meetingId),
      actionItemsApi.listActionItems(props.meetingId),
      issuesApi.listIssues(props.meetingId),
    ])
    const latest = minutes.items.at(-1)
    hasMinutes.value = Boolean(latest)
    latestMinutesStatus.value = latest?.status ?? null
    pendingActionItems.value = actionItems.items.filter(
      (item) => item.status === 'pending_confirmation',
    ).length
    convertedActionItems.value = actionItems.items.filter((item) => item.status === 'converted')
      .length
    openIssues.value = issues.items.filter((issue) => issue.status === 'open').length
  } catch (caught) {
    error.value = caught
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.post-checklist__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.post-checklist__done {
  margin: 0 0 var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.28);
  border-radius: var(--radius-md);
  color: #047857;
  font-size: 0.875rem;
  font-weight: 600;
}

.post-checklist__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.post-checklist__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.post-checklist__body {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.post-checklist__label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-foreground);
}

.post-checklist__link {
  color: var(--color-primary);
  font-size: 0.875rem;
  font-weight: 600;
  text-decoration: none;
}

.post-checklist__link:hover {
  text-decoration: underline;
}
</style>
