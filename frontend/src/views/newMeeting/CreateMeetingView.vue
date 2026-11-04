<template>
  <section class="create-meeting">
    <PageHeader title="新建会议" description="填写会议信息，创建后进入会议流程页" />
    <div class="create-meeting__card">
      <MeetingForm
        :loading="creating"
        :error="createError"
        :categories="categories"
        :closable="false"
        @submit="createMeeting"
        @cancel="goBack"
      />
    </div>
    <p
      v-if="importProgress"
      class="create-meeting__import"
      role="status"
      aria-live="polite"
    >
      正在从本地文件夹导入资料 {{ importProgress.done }}/{{ importProgress.total }}：{{
        importProgress.fileName
      }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import * as meetingsApi from '@/api/meetings'
import MeetingForm, { type MeetingFormPayload } from '@/components/MeetingForm.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { MAX_UPLOAD_MB } from '@/constants/upload'
import {
  AUTO_IMPORT_MAX_FILES,
  autoImportMeetingFiles,
  type AutoImportResult,
} from '@/utils/autoImport'
import { resolveErrorMessage } from '@/utils/errors'
import {
  assignCategory,
  loadCategories,
  type MeetingCategory,
} from '@/utils/meetingCategories'

const router = useRouter()
const toast = useToast()
const ws = useLocalWorkspace()

const creating = ref(false)
const createError = ref<unknown>(null)
const categories = ref<MeetingCategory[]>(loadCategories())
const importProgress = ref<{ done: number; total: number; fileName: string } | null>(null)

/** 汇总导入结果：成功/跳过/失败都要有明确提示，失败列出文件名与原因 */
function reportImportResult(result: AutoImportResult): void {
  const parts: string[] = []
  if (result.imported.length > 0) {
    parts.push(`已导入 ${result.imported.length} 个`)
  }
  if (result.skipped.length > 0) {
    parts.push(`跳过 ${result.skipped.length} 个已存在`)
  }
  if (result.oversized.length > 0) {
    parts.push(`${result.oversized.length} 个超过 ${MAX_UPLOAD_MB}MB`)
  }
  if (result.unsupported.length > 0) {
    parts.push(`${result.unsupported.length} 个格式不支持`)
  }
  if (result.failed.length > 0) {
    parts.push(`失败 ${result.failed.length} 个`)
  }
  if (result.truncated) {
    parts.push(`超出 ${AUTO_IMPORT_MAX_FILES} 个上限部分未读取`)
  }

  if (parts.length === 0) {
    toast.success('本地文件夹中没有可导入的资料')
    return
  }
  const summary = `本地文件夹资料：${parts.join('，')}`
  if (result.failed.length === 0) {
    toast.success(summary)
    return
  }
  const detail = result.failed
    .slice(0, 2)
    .map((item) => `${item.name}（${item.reason}）`)
    .join('、')
  const more = result.failed.length > 2 ? ` 等 ${result.failed.length} 个` : ''
  toast.error(`${summary}：${detail}${more}`)
  console.warn('[auto-import] 失败明细', result.failed)
}

/**
 * 创建成功后从所选文件夹自动导入已有资料。
 * 任何失败都不阻塞创建主流程；配置了（选了文件夹）但失败必须提示，未选则不打扰。
 */
async function autoImportIfPossible(
  meetingId: string,
  segments: string[],
): Promise<void> {
  if (ws.status.value !== 'connected' || !ws.rootHandle.value) {
    // 创建页存储选择器仅在已连接时展示；走到这里说明权限中途失效
    toast.error('本地文件夹权限未授予，资料未自动导入；可在会议详情页恢复权限后手动导入')
    return
  }
  try {
    const result = await autoImportMeetingFiles({
      meetingId,
      root: ws.rootHandle.value,
      segments,
      onProgress: (progress) => {
        importProgress.value = progress
      },
    })
    reportImportResult(result)
  } catch (caught) {
    // 读目录失败（权限过期/路径不存在）或已有资料列表拉取失败（无法去重）
    toast.error(
      `本地文件夹资料未自动导入：${resolveErrorMessage(caught, '读取文件夹失败')}，可在会议详情页手动导入`,
    )
  } finally {
    importProgress.value = null
  }
}

async function createMeeting(payload: MeetingFormPayload): Promise<void> {
  creating.value = true
  createError.value = null
  try {
    const created = await meetingsApi.createMeeting({
      title: payload.title,
      topic: payload.topic,
      meeting_time: payload.meeting_time,
    })
    if (payload.categoryId) {
      assignCategory(created.meeting_id, payload.categoryId)
    }
    // 本地存储位置：显式选择的会议根持久化；未选择且已连接时落默认 <会议名>/
    if (payload.localPath && payload.localPath.length > 0) {
      try {
        const { storeMeetingRoot } = await import('@/utils/localFileSystem')
        await storeMeetingRoot(created.meeting_id, payload.localPath)
      } catch {
        toast.error('本地存储位置保存失败，本次会议将使用默认文件夹')
      }
      toast.success('会议已创建')
      // 选了文件夹 → 自动导入其中已有资料（进度可见，失败不阻塞跳转）
      await autoImportIfPossible(created.meeting_id, payload.localPath)
    } else {
      await ws.createDefaultMeetingFolder(created.title)
      toast.success('会议已创建')
    }
    await router.replace({
      name: ROUTE_NAMES.newMeeting,
      query: { meetingId: created.meeting_id },
    })
  } catch (caught) {
    createError.value = caught
  } finally {
    creating.value = false
  }
}

function goBack(): void {
  if (window.history.length > 1) {
    void router.back()
    return
  }
  void router.push({ name: ROUTE_NAMES.dashboard })
}
</script>

<style scoped>
.create-meeting {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.create-meeting__card {
  max-width: 40rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.create-meeting__card :deep(.meeting-form) {
  padding-top: var(--space-5);
}

.create-meeting__import {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.85rem;
}
</style>
