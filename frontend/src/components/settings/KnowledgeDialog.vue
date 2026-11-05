<template>
  <AppModal :open="open" title="知识库" @close="emit('close')">
    <div class="knowledge-dialog">
      <!-- 工具栏：上传 + 查找（点击上传直接打开文件选择；输入即查找） -->
      <div class="knowledge-toolbar">
        <AppButton :loading="uploading" @click="chooseFile">上传资料</AppButton>
        <div class="knowledge-search">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" stroke="currentColor" stroke-width="1.6" />
            <path
              d="m16 16 4.5 4.5"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
            />
          </svg>
          <input
            v-model="query"
            class="knowledge-search__input"
            type="search"
            placeholder="输入关键词查找资料"
            aria-label="查找资料"
            autocomplete="off"
          />
        </div>
        <input
          id="knowledge-file"
          ref="fileInputEl"
          type="file"
          accept=".pdf,.docx,.txt"
          hidden
          @change="onFileChosen"
        />
      </div>

      <ErrorMessage v-if="uploadError" :error="uploadError" />
      <ErrorMessage v-if="actionError" :error="actionError" />

      <!-- 检索结果（输入查询后出现在文件列表上方） -->
      <section v-if="searched || searching" class="knowledge-panel">
        <h3 class="list-head__title">检索结果</h3>
        <ErrorMessage v-if="searchError" :error="searchError" retryable @retry="runSearch" />
        <LoadingSpinner v-if="searching" class="knowledge-panel__state" />
        <p v-else-if="hits.length === 0" class="knowledge-panel__empty">
          没有检索到相关内容，换个关键词试试。
        </p>
        <ul v-else class="hit-list">
          <li v-for="(hit, index) in hits" :key="`${hit.document_id}-${index}`" class="hit-item">
            <header class="hit-item__head">
              <strong>{{ index + 1 }}. {{ hit.file_name }}</strong>
              <span class="hit-item__score">
                <span class="hit-item__score-value">{{ hit.score.toFixed(3) }}</span>
                <span class="hit-item__score-bar" aria-hidden="true">
                  <span :style="{ width: `${Math.min(hit.score, 1) * 100}%` }" />
                </span>
              </span>
            </header>
            <p class="hit-item__excerpt">{{ hit.excerpt }}</p>
          </li>
        </ul>
      </section>

      <!-- 文件列表（常驻） -->
      <section class="knowledge-panel knowledge-list">
        <div class="list-head">
          <h3 class="list-head__title">已上传文件</h3>
          <span class="list-head__count">共 {{ pagination.total }} 份</span>
        </div>

        <LoadingSpinner v-if="loading && items.length === 0" class="knowledge-panel__state" />
        <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />
        <p v-else-if="items.length === 0" class="knowledge-panel__empty">
          知识库还是空的，点击上方「上传资料」添加第一份文件。
        </p>
        <template v-else>
          <ul class="doc-list">
            <li v-for="document in items" :key="document.document_id" class="doc-item">
              <span class="doc-item__icon" aria-hidden="true"><NavIcon name="file" :size="16" /></span>
              <div class="doc-item__main">
                <strong class="doc-item__name">{{ document.file_name }}</strong>
                <span class="doc-item__meta">
                  {{ document.type.toUpperCase() }} · {{ formatDateTime(document.created_at) }}
                </span>
              </div>
              <StatusBadge :label="statusOf(document).label" :tone="statusOf(document).tone" />
              <button
                type="button"
                class="doc-item__delete"
                title="删除该文档"
                @click="askDelete(document.document_id)"
              >
                删除
              </button>
            </li>
          </ul>
          <AppPagination
            v-if="pagination.total_pages > 1"
            class="doc-list__pagination"
            :page="pagination.page"
            :page-size="pagination.page_size"
            :total="pagination.total"
            @update:page="load"
          />
        </template>
      </section>
    </div>

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
  </AppModal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

import * as knowledgeApi from '@/api/knowledge'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import AppPagination from '@/components/AppPagination.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import NavIcon from '@/components/NavIcon.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import type { KnowledgeDocument, KnowledgeSearchHit } from '@/types/knowledge'
import { formatDateTime } from '@/utils/datetime'
import { validateMaterialFile } from '@/utils/materialUpload'
import { knowledgeStatusMeta } from '@/utils/statusLabels'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const toast = useToast()

const { items, pagination, loading, error, load } = useAsyncList<KnowledgeDocument>({
  fetcher: ({ page, page_size }) => knowledgeApi.listDocuments({ page, page_size }),
})

const fileInputEl = ref<HTMLInputElement | null>(null)
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
const SEARCH_DEBOUNCE_MS = 400
let searchTimer: ReturnType<typeof setTimeout> | undefined

function refresh(): Promise<void> {
  return load()
}

function statusOf(document: KnowledgeDocument) {
  return knowledgeStatusMeta[document.processing_status]
}

function chooseFile(): void {
  fileInputEl.value?.click()
}

async function onFileChosen(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  input.value = ''
  if (!file) {
    return
  }
  const message = validateMaterialFile(file)
  if (message) {
    uploadError.value = {
      status: 'error',
      error_code: 'FILE_TYPE_NOT_SUPPORTED',
      message,
      retryable: false,
    }
    return
  }
  await upload(file)
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

async function runSearch(): Promise<void> {
  const text = query.value.trim()
  if (!text) {
    searched.value = false
    hits.value = []
    searchError.value = null
    return
  }
  searching.value = true
  searched.value = true
  searchError.value = null
  try {
    const result = await knowledgeApi.searchKnowledge({
      query: text,
      top_k: 5,
    })
    hits.value = result.items
  } catch (caught) {
    hits.value = []
    searchError.value = caught
  } finally {
    searching.value = false
  }
}

// 输入即查找：停顿 400ms 后自动检索，清空输入则收起结果
watch(query, (value) => {
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  if (!value.trim()) {
    searched.value = false
    hits.value = []
    searchError.value = null
    return
  }
  searchTimer = setTimeout(() => {
    void runSearch()
  }, SEARCH_DEBOUNCE_MS)
})

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
    pendingDeleteId.value = null
    await load()
    toast.success('知识库资料已删除')
  } catch (caught) {
    actionError.value = caught
  } finally {
    deleting.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      query.value = ''
      searched.value = false
      hits.value = []
      searchError.value = null
      uploadError.value = null
      void refresh()
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.knowledge-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-height: 62vh;
}

/* 工具栏 */
.knowledge-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.knowledge-search {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 6px;
  min-width: 0;
  min-height: 2.4rem;
  padding: 0 var(--space-3);
  color: var(--color-muted-foreground);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.knowledge-search:focus-within {
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.knowledge-search__input {
  flex: 1;
  min-width: 0;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.875rem;
  background: transparent;
  border: 0;
}

.knowledge-search__input:focus {
  outline: none;
}

/* 面板 */
.knowledge-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
}

.knowledge-panel__state {
  display: flex;
  justify-content: center;
  padding: var(--space-3);
}

.knowledge-panel__empty {
  margin: 0;
  padding: var(--space-2) 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.hit-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.hit-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.hit-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: 0.8125rem;
}

.hit-item__score {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  flex: 0 0 auto;
}

.hit-item__score-value {
  color: var(--color-accent-strong);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.hit-item__score-bar {
  display: inline-block;
  width: 4rem;
  height: 4px;
  overflow: hidden;
  background: var(--color-surface-muted);
  border-radius: var(--radius-pill);
}

.hit-item__score-bar span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--color-accent), var(--color-primary));
  border-radius: inherit;
}

.hit-item__excerpt {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.75rem;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* 列表 */
.knowledge-list {
  background: var(--color-surface);
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.list-head__title {
  margin: 0;
  font-size: 0.8125rem;
  font-weight: 650;
}

.list-head__count {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.doc-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.doc-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.doc-item__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.9rem;
  height: 1.9rem;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
}

.doc-item__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  min-width: 0;
}

.doc-item__name {
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-item__meta {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.doc-item__delete {
  flex: 0 0 auto;
  padding: 3px 8px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.6875rem;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.doc-item__delete:hover {
  color: var(--color-down);
}

.doc-list__pagination {
  margin-top: var(--space-1);
}
</style>
