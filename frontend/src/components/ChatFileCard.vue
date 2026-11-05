<template>
  <div class="chat-file" role="status">
    <div class="chat-file__head">
      <span class="chat-file__icon" aria-hidden="true">📄</span>
      <span class="chat-file__name" :title="file.filename">{{ file.filename }}</span>
      <AppButton size="sm" variant="ghost" :loading="downloading" @click="download">
        下载 DOCX
      </AppButton>
    </div>

    <div class="chat-file__states">
      <!-- ② 会议资料（权威副本，主链路） -->
      <span class="chat-file__state" :class="`chat-file__state--${uploadState}`">
        <template v-if="uploadState === 'saving'">正在保存到会议资料…</template>
        <template v-else-if="uploadState === 'saved'">✓ 已保存到会议资料</template>
        <template v-else>
          ✕ 保存到会议资料失败
          <button type="button" class="chat-file__retry" @click="saveToMeeting">重试</button>
        </template>
      </span>

      <!-- ③ 本地文件夹镜像（尽力而为，从） -->
      <span class="chat-file__state" :class="`chat-file__state--${mirrorState}`">
        <template v-if="mirrorState === 'pending'">本地文件夹写入中…</template>
        <template v-else-if="mirrorState === 'written'">✓ 已写入本地文件夹</template>
        <template v-else-if="mirrorState === 'skipped'">未连接本地文件夹</template>
        <template v-else>
          ✕ 本地写入失败
          <button type="button" class="chat-file__retry" @click="mirrorToLocal">重试</button>
        </template>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as materialsApi from '@/api/materials'
import AppButton from '@/components/AppButton.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import type { ChatFile } from '@/types/chat'
import { renderMarkdown } from '@/utils/markdown'
import { buildMinutesDocxBlob, downloadBlob } from '@/utils/minutesDocx'

const props = defineProps<{
  meetingId: string
  file: ChatFile
}>()

const toast = useToast()
const ws = useLocalWorkspace()

const uploading = ref(false)
const downloading = ref(false)
const uploadState = ref<'saving' | 'saved' | 'failed'>('saving')
const mirrorState = ref<'pending' | 'written' | 'skipped' | 'failed'>('pending')

/** DOCX 文件名：xxx.md → xxx.docx */
const docxName = props.file.filename.replace(/\.(md|markdown|txt)$/i, '') + '.docx'

/** 三处保存共用同一份 DOCX（md → HTML → DOCX，复用纪要导出管线） */
async function buildDocx(): Promise<Blob> {
  return buildMinutesDocxBlob(
    props.file.filename.replace(/\.(md|markdown|txt)$/i, ''),
    renderMarkdown(props.file.content),
  )
}

async function saveToMeeting(): Promise<void> {
  uploading.value = true
  uploadState.value = 'saving'
  try {
    const blob = await buildDocx()
    const file = new File([blob], docxName, {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    })
    await materialsApi.uploadMaterial(props.meetingId, { file, source: 'AI 生成' })
    uploadState.value = 'saved'
  } catch (caught) {
    console.warn('[chat-file] 保存到会议资料失败', caught)
    uploadState.value = 'failed'
  } finally {
    uploading.value = false
  }
}

async function mirrorToLocal(): Promise<void> {
  mirrorState.value = 'pending'
  try {
    const blob = await buildDocx()
    const result = await ws.mirrorMeetingFile({
      meetingId: props.meetingId,
      fileName: docxName,
      content: blob,
    })
    mirrorState.value = result === 'written' ? 'written' : result === 'skipped' ? 'skipped' : 'failed'
  } catch (caught) {
    console.warn('[chat-file] 本地镜像失败', caught)
    mirrorState.value = 'failed'
  }
}

async function download(): Promise<void> {
  downloading.value = true
  try {
    const blob = await buildDocx()
    downloadBlob(blob, docxName)
  } catch (caught) {
    console.warn('[chat-file] DOCX 生成失败', caught)
    toast.error('生成 DOCX 失败，请重试（回答正文仍可复制）')
  } finally {
    downloading.value = false
  }
}

onMounted(() => {
  // ② 会议资料（主）与 ③ 本地镜像（从）并行、互不阻塞、各自重试
  void saveToMeeting()
  void mirrorToLocal()
})
</script>

<style scoped>
.chat-file {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.chat-file__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.chat-file__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-file__states {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
}

.chat-file__state {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.chat-file__state--saved,
.chat-file__state--written {
  color: var(--color-success, #16a34a);
}

.chat-file__state--failed {
  color: var(--color-down);
}

.chat-file__state--skipped {
  opacity: 0.7;
}

.chat-file__retry {
  padding: 0;
  color: var(--color-primary);
  font-size: 0.75rem;
  background: none;
  border: 0;
  text-decoration: underline;
  cursor: pointer;
}
</style>
