<template>
  <div class="meeting-files-panel">
    <LoadingSpinner v-if="loading" class="meeting-files-panel__state" />

    <template v-else>
      <!-- 资源管理器式扁平文件列表：不按来源分组，一个会议就是一层文件 -->
      <div class="file-explorer" role="table" aria-label="会议文件列表">
        <div class="file-explorer__head" role="row">
          <span class="file-explorer__col file-explorer__col--name" role="columnheader">名称</span>
          <span class="file-explorer__col file-explorer__col--date" role="columnheader">修改日期</span>
          <span class="file-explorer__col file-explorer__col--type" role="columnheader">类型</span>
          <span class="file-explorer__col file-explorer__col--action" role="columnheader">
            <span class="file-explorer__sr-only">操作</span>
          </span>
        </div>

        <p v-if="loadError" class="file-explorer__error">{{ loadError }}</p>
        <p v-else-if="rows.length === 0" class="file-explorer__empty">
          该会议还没有文件，可在会议工作台导入资料、录音或生成纪要。
        </p>

        <button
          v-for="row in rows"
          :key="row.key"
          type="button"
          class="file-explorer__row"
          :class="{ 'file-explorer__row--previewable': row.preview !== null }"
          :title="row.preview ? `预览 ${row.name}` : `${row.name}（待开放）`"
          @click="openRow(row)"
        >
          <span class="file-explorer__cell file-explorer__cell--name">
            <span
              class="file-icon"
              :class="`file-icon--${row.family}`"
              aria-hidden="true"
            >
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none">
                <path
                  v-for="(path, pathIndex) in iconPathsOf(row.family)"
                  :key="pathIndex"
                  :d="path"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </span>
            <span class="file-explorer__name">{{ row.name }}</span>
          </span>
          <span class="file-explorer__cell file-explorer__cell--date">
            {{ formatDateTime(row.date) }}
          </span>
          <span class="file-explorer__cell file-explorer__cell--type">{{ row.typeLabel }}</span>
          <span class="file-explorer__cell file-explorer__cell--action">
            <span v-if="row.preview" class="file-explorer__open">预览</span>
            <span v-else class="file-explorer__pending" title="文件打开服务将在后端上线后可用">待开放</span>
          </span>
        </button>
      </div>

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
import type { MeetingAudio } from '@/types/audio'
import type { Material } from '@/types/material'
import type { Minutes } from '@/types/minutes'
import type { MeetingRecord } from '@/types/record'
import { formatDateTime } from '@/utils/datetime'
import { recordFileName } from '@/utils/meetingFiles'

const props = defineProps<{ meetingId: string }>()

/** 文件族（决定图标与类型文案） */
type FileFamily =
  | 'doc'
  | 'text'
  | 'sheet'
  | 'pdf'
  | 'markdown'
  | 'slide'
  | 'audio'
  | 'image'
  | 'other'

interface FileRow {
  key: string
  name: string
  date: string
  typeLabel: string
  family: FileFamily
  preview: { title: string; content: string; markdown: boolean } | null
}

const loading = ref(false)
const loadError = ref('')
const rows = ref<FileRow[]>([])
const preview = ref<{ title: string; content: string; markdown: boolean } | null>(null)

const EXT_FAMILY: Record<string, FileFamily> = {
  doc: 'doc',
  docx: 'doc',
  txt: 'text',
  log: 'text',
  csv: 'text',
  xls: 'sheet',
  xlsx: 'sheet',
  pdf: 'pdf',
  md: 'markdown',
  ppt: 'slide',
  pptx: 'slide',
  mp3: 'audio',
  wav: 'audio',
  m4a: 'audio',
  aac: 'audio',
  ogg: 'audio',
  mp4: 'audio',
  mov: 'audio',
  png: 'image',
  jpg: 'image',
  jpeg: 'image',
  gif: 'image',
  svg: 'image',
}

const EXT_TYPE_LABEL: Record<string, string> = {
  doc: 'DOC 文档',
  docx: 'DOCX 文档',
  txt: '文本文档',
  log: '日志文件',
  csv: 'CSV 表格',
  xls: 'XLS 工作表',
  xlsx: 'XLSX 工作表',
  pdf: 'PDF 文档',
  md: 'Markdown 文档',
  ppt: 'PPT 演示文稿',
  pptx: 'PPTX 演示文稿',
  mp3: 'MP3 音频',
  wav: 'WAV 音频',
  m4a: 'M4A 音频',
  aac: 'AAC 音频',
  ogg: 'OGG 音频',
  mp4: 'MP4 视频',
  mov: 'MOV 视频',
  png: 'PNG 图片',
  jpg: 'JPG 图片',
  jpeg: 'JPEG 图片',
  gif: 'GIF 图片',
  svg: 'SVG 图片',
}

/** 图标路径（按文件族取形） */
const FAMILY_ICON_PATHS: Record<FileFamily, string[]> = {
  doc: ['M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z', 'M14 3.5V8h4.5'],
  text: [
    'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
    'M14 3.5V8h4.5M8 11h6M8 14h6M8 17h4',
  ],
  sheet: [
    'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
    'M14 3.5V8h4.5M8 11h6M8 11v7M14 11v7M8 15h6',
  ],
  pdf: [
    'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
    'M14 3.5V8h4.5M8 12h4M8 15h6',
  ],
  markdown: [
    'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
    'M14 3.5V8h4.5M7.5 17v-4l2 2 2-2v4M13.5 15.5v-3l1.75 1.75L17 12.5v3',
  ],
  slide: [
    'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
    'M14 3.5V8h4.5M8 12h6M8 15h4',
  ],
  audio: [
    'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
    'M14 3.5V8h4.5M8 14.5a2 2 0 0 0 2 2h.5v-5h-.5a2 2 0 0 0-2 2v1Zm5-1.5a3.5 3.5 0 0 1 0 5',
  ],
  image: [
    'M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z',
    'M14 3.5V8h4.5M8 15.5l2.2-2.6a.8.8 0 0 1 1.2 0L16 16.5M15 13.2a.9.9 0 1 0 0-1.8.9.9 0 0 0 0 1.8Z',
  ],
  other: ['M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z', 'M14 3.5V8h4.5'],
}

function iconPathsOf(family: FileFamily): string[] {
  return FAMILY_ICON_PATHS[family]
}

function extOf(fileName: string): string {
  const match = /\.([a-z0-9]+)$/i.exec(fileName.trim())
  return match ? match[1].toLowerCase() : ''
}

function familyOf(fileName: string): FileFamily {
  return EXT_FAMILY[extOf(fileName)] ?? 'other'
}

function typeLabelOf(fileName: string, fallback: string): string {
  const ext = extOf(fileName)
  return EXT_TYPE_LABEL[ext] ?? fallback
}

function minutesName(item: Minutes): string {
  return `会议纪要_v${item.version}.md`
}

function rowSort(left: FileRow, right: FileRow): number {
  return left.name.localeCompare(right.name, 'zh-CN')
}

function openRow(row: FileRow): void {
  if (row.preview) {
    preview.value = row.preview
  }
}

async function load(meetingId: string): Promise<void> {
  loading.value = true
  preview.value = null
  loadError.value = ''
  const [materialsResult, audiosResult, minutesResult, recordsResult] = await Promise.allSettled([
    materialsApi.listMaterials(meetingId, { page: 1, page_size: 50 }),
    audioApi.listAudio(meetingId, { page: 1, page_size: 50 }),
    minutesApi.listMinutes(meetingId, { page: 1, page_size: 20 }),
    recordsApi.listRecords(meetingId, { page: 1, page_size: 50 }),
  ])

  const built: FileRow[] = []
  let failed = 0

  if (materialsResult.status === 'fulfilled') {
    for (const item of materialsResult.value.items as Material[]) {
      built.push({
        key: `mat-${item.material_id}`,
        name: item.file_name,
        date: item.created_at,
        typeLabel: typeLabelOf(item.file_name, '文件'),
        family: familyOf(item.file_name),
        preview: null,
      })
    }
  } else {
    failed += 1
  }

  if (audiosResult.status === 'fulfilled') {
    for (const item of audiosResult.value.items as MeetingAudio[]) {
      built.push({
        key: `aud-${item.audio_id}`,
        name: item.file_name,
        date: item.updated_at || item.created_at,
        typeLabel: typeLabelOf(item.file_name, '录音文件'),
        family: familyOf(item.file_name),
        preview: null,
      })
    }
  } else {
    failed += 1
  }

  if (minutesResult.status === 'fulfilled') {
    for (const item of minutesResult.value.items as Minutes[]) {
      built.push({
        key: `min-${item.minutes_id}`,
        name: minutesName(item),
        date: item.updated_at,
        typeLabel: 'Markdown 文档',
        family: 'markdown',
        preview: { title: minutesName(item), content: item.content, markdown: true },
      })
    }
  } else {
    failed += 1
  }

  if (recordsResult.status === 'fulfilled') {
    for (const item of recordsResult.value.items as MeetingRecord[]) {
      built.push({
        key: `rec-${item.record_id}`,
        name: recordFileName(item),
        date: item.updated_at,
        typeLabel: 'Markdown 文档',
        family: 'markdown',
        preview: { title: recordFileName(item), content: item.content, markdown: false },
      })
    }
  } else {
    failed += 1
  }

  built.sort(rowSort)
  rows.value = built
  loadError.value = failed > 0 ? `${failed} 类文件加载失败` : ''
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

/* ===== 资源管理器式文件列表 ===== */
.file-explorer {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.file-explorer__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 650;
  background: var(--color-surface-muted);
  border-bottom: 1px solid var(--color-border);
}

.file-explorer__col {
  flex: 0 0 auto;
}

.file-explorer__col--name {
  flex: 1;
  min-width: 0;
}

.file-explorer__col--date {
  width: 9.5rem;
}

.file-explorer__col--type {
  width: 8rem;
}

.file-explorer__col--action {
  width: 4.5rem;
}

.file-explorer__sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.file-explorer__row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  color: inherit;
  font: inherit;
  text-align: left;
  background: var(--color-surface);
  border: 0;
  border-bottom: 1px solid var(--color-border);
  cursor: default;
  transition: background var(--transition-fast);
}

.file-explorer__row:last-child {
  border-bottom: 0;
}

.file-explorer__row--previewable {
  cursor: pointer;
}

.file-explorer__row:hover {
  background: var(--color-primary-soft);
}

.file-explorer__cell {
  flex: 0 0 auto;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-explorer__cell--name {
  display: flex;
  flex: 1;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.file-explorer__name {
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-explorer__cell--date {
  width: 9.5rem;
  font-variant-numeric: tabular-nums;
}

.file-explorer__cell--type {
  width: 8rem;
}

.file-explorer__cell--action {
  display: flex;
  justify-content: flex-end;
  width: 4.5rem;
}

.file-explorer__open {
  padding: 2px 8px;
  color: var(--color-primary-strong);
  font-size: 0.6875rem;
  font-weight: 600;
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
}

.file-explorer__pending {
  padding: 2px 8px;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  background: var(--color-surface-muted);
  border-radius: var(--radius-pill);
  cursor: not-allowed;
}

.file-explorer__empty {
  margin: 0;
  padding: var(--space-5) var(--space-3);
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  text-align: center;
  background: var(--color-surface);
}

.file-explorer__error {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  color: var(--color-down);
  font-size: 0.75rem;
  background: var(--color-surface);
}

/* 文件族图标配色 */
.file-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  color: var(--color-muted-foreground);
}

.file-icon--doc {
  color: #155eef;
  background: rgba(21, 94, 239, 0.1);
}

.file-icon--sheet {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.1);
}

.file-icon--pdf {
  color: #dc2626;
  background: rgba(220, 38, 38, 0.1);
}

.file-icon--markdown,
.file-icon--text {
  color: #4f46e5;
  background: rgba(79, 70, 229, 0.1);
}

.file-icon--slide {
  color: #ea580c;
  background: rgba(234, 88, 12, 0.1);
}

.file-icon--audio {
  color: #0d9488;
  background: rgba(13, 148, 136, 0.1);
}

.file-icon--image {
  color: #a855f7;
  background: rgba(168, 85, 247, 0.1);
}

/* 文本预览区 */
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

@media (max-width: 720px) {
  .file-explorer__cell--date,
  .file-explorer__col--date {
    display: none;
  }

  .file-explorer__cell--type,
  .file-explorer__col--type {
    width: 5.5rem;
  }
}
</style>
