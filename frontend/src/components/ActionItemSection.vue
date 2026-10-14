<template>
  <div class="action-section">
    <div class="action-section__toolbar">
      <AppButton :loading="extracting" @click="extract">提取行动项</AppButton>
    </div>

    <ErrorMessage v-if="actionError" :error="actionError" />

    <LoadingSpinner v-if="loading && items.length === 0" class="action-section__state" />

    <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />

    <EmptyState
      v-else-if="items.length === 0"
      title="还没有行动项"
      description="从会议记录中提取候选行动项，确认后可转为个人任务。"
    />

    <template v-else>
      <ul class="action-section__list">
        <li v-for="item in items" :key="item.action_id" class="action-item">
          <div class="action-item__head">
            <span class="action-item__content">{{ item.content }}</span>
            <StatusBadge :label="statusOf(item).label" :tone="statusOf(item).tone" />
          </div>

          <div v-if="item.assignee || item.due_date" class="action-item__meta">
            <AppTag v-if="item.assignee" :label="item.assignee" />
            <span v-if="item.due_date" class="action-item__due">截止 {{ dueOf(item) }}</span>
          </div>

          <SourceRef
            v-if="item.source.excerpt"
            :excerpt="item.source.excerpt"
            :reference="item.source.record_id ?? ''"
          />

          <div class="action-item__actions">
            <AppButton
              v-if="item.status === 'pending_confirmation'"
              :loading="busyId === item.action_id"
              @click="confirmItem(item.action_id)"
            >
              确认
            </AppButton>
            <AppButton
              v-if="item.status === 'confirmed'"
              :loading="busyId === item.action_id"
              @click="openConvert(item)"
            >
              转任务
            </AppButton>
            <span v-if="item.status === 'converted'" class="action-item__done">已转任务</span>
          </div>
        </li>
      </ul>

      <AppPagination
        v-if="pagination.total_pages > 1"
        class="action-section__pagination"
        :page="pagination.page"
        :page-size="pagination.page_size"
        :total="pagination.total"
        @update:page="load"
      />
    </template>

    <AppModal :open="convertTarget !== null" title="转为个人任务" @close="closeConvert">
      <form class="action-section__convert" @submit.prevent="submitConvert">
        <FormField
          id="convert-title"
          v-model="convertTitle"
          label="任务标题"
          required
          :error="convertFormError"
        />
        <FormField id="convert-due" v-model="convertDue" label="截止日期" type="date" />
        <ErrorMessage v-if="convertError" :error="convertError" />
        <div class="action-section__convert-actions">
          <AppButton variant="ghost" :disabled="converting" @click="closeConvert">取消</AppButton>
          <AppButton type="submit" :loading="converting">确定</AppButton>
        </div>
      </form>
    </AppModal>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as actionItemsApi from '@/api/actionItems'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import AppPagination from '@/components/AppPagination.vue'
import AppTag from '@/components/AppTag.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import SourceRef from '@/components/SourceRef.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import type { ActionItem } from '@/types/actionItem'
import { formatDate } from '@/utils/datetime'
import { actionItemStatusMeta } from '@/utils/statusLabels'

const props = defineProps<{ meetingId: string }>()

const { items, pagination, loading, error, load } = useAsyncList<ActionItem>({
  fetcher: ({ page, page_size }) =>
    actionItemsApi.listActionItems(props.meetingId, { page, page_size }),
})

const extracting = ref(false)
const busyId = ref<string | null>(null)
const actionError = ref<unknown>(null)

const convertTarget = ref<ActionItem | null>(null)
const convertTitle = ref('')
const convertDue = ref('')
const convertFormError = ref('')
const convertError = ref<unknown>(null)
const converting = ref(false)

function statusOf(item: ActionItem) {
  return actionItemStatusMeta[item.status]
}

function dueOf(item: ActionItem): string {
  return formatDate(item.due_date)
}

function refresh(): Promise<void> {
  return load()
}

onMounted(() => {
  void refresh()
})

async function extract(): Promise<void> {
  extracting.value = true
  actionError.value = null
  try {
    await actionItemsApi.extractActionItems(props.meetingId, { record_ids: [] })
    await load(1)
  } catch (caught) {
    actionError.value = caught
  } finally {
    extracting.value = false
  }
}

async function confirmItem(actionId: string): Promise<void> {
  busyId.value = actionId
  actionError.value = null
  try {
    await actionItemsApi.confirmActionItem(actionId)
    await load()
  } catch (caught) {
    actionError.value = caught
  } finally {
    busyId.value = null
  }
}

function openConvert(item: ActionItem): void {
  convertTarget.value = item
  convertTitle.value = item.content
  convertDue.value = item.due_date ?? ''
  convertFormError.value = ''
  convertError.value = null
}

function closeConvert(): void {
  convertTarget.value = null
}

async function submitConvert(): Promise<void> {
  if (!convertTarget.value) {
    return
  }
  const title = convertTitle.value.trim()
  if (!title) {
    convertFormError.value = '请输入任务标题'
    return
  }
  convertFormError.value = ''
  converting.value = true
  convertError.value = null
  try {
    await actionItemsApi.convertActionItemToTask(convertTarget.value.action_id, {
      title,
      due_date: convertDue.value || undefined,
    })
    convertTarget.value = null
    await load()
  } catch (caught) {
    convertError.value = caught
  } finally {
    converting.value = false
  }
}
</script>

<style scoped>
.action-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.action-section__toolbar {
  display: flex;
  gap: var(--space-2);
}

.action-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.action-section__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.action-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.action-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.action-item__content {
  font-weight: 500;
  overflow-wrap: anywhere;
}

.action-item__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.action-item__due {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.action-item__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.action-item__done {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.action-section__pagination {
  margin-top: var(--space-2);
}

.action-section__convert {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.action-section__convert-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
