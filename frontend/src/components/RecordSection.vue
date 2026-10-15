<template>
  <div class="record-section">
    <form class="record-section__add" @submit.prevent="add">
      <FormTextarea
        id="record-content"
        v-model="newContent"
        label="新增记录"
        :rows="3"
        :error="formError"
      />
      <AppButton type="submit" :loading="adding">保存记录</AppButton>
    </form>

    <ErrorMessage v-if="actionError" :error="actionError" />

    <LoadingSpinner v-if="loading && items.length === 0" class="record-section__state" />

    <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />

    <EmptyState
      v-else-if="items.length === 0"
      title="还没有记录"
      description="在会议过程中添加文字记录，供纪要与行动项提取使用。"
    />

    <template v-else>
      <ul class="record-section__list">
        <RecordItem
          v-for="record in items"
          :key="record.record_id"
          :record="record"
          @save="(content) => saveEdit(record.record_id, content)"
          @delete="askDelete(record.record_id)"
        />
      </ul>
      <AppPagination
        v-if="pagination.total_pages > 1"
        class="record-section__pagination"
        :page="pagination.page"
        :page-size="pagination.page_size"
        :total="pagination.total"
        @update:page="load"
      />
    </template>

    <ConfirmDialog
      :open="showDelete"
      title="删除记录"
      message="删除后该记录不可恢复，确定删除吗？"
      confirm-text="删除"
      danger
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as recordsApi from '@/api/records'
import AppButton from '@/components/AppButton.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import RecordItem from '@/components/RecordItem.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import type { MeetingRecord } from '@/types/record'

const props = defineProps<{ meetingId: string }>()

const { items, pagination, loading, error, load } = useAsyncList<MeetingRecord>({
  fetcher: ({ page, page_size }) => recordsApi.listRecords(props.meetingId, { page, page_size }),
})

const newContent = ref('')
const formError = ref('')
const adding = ref(false)
const actionError = ref<unknown>(null)
const showDelete = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref<string | null>(null)

function refresh(): Promise<void> {
  return load()
}

onMounted(() => {
  void refresh()
})

async function add(): Promise<void> {
  const content = newContent.value.trim()
  if (!content) {
    formError.value = '记录内容不能为空'
    return
  }
  formError.value = ''
  adding.value = true
  actionError.value = null
  try {
    await recordsApi.createRecord(props.meetingId, { content, record_type: 'manual' })
    newContent.value = ''
    await load(1)
  } catch (caught) {
    actionError.value = caught
  } finally {
    adding.value = false
  }
}

async function saveEdit(recordId: string, content: string): Promise<void> {
  actionError.value = null
  try {
    await recordsApi.updateRecord(recordId, { content })
    await load()
  } catch (caught) {
    actionError.value = caught
  }
}

function askDelete(recordId: string): void {
  pendingDeleteId.value = recordId
  showDelete.value = true
}

function cancelDelete(): void {
  showDelete.value = false
  pendingDeleteId.value = null
}

async function confirmDelete(): Promise<void> {
  if (!pendingDeleteId.value) {
    return
  }
  deleting.value = true
  actionError.value = null
  try {
    await recordsApi.deleteRecord(pendingDeleteId.value)
    showDelete.value = false
    await load()
  } catch (caught) {
    actionError.value = caught
  } finally {
    deleting.value = false
    pendingDeleteId.value = null
  }
}
</script>

<style scoped>
.record-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.record-section__add {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  align-items: flex-start;
}

.record-section__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.record-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.record-section__pagination {
  margin-top: var(--space-2);
}
</style>
