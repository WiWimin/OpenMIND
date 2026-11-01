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
          <MaterialSection
            :key="materialsKey"
            :meeting-id="meetingId"
            :readonly="isArchived"
          />
          <LocalWorkspacePanel
            :meeting-id="meetingId"
            :meeting-title="store.current.title"
            :readonly="isArchived"
            @imported="materialsKey += 1"
          />
        </section>

        <section v-else-if="activeTab === 'preparation'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">会前准备</h2>
          <AiAssistantEntry
            v-if="!isArchived"
            description="会前准备由 AI 基于材料生成，可在问答中追问细节。"
            @go-to-chat="openAssistant"
          />
          <PreparationSection :meeting-id="meetingId" :readonly="isArchived" />
        </section>

        <section v-else-if="activeTab === 'records'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">记录与问答</h2>
          <div class="meeting-detail__split">
            <div class="meeting-detail__split-main">
              <RecordSection :key="recordsKey" :meeting-id="meetingId" :readonly="isArchived" />
            </div>
            <aside class="meeting-detail__split-aside">
              <ChatPanel :meeting-id="meetingId" :readonly="isArchived" />
            </aside>
          </div>
        </section>

        <section v-else-if="activeTab === 'audio'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">音频转写</h2>
          <AudioSection
            :meeting-id="meetingId"
            :readonly="isArchived"
            @saved="recordsKey += 1"
          />
        </section>

        <section v-else-if="activeTab === 'minutes'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">纪要与行动项</h2>
          <AiAssistantEntry
            v-if="!isArchived"
            description="纪要与行动项由 AI 从记录中提取生成，确认前可自由编辑。"
            @go-to-chat="openAssistant"
          />
          <MinutesSection
            :key="minutesSectionKey"
            :meeting-id="meetingId"
            :meeting-title="store.current.title"
            :readonly="isArchived"
          />
          <ActionItemSection
            class="meeting-detail__sub"
            :meeting-id="meetingId"
            :readonly="isArchived"
          />
        </section>

        <section v-else-if="activeTab === 'issues'" class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">问题</h2>
          <AiAssistantEntry
            v-if="!isArchived"
            description="问题由 AI 从纪要与记录中提取，可手动编辑补充。"
            @go-to-chat="openAssistant"
          />
          <IssuesSection :meeting-id="meetingId" :readonly="isArchived" />
        </section>

        <section v-else class="meeting-detail__section">
          <h2 class="meeting-detail__section-title">会后收尾</h2>
          <PostMeetingChecklist
            :key="checklistKey"
            :meeting-id="meetingId"
            @go-to-tab="activeTab = $event"
          />
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

    <button
      v-if="!isArchived"
      type="button"
      class="meeting-detail__ai-fab"
      aria-label="打开 AI 助手"
      @click="openAssistant"
    >
      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
        <path
          d="M12 3.5 13.6 8.4 18.5 10 13.6 11.6 12 16.5 10.4 11.6 5.5 10 10.4 8.4 12 3.5Z"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
        <path
          d="M18.5 15.5 19.3 17.7 21.5 18.5 19.3 19.3 18.5 21.5 17.7 19.3 15.5 18.5 17.7 17.7 18.5 15.5Z"
          fill="currentColor"
        />
      </svg>
      <span>AI 助手</span>
    </button>

    <AiAssistantDrawer
      :open="assistantOpen"
      :meeting-id="meetingId"
      @close="assistantOpen = false"
      @minutes-saved="onAssistantMinutesSaved"
      @navigate="onAssistantNavigate"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import ActionItemSection from '@/components/ActionItemSection.vue'
import AiAssistantDrawer from '@/components/AiAssistantDrawer.vue'
import AudioSection from '@/components/AudioSection.vue'
import AiAssistantEntry from '@/components/AiAssistantEntry.vue'
import ChatPanel from '@/components/ChatPanel.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import IssuesSection from '@/components/IssuesSection.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import LocalWorkspacePanel from '@/components/LocalWorkspacePanel.vue'
import MaterialSection from '@/components/MaterialSection.vue'
import MeetingFormDialog from '@/components/MeetingFormDialog.vue'
import MinutesSection from '@/components/MinutesSection.vue'
import PageHeader from '@/components/PageHeader.vue'
import PostMeetingChecklist from '@/components/PostMeetingChecklist.vue'
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
  { value: 'audio', label: '音频' },
  { value: 'minutes', label: '纪要' },
  { value: 'issues', label: '问题' },
  { value: 'checklist', label: '收尾' },
]

function tabFromQuery(): string {
  const tab = route.query?.tab
  return typeof tab === 'string' && tabs.some((item) => item.value === tab) ? tab : 'materials'
}

const activeTab = ref(tabFromQuery())

watch(
  () => route.query?.tab,
  () => {
    const next = tabFromQuery()
    if (next !== activeTab.value) {
      activeTab.value = next
    }
  },
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

const assistantOpen = ref(false)
const materialsKey = ref(0)
const recordsKey = ref(0)
const minutesSectionKey = ref(0)
const checklistKey = ref(0)

watch(activeTab, (tab) => {
  if (tab === 'checklist') {
    checklistKey.value += 1
  }
})

function openAssistant(): void {
  assistantOpen.value = true
}

function onAssistantMinutesSaved(): void {
  minutesSectionKey.value += 1
  activeTab.value = 'minutes'
}

function onAssistantNavigate(tab: string): void {
  activeTab.value = tab
  assistantOpen.value = false
}

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
  background: rgba(21, 94, 239, 0.07);
  color: var(--color-foreground);
}

.meeting-detail__anchor--active {
  color: #ffffff;
  font-weight: 600;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  box-shadow: 0 6px 16px rgba(21, 94, 239, 0.28);
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

/* AI 助手悬浮入口 */
.meeting-detail__ai-fab {
  position: fixed;
  right: 1.25rem;
  bottom: 1.75rem;
  z-index: 80;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.6rem 1.1rem;
  color: #ffffff;
  font-size: 0.875rem;
  font-weight: 600;
  font: inherit;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border: none;
  border-radius: var(--radius-pill);
  box-shadow: 0 8px 24px rgba(21, 94, 239, 0.35);
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast);
}

.meeting-detail__ai-fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 28px rgba(21, 94, 239, 0.45);
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
