<template>
  <div class="meeting-files-panel">
    <LoadingSpinner v-if="loading" class="meeting-files-panel__state" />

    <template v-else>
      <!-- 会议资料 -->
      <section class="file-group">
        <header class="file-group__head">
          <h3 class="file-group__title">会议资料</h3>
          <span class="file-group__count">{{ materials.length }} 个</span>
        </header>
        <p v-if="materialsError" class="file-group__error">{{ materialsError }}</p>
        <p v-else-if="materials.length === 0" class="file-group__empty">未上传资料</p>
        <ul v-else class="file-list">
          <li v-for="item in materials" :key="item.material_id" class="file-list__row">
            <span class="file-list__icon" aria-hidden="true"><NavIcon name="file" :size="15" /></span>
            <span class="file-list__main">
              <span class="file-list__name">{{ item.file_name }}</span>
              <span class="file-list__meta">
                {{ materialStatusOf(item) }} · {{ formatDate(item.created_at) }}
              </span>
            </span>
            <span class="file-list__pending" title="文件打开服务将在后端上线后可用">待开放</span>
          </li>
        </ul>
      </section>

      <!-- 录音 -->
      <section class="file-group">
        <header class="file-group__head">
          <h3 class="file-group__title">录音</h3>
          <span class="file-group__count">{{ audios.length }} 个</span>
        </header>
        <p v-if="audiosError" class="file-group__error">{{ audiosError }}</p>
        <p v-else-if="audios.length === 0" class="file-group__empty">未上传录音</p>
        <ul v-else class="file-list">
          <li v-for="item in audios" :key="item.audio_id" class="file-list__row">
            <span class="file-list__icon" aria-hidden="true"><NavIcon name="mic" :size="15" /></span>
            <span class="file-list__main">
              <span class="file-list__name">{{ item.file_name }}</span>
              <span class="file-list__meta">{{ audioStatusOf(item) }} · {{ formatDate(item.created_at) }}</span>
            </span>
            <span class="file-list__pending" title="文件打开服务将在后端上线后可用">待开放</span>
          </li>
        </ul>
      </section>

      <!-- 纪要 -->
      <section class="file-group">
        <header class="file-group__head">
          <h3 class="file-group__title">纪要</h3>
          <span class="file-group__count">{{ minutesList.length }} 份</span>
        </header>
        <p v-if="minutesError" class="file-group__error">{{ minutesError }}</p>
        <p v-else-if="minutesList.length === 0" class="file-group__empty">尚未生成纪要</p>
        <ul v-else class="file-list">
          <li v-for="item in minutesList" :key="item.minutes_id" class="file-list__row">
            <span class="file-list__icon" aria-hidden="true"><NavIcon name="clipboard" :size="15" /></span>
            <span class="file-list__main">
              <span class="file-list__name">{{ minutesName(item) }}</span>
              <span class="file-list__meta">
                {{ minutesTemplateMeta[item.template]?.label ?? item.template }} · v{{ item.version }} ·
                {{ item.status === 'confirmed' ? '已确认' : '草稿' }} · {{ formatDate(item.updated_at) }}
              </span>
            </span>
            <button type="button" class="file-list__open" @click="previewMinutes(item)">预览</button>
          </li>
        </ul>
      </section>

      <!-- 会议记录 -->
      <section class="file-group">
        <header class="file-group__head">
          <h3 class="file-group__title">会议记录</h3>
          <span class="file-group__count">{{ records.length }} 条</span>
        </header>
        <p v-if="recordsError" class="file-group__error">{{ recordsError }}</p>
        <p v-else-if="records.length === 0" class="file-group__empty">暂无会议记录</p>
        <ul v-else class="file-list">
          <li v-for="item in records" :key="item.record_id" class="file-list__row">
            <span class="file-list__icon" aria-hidden="true"><NavIcon name="list" :size="15" /></span>
            <span class="file-list__main">
              <span class="file-list__name">{{ recordTypeLabel(item.record_type) }}记录</span>
              <span class="file-list__meta">{{ excerpt(item.content) }}</span>
            </span>
            <button type="button" class="file-list__open" @click="previewRecord(item)">预览</button>
          </li>
        </ul>
      </section>

      <!-- 文本预览区 -->
      <section v-if="preview" class="file-preview">
        <header class="file-preview__head">
          <h4 class="file-preview__title">{{ preview.title }}</h4>
          <button type="button" class="file-preview__close" @click="preview = null">关闭预览</button>
        </header>
        <MarkdownView v-if="preview.markdown" class="file-preview__body" :content="preview.content" />
        <pre v-else class="file-preview__body file-preview__body--text">{{ preview.content }}</pre>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

import * as audioApi from '@/api/audio'
import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import * as recordsApi from '@/api/records'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import NavIcon from '@/components/NavIcon.vue'
import type { MeetingAudio } from '@/types/audio'
import type { Material } from '@/types/material'
import type { Minutes } from '@/types/minutes'
import type { MeetingRecord, RecordType } from '@/types/record'
import { formatDate } from '@/utils/datetime'
import { audioStatusMeta, materialStatusMeta, minutesTemplateMeta } from '@/utils/statusLabels'

const props = defineProps<{ meetingId: string }>()

const loading = ref(false)
const materials = ref<Material[]>([])
const materialsError = ref('')
const audios = ref<MeetingAudio[]>([])
const audiosError = ref('')
const minutesList = ref<Minutes[]>([])
const minutesError = ref('')
const records = ref<MeetingRecord[]>([])
const recordsError = ref('')

const preview = ref<{ title: string; content: string; markdown: boolean } | null>(null)

const RECORD_TYPE_LABELS: Record<RecordType, string> = {
  manual: '手动',
  transcript: '转写',
  imported: '导入',
}

function materialStatusOf(item: Material): string {
  return materialStatusMeta[item.processing_status]?.label ?? item.processing_status
}

function audioStatusOf(item: MeetingAudio): string {
  return audioStatusMeta[item.status]?.label ?? item.status
}

function minutesName(item: Minutes): string {
  return `会议纪要_v${item.version}.md`
}

function recordTypeLabel(type: RecordType): string {
  return RECORD_TYPE_LABELS[type] ?? type
}

function excerpt(text: string): string {
  const normalized = text.replace(/\s+/g, ' ').trim()
  return normalized.length > 42 ? `${normalized.slice(0, 42)}…` : normalized
}

function previewMinutes(item: Minutes): void {
  preview.value = {
    title: minutesName(item),
    content: item.content,
    markdown: true,
  }
}

function previewRecord(item: MeetingRecord): void {
  preview.value = {
    title: `${recordTypeLabel(item.record_type)}记录 · ${formatDate(item.created_at)}`,
    content: item.content,
    markdown: false,
  }
}

async function load(meetingId: string): Promise<void> {
  loading.value = true
  preview.value = null
  materialsError.value = ''
  audiosError.value = ''
  minutesError.value = ''
  recordsError.value = ''
  const [materialsResult, audiosResult, minutesResult, recordsResult] = await Promise.allSettled([
    materialsApi.listMaterials(meetingId, { page: 1, page_size: 50 }),
    audioApi.listAudio(meetingId, { page: 1, page_size: 50 }),
    minutesApi.listMinutes(meetingId, { page: 1, page_size: 20 }),
    recordsApi.listRecords(meetingId, { page: 1, page_size: 50 }),
  ])
  if (materialsResult.status === 'fulfilled') {
    materials.value = materialsResult.value.items
  } else {
    materials.value = []
    materialsError.value = '资料加载失败'
  }
  if (audiosResult.status === 'fulfilled') {
    audios.value = audiosResult.value.items
  } else {
    audios.value = []
    audiosError.value = '录音加载失败'
  }
  if (minutesResult.status === 'fulfilled') {
    minutesList.value = minutesResult.value.items
  } else {
    minutesList.value = []
    minutesError.value = '纪要加载失败'
  }
  if (recordsResult.status === 'fulfilled') {
    records.value = recordsResult.value.items
  } else {
    records.value = []
    recordsError.value = '记录加载失败'
  }
  loading.value = false
}

watch(
  () => props.meetingId,
  (meetingId) => {
    if (meetingId) {
      void load(meetingId)
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.meeting-files-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.meeting-files-panel__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

.file-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.file-group__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.file-group__title {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 650;
}

.file-group__count {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.file-group__empty {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  background: var(--color-surface-strong);
  border-radius: var(--radius-md);
}

.file-group__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.75rem;
}

.file-list {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.file-list__row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.file-list__row:last-child {
  border-bottom: 0;
}

.file-list__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.9rem;
  height: 1.9rem;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
}

.file-list__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.file-list__name {
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-list__meta {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-list__pending {
  flex: 0 0 auto;
  padding: 2px 8px;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  background: var(--color-surface-muted);
  border-radius: var(--radius-pill);
  cursor: not-allowed;
}

.file-list__open {
  flex: 0 0 auto;
  padding: 3px 10px;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 600;
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.2);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.file-list__open:hover {
  background: #ffffff;
}

.file-preview {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid rgba(21, 94, 239, 0.25);
  border-radius: var(--radius-md);
  background: var(--color-primary-soft);
}

.file-preview__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.file-preview__title {
  margin: 0;
  font-size: 0.8125rem;
  font-weight: 650;
}

.file-preview__close {
  padding: 2px 8px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.6875rem;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.file-preview__close:hover {
  color: var(--color-foreground);
}

.file-preview__body {
  margin: 0;
  max-height: 16rem;
  overflow-y: auto;
  padding: var(--space-3);
  font-size: 0.8125rem;
  line-height: 1.7;
  background: var(--color-surface);
  border-radius: var(--radius-md);
}

.file-preview__body--text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--color-foreground);
}
</style>
