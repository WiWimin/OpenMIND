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
    } else {
      await ws.createDefaultMeetingFolder(created.title)
    }
    toast.success('会议已创建')
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
</style>
