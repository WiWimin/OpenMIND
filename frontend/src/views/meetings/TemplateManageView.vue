<template>
  <section class="template-manage">
    <PageHeader
      title="会议模板管理"
      description="项目内置常用会议模板，也可以上传自己的模板文件（DOCX / TXT / MD），在资料预处理等场景套用。"
    >
      <template #actions>
        <AppButton variant="ghost" @click="goBack">返回会议管理</AppButton>
      </template>
    </PageHeader>

    <div class="template-manage__layout">
      <section class="template-panel template-panel--upload">
        <header class="template-panel__head">
          <div>
            <h2 class="template-panel__title">上传自定义模板</h2>
            <p class="template-panel__hint">支持 DOCX / TXT / MD，单个文件不超过 20 MB。</p>
          </div>
        </header>

        <FormField id="template-name" v-model="name" label="模板名称（可选，默认取文件名）" />
        <FormField id="template-desc" v-model="description" label="模板描述（可选）" />

        <div
          class="template-upload"
          :class="{ 'template-upload--active': dragging }"
          role="button"
          tabindex="0"
          aria-label="选择模板文件：拖拽文件到此处，或点击选择"
          @click="fileEl?.click()"
          @keydown.enter.prevent="fileEl?.click()"
          @keydown.space.prevent="fileEl?.click()"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="onDrop"
        >
          <input
            ref="fileEl"
            class="template-upload__native"
            type="file"
            accept=".docx,.txt,.md"
            :disabled="uploading"
            @change="onFileChange"
          />
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true">
            <path
              d="M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5ZM12 10.5v7M8.8 13.5 12 10.3l3.2 3.2"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <p class="template-upload__text">
            {{ file ? file.name : '拖拽模板文件到此处，或点击选择' }}
          </p>
        </div>

        <p v-if="uploadError" class="template-panel__error" role="alert">{{ uploadError }}</p>

        <AppButton class="template-upload__submit" :loading="uploading" @click="submitUpload">
          上传模板
        </AppButton>
      </section>

      <section class="template-panel">
        <header class="template-panel__head">
          <div>
            <h2 class="template-panel__title">模板列表</h2>
            <p class="template-panel__hint">内置模板由项目提供，不可删除；自定义模板仅本人可见。</p>
          </div>
          <AppButton variant="ghost" :loading="loading" @click="load()">刷新</AppButton>
        </header>

        <LoadingSpinner v-if="loading && templates.length === 0" class="template-panel__state" />
        <ErrorMessage v-else-if="error" :error="error" retryable @retry="load()" />
        <EmptyState
          v-else-if="templates.length === 0"
          title="还没有可用模板"
          description="上传一个模板文件，或在资料预处理中使用默认结构。"
        />

        <ul v-else class="template-list">
          <li v-for="template in templates" :key="template.template_id" class="template-item">
            <div class="template-item__main">
              <div class="template-item__title-row">
                <strong class="template-item__name">{{ template.name }}</strong>
                <StatusBadge
                  :label="template.source === 'builtin' ? '内置' : '自定义'"
                  :tone="template.source === 'builtin' ? 'neutral' : 'info'"
                />
              </div>
              <p class="template-item__desc">{{ template.description || '暂无描述' }}</p>
              <p v-if="template.file_name" class="template-item__file">{{ template.file_name }}</p>
            </div>
            <div class="template-item__actions">
              <button type="button" class="template-item__action" @click="openPreview(template)">
                预览
              </button>
              <button
                v-if="template.source === 'custom'"
                type="button"
                class="template-item__action template-item__action--danger"
                @click="askDelete(template)"
              >
                删除
              </button>
            </div>
          </li>
        </ul>
      </section>
    </div>

    <AppModal :open="previewTarget !== null" title="模板预览" @close="previewTarget = null">
      <p v-if="previewLoading" class="template-panel__state">正在加载模板内容…</p>
      <p v-else-if="previewError" class="template-panel__error">{{ previewError }}</p>
      <pre v-else-if="previewContent" class="template-preview">{{ previewContent }}</pre>
      <template #footer>
        <AppButton variant="ghost" @click="previewTarget = null">关闭</AppButton>
      </template>
    </AppModal>

    <ConfirmDialog
      :open="showDelete"
      title="删除模板"
      message="删除后该模板不可恢复，确定删除吗？"
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
import { useRouter } from 'vue-router'

import * as templatesApi from '@/api/templates'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import type { MeetingTemplate } from '@/types/template'

const ALLOWED_EXTENSIONS = ['docx', 'txt', 'md'] as const
const MAX_MB = 20

const router = useRouter()
const toast = useToast()

const templates = ref<MeetingTemplate[]>([])
const loading = ref(false)
const error = ref<unknown>(null)

const fileEl = ref<HTMLInputElement | null>(null)
const file = ref<File | null>(null)
const name = ref('')
const description = ref('')
const dragging = ref(false)
const uploading = ref(false)
const uploadError = ref('')

const previewTarget = ref<MeetingTemplate | null>(null)
const previewLoading = ref(false)
const previewError = ref('')
const previewContent = ref('')

const showDelete = ref(false)
const deleting = ref(false)
const pendingDeleteId = ref<string | null>(null)

function fileExtension(fileName: string): string {
  const index = fileName.lastIndexOf('.')
  return index === -1 ? '' : fileName.slice(index + 1).toLowerCase()
}

function validateTemplateFile(candidate: File): string | null {
  if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(fileExtension(candidate.name))) {
    return `仅支持 ${ALLOWED_EXTENSIONS.join(' / ')} 文件`
  }
  if (candidate.size > MAX_MB * 1024 * 1024) {
    return `文件不能超过 ${MAX_MB} MB`
  }
  return null
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    templates.value = await templatesApi.listTemplates()
  } catch (caught) {
    error.value = caught
  } finally {
    loading.value = false
  }
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const candidate = input.files?.[0] ?? null
  if (!candidate) {
    file.value = null
    return
  }
  const message = validateTemplateFile(candidate)
  if (message) {
    uploadError.value = message
    file.value = null
    input.value = ''
    return
  }
  uploadError.value = ''
  file.value = candidate
}

function onDrop(event: DragEvent): void {
  dragging.value = false
  const candidate = event.dataTransfer?.files?.[0]
  if (!candidate) {
    return
  }
  const message = validateTemplateFile(candidate)
  if (message) {
    uploadError.value = message
    file.value = null
    return
  }
  uploadError.value = ''
  file.value = candidate
}

async function submitUpload(): Promise<void> {
  if (!file.value) {
    uploadError.value = '请先选择模板文件'
    return
  }
  uploading.value = true
  uploadError.value = ''
  try {
    await templatesApi.uploadTemplate({
      file: file.value,
      name: name.value.trim() || undefined,
      description: description.value.trim() || undefined,
    })
    file.value = null
    name.value = ''
    description.value = ''
    toast.success('模板已上传')
    await load()
  } catch (caught) {
    uploadError.value = resolvedMessage(caught, '模板上传失败，请稍后重试')
  } finally {
    uploading.value = false
  }
}

function resolvedMessage(caught: unknown, fallback: string): string {
  const message = (caught as { message?: string } | null)?.message
  return message && message.trim() ? message : fallback
}

async function openPreview(template: MeetingTemplate): Promise<void> {
  previewTarget.value = template
  previewLoading.value = true
  previewError.value = ''
  previewContent.value = ''
  try {
    const detail = await templatesApi.getTemplate(template.template_id)
    previewContent.value = detail.content_text
  } catch (caught) {
    previewError.value = resolvedMessage(caught, '模板内容加载失败')
  } finally {
    previewLoading.value = false
  }
}

function askDelete(template: MeetingTemplate): void {
  pendingDeleteId.value = template.template_id
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
  try {
    await templatesApi.deleteTemplate(pendingDeleteId.value)
    showDelete.value = false
    toast.success('模板已删除')
    await load()
  } catch (caught) {
    toast.error(resolvedMessage(caught, '模板删除失败'))
  } finally {
    deleting.value = false
    pendingDeleteId.value = null
  }
}

function goBack(): void {
  void router.push({ name: ROUTE_NAMES.meetings })
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.template-manage {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.template-manage__layout {
  display: grid;
  grid-template-columns: 22rem minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.template-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.template-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.template-panel__title {
  margin: 0;
  font-size: 0.9375rem;
  font-weight: 650;
}

.template-panel__hint {
  margin: 2px 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  line-height: 1.55;
}

.template-panel__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}

.template-upload {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-5) var(--space-3);
  text-align: center;
  color: var(--color-primary-strong);
  background: var(--color-surface-strong);
  border: 1.5px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.template-upload:hover,
.template-upload--active {
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
}

.template-upload__native {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.template-upload__text {
  margin: 0;
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.template-upload__submit {
  align-self: flex-end;
}

.template-list {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.template-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-border);
}

.template-item:last-child {
  border-bottom: 0;
}

.template-item__main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.template-item__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.template-item__name {
  font-size: 0.875rem;
  font-weight: 650;
}

.template-item__desc {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  line-height: 1.55;
}

.template-item__file {
  margin: 0;
  color: var(--color-subtle-foreground);
  font-size: 0.6875rem;
}

.template-item__actions {
  display: flex;
  flex: 0 0 auto;
  gap: var(--space-1);
}

.template-item__action {
  padding: 0.3rem 0.7rem;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.template-item__action:hover {
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.26);
}

.template-item__action--danger {
  color: var(--color-down);
}

.template-item__action--danger:hover {
  background: rgba(220, 38, 38, 0.06);
  border-color: rgba(220, 38, 38, 0.3);
}

.template-preview {
  max-height: 22rem;
  margin: 0;
  padding: var(--space-3);
  overflow-y: auto;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

@media (max-width: 1080px) {
  .template-manage__layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
