<template>
  <div class="audio-section">
    <div v-if="!readonly" class="audio-section__upload">
      <div class="form-field">
        <label class="form-field__label" for="audio-file">音频文件</label>
        <input
          id="audio-file"
          class="audio-section__file"
          type="file"
          accept=".mp3,.wav,.m4a,.webm"
          @change="onFileChange"
        />
      </div>
      <p v-if="fileError" class="audio-section__error" role="alert">{{ fileError }}</p>
      <AppButton :loading="uploading" :disabled="!selectedFile" @click="upload">
        上传并转写
      </AppButton>
    </div>

    <ErrorMessage v-if="uploadError" :error="uploadError" />

    <LoadingSpinner v-if="loading && items.length === 0" class="audio-section__state" />
    <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />
    <EmptyState
      v-else-if="items.length === 0"
      title="还没有音频"
      description="上传录音文件后生成可编辑的转写文本，确认后保存为会议记录。"
    />

    <template v-else>
      <ul class="audio-section__list">
        <li v-for="item in items" :key="item.audio_id">
          <button
            type="button"
            class="audio-section__item"
            :class="{ 'audio-section__item--active': selected?.audio_id === item.audio_id }"
            @click="select(item)"
          >
            <span class="audio-section__item-main">
              <strong>{{ item.file_name }}</strong>
              <span>{{ timeOf(item) }}</span>
            </span>
            <StatusBadge :label="statusOf(item).label" :tone="statusOf(item).tone" />
          </button>
        </li>
      </ul>

      <div v-if="selected" class="audio-section__editor">
        <div class="audio-section__editor-head">
          <StatusBadge :label="statusOf(selected).label" :tone="statusOf(selected).tone" />
          <span class="audio-section__meta">{{ selected.file_name }}</span>
        </div>

        <p v-if="selected.error" class="audio-section__error">{{ selected.error }}</p>

        <FormTextarea
          id="audio-transcript"
          v-model="draft"
          label="转写文本"
          :rows="10"
          :readonly="readonly || selected.status === 'confirmed'"
        />

        <div v-if="!readonly" class="audio-section__actions">
          <AppButton
            :loading="saving"
            :disabled="selected.status === 'failed' || selected.status === 'confirmed'"
            @click="saveTranscript"
          >
            保存修订
          </AppButton>
          <AppButton
            v-if="selected.status === 'failed'"
            variant="ghost"
            :loading="retrying"
            @click="retry"
          >
            重新转写
          </AppButton>
          <AppButton
            v-if="selected.status !== 'confirmed' && selected.transcript"
            :loading="confirming"
            @click="confirm"
          >
            确认并保存为记录
          </AppButton>
          <AppButton
            v-if="selected.status !== 'confirmed'"
            variant="danger"
            :loading="deleting"
            @click="showDelete = true"
          >
            删除音频
          </AppButton>
        </div>

        <p v-if="selected.record_id" class="audio-section__saved">
          已保存为会议记录：{{ selected.record_id }}
        </p>
      </div>

      <AppPagination
        v-if="pagination.total_pages > 1"
        :page="pagination.page"
        :page-size="pagination.page_size"
        :total="pagination.total"
        @update:page="load"
      />
    </template>

    <ErrorMessage v-if="actionError" :error="actionError" />

    <ConfirmDialog
      :open="showDelete"
      title="删除音频"
      message="删除后音频文件和转写文本将不可恢复，确定删除吗？"
      confirm-text="删除"
      danger
      :loading="deleting"
      @confirm="deleteAudio"
      @cancel="showDelete = false"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as audioApi from '@/api/audio'
import AppButton from '@/components/AppButton.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import type { MeetingAudio } from '@/types/audio'
import { validateAudioFile } from '@/utils/audioUpload'
import { formatDateTime } from '@/utils/datetime'
import { audioStatusMeta } from '@/utils/statusLabels'

const props = withDefaults(
  defineProps<{ meetingId: string; readonly?: boolean }>(),
  { readonly: false },
)

const emit = defineEmits<{ saved: [] }>()

const toast = useToast()
const { items, pagination, loading, error, load } = useAsyncList<MeetingAudio>({
  fetcher: ({ page, page_size }) => audioApi.listAudio(props.meetingId, { page, page_size }),
})

const selectedFile = ref<File | null>(null)
const fileError = ref('')
const uploading = ref(false)
const uploadError = ref<unknown>(null)
const selected = ref<MeetingAudio | null>(null)
const draft = ref('')
const saving = ref(false)
const retrying = ref(false)
const confirming = ref(false)
const deleting = ref(false)
const showDelete = ref(false)
const actionError = ref<unknown>(null)

function refresh(): Promise<void> {
  return load()
}

onMounted(async () => {
  await refresh()
  if (items.value[0]) {
    select(items.value[0])
  }
})

function statusOf(audio: MeetingAudio) {
  return audioStatusMeta[audio.status]
}

function timeOf(audio: MeetingAudio): string {
  return formatDateTime(audio.created_at)
}

function select(audio: MeetingAudio): void {
  selected.value = audio
  draft.value = audio.transcript ?? ''
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  if (!file) {
    selectedFile.value = null
    return
  }
  const message = validateAudioFile(file)
  if (message) {
    fileError.value = message
    selectedFile.value = null
    input.value = ''
    return
  }
  fileError.value = ''
  selectedFile.value = file
}

async function upload(): Promise<void> {
  if (!selectedFile.value) {
    return
  }
  uploading.value = true
  uploadError.value = null
  try {
    const audio = await audioApi.uploadAudio(props.meetingId, selectedFile.value)
    selectedFile.value = null
    await load(1)
    select(audio)
    if (audio.status === 'failed') {
      uploadError.value = {
        status: 'error',
        error_code: 'MODEL_TIMEOUT',
        message: audio.error ?? '音频转写失败',
        retryable: true,
      }
    } else {
      toast.success('音频已转写，请检查文本')
    }
  } catch (caught) {
    uploadError.value = caught
  } finally {
    uploading.value = false
  }
}

async function saveTranscript(): Promise<void> {
  if (!selected.value) {
    return
  }
  const text = draft.value.trim()
  if (!text) {
    actionError.value = {
      status: 'error',
      error_code: 'VALIDATION_ERROR',
      message: '转写文本不能为空',
      retryable: false,
    }
    return
  }
  saving.value = true
  actionError.value = null
  try {
    const updated = await audioApi.updateTranscript(selected.value.audio_id, text)
    select(updated)
    await load()
    toast.success('转写文本已保存')
  } catch (caught) {
    actionError.value = caught
  } finally {
    saving.value = false
  }
}

async function retry(): Promise<void> {
  if (!selected.value) {
    return
  }
  retrying.value = true
  actionError.value = null
  try {
    const updated = await audioApi.retryAudio(selected.value.audio_id)
    select(updated)
    await load()
    if (updated.status === 'failed') {
      actionError.value = {
        status: 'error',
        error_code: 'MODEL_TIMEOUT',
        message: updated.error ?? '音频转写失败',
        retryable: true,
      }
    }
  } catch (caught) {
    actionError.value = caught
  } finally {
    retrying.value = false
  }
}

async function confirm(): Promise<void> {
  if (!selected.value) {
    return
  }
  confirming.value = true
  actionError.value = null
  try {
    const updated = await audioApi.confirmAudio(selected.value.audio_id)
    select(updated)
    await load()
    emit('saved')
    toast.success('已保存为会议记录')
  } catch (caught) {
    actionError.value = caught
  } finally {
    confirming.value = false
  }
}

async function deleteAudio(): Promise<void> {
  if (!selected.value) {
    return
  }
  deleting.value = true
  actionError.value = null
  try {
    await audioApi.deleteAudio(selected.value.audio_id)
    showDelete.value = false
    selected.value = null
    draft.value = ''
    await load()
    toast.success('音频已删除')
  } catch (caught) {
    actionError.value = caught
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.audio-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.audio-section__upload {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: flex-start;
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field__label {
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 600;
}

.audio-section__file {
  min-height: 2.6rem;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font: inherit;
}

.audio-section__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.85rem;
}

.audio-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.audio-section__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.audio-section__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.audio-section__item--active {
  border-color: var(--color-primary);
  background: rgba(59, 111, 212, 0.06);
}

.audio-section__item-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
}

.audio-section__item-main span {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.audio-section__editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.audio-section__editor-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.audio-section__meta,
.audio-section__saved {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.audio-section__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
