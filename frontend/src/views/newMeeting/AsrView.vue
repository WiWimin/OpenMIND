<template>
  <StageShell
    stage="asr"
    title="实时录音转写"
  >
    <template #actions>
      <AppButton variant="ghost" class="ai-header-btn" @click="chatOpen = true">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
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
        AI 助手
      </AppButton>
    </template>

    <template #default="{ meeting }">
      <div class="asr-page">
        <!-- 左栏：会议信息 -->
        <aside class="asr-page__info">
          <h2 class="info-card__title">会议信息</h2>
          <div class="info-list">
              <div class="info-list__item">
                <span class="info-list__label">会议名称</span>
                <span class="info-list__value">{{ meeting.title }}</span>
              </div>
              <div class="info-list__item">
                <span class="info-list__label">会议时间</span>
                <span class="info-list__value">
                  {{ meeting.meeting_time ? formatDateTime(meeting.meeting_time) : '未设置' }}
                </span>
              </div>
              <div class="info-list__item">
                <span class="info-list__label">会议主题</span>
                <span class="info-list__value">{{ meeting.topic || '未填写' }}</span>
              </div>
              <div class="info-list__item">
                <span class="info-list__label">文件状态</span>
                <span class="info-list__value">
                  {{
                    audioPagination.total > 0
                      ? `已上传 ${audioPagination.total} 个音频`
                      : '未上传音频'
                  }}
                </span>
              </div>
              <div class="info-list__item">
                <span class="info-list__label">会议记录</span>
                <span class="info-list__value">{{ recordPagination.total }} 条</span>
              </div>
          </div>
        </aside>

        <!-- 中栏：录音与转写 -->
        <main ref="mainEl" class="asr-page__main" @mouseup="captureSelection">
          <section class="work-card">
            <!-- 顶部操作条 -->
            <div class="work-card__toolbar">
              <div v-if="meeting.status !== 'archived'" class="work-card__tools">
                <AppButton
                  v-if="!recording"
                  :loading="startingRecorder || uploading"
                  @click="startRecording"
                >
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                    <path
                      d="M12 3.5a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0v-5a3 3 0 0 0-3-3ZM6.5 11.5v.5a5.5 5.5 0 0 0 11 0v-.5M12 17.5V21"
                      stroke="currentColor"
                      stroke-width="1.7"
                      stroke-linecap="round"
                    />
                  </svg>
                  开始实时录音
                </AppButton>
                <button
                  v-else
                  type="button"
                  class="recording-pill"
                  :disabled="stoppingRecorder"
                  @click="stopRecording"
                >
                  <span class="recording-pill__dot" aria-hidden="true" />
                  {{ stoppingRecorder ? '正在结束转写…' : `停止录音 · ${recordingLabel}` }}
                </button>
                <AppButton
                  variant="ghost"
                  :disabled="recording || uploading"
                  @click="fileInputEl?.click()"
                >
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                    <path
                      d="M12 16V4m0 0 4 4m-4-4-4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                      stroke="currentColor"
                      stroke-width="1.7"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    />
                  </svg>
                  上传音频文件
                </AppButton>
                <input
                  ref="fileInputEl"
                  type="file"
                  accept=".mp3,.wav,.m4a,.webm"
                  hidden
                  @change="onFileChange"
                />
              </div>
              <div v-if="meeting.status !== 'archived'" class="work-card__tools">
                <AppButton
                  variant="ghost"
                  size="sm"
                  :disabled="selectedKeys.length === 0 || marking"
                  @click="applyMarker('highlight')"
                >
                  标记重点
                </AppButton>
                <AppButton
                  variant="ghost"
                  size="sm"
                  :disabled="selectedKeys.length === 0 || marking"
                  @click="applyMarker('decision')"
                >
                  标记决议
                </AppButton>
                <AppButton
                  variant="ghost"
                  size="sm"
                  :disabled="selectedKeys.length === 0 || marking"
                  @click="applyMarker('question')"
                >
                  标记疑问
                </AppButton>
              </div>
            </div>

            <!-- 主体：音频条 / 转写文稿 / 记录时间轴 -->
            <div class="work-card__body">
              <ErrorMessage v-if="uploadError" :error="uploadError" />
              <ErrorMessage v-if="audioActionError" :error="audioActionError" />
              <p v-if="recording" class="record-note" role="status">
                正在录音（{{ recordingLabel }}），语音将分段转写并实时显示，停止后自动完成合并。
              </p>

              <LoadingSpinner
                v-if="audioLoading && audioItems.length === 0"
                class="work-card__state"
              />
              <ErrorMessage
                v-else-if="audioError"
                :error="audioError"
                retryable
                @retry="loadAudio()"
              />

              <template v-else>
                <div v-if="audioItems.length > 0" class="audio-chips">
                  <button
                    v-for="item in audioItems"
                    :key="item.audio_id"
                    type="button"
                    class="audio-chip"
                    :class="{ 'audio-chip--active': selectedAudio?.audio_id === item.audio_id }"
                    :disabled="recording"
                    @click="selectAudio(item)"
                  >
                    <span class="audio-chip__name">{{ item.file_name }}</span>
                    <StatusBadge
                      :label="audioStatusMeta[item.status].label"
                      :tone="audioStatusMeta[item.status].tone"
                    />
                  </button>
                </div>

                <div v-if="selectedAudio" class="transcript">
                  <div class="transcript__head">
                    <StatusBadge
                      :label="audioStatusMeta[selectedAudio.status].label"
                      :tone="audioStatusMeta[selectedAudio.status].tone"
                    />
                    <span class="transcript__name">{{ selectedAudio.file_name }}</span>
                    <button
                      v-if="meeting.status !== 'archived' && canEditTranscript"
                      type="button"
                      class="transcript__edit-toggle"
                      @click="toggleTranscriptEdit"
                    >
                      {{ editingTranscript ? '取消编辑' : '编辑文稿' }}
                    </button>
                  </div>
                  <p v-if="selectedAudio.error" class="transcript__error">
                    {{ selectedAudio.error }}
                  </p>
                  <div v-if="editingTranscript" class="transcript__edit">
                    <FormTextarea
                      id="asr-transcript"
                      v-model="transcriptDraft"
                      label="转写文稿"
                      :rows="10"
                    />
                    <div class="transcript__actions">
                      <AppButton :loading="savingTranscript" @click="saveTranscript">
                        保存修改
                      </AppButton>
                    </div>
                  </div>
                  <p v-if="selectedAudio.record_id" class="transcript__saved">
                    已保存为会议记录，可在下方内容流中查看。
                  </p>
                  <div
                    v-if="meeting.status !== 'archived' && !recording"
                    class="transcript__actions"
                  >
                    <AppButton
                      v-if="selectedAudio.status === 'failed'"
                      variant="ghost"
                      :loading="retryingAudio"
                      @click="retryAudioAction"
                    >
                      重新转写
                    </AppButton>
                    <AppButton
                      v-if="selectedAudio.status !== 'confirmed' && selectedAudio.transcript"
                      :loading="confirmingAudio"
                      @click="confirmAudioAction"
                    >
                      确认并保存为记录
                    </AppButton>
                    <AppButton
                      v-if="selectedAudio.status !== 'confirmed'"
                      variant="danger"
                      :loading="deletingAudio"
                      @click="askDeleteAudio"
                    >
                      删除音频
                    </AppButton>
                  </div>
                </div>

                <EmptyState
                  v-else-if="audioItems.length === 0"
                  title="还没有音频"
                />
              </template>

              <div class="timeline-head">
                <h3 class="timeline-head__title">转写内容流</h3>
                <span class="timeline-head__count">{{ streamEntries.length }} 条</span>
                <button
                  v-if="meeting.status !== 'archived'"
                  type="button"
                  class="timeline-head__toggle"
                  @click="toggleComposer"
                >
                  {{ composerOpen ? '收起' : '补充记录' }}
                </button>
              </div>

              <ErrorMessage v-if="recordActionError" :error="recordActionError" />

              <div v-if="editingId" class="composer">
                <FormTextarea
                  id="asr-timeline-edit"
                  v-model="editDraft"
                  label="编辑记录"
                  :rows="3"
                  :error="editError"
                />
                <div class="composer__actions">
                  <AppButton
                    size="sm"
                    variant="ghost"
                    :disabled="savingEdit"
                    @click="cancelEdit"
                  >
                    取消
                  </AppButton>
                  <AppButton size="sm" :loading="savingEdit" @click="saveEdit">
                    保存
                  </AppButton>
                </div>
              </div>

              <form
                v-if="composerOpen && meeting.status !== 'archived'"
                class="composer"
                @submit.prevent="addRecord"
              >
                <FormTextarea
                  id="asr-composer"
                  v-model="composerContent"
                  label="补充记录"
                  :rows="3"
                  :error="composerError"
                />
                <FormSelect
                  id="asr-composer-type"
                  v-model="composerType"
                  label="记录类型"
                  :options="composerTypeOptions"
                />
                <div class="composer__actions">
                  <AppButton type="submit" :loading="addingRecord">保存记录</AppButton>
                  <AppButton variant="ghost" type="button" @click="toggleComposer">取消</AppButton>
                </div>
              </form>

              <LoadingSpinner
                v-if="recordsLoading && recordItems.length === 0"
                class="work-card__state"
              />
              <ErrorMessage
                v-else-if="recordsError"
                :error="recordsError"
                retryable
                @retry="loadRecords()"
              />
              <EmptyState
                v-else-if="streamEntries.length === 0"
                title="还没有内容"
              />
              <template v-else>
                <TranscriptStream
                  :entries="streamEntries"
                  :selected-keys="selectedKeys"
                  :selectable="meeting.status !== 'archived' && !recording"
                  :can-retry-segment="recording"
                  @toggle-select="toggleStreamSelection"
                  @retry-segment="onRetrySegment"
                >
                  <template #record-actions="{ entry }">
                    <template v-if="meeting.status !== 'archived'">
                      <button
                        type="button"
                        class="timeline__link"
                        @click="startEditRecord(entry.recordId ?? '')"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="timeline__link timeline__link--danger"
                        @click="askDeleteRecord(entry.recordId ?? '')"
                      >
                        删除
                      </button>
                    </template>
                  </template>
                </TranscriptStream>
                <AppPagination
                  v-if="recordPagination.total_pages > 1"
                  :page="recordPagination.page"
                  :page-size="recordPagination.page_size"
                  :total="recordPagination.total"
                  @update:page="loadRecords"
                />
              </template>
            </div>

            <!-- 底部操作条 -->
            <footer class="work-card__footer">
              <AppButton
                variant="ghost"
                :loading="savingTranscript"
                :disabled="meeting.status === 'archived' || saveTranscriptDisabled"
                :title="editingTranscript ? '保存修改后的转写文本' : '打开编辑并保存转写文本'"
                @click="onSaveTranscriptClick"
              >
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                  <path
                    d="M5 5.5h14v15H5zM8 3v5h8V3M8 14h8M8 17h5"
                    stroke="currentColor"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                保存转写
              </AppButton>
              <AppButton
                variant="ghost"
                :disabled="!selectedAudio?.transcript && recordItems.length === 0"
                @click="exportTxt(meeting)"
              >
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                  <path
                    d="M12 4v12m0 0 4-4m-4 4-4-4M4 19h16"
                    stroke="currentColor"
                    stroke-width="1.7"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                导出 TXT
              </AppButton>
              <AppButton @click="goMinutes">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                  <path
                    d="M4 12h15m0 0-5.5-5.5M19 12l-5.5 5.5"
                    stroke="currentColor"
                    stroke-width="1.7"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
                跳转纪要生成
              </AppButton>
            </footer>
          </section>

          <div v-if="selectedText" class="selection-bar" role="status">
            <span class="selection-bar__dot" aria-hidden="true" />
            <span class="selection-bar__text">
              已选中 {{ selectedText.length }} 字，提问时会自动引用
            </span>
            <button type="button" class="selection-bar__clear" @click="selectedText = ''">
              取消
            </button>
          </div>
        </main>

        <!-- AI 会议助手：默认隐藏，按需打开的侧边抽屉（固定 plan 模式，无模板） -->
        <div v-show="chatOpen" class="assistant-root">
          <div class="assistant-root__backdrop" @click="chatOpen = false" />
          <aside class="assistant-drawer" role="dialog" aria-modal="true" aria-label="AI 会议助手">
            <AgentChat
              agent-name="AI答疑助手"
              welcome-title="AI答疑助手"
              :quick-actions="quickActions"
              :on-send="handleSend"
              :on-task="handleTask"
              :context-text="selectedText"
              :disabled="!meeting.meeting_id"
              placeholder="针对当前讨论提问…"
              compact
              @clear-context="selectedText = ''"
            >
              <template #composer-extra>
                <ModelPickerPopover
                  :disabled="!meeting.meeting_id"
                  :selected="selectedModel"
                  @select="onSelectModel"
                  @manage="openPanel('model')"
                />
              </template>
              <template #structured="{ message }">
                <SummaryCard
                  v-if="message.kind === 'summary' && isSummaryStructured(message.structured)"
                  :data="message.structured"
                />
                <PolishDiffPanel
                  v-else-if="message.kind === 'polish' && isPolishSuggestions(message.structured)"
                  :suggestions="message.structured"
                  :readonly="polishReadonly"
                  :applying="applyingPolish"
                  :source-text="polishSourceText"
                  :readonly-hint="polishHint"
                  @apply="applyPolish"
                />
              </template>
              <template #header-actions>
                <button
                  type="button"
                  class="assistant-drawer__close"
                  aria-label="关闭 AI 助手"
                  @click="chatOpen = false"
                >
                  ×
                </button>
              </template>
            </AgentChat>
          </aside>
        </div>
      </div>

      <ConfirmDialog
        :open="showDeleteAudio"
        title="删除音频"
        message="删除后音频文件和转写文本将不可恢复，确定删除吗？"
        confirm-text="删除"
        danger
        :loading="deletingAudio"
        @confirm="deleteAudioAction"
        @cancel="showDeleteAudio = false"
      />

      <ConfirmDialog
        :open="showDeleteRecord"
        title="删除记录"
        message="删除后该记录不可恢复，确定删除吗？"
        confirm-text="删除"
        danger
        :loading="deletingRecord"
        @confirm="deleteRecordAction"
        @cancel="showDeleteRecord = false"
      />

      <ConfirmDialog
        :open="showFallbackConfirm"
        title="使用最近的会议记录？"
        message="未检测到选中文本或已转写音频，将基于最近的会议记录生成。是否继续？"
        confirm-text="继续生成"
        cancel-text="取消"
        @confirm="resolveFallback(true)"
        @cancel="resolveFallback(false)"
      />
    </template>
  </StageShell>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as audioApi from '@/api/audio'
import * as chatApi from '@/api/chat'
import * as recordsApi from '@/api/records'
import AgentChat from '@/components/AgentChat.vue'
import AppButton from '@/components/AppButton.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormSelect from '@/components/FormSelect.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ModelPickerPopover from '@/components/ModelPickerPopover.vue'
import PolishDiffPanel from '@/components/PolishDiffPanel.vue'
import StageShell from '@/components/StageShell.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import SummaryCard from '@/components/SummaryCard.vue'
import TranscriptStream from '@/components/TranscriptStream.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useAsyncList } from '@/composables/useAsyncList'
import { useLiveRecording } from '@/composables/useLiveRecording'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useSettingsPanels } from '@/composables/useSettingsPanels'
import { useToast } from '@/composables/useToast'
import type { AgentQuickAction, AgentReply } from '@/types/agent'
import type { MeetingAudio, TranscriptEntry } from '@/types/audio'
import type {
  ChatSource,
  OrganizePayload,
  OrganizeTask,
  PolishSuggestion,
  SummaryStructured,
} from '@/types/chat'
import type { Meeting } from '@/types/meeting'
import type { MeetingRecord, RecordMarkerType, RecordType } from '@/types/record'
import { formatDateTime, formatTime } from '@/utils/datetime'
import { resolveErrorMessage } from '@/utils/errors'
import { audioStatusMeta, recordMarkerMeta, recordTypeMeta } from '@/utils/statusLabels'
import { validateAudioFile } from '@/utils/audioUpload'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const { mirrorMeetingFile } = useLocalWorkspace()
const { openPanel } = useSettingsPanels()

const meetingId = computed(() => String(route.query.meetingId ?? ''))
const selectedText = ref('')
const mainEl = ref<HTMLElement | null>(null)
const chatOpen = ref(false)

function onDrawerKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    chatOpen.value = false
  }
}

watch(chatOpen, (open) => {
  if (open) {
    document.addEventListener('keydown', onDrawerKeydown)
  } else {
    document.removeEventListener('keydown', onDrawerKeydown)
  }
})

/* ============================== 音频列表与转写 ============================== */

const {
  items: audioItems,
  pagination: audioPagination,
  loading: audioLoading,
  error: audioError,
  load: loadAudio,
} = useAsyncList<MeetingAudio>({
  fetcher: ({ page, page_size }) => audioApi.listAudio(meetingId.value, { page, page_size }),
})

const selectedAudio = ref<MeetingAudio | null>(null)
const transcriptDraft = ref('')
const savingTranscript = ref(false)
const confirmingAudio = ref(false)
const retryingAudio = ref(false)
const deletingAudio = ref(false)
const showDeleteAudio = ref(false)
const audioActionError = ref<unknown>(null)
const uploadError = ref<unknown>(null)
const uploading = ref(false)

function selectAudio(audio: MeetingAudio): void {
  selectedAudio.value = audio
  transcriptDraft.value = audio.transcript ?? ''
  editingTranscript.value = false
}

/* ---------- 转写文稿编辑态 ---------- */

const editingTranscript = ref(false)

const canEditTranscript = computed(
  () =>
    !recording.value &&
    !!selectedAudio.value &&
    selectedAudio.value.status !== 'confirmed' &&
    !!selectedAudio.value.transcript,
)

const saveTranscriptDisabled = computed(() => {
  if (!selectedAudio.value) {
    return true
  }
  if (selectedAudio.value.status === 'confirmed') {
    return true
  }
  return editingTranscript.value
    ? !transcriptDraft.value.trim()
    : !selectedAudio.value.transcript
})

function toggleTranscriptEdit(): void {
  if (!selectedAudio.value) {
    return
  }
  editingTranscript.value = !editingTranscript.value
  if (editingTranscript.value) {
    transcriptDraft.value = selectedAudio.value.transcript ?? ''
  }
}

function onSaveTranscriptClick(): void {
  if (editingTranscript.value) {
    void saveTranscript()
  } else {
    toggleTranscriptEdit()
  }
}

async function saveTranscript(): Promise<void> {
  const audio = selectedAudio.value
  if (!audio) {
    return
  }
  const text = transcriptDraft.value.trim()
  if (!text) {
    toast.error('转写文本不能为空')
    return
  }
  savingTranscript.value = true
  audioActionError.value = null
  try {
    const updated = await audioApi.updateTranscript(audio.audio_id, text)
    selectAudio(updated)
    await loadAudio()
    toast.success('转写文本已保存')
  } catch (caught) {
    audioActionError.value = caught
  } finally {
    savingTranscript.value = false
  }
}

async function confirmAudioAction(): Promise<void> {
  const audio = selectedAudio.value
  if (!audio) {
    return
  }
  confirmingAudio.value = true
  audioActionError.value = null
  try {
    const updated = await audioApi.confirmAudio(audio.audio_id)
    selectAudio(updated)
    await loadAudio()
    await loadRecords(1)
    toast.success('已保存为会议记录')
  } catch (caught) {
    audioActionError.value = caught
  } finally {
    confirmingAudio.value = false
  }
}

async function retryAudioAction(): Promise<void> {
  const audio = selectedAudio.value
  if (!audio) {
    return
  }
  retryingAudio.value = true
  audioActionError.value = null
  try {
    const updated = await audioApi.retryAudio(audio.audio_id)
    selectAudio(updated)
    await loadAudio()
    if (updated.status === 'failed') {
      audioActionError.value = {
        status: 'error',
        error_code: 'MODEL_TIMEOUT',
        message: updated.error ?? '音频转写失败',
        retryable: true,
      }
    }
  } catch (caught) {
    audioActionError.value = caught
  } finally {
    retryingAudio.value = false
  }
}

function askDeleteAudio(): void {
  showDeleteAudio.value = true
}

async function deleteAudioAction(): Promise<void> {
  const audio = selectedAudio.value
  if (!audio) {
    return
  }
  deletingAudio.value = true
  audioActionError.value = null
  try {
    await audioApi.deleteAudio(audio.audio_id)
    showDeleteAudio.value = false
    selectedAudio.value = null
    transcriptDraft.value = ''
    await loadAudio(1)
    if (audioItems.value[0]) {
      selectAudio(audioItems.value[0])
    }
    toast.success('音频已删除')
  } catch (caught) {
    audioActionError.value = caught
  } finally {
    deletingAudio.value = false
  }
}

/* ============================== 上传与实时录音（分片边录边转） ============================== */

const fileInputEl = ref<HTMLInputElement | null>(null)

const {
  recording,
  startingRecorder,
  stoppingRecorder,
  recordingLabel,
  liveSegments,
  liveAudioId,
  startRecording: startLiveSession,
  stopRecording: stopLiveSession,
  retrySegment: retryLiveSegment,
} = useLiveRecording({
  meetingId: () => meetingId.value,
  onSessionStarted: (audio) => {
    uploadError.value = null
    selectAudio(audio)
  },
  onSessionFinished: async (audio) => {
    await loadAudio(1)
    selectAudio(audio)
    if (audio.status === 'failed') {
      uploadError.value = {
        status: 'error',
        error_code: 'MODEL_TIMEOUT',
        message: audio.error ?? '实时转写失败',
        retryable: true,
      }
    } else {
      toast.success('录音已分段转写完成，请检查文本')
    }
  },
  onError: (message) => {
    toast.error(message)
  },
})

async function startRecording(): Promise<void> {
  if (!meetingId.value) {
    return
  }
  await startLiveSession()
}

async function stopRecording(): Promise<void> {
  await stopLiveSession()
}

async function onRetrySegment(seq: number): Promise<void> {
  await retryLiveSegment(seq)
}

async function uploadAudioFile(file: File): Promise<void> {
  if (!meetingId.value) {
    return
  }
  const invalid = validateAudioFile(file)
  if (invalid) {
    toast.error(invalid)
    return
  }
  uploading.value = true
  uploadError.value = null
  try {
    const audio = await audioApi.uploadAudio(meetingId.value, file)
    await loadAudio(1)
    selectAudio(audio)
    if (audio.status === 'failed') {
      uploadError.value = {
        status: 'error',
        error_code: 'MODEL_TIMEOUT',
        message: audio.error ?? '音频转写失败',
        retryable: true,
      }
    } else {
      toast.success('音频已转写，请检查文本')
      void mirrorMeetingFile({
        meetingId: meetingId.value,
        fileName: file.name,
        content: file,
      })
    }
  } catch (caught) {
    uploadError.value = caught
  } finally {
    uploading.value = false
  }
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  input.value = ''
  if (!file) {
    return
  }
  void uploadAudioFile(file)
}

/* ============================== 记录时间轴 ============================== */

const {
  items: recordItems,
  pagination: recordPagination,
  loading: recordsLoading,
  error: recordsError,
  load: loadRecords,
} = useAsyncList<MeetingRecord>({
  fetcher: ({ page, page_size }) => recordsApi.listRecords(meetingId.value, { page, page_size }),
})

/* ---------- 转写内容流：分段 + 记录统一展示 ---------- */

function segmentText(segment: { text: string; error?: string | null }): string {
  if (segment.text) {
    return segment.text
  }
  return segment.error ? '（本段转写失败）' : '（本段无语音内容）'
}

const streamEntries = computed<TranscriptEntry[]>(() => {
  if (recording.value) {
    return liveSegments.value.map((segment) => ({
      key: `seg-${liveAudioId.value}-${segment.seq}`,
      kind: 'segment' as const,
      seq: segment.seq,
      time: offsetLabel(segment.offset_seconds),
      text: segmentText(segment),
      marker: segment.marker_type ?? null,
      error: segment.error ?? null,
    }))
  }
  const audio = selectedAudio.value
  const segmentEntries: TranscriptEntry[] = (audio?.segments ?? []).map((segment) => ({
    key: `seg-${audio?.audio_id ?? 'x'}-${segment.seq}`,
    kind: 'segment' as const,
    seq: segment.seq,
    time: offsetLabel(segment.offset_seconds),
    text: segmentText(segment),
    marker: segment.marker_type ?? null,
    error: segment.error ?? null,
  }))
  const recordEntries: TranscriptEntry[] = recordItems.value.map((record) => ({
    key: `rec-${record.record_id}`,
    kind: 'record' as const,
    seq: null,
    time: formatTime(record.created_at),
    text: record.content,
    marker: record.marker_type,
    tag: recordTypeLabel(record.record_type),
    recordId: record.record_id,
  }))
  return [...segmentEntries, ...recordEntries]
})

const entryByKey = computed(() => {
  const map = new Map<string, TranscriptEntry>()
  for (const entry of streamEntries.value) {
    map.set(entry.key, entry)
  }
  return map
})

function toggleStreamSelection(key: string): void {
  selectedKeys.value = selectedKeys.value.includes(key)
    ? selectedKeys.value.filter((item) => item !== key)
    : [...selectedKeys.value, key]
}

const selectedKeys = ref<string[]>([])
const marking = ref(false)
const composerOpen = ref(false)
const composerContent = ref('')
const composerType = ref('manual')
const composerError = ref('')
const addingRecord = ref(false)
const recordActionError = ref<unknown>(null)
const showDeleteRecord = ref(false)
const pendingDeleteId = ref<string | null>(null)
const deletingRecord = ref(false)
const editingId = ref<string | null>(null)
const editDraft = ref('')
const editError = ref('')
const savingEdit = ref(false)

const composerTypeOptions: { label: string; value: string }[] = [
  { label: '手动记录', value: 'manual' },
  { label: '导入文本', value: 'imported' },
]

function recordTypeLabel(type: RecordType): string {
  return recordTypeMeta[type]?.label ?? type
}

function offsetLabel(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safe / 60)
  const secs = safe % 60
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function toggleComposer(): void {
  composerOpen.value = !composerOpen.value
  composerContent.value = ''
  composerType.value = 'manual'
  composerError.value = ''
}

async function addRecord(): Promise<void> {
  const content = composerContent.value.trim()
  if (!content) {
    composerError.value = '记录内容不能为空'
    return
  }
  composerError.value = ''
  addingRecord.value = true
  recordActionError.value = null
  try {
    await recordsApi.createRecord(meetingId.value, {
      content,
      record_type: composerType.value === 'imported' ? 'imported' : 'manual',
    })
    toggleComposer()
    await loadRecords(1)
    toast.success('记录已保存')
  } catch (caught) {
    recordActionError.value = caught
  } finally {
    addingRecord.value = false
  }
}

async function applyMarker(marker: RecordMarkerType): Promise<void> {
  if (selectedKeys.value.length === 0 || marking.value) {
    return
  }
  marking.value = true
  recordActionError.value = null
  const keys = [...selectedKeys.value]
  const results = await Promise.allSettled(
    keys.map((key) => {
      const entry = entryByKey.value.get(key)
      if (!entry) {
        return Promise.reject(new Error('条目不存在'))
      }
      const next = entry.marker === marker ? null : marker
      if (entry.kind === 'segment' && entry.seq !== null && selectedAudio.value) {
        const audioId = selectedAudio.value.audio_id
        return audioApi
          .updateSegmentMarker(audioId, entry.seq, next)
          .then((updated) => {
            const fresh = (updated.segments ?? []).find((item) => item.seq === entry.seq)
            if (!fresh) {
              return
            }
            if (recording.value) {
              const rest = liveSegments.value.filter((item) => item.seq !== entry.seq)
              liveSegments.value = [...rest, fresh].sort((a, b) => a.seq - b.seq)
            } else if (selectedAudio.value) {
              selectedAudio.value = { ...selectedAudio.value, segments: updated.segments }
            }
          })
      }
      if (entry.kind === 'record' && entry.recordId) {
        return recordsApi
          .updateRecord(entry.recordId, { marker_type: next })
          .then(() => {})
      }
      return Promise.reject(new Error('条目不支持标记'))
    }),
  )
  const failed = results.filter((result) => result.status === 'rejected').length
  if (failed > 0) {
    toast.error(`${failed} 条内容标记失败，请重试`)
  } else {
    toast.success(keys.length > 1 ? `已更新 ${keys.length} 条内容标记` : '标记已更新')
  }
  selectedKeys.value = []
  if (!recording.value) {
    await loadRecords()
  }
  marking.value = false
}

function startEditRecord(recordId: string): void {
  const record = recordItems.value.find((item) => item.record_id === recordId)
  if (!record) {
    return
  }
  editingId.value = recordId
  editDraft.value = record.content
  editError.value = ''
}

function cancelEdit(): void {
  editingId.value = null
  editDraft.value = ''
  editError.value = ''
}

async function saveEdit(): Promise<void> {
  const recordId = editingId.value
  if (!recordId) {
    return
  }
  const content = editDraft.value.trim()
  if (!content) {
    editError.value = '记录内容不能为空'
    return
  }
  editError.value = ''
  savingEdit.value = true
  recordActionError.value = null
  try {
    await recordsApi.updateRecord(recordId, { content })
    cancelEdit()
    await loadRecords()
    toast.success('记录已更新')
  } catch (caught) {
    recordActionError.value = caught
  } finally {
    savingEdit.value = false
  }
}

function askDeleteRecord(recordId: string): void {
  pendingDeleteId.value = recordId
  showDeleteRecord.value = true
}

async function deleteRecordAction(): Promise<void> {
  const recordId = pendingDeleteId.value
  if (!recordId) {
    return
  }
  deletingRecord.value = true
  recordActionError.value = null
  try {
    await recordsApi.deleteRecord(recordId)
    showDeleteRecord.value = false
    pendingDeleteId.value = null
    selectedKeys.value = selectedKeys.value.filter((key) => key !== `rec-${recordId}`)
    await loadRecords()
    toast.success('记录已删除')
  } catch (caught) {
    recordActionError.value = caught
  } finally {
    deletingRecord.value = false
  }
}

/* ============================== 导出与跳转 ============================== */

function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '-').trim() || '会议'
}

function exportTxt(meeting: Meeting): void {
  const lines: string[] = [`# ${meeting.title} 会议记录`]
  if (meeting.meeting_time) {
    lines.push(`时间：${formatDateTime(meeting.meeting_time)}`)
  }
  if (meeting.topic) {
    lines.push(`主题：${meeting.topic}`)
  }
  const transcript = selectedAudio.value?.transcript?.trim()
  if (transcript) {
    lines.push('', '## 转写文稿', transcript)
  }
  if (recordItems.value.length > 0) {
    lines.push('', '## 会议记录')
    for (const record of recordItems.value) {
      const marker = record.marker_type
        ? `［${recordMarkerMeta[record.marker_type].label}］`
        : ''
      lines.push(`[${formatTime(record.created_at)}]${marker} ${record.content}`)
    }
  }
  const blob = new Blob([`${lines.join('\n')}\n`], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${sanitizeFileName(meeting.title)}-会议记录-${new Date()
    .toISOString()
    .slice(0, 10)}.txt`
  anchor.click()
  URL.revokeObjectURL(url)
  toast.success('已导出 TXT 文件')
}

function goMinutes(): void {
  void router.push({
    name: ROUTE_NAMES.minutesGenerate,
    query: { meetingId: meetingId.value },
  })
}

/* ============================== AI 助手与选中提问 ============================== */

// 会中助手固定 plan 模式、无模板，仅提供对话模型选择
const selectedModel = ref('')

function onSelectModel(model: string): void {
  selectedModel.value = model
}

// 快捷任务走后端 organize 链的专用 prompt（summary/polish/brief），不再前端拼提示词
const quickActions: AgentQuickAction[] = [
  {
    label: '提炼要点',
    task: 'summary',
    prompt: '基于当前会议内容提炼要点，按结论与决议、关键讨论、待办与责任、待确认问题分节输出。',
  },
  {
    label: '修正口误',
    task: 'polish',
    prompt: '检查转写文本中的口误、识别错误与不通顺之处，逐条给出修改建议。',
  },
  {
    label: '简短摘要',
    task: 'brief',
    prompt: '用 3-5 句话概括当前会议进展。',
  },
]

/* ---------- 快捷任务：organize 链（后端专用 prompt + 结构化输出） ---------- */

const showFallbackConfirm = ref(false)
let fallbackResolve: ((confirmed: boolean) => void) | null = null

function confirmRecordFallback(): Promise<boolean> {
  showFallbackConfirm.value = true
  return new Promise((resolve) => {
    fallbackResolve = resolve
  })
}

function resolveFallback(confirmed: boolean): void {
  showFallbackConfirm.value = false
  fallbackResolve?.(confirmed)
  fallbackResolve = null
}

const polishAudioId = ref<string | null>(null)
const applyingPolish = ref(false)

// 组织化回复的类型守卫：kind 与 structured 独立存储，需要显式收窄
function isSummaryStructured(data: unknown): data is SummaryStructured {
  return data !== undefined && data !== null && !Array.isArray(data)
}

function isPolishSuggestions(data: unknown): data is PolishSuggestion[] {
  return Array.isArray(data)
}

const polishTargetAudio = computed<MeetingAudio | null>(() => {
  if (!polishAudioId.value) {
    return null
  }
  return audioItems.value.find((item) => item.audio_id === polishAudioId.value) ?? null
})

const polishSourceText = computed(() => polishTargetAudio.value?.transcript ?? '')

const polishReadonly = computed(() => {
  if (recording.value) {
    return true
  }
  const audio = polishTargetAudio.value
  // 仅「已转写」的音频可写回；未关联/进行中/已确认/失败均只读
  return !audio || audio.status !== 'transcribed'
})

const polishHint = computed(() => {
  if (recording.value) {
    return '录音进行中，暂不能采纳修改；可先复制修订稿。'
  }
  const audio = polishTargetAudio.value
  if (!audio) {
    return '本次修改基于选中文本，未关联转写音频；可复制修订稿手动更新。'
  }
  if (audio.status === 'confirmed') {
    return '该音频已确认生成记录，不能直接修改；可复制修订稿手动更新记录。'
  }
  if (audio.status === 'processing') {
    return '转写进行中，暂不能采纳修改。'
  }
  return ''
})

async function handleTask(task: string, prompt: string, signal: AbortSignal): Promise<AgentReply> {
  if (!meetingId.value) {
    throw new Error('请先选择一场会议。')
  }
  const payload: OrganizePayload = {
    task: task as OrganizeTask,
    model: selectedModel.value || undefined,
  }
  // prompt 为用户在任务标记下补充的要求（可为空）
  if (prompt.trim()) {
    payload.instruction = prompt.trim().slice(0, 2000)
  }
  if (selectedText.value.trim()) {
    payload.text = selectedText.value
  } else if (selectedAudio.value?.transcript?.trim()) {
    payload.audio_id = selectedAudio.value.audio_id
  } else {
    const confirmed = await confirmRecordFallback()
    if (!confirmed || signal.aborted) {
      throw new Error('已取消本次任务。')
    }
  }

  try {
    const result = await chatApi.organizeRecords(meetingId.value, payload, signal)
    if (result.task === 'summary' && result.structured && !Array.isArray(result.structured)) {
      return {
        content: '',
        kind: 'summary',
        structured: result.structured,
        note: '要点基于当前会议内容生成；待办如需保存为草稿，请使用「待办任务」功能。',
      }
    }
    if (result.task === 'polish' && Array.isArray(result.structured)) {
      polishAudioId.value = payload.audio_id ?? null
      return {
        content: '',
        kind: 'polish',
        structured: result.structured,
        note: recording.value
          ? '录音进行中：建议先复制修订稿，停止录音后可采纳修改。'
          : '请勾选并采纳修改，确认后会写回转写文本（不覆盖原始录音）。',
      }
    }
    return { content: result.organized_content }
  } catch (caught) {
    if (signal.aborted) {
      throw new Error('已取消本次请求。')
    }
    throw new Error(resolveErrorMessage(caught, '任务处理失败，请稍后重试。'))
  }
}

async function applyPolish(selected: PolishSuggestion[]): Promise<void> {
  const audio = polishTargetAudio.value
  if (!audio || !audio.transcript || recording.value || applyingPolish.value) {
    return
  }
  if (audio.status !== 'transcribed') {
    toast.error('当前音频状态不允许修改转写')
    return
  }
  let text = audio.transcript
  let applied = 0
  for (const item of selected) {
    if (item.original && item.suggested && text.includes(item.original)) {
      text = text.replace(item.original, item.suggested)
      applied += 1
    }
  }
  if (applied === 0) {
    toast.error('未能在转写文本中定位建议的原文，请手动修改')
    return
  }
  applyingPolish.value = true
  try {
    const updated = await audioApi.updateTranscript(audio.audio_id, text)
    polishAudioId.value = null
    selectAudio(updated)
    await loadAudio()
    toast.success(`已采纳 ${applied} 处修改`)
  } catch (caught) {
    toast.error(resolveErrorMessage(caught, '修改保存失败，请稍后重试'))
  } finally {
    applyingPolish.value = false
  }
}

function sourceLabel(source: ChatSource): string {
  if (source.document_name) {
    return source.document_name
  }
  if (source.record_id) {
    return '会议记录'
  }
  if (source.material_id) {
    return '会议资料'
  }
  if (source.meeting_id) {
    return '会议上下文'
  }
  return '来源'
}

function captureSelection(): void {
  const selection = window.getSelection()
  const text = selection?.toString().trim() ?? ''
  const anchor = selection?.anchorNode
  if (!text || text.length < 2 || !anchor) {
    return
  }
  if (!mainEl.value?.contains(anchor)) {
    return
  }
  selectedText.value = text.slice(0, 1200)
}

async function handleSend(text: string, signal: AbortSignal): Promise<AgentReply> {
  if (!meetingId.value) {
    throw new Error('请先选择一场会议。')
  }
  try {
    const result = await chatApi.askMeeting(
      meetingId.value,
      {
        question: text,
        context_scope: 'current_meeting',
        include_sources: true,
        model: selectedModel.value || undefined,
      },
      signal,
    )
    return {
      content: result.answer,
      sources: result.sources.slice(0, 3).map((source) => ({
        label: sourceLabel(source),
        detail: source.excerpt.replace(/\s+/g, ' ').slice(0, 64),
      })),
      note: result.insufficient_evidence ? '证据不足，回答仅供参考。' : undefined,
    }
  } catch (caught) {
    throw new Error(resolveErrorMessage(caught, 'Agent 处理失败，请稍后重试。'))
  }
}

/* ============================== 初始化与清理 ============================== */

async function refreshAll(): Promise<void> {
  if (!meetingId.value) {
    return
  }
  selectedAudio.value = null
  transcriptDraft.value = ''
  editingTranscript.value = false
  selectedKeys.value = []
  editingId.value = null
  composerOpen.value = false
  await Promise.all([loadAudio(1), loadRecords(1)])
  if (audioItems.value[0]) {
    selectAudio(audioItems.value[0])
  }
}

watch(meetingId, () => {
  void refreshAll()
})

onMounted(() => {
  void refreshAll()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDrawerKeydown)
  // 录音器的停止与清理由 useLiveRecording 的卸载钩子负责
})
</script>

<style scoped>
.asr-page {
  display: grid;
  grid-template-columns: 17rem minmax(0, 1fr);
  gap: var(--space-4);
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

/* ===== 左栏：会议信息（容器即卡片，全高与右侧工作卡对齐） ===== */
.asr-page__info {
  position: sticky;
  top: 72px;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.info-card__title {
  margin: 0;
  padding-bottom: var(--space-2);
  font-size: 0.9375rem;
  font-weight: 650;
  border-bottom: 1px solid var(--color-border);
}

.info-list {
  display: flex;
  flex-direction: column;
}

.info-list__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--color-border);
}

.info-list__item:last-child {
  border-bottom: 0;
}

.info-list__label {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.info-list__value {
  color: var(--color-foreground);
  font-size: 0.875rem;
  word-break: break-word;
}

/* ===== 中栏：录音与转写卡片 ===== */
.asr-page__main {
  position: relative;
  min-width: 0;
}

.work-card {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.work-card__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.work-card__tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.work-card__tools svg {
  margin-right: 2px;
}

.work-card__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  flex: 1;
  min-height: 0;
  padding: var(--space-4);
  overflow-y: auto;
}

.work-card__footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
}

.work-card__footer svg {
  margin-right: 2px;
}

.work-card__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

/* 录音中状态胶囊 */
.recording-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 2.4rem;
  padding: 0 var(--space-4);
  color: #ffffff;
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  background: #dc2626;
  border: 0;
  border-radius: var(--radius-md);
  box-shadow: 0 6px 16px rgba(220, 38, 38, 0.24);
  cursor: pointer;
}

.recording-pill__dot {
  width: 8px;
  height: 8px;
  background: #ffffff;
  border-radius: 50%;
  animation: recording-pulse 1.2s ease-in-out infinite;
}

@keyframes recording-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.record-note {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

/* 音频条 */
.audio-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.audio-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.35rem 0.75rem;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 550;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.audio-chip:hover {
  border-color: var(--color-border-strong);
}

.audio-chip--active {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.45);
}

.audio-chip__name {
  max-width: 12rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 转写文稿 */
.transcript {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.transcript__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.transcript__name {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.transcript__edit-toggle {
  margin-left: auto;
  padding: 0.2rem 0.7rem;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.22);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.transcript__edit-toggle:hover {
  background: rgba(21, 94, 239, 0.14);
}

.transcript__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}

.transcript__saved {
  margin: 0;
  color: var(--color-accent-strong);
  font-size: 0.75rem;
}

.transcript__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

/* 记录时间轴 */
.timeline-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.timeline-head__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 650;
}

.timeline-head__count {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.timeline-head__toggle {
  margin-left: auto;
  padding: 0.2rem 0.7rem;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.22);
  border-radius: var(--radius-pill);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.timeline-head__toggle:hover {
  background: rgba(21, 94, 239, 0.14);
}

.composer {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface-strong);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
}

.composer__actions {
  display: flex;
  gap: var(--space-2);
}

.timeline__link {
  padding: 0;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.75rem;
  background: none;
  border: 0;
  cursor: pointer;
  transition: color var(--transition-fast);
}

.timeline__link:hover {
  color: var(--color-primary-strong);
}

.timeline__link--danger:hover {
  color: var(--color-down);
}

/* ===== AI 会议助手：页头入口 + 侧边抽屉 ===== */
.ai-header-btn svg {
  margin-right: 2px;
}

.assistant-root {
  position: fixed;
  inset: 0;
  z-index: 90;
}

.assistant-root__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.28);
}

.assistant-drawer {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  display: flex;
  width: min(24rem, 100vw);
  padding: var(--space-3);
  background: var(--color-background);
  border-left: 1px solid var(--color-border);
  box-shadow: var(--shadow-md);
  animation: assistant-drawer-in var(--transition);
}

@keyframes assistant-drawer-in {
  from {
    transform: translateX(24px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.assistant-drawer :deep(.agent-chat) {
  flex: 1;
  min-height: 0;
  height: auto;
}

/* 隐藏弹窗内聊天框上方的头像与标题，仅保留操作按钮 */
.assistant-drawer :deep(.agent-chat__avatar),
.assistant-drawer :deep(.agent-chat__identity) {
  display: none;
}

.assistant-drawer__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  color: var(--color-muted-foreground);
  font-size: 1.25rem;
  line-height: 1;
  background: transparent;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.assistant-drawer__close:hover {
  background: var(--color-surface-muted);
  color: var(--color-foreground);
}

/* 选中文字提示条 */
.selection-bar {
  position: sticky;
  bottom: var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: rgba(15, 23, 42, 0.92);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-md);
  color: #e2e8f0;
  font-size: 0.75rem;
  backdrop-filter: blur(8px);
}

.selection-bar__dot {
  width: 6px;
  height: 6px;
  background: #5eead4;
  border-radius: 50%;
}

.selection-bar__text {
  flex: 1;
}

.selection-bar__clear {
  padding: 2px 8px;
  color: #e2e8f0;
  font: inherit;
  font-size: 0.6875rem;
  background: rgba(255, 255, 255, 0.1);
  border: 0;
  border-radius: var(--radius-pill);
  cursor: pointer;
}

/* ===== 响应式 ===== */
@media (max-width: 1180px) {
  .asr-page {
    grid-template-columns: minmax(0, 1fr);
    height: auto;
  }

  .asr-page__info {
    position: static;
    overflow: visible;
  }

  .work-card {
    height: auto;
    min-height: 0;
  }

  .work-card__body {
    overflow: visible;
  }
}

@media (max-width: 600px) {
  .assistant-drawer {
    width: 100vw;
    padding: var(--space-2);
  }
}
</style>
