<template>
  <section class="template-manage">
    <PageHeader title="会议模板管理">
      <template #actions>
        <AppButton variant="ghost" :loading="uploading" @click="fileEl?.click()">
          上传模板文件
        </AppButton>
        <AppButton @click="openCreate('ai')">AI 生成模板</AppButton>
      </template>
    </PageHeader>

    <div class="template-manage__toolbar">
      <div class="template-manage__search">
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
          v-model="search"
          class="template-manage__search-input"
          type="search"
          placeholder="搜索模板名称或分类"
          aria-label="搜索模板"
        />
      </div>
      <div class="template-manage__filters" role="group" aria-label="模板筛选">
        <button
          v-for="filter in FILTERS"
          :key="filter.value"
          type="button"
          class="template-manage__filter"
          :class="{ 'template-manage__filter--active': activeFilter === filter.value }"
          @click="activeFilter = filter.value"
        >
          {{ filter.label }}
        </button>
      </div>
    </div>

    <input
      ref="fileEl"
      type="file"
      accept=".docx,.txt,.md"
      hidden
      :disabled="uploading"
      @change="onFileChosen"
    />
    <ErrorMessage v-if="uploadError" :error="uploadError" />

    <section class="template-grid-wrap">
      <LoadingSpinner v-if="loading && templates.length === 0" class="template-grid__state" />
      <ErrorMessage v-else-if="error" :error="error" retryable @retry="load()" />
      <EmptyState
        v-else-if="filteredTemplates.length === 0"
        title="没有匹配的模板"
        description="调整搜索关键词或筛选条件试试。"
      />
      <div v-else class="template-grid">
        <article
          v-for="template in filteredTemplates"
          :key="template.template_id"
          class="template-card"
        >
          <div class="template-card__thumb" aria-hidden="true">
            <p class="template-card__thumb-title">{{ template.name }}</p>
            <p
              v-for="(line, index) in previewLines(template)"
              :key="index"
              class="template-card__thumb-line"
            >
              {{ line }}
            </p>
          </div>
          <div class="template-card__body">
            <div class="template-card__title-row">
              <span class="template-card__fileicon" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none">
                  <path
                    d="M7 3.5h7L18.5 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z"
                    stroke="currentColor"
                    stroke-width="1.7"
                    stroke-linejoin="round"
                  />
                </svg>
              </span>
              <strong class="template-card__name">{{ template.name }}</strong>
              <span
                v-if="template.source === 'custom'"
                class="template-card__tag template-card__tag--info"
              >
                我的
              </span>
              <span
                v-if="defaultTemplateId === template.template_id"
                class="template-card__tag template-card__tag--success"
              >
                默认
              </span>
            </div>
            <div class="template-card__actions">
              <button type="button" class="template-card__action" @click="openPreview(template)">
                预览
              </button>
              <button type="button" class="template-card__action" @click="useTemplate(template)">
                使用
              </button>
              <button
                type="button"
                class="template-card__action"
                :disabled="duplicating"
                @click="duplicateTemplate(template)"
              >
                另存为
              </button>
              <button
                v-if="defaultTemplateId !== template.template_id"
                type="button"
                class="template-card__action"
                :disabled="settingDefault"
                @click="setDefault(template)"
              >
                设为默认
              </button>
              <button
                v-if="template.source === 'custom'"
                type="button"
                class="template-card__action template-card__action--danger"
                @click="askDelete(template)"
              >
                删除
              </button>
            </div>
          </div>
        </article>
      </div>
    </section>

    <AppModal :open="previewTarget !== null" title="模板预览" @close="previewTarget = null">
      <p v-if="previewLoading" class="template-manage__state">正在加载模板内容…</p>
      <p v-else-if="previewError" class="template-manage__error">{{ previewError }}</p>
      <pre v-else-if="previewContent" class="template-preview">{{ previewContent }}</pre>
      <template #footer>
        <AppButton variant="ghost" @click="previewTarget = null">关闭</AppButton>
      </template>
    </AppModal>

    <ConfirmDialog
      :open="deleteTarget !== null"
      title="删除模板"
      message="删除后该模板不可恢复，确定删除吗？"
      confirm-text="删除"
      danger
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />

    <TemplateFormDialog
      :open="formOpen"
      :initial-tab="formTab"
      @close="formOpen = false"
      @created="onCreated"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as memoryApi from '@/api/memory'
import * as templatesApi from '@/api/templates'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import PageHeader from '@/components/PageHeader.vue'
import TemplateFormDialog from '@/components/settings/TemplateFormDialog.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import type { MeetingTemplate } from '@/types/template'

const FILTERS = [
  { value: 'all', label: '全部' },
  { value: 'builtin', label: '内置' },
  { value: 'custom', label: '我的' },
] as const

type TemplateFilter = (typeof FILTERS)[number]['value']

const router = useRouter()
const route = useRoute()
const toast = useToast()

const templates = ref<MeetingTemplate[]>([])
const loading = ref(false)
const error = ref<unknown>(null)
const search = ref('')
const activeFilter = ref<TemplateFilter>('all')

const formOpen = ref(false)
const formTab = ref<'manual' | 'ai'>('manual')

const fileEl = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadError = ref<unknown>(null)

const previewTarget = ref<MeetingTemplate | null>(null)
const previewLoading = ref(false)
const previewError = ref('')
const previewContent = ref('')

const deleteTarget = ref<MeetingTemplate | null>(null)

const defaultTemplateId = ref('')
const settingDefault = ref(false)
const duplicating = ref(false)

const filteredTemplates = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return templates.value.filter((template) => {
    if (activeFilter.value !== 'all' && template.source !== activeFilter.value) {
      return false
    }
    if (!keyword) {
      return true
    }
    return (
      template.name.toLowerCase().includes(keyword) ||
      (template.category ?? '').toLowerCase().includes(keyword)
    )
  })
})

function previewLines(template: MeetingTemplate): string[] {
  const text = template.content_preview.trim()
  if (!text) {
    return []
  }
  return text.split(/[；;]\s*/).slice(0, 4)
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

async function loadDefaultTemplate(): Promise<void> {
  try {
    const memory = await memoryApi.getMemory()
    const preferred = memory.preferred_minutes_template ?? ''
    // 枚举值（standard 等）不作为卡片默认标记，只有模板 id 才对应清单中的模板
    defaultTemplateId.value = preferred.startsWith('tpl') ? preferred : ''
  } catch {
    defaultTemplateId.value = ''
  }
}

function openCreate(tab: 'manual' | 'ai'): void {
  formTab.value = tab
  formOpen.value = true
}

function onCreated(): void {
  void load()
}

async function onFileChosen(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  input.value = ''
  if (!file) {
    return
  }
  uploading.value = true
  uploadError.value = null
  try {
    await templatesApi.uploadTemplate({ file })
    toast.success('模板已上传')
    await load()
  } catch (caught) {
    uploadError.value = caught
  } finally {
    uploading.value = false
  }
}

async function openPreview(template: MeetingTemplate): Promise<void> {
  previewTarget.value = template
  previewLoading.value = true
  previewError.value = ''
  previewContent.value = ''
  try {
    const detail = await templatesApi.getTemplate(template.template_id)
    previewContent.value = detail.content_text
  } catch {
    previewError.value = '模板内容加载失败，请稍后重试'
  } finally {
    previewLoading.value = false
  }
}

function useTemplate(template: MeetingTemplate): void {
  // 从 AI 输入框跳转而来时原路返回并预选模板；直接访问则落到预处理页
  const returnTo = String(route.query.returnTo ?? '')
  const meetingId = String(route.query.meetingId ?? '')
  const query = {
    ...(meetingId ? { meetingId } : {}),
    templateId: template.template_id,
  }
  if (returnTo === 'minutes') {
    void router.push({ name: ROUTE_NAMES.minutesGenerate, query })
    return
  }
  void router.push({ name: ROUTE_NAMES.preprocess, query })
}

async function duplicateTemplate(template: MeetingTemplate): Promise<void> {
  duplicating.value = true
  try {
    const detail = await templatesApi.getTemplate(template.template_id)
    await templatesApi.createTemplateText({
      name: `${template.name} 副本`,
      description: template.description ?? undefined,
      category: template.category ?? undefined,
      content_text: detail.content_text,
    })
    toast.success('已另存为我的模板')
    await load()
  } catch (caught) {
    toast.error(caught instanceof Error ? caught.message : '另存为失败，请稍后重试')
  } finally {
    duplicating.value = false
  }
}

async function setDefault(template: MeetingTemplate): Promise<void> {
  settingDefault.value = true
  try {
    const memory = await memoryApi.getMemory()
    await memoryApi.saveMemory({
      role: memory.role,
      work_scenarios: memory.work_scenarios,
      communication_style: memory.communication_style,
      preferred_minutes_template: template.template_id,
    })
    defaultTemplateId.value = template.template_id
    toast.success('已设为默认模板')
  } catch (caught) {
    toast.error(caught instanceof Error ? caught.message : '设置默认模板失败')
  } finally {
    settingDefault.value = false
  }
}

function askDelete(template: MeetingTemplate): void {
  deleteTarget.value = template
}

async function confirmDelete(): Promise<void> {
  if (!deleteTarget.value) {
    return
  }
  try {
    await templatesApi.deleteTemplate(deleteTarget.value.template_id)
    if (defaultTemplateId.value === deleteTarget.value.template_id) {
      defaultTemplateId.value = ''
    }
    toast.success('模板已删除')
    deleteTarget.value = null
    await load()
  } catch (caught) {
    toast.error(caught instanceof Error ? caught.message : '删除失败，请稍后重试')
  }
}

onMounted(() => {
  void load()
  void loadDefaultTemplate()
})
</script>

<style scoped>
.template-manage {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.template-manage__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.template-manage__search {
  display: flex;
  flex: 1 1 16rem;
  align-items: center;
  gap: 6px;
  min-height: 2.4rem;
  max-width: 22rem;
  padding: 0 var(--space-3);
  color: var(--color-muted-foreground);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.template-manage__search:focus-within {
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.template-manage__search-input {
  flex: 1;
  min-width: 0;
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.875rem;
  background: transparent;
  border: 0;
}

.template-manage__search-input:focus {
  outline: none;
}

.template-manage__filters {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  background: var(--color-surface-muted);
  border-radius: var(--radius-md);
}

.template-manage__filter {
  padding: 5px 14px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.8125rem;
  font-weight: 600;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.template-manage__filter--active {
  color: var(--color-primary-strong);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.template-grid-wrap {
  min-width: 0;
}

.template-grid__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(13rem, 1fr));
  gap: var(--space-3);
}

.template-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.template-card:hover {
  border-color: rgba(21, 94, 239, 0.35);
  box-shadow: var(--shadow-md);
}

/* 仿文档页面缩略图：白色纸张 + 居中标题 + 内容行 */
.template-card__thumb {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  aspect-ratio: 3 / 4;
  padding: var(--space-4) var(--space-3);
  overflow: hidden;
  background: #ffffff;
  border-bottom: 1px solid var(--color-border);
}

.template-card__thumb-title {
  margin: 0 0 4px;
  color: var(--color-foreground);
  font-size: 0.75rem;
  font-weight: 700;
  text-align: center;
}

.template-card__thumb-line {
  width: 100%;
  margin: 0;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.5625rem;
  line-height: 1.5;
  text-align: center;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.template-card__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3) var(--space-3);
}

.template-card__title-row {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.template-card__fileicon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 1.15rem;
  height: 1.15rem;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-radius: var(--radius-sm);
}

.template-card__name {
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-card__tag {
  flex: 0 0 auto;
  padding: 1px 7px;
  font-size: 0.625rem;
  font-weight: 650;
  border-radius: var(--radius-pill);
}

.template-card__tag--info {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.template-card__tag--success {
  color: var(--color-up);
  background: var(--color-up-soft, rgba(22, 163, 74, 0.12));
}

.template-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.template-card__action {
  padding: 3px 8px;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 600;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.template-card__action:hover:not(:disabled) {
  background: var(--color-primary-soft);
}

.template-card__action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.template-card__action--danger {
  color: var(--color-down);
}

.template-card__action--danger:hover:not(:disabled) {
  background: rgba(220, 38, 38, 0.08);
}

.template-manage__state {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.template-manage__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}

.template-preview {
  margin: 0;
  padding: var(--space-3);
  overflow-x: auto;
  color: var(--color-foreground);
  font-family: var(--font-mono);
  font-size: 0.8125rem;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}
</style>
