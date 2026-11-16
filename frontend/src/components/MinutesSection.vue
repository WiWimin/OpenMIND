<template>
  <div class="minutes-section">
    <ErrorMessage v-if="actionError" :error="actionError" />

    <LoadingSpinner v-if="loading && items.length === 0" class="minutes-section__state" />

    <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />

    <EmptyState
      v-else-if="items.length === 0"
      title="还没有纪要"
      description="基于会议记录生成会议纪要，确认后可提取行动项。"
    />

    <!-- 文档编辑区：打开即展示最新一版正文，操作按钮在编辑区上方工具栏右侧 -->
    <div v-else-if="selected" class="minutes-section__editor">
      <RichTextEditor
        id="minutes-content"
        v-model="draft"
        label="纪要内容"
        :editable="!readonly"
        variant="document"
      >
        <template #toolbar-end>
          <div v-if="!readonly" class="minutes-section__actions">
            <AppButton size="sm" variant="ghost" :loading="saving" @click="save">保存</AppButton>
            <AppButton
              v-if="selected.status !== 'confirmed'"
              size="sm"
              variant="ghost"
              :loading="confirming"
              @click="confirm"
            >
              确认
            </AppButton>
            <AppButton size="sm" variant="ghost" :loading="exporting" @click="exportDocx">
              导出 DOCX
            </AppButton>
          </div>
        </template>
      </RichTextEditor>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as minutesApi from '@/api/minutes'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import type { Minutes } from '@/types/minutes'

const props = withDefaults(
  defineProps<{
    meetingId: string
    meetingTitle?: string
    readonly?: boolean
  }>(),
  {
    meetingTitle: '',
    readonly: false,
  },
)

const toast = useToast()
const { mirrorConfirmedMinutes } = useLocalWorkspace()

const { items, loading, error, load } = useAsyncList<Minutes>({
  fetcher: ({ page, page_size }) => minutesApi.listMinutes(props.meetingId, { page, page_size }),
})

const selected = ref<Minutes | null>(null)
const draft = ref('')
const saving = ref(false)
const confirming = ref(false)
const exporting = ref(false)
const actionError = ref<unknown>(null)

function select(minutes: Minutes): void {
  selected.value = minutes
  draft.value = minutes.content
}

function syncSelected(updated: Minutes): void {
  if (selected.value?.minutes_id === updated.minutes_id) {
    selected.value = updated
    draft.value = updated.content
  }
}

async function refresh(): Promise<void> {
  await load()
  // 无历史列表：打开即选中最新一版正文
  if (!selected.value && items.value.length > 0) {
    select(items.value[0])
  }
}

onMounted(() => {
  void refresh()
})

async function save(): Promise<void> {
  if (!selected.value) {
    return
  }
  saving.value = true
  actionError.value = null
  try {
    const updated = await minutesApi.updateMinutes(selected.value.minutes_id, { content: draft.value })
    syncSelected(updated)
    await load()
    toast.success('纪要已保存')
  } catch (caught) {
    actionError.value = caught
  } finally {
    saving.value = false
  }
}

async function confirm(): Promise<void> {
  if (!selected.value) {
    return
  }
  confirming.value = true
  actionError.value = null
  try {
    const updated = await minutesApi.confirmMinutes(selected.value.minutes_id)
    syncSelected(updated)
    await load()
    toast.success('纪要已确认')
    // 确认后才镜像到本地，未确认的版本不落盘；未连接本地文件夹时静默跳过
    const mirror = await mirrorConfirmedMinutes(
      props.meetingId,
      updated.content,
      props.meetingTitle,
    )
    if (mirror === 'written') {
      toast.success('纪要已同步到本地文件夹')
    } else if (mirror === 'failed') {
      toast.error('本地文件夹同步失败，请检查文件夹授权')
    }
  } catch (caught) {
    actionError.value = caught
  } finally {
    confirming.value = false
  }
}

async function exportDocx(): Promise<void> {
  if (!selected.value) {
    return
  }
  exporting.value = true
  actionError.value = null
  try {
    const { buildMinutesDocxBlob, downloadBlob } = await import('@/utils/minutesDocx')
    const title = props.meetingTitle ? `${props.meetingTitle} · 会议纪要` : '会议纪要'
    const blob = await buildMinutesDocxBlob(title, draft.value)
    downloadBlob(blob, `${title}.docx`)
    toast.success('纪要已导出为 DOCX')
  } catch (caught) {
    actionError.value = caught
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.minutes-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.minutes-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

/* 文档编辑区：占满抽屉正文宽度，纸张样式由编辑器 document 变体提供 */
.minutes-section__editor {
  display: flex;
  flex-direction: column;
}

.minutes-section__actions {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
