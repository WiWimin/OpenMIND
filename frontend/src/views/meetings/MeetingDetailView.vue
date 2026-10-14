<template>
  <section class="meeting-detail">
    <LoadingSpinner v-if="store.currentLoading && !store.current" class="meeting-detail__state" />

    <ErrorMessage
      v-else-if="store.currentError"
      :error="store.currentError"
      retryable
      @retry="reload"
    />

    <template v-else-if="store.current">
      <PageHeader :title="store.current.title" :description="subtitle">
        <template #actions>
          <AppButton variant="ghost" :disabled="isArchived" @click="openEdit">编辑</AppButton>
          <AppButton variant="ghost" :disabled="isArchived" @click="showArchive = true">归档</AppButton>
          <AppButton variant="danger" @click="showDelete = true">删除</AppButton>
        </template>
      </PageHeader>

      <p v-if="isArchived" class="meeting-detail__archived">该会议已归档，仅可查看。</p>

      <ErrorMessage v-if="actionError" :error="actionError" />

      <AppTabs v-model="activeTab" :tabs="tabs" />

      <div class="meeting-detail__panel">
        <MaterialSection v-if="activeTab === 'materials'" :meeting-id="meetingId" />

        <template v-else-if="activeTab === 'records'">
          <RecordSection :meeting-id="meetingId" />
          <ChatPanel class="meeting-detail__chat" :meeting-id="meetingId" />
        </template>

        <EmptyState
          v-else
          :title="activeTabLabel"
          description="该区域将在后续模块（会前准备 / 纪要 / 任务 / 问题）中提供。"
        />
      </div>
    </template>

    <MeetingFormDialog
      :open="showEdit"
      :meeting="store.current"
      :loading="saving"
      :error="saveError"
      @submit="saveEdit"
      @cancel="showEdit = false"
    />

    <ConfirmDialog
      :open="showArchive"
      title="归档会议"
      message="归档后该会议只读，确定归档吗？"
      confirm-text="归档"
      :loading="archiving"
      @confirm="confirmArchive"
      @cancel="showArchive = false"
    />

    <ConfirmDialog
      :open="showDelete"
      title="删除会议"
      message="删除后会议及其关联数据将不可恢复，确定删除吗？"
      confirm-text="删除"
      danger
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="showDelete = false"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import AppTabs from '@/components/AppTabs.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MaterialSection from '@/components/MaterialSection.vue'
import MeetingFormDialog from '@/components/MeetingFormDialog.vue'
import PageHeader from '@/components/PageHeader.vue'
import RecordSection from '@/components/RecordSection.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useMeetingsStore } from '@/stores/meetings'
import type { CreateMeetingPayload } from '@/types/meeting'
import type { TabItem } from '@/types/ui'
import { formatDateTime } from '@/utils/datetime'

const route = useRoute()
const router = useRouter()
const store = useMeetingsStore()

const meetingId = computed(() => String(route.params.meetingId))

const tabs: TabItem[] = [
  { value: 'materials', label: '材料' },
  { value: 'preparation', label: '会前准备' },
  { value: 'records', label: '记录' },
  { value: 'minutes', label: '纪要' },
  { value: 'tasks', label: '任务' },
  { value: 'issues', label: '问题' },
]
const activeTab = ref('materials')
const activeTabLabel = computed(
  () => tabs.find((tab) => tab.value === activeTab.value)?.label ?? '',
)

const isArchived = computed(() => store.current?.status === 'archived')

const subtitle = computed(() => {
  const meeting = store.current
  if (!meeting) {
    return ''
  }
  const parts = [meeting.topic, meeting.meeting_time ? formatDateTime(meeting.meeting_time) : '']
  return parts.filter(Boolean).join(' · ')
})

const showEdit = ref(false)
const saving = ref(false)
const saveError = ref<unknown>(null)
const showArchive = ref(false)
const archiving = ref(false)
const showDelete = ref(false)
const deleting = ref(false)
const actionError = ref<unknown>(null)

function reload(): void {
  void store.fetchMeeting(meetingId.value)
}

onMounted(reload)

function openEdit(): void {
  saveError.value = null
  showEdit.value = true
}

async function saveEdit(payload: CreateMeetingPayload): Promise<void> {
  saving.value = true
  saveError.value = null
  try {
    await store.updateMeeting(meetingId.value, payload)
    showEdit.value = false
  } catch (caught) {
    saveError.value = caught
  } finally {
    saving.value = false
  }
}

async function confirmArchive(): Promise<void> {
  archiving.value = true
  actionError.value = null
  try {
    await store.archiveMeeting(meetingId.value)
    showArchive.value = false
  } catch (caught) {
    actionError.value = caught
  } finally {
    archiving.value = false
  }
}

async function confirmDelete(): Promise<void> {
  deleting.value = true
  actionError.value = null
  try {
    await store.deleteMeeting(meetingId.value)
    showDelete.value = false
    await router.push({ name: ROUTE_NAMES.meetings })
  } catch (caught) {
    actionError.value = caught
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.meeting-detail__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

.meeting-detail__archived {
  margin: 0 0 var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
}

.meeting-detail__panel {
  padding-top: var(--space-4);
}

.meeting-detail__chat {
  margin-top: var(--space-4);
}
</style>
