<template>
  <section class="local-workspace">
    <header class="local-workspace__head">
      <div>
        <h3 class="local-workspace__title">本地会议工作区</h3>
        <p class="local-workspace__hint">
          <template v-if="showExport">
            选择本地文件夹后，可把资料导入当前会议，或把最新纪要导出到该文件夹。仅在浏览器授权后访问。
          </template>
          <template v-else>
            选择本地文件夹后，可把资料导入当前会议。仅在浏览器授权后访问。
          </template>
        </p>
      </div>
    </header>

    <p v-if="!supported" class="local-workspace__unsupported">
      当前浏览器不支持本地文件夹访问。请使用支持 File System Access API 的 Chromium 浏览器。
    </p>

    <template v-else>
      <div class="local-workspace__actions">
        <AppButton variant="ghost" :loading="picking" @click="chooseDirectory">
          选择本地文件夹
        </AppButton>
        <AppButton
          v-if="!readonly"
          :loading="importing"
          :disabled="!directory || files.length === 0"
          @click="importFiles"
        >
          导入资料（{{ files.length }}）
        </AppButton>
        <AppButton
          v-if="showExport"
          :loading="exporting"
          :disabled="!directory"
          @click="exportMinutes"
        >
          导出最新纪要
        </AppButton>
      </div>

      <p v-if="directory" class="local-workspace__directory">
        已选择：<strong>{{ directory.name }}</strong>
      </p>
      <p v-if="readonly" class="local-workspace__hint">
        会议已归档，可导出纪要，但不能从本地导入资料。
      </p>

      <ul v-if="files.length" class="local-workspace__files">
        <li v-for="entry in files" :key="entry.name">
          <span>{{ entry.name }}</span>
          <span>{{ formatSize(entry.size) }}</span>
        </li>
      </ul>

      <p v-if="status" class="local-workspace__status" role="status">{{ status }}</p>
      <p v-if="error" class="local-workspace__error" role="alert">{{ error }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'

import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import AppButton from '@/components/AppButton.vue'
import { ALLOWED_MATERIAL_EXTENSIONS } from '@/constants/upload'
import { fileExtension } from '@/utils/materialUpload'

interface LocalFileEntry {
  name: string
  file: File
  size: number
}

interface LocalDirectoryEntry {
  kind: 'file' | 'directory'
  name: string
  getFile?: () => Promise<File>
}

interface LocalWritable {
  write: (data: Blob) => Promise<void>
  close: () => Promise<void>
}

interface LocalFileHandle {
  getFile: () => Promise<File>
  createWritable: () => Promise<LocalWritable>
}

interface LocalDirectoryHandle {
  name: string
  values: () => AsyncIterableIterator<LocalDirectoryEntry>
  getFileHandle: (name: string, options?: { create?: boolean }) => Promise<LocalFileHandle>
}

interface DirectoryPickerWindow extends Window {
  showDirectoryPicker?: () => Promise<LocalDirectoryHandle>
}

const props = withDefaults(
  defineProps<{
    meetingId: string
    meetingTitle?: string
    readonly?: boolean
    /** 是否显示「导出最新纪要」（预处理阶段尚无纪要，可关闭） */
    showExport?: boolean
  }>(),
  {
    meetingTitle: '',
    readonly: false,
    showExport: true,
  },
)

const emit = defineEmits<{ imported: [] }>()

const supported = computed(
  () =>
    typeof window !== 'undefined' &&
    typeof (window as DirectoryPickerWindow).showDirectoryPicker === 'function',
)

const directory = shallowRef<LocalDirectoryHandle | null>(null)
const files = ref<LocalFileEntry[]>([])
const picking = ref(false)
const importing = ref(false)
const exporting = ref(false)
const status = ref('')
const error = ref('')

function messageOf(caught: unknown): string {
  if (typeof caught === 'object' && caught !== null && 'message' in caught) {
    return String((caught as { message: unknown }).message)
  }
  return '操作失败，请重试'
}

function isAbort(caught: unknown): boolean {
  return (
    typeof caught === 'object' &&
    caught !== null &&
    'name' in caught &&
    (caught as { name: unknown }).name === 'AbortError'
  )
}

function formatSize(size: number): string {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

async function readFiles(handle: LocalDirectoryHandle): Promise<LocalFileEntry[]> {
  const result: LocalFileEntry[] = []
  for await (const entry of handle.values()) {
    if (result.length >= 50) {
      break
    }
    if (entry.kind !== 'file' || !entry.getFile) {
      continue
    }
    if (!(ALLOWED_MATERIAL_EXTENSIONS as readonly string[]).includes(fileExtension(entry.name))) {
      continue
    }
    const file = await entry.getFile()
    result.push({ name: entry.name, file, size: file.size })
  }
  return result.sort((left, right) => left.name.localeCompare(right.name))
}

async function chooseDirectory(): Promise<void> {
  const picker = (window as DirectoryPickerWindow).showDirectoryPicker
  if (!picker) {
    error.value = '当前浏览器不支持本地文件夹访问'
    return
  }
  picking.value = true
  error.value = ''
  status.value = ''
  try {
    const handle = await picker()
    directory.value = handle
    files.value = await readFiles(handle)
    status.value =
      files.value.length > 0
        ? `已读取 ${files.value.length} 个支持的资料文件`
        : '文件夹中没有 PDF / DOCX / TXT 资料'
  } catch (caught) {
    if (!isAbort(caught)) {
      error.value = messageOf(caught)
    }
  } finally {
    picking.value = false
  }
}

async function importFiles(): Promise<void> {
  if (!directory.value || files.value.length === 0 || props.readonly) {
    return
  }
  importing.value = true
  error.value = ''
  status.value = ''
  let imported = 0
  const failures: string[] = []
  try {
    for (const entry of files.value) {
      try {
        await materialsApi.uploadMaterial(props.meetingId, {
          file: entry.file,
          source: '本地工作区',
        })
        imported += 1
      } catch (caught) {
        failures.push(`${entry.name}：${messageOf(caught)}`)
      }
    }
    if (imported > 0) {
      emit('imported')
      status.value = `已导入 ${imported} 个文件`
    }
    if (failures.length > 0) {
      error.value = failures.join('\n')
    }
  } finally {
    importing.value = false
  }
}

function safeFileName(title: string): string {
  const base = `${title || '会议'}-会议纪要`.replace(/[\\/:*?"<>|]/g, '_').trim()
  return `${base || '会议纪要'}.docx`
}

async function exportMinutes(): Promise<void> {
  if (!directory.value) {
    return
  }
  exporting.value = true
  error.value = ''
  status.value = ''
  try {
    const list = await minutesApi.listMinutes(props.meetingId, {
      page: 1,
      page_size: 1,
    })
    const latest = list.items[0]
    if (!latest) {
      error.value = '当前会议还没有可导出的纪要'
      return
    }
    const { buildMinutesDocxBlob } = await import('@/utils/minutesDocx')
    const blob = await buildMinutesDocxBlob(
      `${props.meetingTitle || '会议'} · 会议纪要`,
      latest.content,
    )
    const fileHandle = await directory.value.getFileHandle(
      safeFileName(props.meetingTitle),
      { create: true },
    )
    const writable = await fileHandle.createWritable()
    await writable.write(blob)
    await writable.close()
    status.value = '最新纪要已导出到本地文件夹'
  } catch (caught) {
    error.value = messageOf(caught)
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.local-workspace {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
}

.local-workspace__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.local-workspace__hint,
.local-workspace__unsupported,
.local-workspace__directory,
.local-workspace__status {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.85rem;
}

.local-workspace__unsupported,
.local-workspace__error {
  color: var(--color-down);
}

.local-workspace__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.local-workspace__files {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 12rem;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.local-workspace__files li {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  padding: 4px var(--space-2);
  background: var(--color-surface-strong);
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
}

.local-workspace__error {
  margin: 0;
  font-size: 0.85rem;
  white-space: pre-wrap;
}
</style>
