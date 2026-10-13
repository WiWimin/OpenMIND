<template>
  <section class="meetings">
    <PageHeader title="会议" description="查看与管理你的会议">
      <template #actions>
        <AppButton @click="openCreate">新建会议</AppButton>
      </template>
    </PageHeader>

    <div class="meetings__toolbar">
      <FormSelect
        id="meeting-status-filter"
        label="状态"
        :model-value="store.filters.status"
        :options="statusOptions"
        @update:model-value="onFilterChange"
      />
    </div>

    <LoadingSpinner v-if="store.loading && store.items.length === 0" class="meetings__state" />

    <ErrorMessage v-else-if="store.error" :error="store.error" retryable @retry="store.fetchList()" />

    <EmptyState
      v-else-if="store.items.length === 0"
      title="还没有会议"
      description="创建一个会议，开始会前准备、会中记录与会后整理。"
    >
      <AppButton @click="openCreate">新建会议</AppButton>
    </EmptyState>

    <template v-else>
      <MeetingList :items="store.items" @select="openDetail" />
      <AppPagination
        class="meetings__pagination"
        :page="store.pagination.page"
        :page-size="store.pagination.page_size"
        :total="store.pagination.total"
        @update:page="store.setPage"
      />
    </template>

    <MeetingFormDialog
      :open="showForm"
      :loading="saving"
      :error="saveError"
      @submit="createMeeting"
      @cancel="closeForm"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import AppPagination from '@/components/AppPagination.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormSelect from '@/components/FormSelect.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MeetingFormDialog from '@/components/MeetingFormDialog.vue'
import MeetingList from '@/components/MeetingList.vue'
import PageHeader from '@/components/PageHeader.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useMeetingsStore, type MeetingStatusFilter } from '@/stores/meetings'
import type { CreateMeetingPayload } from '@/types/meeting'
import type { SelectOption } from '@/types/ui'

const store = useMeetingsStore()
const router = useRouter()

const showForm = ref(false)
const saving = ref(false)
const saveError = ref<unknown>(null)

const statusOptions: SelectOption[] = [
  { value: '', label: '全部' },
  { value: 'scheduled', label: '已安排' },
  { value: 'archived', label: '已归档' },
]

onMounted(() => {
  void store.fetchList()
})

function openCreate(): void {
  saveError.value = null
  showForm.value = true
}

function closeForm(): void {
  showForm.value = false
}

function onFilterChange(value: string): void {
  void store.setStatusFilter(value as MeetingStatusFilter)
}

function openDetail(meetingId: string): void {
  void router.push({ name: ROUTE_NAMES.meetingDetail, params: { meetingId } })
}

async function createMeeting(payload: CreateMeetingPayload): Promise<void> {
  saving.value = true
  saveError.value = null
  try {
    await store.createMeeting(payload)
    showForm.value = false
  } catch (caught) {
    saveError.value = caught
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.meetings__toolbar {
  margin-bottom: var(--space-4);
  max-width: 12rem;
}

.meetings__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

.meetings__pagination {
  margin-top: var(--space-4);
}
</style>
