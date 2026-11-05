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
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import {
  assignCategory,
  createCategory,
  loadCategories,
  type MeetingCategory,
} from '@/utils/meetingCategories'

const router = useRouter()
const toast = useToast()

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
    // 未选择文件夹 → 在会议管理以会议名为名建文件夹（同名已存在则复用）并归入
    let categoryId = payload.categoryId
    if (!categoryId) {
      const existing = categories.value.find((item) => item.name === created.title)
      categoryId = (existing ?? createCategory(created.title)).id
      categories.value = loadCategories()
    }
    assignCategory(created.meeting_id, categoryId)
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
