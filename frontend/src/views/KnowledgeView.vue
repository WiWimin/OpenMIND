<template>
  <section class="knowledge-view">
    <PageHeader
      title="个人知识库"
      description="导入长期资料，解析并建立向量索引，按问题检索相关片段。"
    />

    <div class="knowledge-view__grid">
      <section class="knowledge-panel">
        <h2 class="knowledge-panel__title">添加资料</h2>
        <KnowledgeUploader :uploading="uploading" @upload="upload" />
        <ErrorMessage v-if="uploadError" :error="uploadError" />
      </section>

      <section class="knowledge-panel">
        <h2 class="knowledge-panel__title">检索知识库</h2>
        <form class="knowledge-search" @submit.prevent="search">
          <FormField
            id="knowledge-query"
            v-model="query"
            label="检索内容"
            placeholder="例如：项目上线检查项"
          />
          <AppButton type="submit" :loading="searching">检索</AppButton>
        </form>
        <ErrorMessage v-if="searchError" :error="searchError" />
        <LoadingSpinner v-if="searching" class="knowledge-view__state" />
        <EmptyState
          v-else-if="searched && hits.length === 0"
          title="没有检索到相关内容"
          description="换个问法，或先上传资料建立索引。"
        />
        <ul v-else-if="hits.length" class="knowledge-hits">
          <li v-for="hit in hits" :key="`${hit.document_id}-${hit.excerpt}`" class="knowledge-hit">
            <div class="knowledge-hit__head">
              <strong>{{ hit.file_name }}</strong>
              <span>相似度 {{ hit.score.toFixed(2) }}</span>
            </div>
            <p>{{ hit.excerpt }}</p>
          </li>
        </ul>
      </section>
    </div>

    <section class="knowledge-panel">
      <div class="knowledge-panel__head">
        <h2 class="knowledge-panel__title">我的资料</h2>
        <span class="knowledge-panel__count">共 {{ pagination.total }} 份</span>
      </div>

      <LoadingSpinner v-if="loading && items.length === 0" class="knowledge-view__state" />
      <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />
      <EmptyState
        v-else-if="items.length === 0"
        title="知识库还是空的"
        description="上传 PDF、Word 或 TXT，建立可检索的个人资料库。"
      />
      <template v-else>
        <ul class="knowledge-docs">
          <li v-for="document in items" :key="document.document_id" class="knowledge-doc">
            <div class="knowledge-doc__main">
              <strong>{{ document.file_name }}</strong>
              <span>{{ document.type.toUpperCase() }} · {{ timeOf(document) }}</span>
              <span
                class="knowledge-doc__status"
                :class="`knowledge-doc__status--${statusOf(document).tone}`"
              >
                {{ statusOf(document).label }}
              </span>
              <span v-if="document.parse_error" class="knowledge-doc__error">
                {{ document.parse_error }}
              </span>
            </div>
            <AppButton variant="ghost" @click="askDelete(document.document_id)">删除</AppButton>
          </li>
        </ul>
        <AppPagination
          v-if="pagination.total_pages > 1"
          class="knowledge-view__pagination"
          :page="pagination.page"
          :page-size="pagination.page_size"
          :total="pagination.total"
          @update:page="load"
        />
      </template>
    </section>

    <ErrorMessage v-if="actionError" :error="actionError" />

    <ConfirmDialog
      :open="showDelete"
      title="删除知识库资料"
      message="删除后文档、分块和向量索引将不可恢复，确定删除吗？"
      confirm-text="删除"
      danger
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as knowledgeApi from '@/api/knowledge'
import AppButton from '@/components/AppButton.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import KnowledgeUploader from '@/components/KnowledgeUploader.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import type { KnowledgeDocument, KnowledgeSearchHit } from '@/types/knowledge'
import { formatDateTime } from '@/utils/datetime'
import { knowledgeStatusMeta } from '@/utils/statusLabels'

const toast = useToast()

const { items, pagination, loading, error, load } = useAsyncList<KnowledgeDocument>({
  fetcher: ({ page, page_size }) => knowledgeApi.listDocuments({ page, page_size }),
})

const uploading = ref(false)
const uploadError = ref<unknown>(null)
const query = ref('')
const searching = ref(false)
const searched = ref(false)
const searchError = ref<unknown>(null)
const hits = ref<KnowledgeSearchHit[]>([])
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

function statusOf(document: KnowledgeDocument) {
  return knowledgeStatusMeta[document.processing_status]
}

function timeOf(document: KnowledgeDocument): string {
  return formatDateTime(document.created_at)
}

async function upload(file: File): Promise<void> {
  uploading.value = true
  uploadError.value = null
  try {
    const document = await knowledgeApi.uploadDocument(file)
    await load(1)
    if (document.processing_status === 'failed') {
      uploadError.value = {
        status: 'error',
        error_code: 'FILE_PARSE_FAILED',
        message: document.parse_error ?? '文件解析失败',
        retryable: false,
      }
      return
    }
    toast.success('资料已加入知识库')
  } catch (caught) {
    uploadError.value = caught
  } finally {
    uploading.value = false
  }
}

async function search(): Promise<void> {
  const text = query.value.trim()
  if (!text) {
    searchError.value = {
      status: 'error',
      error_code: 'VALIDATION_ERROR',
      message: '请输入检索内容',
      retryable: false,
    }
    return
  }
  searching.value = true
  searched.value = true
  searchError.value = null
  try {
    const result = await knowledgeApi.searchKnowledge({ query: text })
    hits.value = result.items
  } catch (caught) {
    searchError.value = caught
    hits.value = []
  } finally {
    searching.value = false
  }
}

function askDelete(documentId: string): void {
  pendingDeleteId.value = documentId
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
    await knowledgeApi.deleteDocument(pendingDeleteId.value)
    showDelete.value = false
    await load()
    toast.success('资料已删除')
  } catch (caught) {
    actionError.value = caught
  } finally {
    deleting.value = false
    pendingDeleteId.value = null
  }
}
</script>

<style scoped>
.knowledge-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.knowledge-view__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
  gap: var(--space-4);
}

.knowledge-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.knowledge-panel__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.knowledge-panel__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.knowledge-panel__count {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.knowledge-search {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
}

.knowledge-search :deep(.form-field) {
  flex: 1;
}

.knowledge-view__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.knowledge-hits,
.knowledge-docs {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.knowledge-hit {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border-radius: var(--radius-md);
}

.knowledge-hit__head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.knowledge-hit p {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.knowledge-doc {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.knowledge-doc__main {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.knowledge-doc__main > span {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.knowledge-doc__status--success {
  color: var(--color-ok);
}

.knowledge-doc__status--danger {
  color: var(--color-down);
}

.knowledge-doc__status--info {
  color: var(--color-primary-strong);
}

.knowledge-doc__error {
  width: 100%;
  color: var(--color-down) !important;
}

.knowledge-view__pagination {
  margin-top: var(--space-2);
}
</style>
