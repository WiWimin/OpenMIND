<template>
  <AppModal :open="open" title="知识库" @close="emit('close')">
    <div class="knowledge-dialog">
      <!-- 图标气泡框 -->
      <div class="knowledge-bubbles">
        <button
          type="button"
          class="knowledge-bubble"
          :class="{ 'knowledge-bubble--active': uploadOpen }"
          :aria-expanded="uploadOpen"
          @click="togglePanel('upload')"
        >
          <span class="knowledge-bubble__icon knowledge-bubble__icon--primary" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="19" height="19" fill="none">
              <path
                d="M12 16V4m0 0 4 4m-4-4-4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                stroke="currentColor"
                stroke-width="1.7"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </span>
          <span class="knowledge-bubble__body">
            <strong>上传资料</strong>
            <span>PDF · Word · TXT</span>
          </span>
        </button>

        <button
          type="button"
          class="knowledge-bubble"
          :class="{ 'knowledge-bubble--active': searchOpen }"
          :aria-expanded="searchOpen"
          @click="togglePanel('search')"
        >
          <span class="knowledge-bubble__icon knowledge-bubble__icon--accent" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="19" height="19" fill="none">
              <path
                d="M10.8 17.6a6.8 6.8 0 1 0 0-13.6 6.8 6.8 0 0 0 0 13.6ZM16 16l4 4"
                stroke="currentColor"
                stroke-width="1.7"
                stroke-linecap="round"
              />
            </svg>
          </span>
          <span class="knowledge-bubble__body">
            <strong>查找资料</strong>
            <span>按问题检索知识片段</span>
          </span>
        </button>
      </div>

      <!-- 上传面板 -->
      <section v-if="uploadOpen" class="knowledge-panel">
        <KnowledgeUploader :uploading="uploading" @upload="upload" />
        <ErrorMessage v-if="uploadError" :error="uploadError" />
      </section>

      <!-- 查找面板 -->
      <section v-else-if="searchOpen" class="knowledge-panel">
        <form class="knowledge-search" @submit.prevent="search">
          <div class="knowledge-search__row">
            <input
              id="knowledge-search-input"
              v-model="query"
              class="knowledge-search__input"
              type="search"
              placeholder="例如：项目上线前需要检查哪些事项？"
              autocomplete="off"
            />
            <label class="knowledge-search__topk">
              <span>Top K</span>
              <select v-model="topK">
                <option value="3">3</option>
                <option value="5">5</option>
                <option value="10">10</option>
              </select>
            </label>
            <AppButton type="submit" :loading="searching">检索</AppButton>
          </div>
          <p v-if="searchFormError" class="knowledge-search__error" role="alert">
            {{ searchFormError }}
          </p>
        </form>

        <ErrorMessage v-if="searchError" :error="searchError" retryable @retry="search" />
        <LoadingSpinner v-if="searching" class="knowledge-panel__state" />
        <p v-else-if="searched && hits.length === 0" class="knowledge-panel__empty">
          没有检索到相关内容，换个问法试试。
        </p>
        <ul v-else-if="hits.length" class="hit-list">
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

      <!-- 已上传文件列表（常驻） -->
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
        <ErrorMessage v-if="actionError" :error="actionError" />
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
import KnowledgeUploader from '@/components/KnowledgeUploader.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import NavIcon from '@/components/NavIcon.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import type { KnowledgeDocument, KnowledgeSearchHit } from '@/types/knowledge'
import { formatDateTime } from '@/utils/datetime'
import { knowledgeStatusMeta } from '@/utils/statusLabels'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const toast = useToast()

const uploadOpen = ref(false)
const searchOpen = ref(false)

function togglePanel(panel: 'upload' | 'search'): void {
  if (panel === 'upload') {
    uploadOpen.value = !uploadOpen.value
    if (uploadOpen.value) {
      searchOpen.value = false
    }
  } else {
    searchOpen.value = !searchOpen.value
    if (searchOpen.value) {
      uploadOpen.value = false
    }
  }
}

const { items, pagination, loading, error, load } = useAsyncList<KnowledgeDocument>({
  fetcher: ({ page, page_size }) => knowledgeApi.listDocuments({ page, page_size }),
})

const uploading = ref(false)
const uploadError = ref<unknown>(null)
const query = ref('')
const topK = ref('5')
const searching = ref(false)
const searched = ref(false)
const searchError = ref<unknown>(null)
const searchFormError = ref('')
const hits = ref<KnowledgeSearchHit[]>([])
const actionError = ref<unknown>(null)
const showDelete = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref<string | null>(null)

function refresh(): Promise<void> {
  return load()
}

function statusOf(document: KnowledgeDocument) {
  return knowledgeStatusMeta[document.processing_status]
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
    // 上传成功后收起上传区，让新文件直接可见
    uploadOpen.value = false
  } catch (caught) {
    uploadError.value = caught
  } finally {
    uploading.value = false
  }
}

async function search(): Promise<void> {
  const text = query.value.trim()
  if (!text) {
    searchFormError.value = '请输入检索内容'
    return
  }
  searchFormError.value = ''
  searching.value = true
  searched.value = true
  searchError.value = null
  try {
    const result = await knowledgeApi.searchKnowledge({
      query: text,
      top_k: Number(topK.value),
    })
    hits.value = result.items
  } catch (caught) {
    hits.value = []
    searchError.value = caught
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
      uploadOpen.value = false
      searchOpen.value = false
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

/* 图标气泡框 */
.knowledge-bubbles {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.knowledge-bubble {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  text-align: left;
  font: inherit;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    border-color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.knowledge-bubble:hover {
  transform: translateY(-1px);
  border-color: rgba(21, 94, 239, 0.35);
  box-shadow: var(--shadow-md);
}

.knowledge-bubble--active {
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.45);
}

.knowledge-bubble__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 2.35rem;
  height: 2.35rem;
  border-radius: var(--radius-md);
}

.knowledge-bubble__icon--primary {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.knowledge-bubble__icon--accent {
  color: var(--color-accent-strong);
  background: var(--color-accent-soft);
}

.knowledge-bubble--active .knowledge-bubble__icon--primary {
  color: #ffffff;
  background: var(--color-primary);
}

.knowledge-bubble--active .knowledge-bubble__icon--accent {
  color: #ffffff;
  background: var(--color-accent);
}

.knowledge-bubble__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.knowledge-bubble__body strong {
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 650;
}

.knowledge-bubble__body span {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
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

/* 查找 */
.knowledge-search {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.knowledge-search__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.knowledge-search__input {
  flex: 1;
  min-width: 12rem;
  min-height: 2.5rem;
  padding: 0 var(--space-3);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.875rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
}

.knowledge-search__input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.knowledge-search__topk {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.knowledge-search__topk select {
  min-height: 2.5rem;
  padding: 0 var(--space-2);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.8125rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.knowledge-search__error {
  margin: 0;
  color: var(--color-down);
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
