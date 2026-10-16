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
      <div class="record-section__add-actions">
        <AppButton type="submit" :loading="adding">保存记录</AppButton>
        <AppButton variant="ghost" @click="toggleImport">
          {{ importOpen ? '收起导入' : '导入转写文本' }}
        </AppButton>
      </div>
    </form>

    <form v-if="importOpen" class="record-section__import" @submit.prevent="importText">
      <FormTextarea
        id="record-import-content"
        v-model="importContent"
        label="粘贴录音转写稿或外部文本"
        :rows="8"
        :error="importError"
      />
      <FormSelect
        id="record-import-type"
        v-model="importType"
        label="记录类型"
        :options="importTypeOptions"
      />
      <div class="record-section__add-actions">
        <AppButton type="submit" :loading="importing">导入</AppButton>
        <AppButton variant="ghost" type="button" @click="toggleImport">取消</AppButton>
      </div>
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
      <div class="record-section__organize">
        <AppButton :disabled="selectedIds.length === 0" :loading="organizing" @click="organize">
          AI 整理所选（{{ selectedIds.length }}）
        </AppButton>
        <p class="record-section__organize-hint">
          勾选讨论记录后，AI 会整理出议题、观点、待确认事项与当前进展，结果可修改后另存为记录。
        </p>
      </div>
      <ErrorMessage v-if="organizeError" :error="organizeError" />

      <ul class="record-section__list">
        <li v-for="record in items" :key="record.record_id" class="record-section__row">
          <input
            v-model="selectedIds"
            type="checkbox"
            class="record-section__checkbox"
            :value="record.record_id"
            :aria-label="`选择记录 ${record.record_id}`"
          />
          <RecordItem
            class="record-section__item"
            :record="record"
            @save="(content) => saveEdit(record.record_id, content)"
            @delete="askDelete(record.record_id)"
          />
        </li>
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

    <div v-if="organizedVisible" class="record-section__result">
      <header class="record-section__result-head">
        <h3 class="record-section__result-title">AI 整理结果</h3>
        <AppButton variant="ghost" @click="clearOrganized">关闭</AppButton>
      </header>
      <FormTextarea
        id="record-organized-content"
        v-model="organizedDraft"
        label="整理内容"
        :rows="10"
      />
      <div class="record-section__result-actions">
        <AppButton :loading="savingOrganized" @click="saveOrganized">另存为记录</AppButton>
      </div>
    </div>

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

import { organizeRecords } from '@/api/chat'
import * as recordsApi from '@/api/records'
import AppButton from '@/components/AppButton.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormSelect from '@/components/FormSelect.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import RecordItem from '@/components/RecordItem.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import type { MeetingRecord } from '@/types/record'

const props = defineProps<{ meetingId: string }>()

const toast = useToast()

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

const selectedIds = ref<string[]>([])
const organizing = ref(false)
const organizeError = ref<unknown>(null)
const organizedVisible = ref(false)
const organizedDraft = ref('')
const savingOrganized = ref(false)

const importOpen = ref(false)
const importContent = ref('')
const importType = ref<string>('transcript')
const importError = ref('')
const importing = ref(false)

const importTypeOptions: { label: string; value: string }[] = [
  { label: '转写（录音转写稿）', value: 'transcript' },
  { label: '导入（外部文本）', value: 'imported' },
]

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
    toast.success('记录已保存')
  } catch (caught) {
    actionError.value = caught
  } finally {
    adding.value = false
  }
}

function toggleImport(): void {
  importOpen.value = !importOpen.value
  importContent.value = ''
  importError.value = ''
}

async function importText(): Promise<void> {
  const content = importContent.value.trim()
  if (!content) {
    importError.value = '导入内容不能为空'
    return
  }
  importError.value = ''
  importing.value = true
  actionError.value = null
  try {
    await recordsApi.createRecord(props.meetingId, {
      content,
      record_type: importType.value === 'imported' ? 'imported' : 'transcript',
    })
    importOpen.value = false
    importContent.value = ''
    await load(1)
    toast.success('文本已导入为记录')
  } catch (caught) {
    actionError.value = caught
  } finally {
    importing.value = false
  }
}

async function saveEdit(recordId: string, content: string): Promise<void> {
  actionError.value = null
  try {
    await recordsApi.updateRecord(recordId, { content })
    await load()
    toast.success('记录已更新')
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
    toast.success('记录已删除')
  } catch (caught) {
    actionError.value = caught
  } finally {
    deleting.value = false
    pendingDeleteId.value = null
  }
}

async function organize(): Promise<void> {
  if (selectedIds.value.length === 0) {
    return
  }
  organizing.value = true
  organizeError.value = null
  try {
    const result = await organizeRecords(props.meetingId, {
      record_ids: selectedIds.value,
    })
    organizedDraft.value = result.organized_content
    organizedVisible.value = true
  } catch (caught) {
    organizeError.value = caught
  } finally {
    organizing.value = false
  }
}

function clearOrganized(): void {
  organizedVisible.value = false
  organizedDraft.value = ''
}

async function saveOrganized(): Promise<void> {
  const content = organizedDraft.value.trim()
  if (!content) {
    toast.error('整理内容不能为空')
    return
  }
  savingOrganized.value = true
  organizeError.value = null
  try {
    await recordsApi.createRecord(props.meetingId, { content, record_type: 'manual' })
    clearOrganized()
    await load(1)
    toast.success('整理结果已另存为记录')
  } catch (caught) {
    organizeError.value = caught
  } finally {
    savingOrganized.value = false
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

.record-section__add-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.record-section__import {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid rgba(59, 111, 212, 0.28);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.record-section__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.record-section__organize {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.record-section__organize-hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.record-section__row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
}

.record-section__checkbox {
  margin-top: var(--space-3);
  flex: 0 0 auto;
  width: 1rem;
  height: 1rem;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.record-section__item {
  flex: 1;
  min-width: 0;
}

.record-section__result {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid rgba(59, 111, 212, 0.28);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.record-section__result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.record-section__result-title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 700;
  color: var(--color-primary-strong);
}

.record-section__result-actions {
  display: flex;
  gap: var(--space-2);
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
