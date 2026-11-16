<template>
  <div class="doc-card" role="group" :aria-label="title">
    <div class="doc-card__main">
      <span class="doc-card__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
          <path
            d="M6 3.5h8l4 4v13H6zM14 3.5v4h4"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
      <div class="doc-card__text">
        <p class="doc-card__title">{{ title }}</p>
        <p class="doc-card__meta">
          <span v-if="meta?.template" class="doc-card__badge">{{ templateLabel }}</span>
          <span class="doc-card__size">{{ file.filename }}</span>
        </p>
      </div>
      <div class="doc-card__actions">
        <button
          type="button"
          class="doc-card__btn doc-card__btn--primary"
          title="在右侧打开查看与编辑"
          @click="emit('open')"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
            <path
              d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linejoin="round"
            />
            <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6" />
          </svg>
          打开
        </button>
        <button
          type="button"
          class="doc-card__btn"
          :disabled="saving"
          :title="savingLabel"
          aria-label="保存到会议资料与本地文件夹"
          @click="save"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
            <path
              d="M5 5.5h11l3 3v10H5zM8 5.5v5h7v-5M8 19v-4.5h8V19"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
        <button
          type="button"
          class="doc-card__btn"
          :disabled="downloading"
          title="下载 DOCX"
          aria-label="下载 DOCX"
          @click="download"
        >
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
            <path
              d="M12 4v11m0 0-4-4m4 4 4-4M5 19.5h14"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      </div>
    </div>

    <p v-if="saveState" class="doc-card__state" :class="`doc-card__state--${saveState}`">
      {{ saveStateText }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import * as materialsApi from '@/api/materials'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import type { MinutesDocMeta } from '@/types/agent'
import type { ChatFile } from '@/types/chat'
import { renderMarkdown } from '@/utils/markdown'
import { buildMinutesDocxBlob, downloadBlob } from '@/utils/minutesDocx'

const props = defineProps<{
  meetingId: string
  file: ChatFile
  meta?: MinutesDocMeta
}>()

const emit = defineEmits<{ open: [] }>()

const toast = useToast()
const ws = useLocalWorkspace()

const saving = ref(false)
const downloading = ref(false)
const saveState = ref<'saved' | 'partial' | 'failed' | ''>('')

const title = computed(() => {
  const base = props.file.filename.replace(/\.(md|markdown|txt)$/i, '')
  return props.meta?.version ? `会议纪要 v${props.meta.version}` : base
})

const templateLabel = computed(() => {
  const map: Record<string, string> = {
    standard: '标准纪要',
    concise: '简洁记录',
    task_list: '任务清单',
    custom: '自定义模板',
  }
  return map[props.meta?.template ?? ''] ?? ''
})

const savingLabel = computed(() => (saving.value ? '保存中…' : '保存到会议资料与本地文件夹'))

const saveStateText = computed(() => {
  if (saveState.value === 'saved') return '已存入会议资料，并写入本地文件夹'
  if (saveState.value === 'partial') return '已存入会议资料，本地文件夹未连接'
  if (saveState.value === 'failed') return '保存失败，请重试'
  return ''
})

/** 同一份 DOCX 同时写会议资料（权威副本）与本地文件夹（尽力而为） */
async function save(): Promise<void> {
  if (saving.value) {
    return
  }
  saving.value = true
  saveState.value = ''
  try {
    const docxName = props.file.filename.replace(/\.(md|markdown|txt)$/i, '') + '.docx'
    const blob = await buildMinutesDocxBlob(
      title.value,
      renderMarkdown(props.file.content),
    )
    const [meetingResult, localResult] = await Promise.allSettled([
      materialsApi.uploadMaterial(props.meetingId, {
        file: new File([blob], docxName, {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }),
        source: 'AI 生成',
      }),
      ws.mirrorMeetingFile({
        meetingId: props.meetingId,
        fileName: docxName,
        content: blob,
      }),
    ])

    const meetingOk = meetingResult.status === 'fulfilled'
    const localOk = localResult.status === 'fulfilled' && localResult.value === 'written'

    if (meetingOk && localOk) {
      saveState.value = 'saved'
      toast.success('已存入会议资料并写入本地文件夹')
    } else if (meetingOk) {
      saveState.value = 'partial'
      toast.success('已存入会议资料')
    } else {
      saveState.value = 'failed'
      toast.error('保存失败，请重试')
    }
  } catch {
    saveState.value = 'failed'
    toast.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}

async function download(): Promise<void> {
  if (downloading.value) {
    return
  }
  downloading.value = true
  try {
    const docxName = props.file.filename.replace(/\.(md|markdown|txt)$/i, '') + '.docx'
    const blob = await buildMinutesDocxBlob(title.value, renderMarkdown(props.file.content))
    downloadBlob(blob, docxName)
  } catch {
    toast.error('生成 DOCX 失败，请重试')
  } finally {
    downloading.value = false
  }
}
</script>

<style scoped>
.doc-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.doc-card__main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.doc-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 2.25rem;
  height: 2.25rem;
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
  border-radius: var(--radius-sm);
}

.doc-card__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.doc-card__title {
  margin: 0;
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.9375rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
}

.doc-card__badge {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  padding: 1px 6px;
  background: var(--color-surface-muted);
  border-radius: 999px;
}

.doc-card__size {
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-card__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: none;
}

.doc-card__btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 1.875rem;
  padding: 0 0.5rem;
  color: var(--color-foreground);
  font-size: 0.75rem;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.doc-card__btn:hover:not(:disabled) {
  background: var(--color-surface-muted);
}

.doc-card__btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.doc-card__btn--primary {
  color: var(--color-primary-strong);
  border-color: var(--color-primary-soft, var(--color-border));
}

.doc-card__state {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.doc-card__state--saved {
  color: var(--color-success, #16a34a);
}

.doc-card__state--failed {
  color: var(--color-down);
}
</style>
