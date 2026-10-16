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

      <nav class="meeting-detail__anchors" aria-label="页面小节">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          type="button"
          class="meeting-detail__anchor"
          :class="{ 'meeting-detail__anchor--active': activeTab === tab.value }"
          role="tab"
          :aria-selected="activeTab === tab.value"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div class="meeting-detail__panel">
        <section v-if="activeTab === 'materials'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">材料</h2>
          <MaterialSection :meeting-id="meetingId" />
        </section>

        <section v-else-if="activeTab === 'preparation'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">会前准备</h2>
          <AiAssistantEntry
            description="会前准备由 AI 基于材料生成，可在问答中追问细节。"
            @go-to-chat="activeTab = 'records'"
          />
          <PreparationSection :meeting-id="meetingId" />
        </section>

        <section v-else-if="activeTab === 'records'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">记录与问答</h2>
          <div class="meeting-detail__split">
            <div class="meeting-detail__split-main">
              <RecordSection :meeting-id="meetingId" />
            </div>
            <aside class="meeting-detail__split-aside">
              <ChatPanel :meeting-id="meetingId" />
            </aside>
          </div>
        </section>

        <section v-else-if="activeTab === 'minutes'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">纪要与行动项</h2>
          <AiAssistantEntry
            description="纪要与行动项由 AI 从记录中提取生成，确认前可自由编辑。"
            @go-to-chat="activeTab = 'records'"
          />
          <MinutesSection :meeting-id="meetingId" />
          <ActionItemSection class="meeting-detail__sub" :meeting-id="meetingId" />
        </section>

        <section v-else-if="activeTab === 'tasks'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">任务</h2>
          <EmptyState title="任务" description="该区域将在后续模块（任务）中提供。" />
        </section>

        <section v-else class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">问题</h2>
          <AiAssistantEntry
            description="问题由 AI 从纪要与记录中提取，可手动编辑补充。"
            @go-to-chat="activeTab = 'records'"
          />
          <IssuesSection :meeting-id="meetingId" />
        </section>
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
import ActionItemSection from '@/components/ActionItemSection.vue'
import AiAssistantEntry from '@/components/AiAssistantEntry.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import IssuesSection from '@/components/IssuesSection.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MaterialSection from '@/components/MaterialSection.vue'
import MeetingFormDialog from '@/components/MeetingFormDialog.vue'
import MinutesSection from '@/components/MinutesSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import PreparationSection from '@/components/PreparationSection.vue'
import RecordSection from '@/components/RecordSection.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useMeetingsStore } from '@/stores/meetings'
import type { CreateMeetingPayload } from '@/types/meeting'
import type { TabItem } from '@/types/ui'
import { formatDateTime } from '@/utils/datetime'

const route = useRoute()
const router = useRouter()
const toast = useToast()
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
    toast.success('会议已更新')
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
    toast.success('会议已归档')
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
    toast.success('会议已删除')
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
  background: rgba(217, 119, 6, 0.08);
  border: 1px solid rgba(217, 119, 6, 0.24);
  border-radius: var(--radius-md);
  color: #92400e;
  font-size: 0.875rem;
}

/* 小节切换导航 */
.meeting-detail__anchors {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  padding: var(--space-2);
  margin-bottom: var(--space-3);
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
}

.meeting-detail__anchor {
  padding: 0.4rem 0.9rem;
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
  font-weight: 500;
  font: inherit;
  text-decoration: none;
  border: none;
  background: transparent;
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.meeting-detail__anchor:hover {
  background: rgba(59, 111, 212, 0.07);
  color: var(--color-foreground);
}

.meeting-detail__anchor--active {
  color: #ffffff;
  font-weight: 600;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  box-shadow: 0 6px 16px rgba(59, 111, 212, 0.28);
}

.meeting-detail__panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
}

/* 当前小节 */
.meeting-detail__section {
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border);
}

.meeting-detail__section:first-child {
  padding-top: 0;
  border-top: none;
}

.meeting-detail__section-title {
  margin: 0 0 var(--space-3);
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--color-foreground);
}

/* 记录小节：左记录 + 右问答 双栏 */
.meeting-detail__split {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
}

.meeting-detail__split-aside {
  padding-left: var(--space-4);
  border-left: 1px solid var(--color-border);
}

.meeting-detail__sub {
  margin-top: var(--space-4);
}

@media (max-width: 900px) {
  .meeting-detail__split {
    grid-template-columns: 1fr;
  }

  .meeting-detail__split-aside {
    padding-left: 0;
    border-left: none;
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-4);
  }
}
</style>
