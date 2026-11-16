<template>
  <MeetingFormDialog
    :open="open"
    :loading="creating"
    :error="createError"
    :categories="categories"
    @submit="createMeeting"
    @cancel="close"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import * as meetingsApi from '@/api/meetings'
import MeetingFormDialog, { type MeetingFormPayload } from '@/components/MeetingFormDialog.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import {
  assignCategory,
  loadCategories,
  type MeetingCategory,
} from '@/utils/meetingCategories'

const router = useRouter()
const toast = useToast()
const ws = useLocalWorkspace()

const open = ref(false)
const creating = ref(false)
const createError = ref<unknown>(null)
const categories = ref<MeetingCategory[]>(loadCategories())

/** 打开创建会议窗口（每次打开刷新文件夹清单） */
function openDialog(): void {
  categories.value = loadCategories()
  createError.value = null
  open.value = true
}

function close(): void {
  open.value = false
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
    // 未选择分类 → 归入「未分类」；分类是可选项，创建的始终是会议，不自动建分类
    const categoryId = payload.categoryId || null
    assignCategory(created.meeting_id, categoryId)
    // 本地同步：有分类建 <分类>/<会议>/，无分类建 <会议>/（未连接本地文件夹时静默跳过）
    void ws.createMeetingLocal(created.meeting_id, created.title, categoryId)
    open.value = false
    toast.success('会议已创建')
    await router.push({
      name: ROUTE_NAMES.newMeeting,
      query: { meetingId: created.meeting_id },
    })
  } catch (caught) {
    createError.value = caught
  } finally {
    creating.value = false
  }
}

defineExpose({ open: openDialog })
</script>
