<template>
  <div class="issues-section">
    <div class="issues-section__toolbar">
      <AppButton :loading="extracting" @click="extract">提取问题</AppButton>
    </div>

    <ErrorMessage v-if="actionError" :error="actionError" />

    <LoadingSpinner v-if="loading && items.length === 0" class="issues-section__state" />

    <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />

    <EmptyState
      v-else-if="items.length === 0"
      title="还没有未解决问题"
      description="从会议记录中提取待跟进问题，并维护其状态与跟进信息。"
    />

    <template v-else>
      <ul class="issues-section__list">
        <li v-for="issue in items" :key="issue.issue_id" class="issue-item">
          <div class="issue-item__head">
            <span class="issue-item__description">{{ issue.description }}</span>
            <StatusBadge :label="statusOf(issue).label" :tone="statusOf(issue).tone" />
          </div>

          <AppTag v-if="issue.source.record_id" :label="`来源 ${issue.source.record_id}`" />

          <template v-if="editingId === issue.issue_id">
            <FormSelect
              id="issue-status"
              v-model="draftStatus"
              label="状态"
              :options="statusOptions"
            />
            <FormTextarea id="issue-follow-up" v-model="draftFollowUp" label="跟进" :rows="2" />
            <div class="issue-item__actions">
              <AppButton variant="ghost" :disabled="busyId === issue.issue_id" @click="cancelEdit">
                取消
              </AppButton>
              <AppButton :loading="busyId === issue.issue_id" @click="save(issue.issue_id)">
                保存
              </AppButton>
            </div>
          </template>

          <template v-else>
            <p v-if="issue.follow_up" class="issue-item__follow">跟进：{{ issue.follow_up }}</p>
            <div class="issue-item__actions">
              <AppButton variant="ghost" @click="startEdit(issue)">编辑</AppButton>
            </div>
          </template>
        </li>
      </ul>

      <AppPagination
        v-if="pagination.total_pages > 1"
        class="issues-section__pagination"
        :page="pagination.page"
        :page-size="pagination.page_size"
        :total="pagination.total"
        @update:page="load"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as issuesApi from '@/api/issues'
import AppButton from '@/components/AppButton.vue'
import AppPagination from '@/components/AppPagination.vue'
import AppTag from '@/components/AppTag.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormSelect from '@/components/FormSelect.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import type { IssueStatus, OpenIssue } from '@/types/issue'
import type { SelectOption } from '@/types/ui'
import { issueStatusMeta } from '@/utils/statusLabels'

const props = defineProps<{ meetingId: string }>()

const { items, pagination, loading, error, load } = useAsyncList<OpenIssue>({
  fetcher: ({ page, page_size }) => issuesApi.listIssues(props.meetingId, { page, page_size }),
})

const statusOptions: SelectOption[] = [
  { value: 'open', label: '待处理' },
  { value: 'resolved', label: '已解决' },
  { value: 'cancelled', label: '已取消' },
]

const extracting = ref(false)
const busyId = ref<string | null>(null)
const actionError = ref<unknown>(null)

const editingId = ref<string | null>(null)
const draftStatus = ref<IssueStatus>('open')
const draftFollowUp = ref('')

function statusOf(issue: OpenIssue) {
  return issueStatusMeta[issue.status]
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
    await issuesApi.extractIssues(props.meetingId, { record_ids: [] })
    await load(1)
  } catch (caught) {
    actionError.value = caught
  } finally {
    extracting.value = false
  }
}

function startEdit(issue: OpenIssue): void {
  editingId.value = issue.issue_id
  draftStatus.value = issue.status
  draftFollowUp.value = issue.follow_up ?? ''
}

function cancelEdit(): void {
  editingId.value = null
}

async function save(issueId: string): Promise<void> {
  busyId.value = issueId
  actionError.value = null
  try {
    await issuesApi.updateIssue(issueId, {
      status: draftStatus.value,
      follow_up: draftFollowUp.value,
    })
    editingId.value = null
    await load()
  } catch (caught) {
    actionError.value = caught
  } finally {
    busyId.value = null
  }
}
</script>

<style scoped>
.issues-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.issues-section__toolbar {
  display: flex;
  gap: var(--space-2);
}

.issues-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.issues-section__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.issue-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.issue-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.issue-item__description {
  font-weight: 500;
  overflow-wrap: anywhere;
}

.issue-item__follow {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
}

.issue-item__actions {
  display: flex;
  gap: var(--space-2);
}

.issues-section__pagination {
  margin-top: var(--space-2);
}
</style>
