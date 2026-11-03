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
          {{ wsStatus === 'connected' ? '更换文件夹' : '选择本地文件夹' }}
        </AppButton>
        <AppButton
          v-if="wsStatus === 'needs-permission'"
          variant="ghost"
          :loading="picking"
          @click="restorePermission"
        >
          恢复权限
        </AppButton>
        <AppButton
          v-if="!readonly"
          :loading="importing"
          :disabled="!connected || files.length === 0"
          @click="importFiles"
        >
          导入资料（{{ files.length }}）
        </AppButton>
        <AppButton
          v-if="showExport"
          :loading="exporting"
          :disabled="!connected"
          @click="exportMinutes"
        >
          导出最新纪要
        </AppButton>
      </div>

      <div
        v-if="wsStatus === 'needs-permission'"
        class="local-workspace__reminder"
        role="status"
      >
        <span class="local-workspace__reminder-text">
          本地文件夹权限已过期或被撤销，点击「恢复权限」继续，无需重新选择目录
        </span>
      </div>

      <p v-if="wsDirectory" class="local-workspace__directory">
        已选择：<strong>{{ wsDirectory }}</strong>
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

      <!-- 新文件提醒：检测到未导入的本地文件，需用户点击确认后才上传 -->
      <div v-if="newFiles.length" class="local-workspace__reminder" role="status">
        <span class="local-workspace__reminder-text">
          检测到 {{ newFiles.length }} 个本地新文件尚未导入该会议
        </span>
        <AppButton size="sm" :loading="importing" :disabled="readonly" @click="importNewFiles">
          仅导入新文件
        </AppButton>
      </div>

      <p v-if="status" class="local-workspace__status" role="status">{{ status }}</p>
      <p v-if="error" class="local-workspace__error" role="alert">{{ error }}</p>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import AppButton from '@/components/AppButton.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { ALLOWED_MATERIAL_EXTENSIONS } from '@/constants/upload'
import {
  isLocalWorkspaceSupported,
  writeBlobToPath,
  type LocalDirHandle,
} from '@/utils/localFileSystem'
import { isAllowedExtension } from '@/utils/materialUpload'

interface LocalFileEntry {
  name: string
  file: File
  size: number
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

/** 全局共享目录句柄（与会议管理页、镜像功能同一份授权） */
const ws = useLocalWorkspace()

const supported = computed(() => isLocalWorkspaceSupported())
const wsStatus = computed(() => ws.status.value)
const wsDirectory = computed(() => ws.directoryName.value)
const connected = computed(() => wsStatus.value === 'connected')

const files = ref<LocalFileEntry[]>([])
const existingNames = ref<Set<string>>(new Set())
const picking = ref(false)
const importing = ref(false)
const exporting = ref(false)
const status = ref('')
const error = ref('')

/** 目录扫描结果中尚未导入到当前会议的文件 */
const newFiles = computed<LocalFileEntry[]>(() =>
  files.value.filter((entry) => !existingNames.value.has(entry.name)),
)

function messageOf(caught: unknown): string {
  if (typeof caught === 'object' && caught !== null && 'message' in caught) {
    return String((caught as { message: unknown }).message)
  }
  return '操作失败，请重试'
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

async function readFiles(handle: LocalDirHandle): Promise<LocalFileEntry[]> {
  const result: LocalFileEntry[] = []
  for await (const entry of handle.values()) {
    if (result.length >= 50) {
      break
    }
    if (entry.kind !== 'file' || !entry.getFile) {
      continue
    }
    if (!isAllowedExtension(entry.name, ALLOWED_MATERIAL_EXTENSIONS)) {
      continue
    }
    const file = await entry.getFile()
    result.push({ name: entry.name, file, size: file.size })
  }
  return result.sort((left, right) => left.name.localeCompare(right.name))
}

/** 拉取当前会议已有资料文件名，用于识别本地新文件 */
async function loadExistingMaterials(): Promise<void> {
  try {
    const result = await materialsApi.listMaterials(props.meetingId, { page: 1, page_size: 100 })
    existingNames.value = new Set(result.items.map((item) => item.file_name))
  } catch {
    existingNames.value = new Set()
  }
}

/** 从共享句柄刷新文件列表（连接/恢复权限/挂载后调用） */
async function refreshFromRoot(): Promise<void> {
  const root = ws.rootHandle.value
  if (!root) {
    files.value = []
    return
  }
  files.value = await readFiles(root)
  await loadExistingMaterials()
}

onMounted(async () => {
  await ws.init()
  if (ws.rootHandle.value) {
    try {
      await refreshFromRoot()
      status.value =
        files.value.length > 0
          ? `已读取 ${files.value.length} 个支持的资料文件`
          : '文件夹中没有 PDF / DOCX / TXT 资料'
    } catch (caught) {
      /* 权限过期时等待恢复，不作为错误上报 */
      if (wsStatus.value === 'connected') {
        error.value = messageOf(caught)
      }
    }
  }
})

async function chooseDirectory(): Promise<void> {
  picking.value = true
  error.value = ''
  status.value = ''
  try {
    const granted = await ws.connect()
    if (!granted) {
      if (wsStatus.value === 'needs-permission') {
        status.value = '本地文件夹权限未授予，点击「恢复权限」重试'
      }
      return
    }
    await refreshFromRoot()
    status.value =
      files.value.length > 0
        ? `已读取 ${files.value.length} 个支持的资料文件`
        : '文件夹中没有 PDF / DOCX / TXT 资料'
  } catch (caught) {
    error.value = messageOf(caught)
  } finally {
    picking.value = false
  }
}

/** 权限过期后的一键恢复（手势内原生弹窗，无需重新选目录） */
async function restorePermission(): Promise<void> {
  picking.value = true
  error.value = ''
  status.value = ''
  try {
    const granted = await ws.restore()
    if (!granted) {
      error.value = '未能恢复权限，请点击「选择本地文件夹」重新授权'
      return
    }
    await refreshFromRoot()
    status.value = '本地文件夹权限已恢复'
  } catch (caught) {
    error.value = messageOf(caught)
  } finally {
    picking.value = false
  }
}

async function uploadEntries(
  entries: LocalFileEntry[],
): Promise<{ importedNames: string[]; failures: string[] }> {
  const importedNames: string[] = []
  const failures: string[] = []
  for (const entry of entries) {
    try {
      await materialsApi.uploadMaterial(props.meetingId, {
        file: entry.file,
        source: '本地工作区',
      })
      importedNames.push(entry.name)
    } catch (caught) {
      failures.push(`${entry.name}：${messageOf(caught)}`)
    }
  }
  return { importedNames, failures }
}

function markImported(names: string[]): void {
  const next = new Set(existingNames.value)
  for (const name of names) {
    next.add(name)
  }
  existingNames.value = next
}

async function importFiles(): Promise<void> {
  if (!connected.value || files.value.length === 0 || props.readonly) {
    return
  }
  importing.value = true
  error.value = ''
  status.value = ''
  try {
    const { importedNames, failures } = await uploadEntries(files.value)
    if (importedNames.length > 0) {
      markImported(importedNames)
      emit('imported')
      status.value = `已导入 ${importedNames.length} 个文件`
    }
    if (failures.length > 0) {
      error.value = failures.join('\n')
    }
  } finally {
    importing.value = false
  }
}

/** 只导入检测到的新文件，需用户点击确认后才上传 */
async function importNewFiles(): Promise<void> {
  if (!connected.value || newFiles.value.length === 0 || props.readonly) {
    return
  }
  importing.value = true
  error.value = ''
  status.value = ''
  const targets = [...newFiles.value]
  try {
    const { importedNames, failures } = await uploadEntries(targets)
    if (importedNames.length > 0) {
      markImported(importedNames)
      emit('imported')
      status.value = `已导入 ${importedNames.length} 个新文件`
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
  const root = ws.rootHandle.value
  if (!root || !connected.value) {
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
    // 写入会议根（新建会议时选择的存储位置，默认 <会议名>/）
    const segments = await ws.meetingRootSegments(
      props.meetingId,
      props.meetingTitle || '会议',
    )
    await writeBlobToPath(root, segments, safeFileName(props.meetingTitle), blob)
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

.local-workspace__reminder {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.25);
  border-radius: var(--radius-md);
  font-size: 0.8125rem;
}

.local-workspace__reminder-text {
  color: var(--color-primary-strong);
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
