<template>
  <section class="template-manage">
    <!-- 顶部：大搜索栏 + 三个创建入口 -->
    <div class="template-manage__topbar">
      <div class="template-manage__search">
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" aria-hidden="true">
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
      <div class="template-manage__create-actions">
        <AppButton variant="ghost" :loading="uploading" @click="fileEl?.click()">
          上传模板文件
        </AppButton>
        <AppButton variant="ghost" @click="openCreate('ai')">AI 生成模板</AppButton>
        <AppButton @click="openCreate('manual')">
          <svg class="template-manage__plus" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path
              d="M8 3v10M3 8h10"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
            />
          </svg>
          创建模板
        </AppButton>
      </div>
    </div>

    <!-- 大标题 + 筛选 -->
    <div class="template-manage__title-row">
      <h1 class="template-manage__title">会议模板中心</h1>
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
          <div class="template-card__hero">
            <span class="template-card__category">{{ template.category ?? '通用' }}</span>
            <h2 class="template-card__name">{{ template.name }}</h2>
            <p
              v-for="(line, index) in previewLines(template)"
              :key="index"
              class="template-card__hero-line"
            >
              {{ line }}
            </p>
          </div>
          <div class="template-card__meta">
            <span class="template-card__source">
              {{ template.source === 'custom' ? '我的模板' : '内置模板' }}
            </span>
            <span
              v-if="defaultTemplateId === template.template_id"
              class="template-card__tag template-card__tag--success"
            >
              默认
            </span>
          </div>
          <div class="template-card__actions">
            <button type="button" class="template-card__use" @click="useTemplate(template)">
              使用模板
            </button>
            <div class="template-card__tools">
              <button
                type="button"
                class="template-card__action"
                @click="openPreview(template)"
              >
                预览
              </button>
              <button
                v-if="template.source === 'custom'"
                type="button"
                class="template-card__action template-card__action--danger"
                @click="askDelete(template)"
              >
                删除
              </button>
              <div class="template-card__more-wrap">
                <button
                  type="button"
                  class="template-card__action"
                  :aria-expanded="menuId === template.template_id"
                  @click.stop="toggleMenu(template.template_id)"
                >
                  更多
                </button>
                <div
                  v-if="menuId === template.template_id"
                  class="template-card__menu"
                  role="menu"
                  @click.stop
                >
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
                </div>
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- 模板文档预览：像打开文件一样阅读模板正文 -->
    <AppModal
      :open="previewTarget !== null"
      :title="previewTarget?.name ?? '模板预览'"
      size="lg"
      label="模板预览"
      @close="previewTarget = null"
    >
      <div v-if="previewTarget" class="tpl-doc">
        <div class="tpl-doc__meta">
          <span class="tpl-doc__chip">{{ previewTarget.category ?? '通用' }}</span>
          <span class="tpl-doc__chip tpl-doc__chip--muted">
            {{ previewTarget.source === 'custom' ? '我的模板' : '内置模板' }}
          </span>
          <span v-if="previewTarget.file_name" class="tpl-doc__file">
            {{ previewTarget.file_name }}
          </span>
        </div>
        <div class="tpl-doc__paper">
          <p v-if="previewLoading" class="tpl-doc__state">正在打开模板文件…</p>
          <p v-else-if="previewError" class="tpl-doc__state tpl-doc__state--error">
            {{ previewError }}
          </p>
          <MarkdownView v-else-if="previewContent" class="tpl-doc__body" :content="previewContent" />
          <p v-else class="tpl-doc__state">模板内容为空。</p>
        </div>
      </div>
      <template #footer>
        <AppButton v-if="previewError" variant="ghost" @click="retryPreview()">重试</AppButton>
        <AppButton variant="ghost" @click="previewTarget = null">关闭</AppButton>
        <AppButton
          :disabled="previewLoading || !!previewError"
          @click="previewTarget && useTemplate(previewTarget)"
        >
          使用模板
        </AppButton>
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as memoryApi from '@/api/memory'
import * as templatesApi from '@/api/templates'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import TemplateFormDialog from '@/components/settings/TemplateFormDialog.vue'
import { useToast } from '@/composables/useToast'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { resolveErrorMessage } from '@/utils/errors'
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

/** 卡片「更多」菜单（另存为 / 设为默认）：一次只展开一张卡片 */
const menuId = ref<string | null>(null)

function toggleMenu(templateId: string): void {
  menuId.value = menuId.value === templateId ? null : templateId
}

function closeMenu(): void {
  menuId.value = null
}

/** 点击卡片菜单以外区域收起菜单 */
function onDocClick(): void {
  closeMenu()
}

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
  return text.split(/[；;]\s*/).slice(0, 2)
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

function retryPreview(): void {
  if (previewTarget.value) {
    void openPreview(previewTarget.value)
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
  closeMenu()
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
    toast.error(resolveErrorMessage(caught, '另存为失败，请稍后重试'))
  } finally {
    duplicating.value = false
  }
}

async function setDefault(template: MeetingTemplate): Promise<void> {
  closeMenu()
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
    toast.error(resolveErrorMessage(caught, '设置默认模板失败'))
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
    toast.error(resolveErrorMessage(caught, '删除失败，请稍后重试'))
  }
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  void load()
  void loadDefaultTemplate()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})
</script>

<style scoped>
.template-manage {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* ===== 顶部：大搜索栏 + 创建入口 ===== */
.template-manage__topbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.template-manage__search {
  display: flex;
  flex: 1 1 20rem;
  align-items: center;
  gap: 8px;
  min-height: 2.75rem;
  padding: 0 var(--space-4);
  color: var(--color-muted-foreground);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
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
  font-size: 0.9375rem;
  background: transparent;
  border: 0;
}

.template-manage__search-input:focus {
  outline: none;
}

.template-manage__create-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.template-manage__plus {
  margin-right: 2px;
}

/* ===== 大标题 + 筛选 ===== */
.template-manage__title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.template-manage__title {
  margin: 0;
  color: var(--color-foreground);
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
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
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
  gap: var(--space-4);
}

.template-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.template-card:hover {
  border-color: rgba(21, 94, 239, 0.35);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

/* 蓝色渐变头图：分类小标签 + 大标题 + 描述行 */
.template-card__hero {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-4) var(--space-3);
  background: linear-gradient(180deg, var(--color-primary-soft) 0%, var(--color-surface) 100%);
}

.template-card__category {
  align-self: flex-start;
  padding: 1px 9px;
  color: var(--color-primary-strong);
  font-size: 0.6875rem;
  font-weight: 650;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(21, 94, 239, 0.16);
  border-radius: var(--radius-pill);
}

.template-card__name {
  margin: 0;
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 1.0625rem;
  font-weight: 700;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.template-card__hero-line {
  margin: 0;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

.template-card__tag {
  flex: 0 0 auto;
  padding: 1px 7px;
  font-size: 0.625rem;
  font-weight: 650;
  border-radius: var(--radius-pill);
}

.template-card__tag--success {
  color: var(--color-up);
  background: var(--color-up-soft, rgba(22, 163, 74, 0.12));
}

/* 元信息行：来源 + 默认徽标 */
.template-card__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-4) var(--space-3);
}

.template-card__source {
  color: var(--color-subtle-foreground);
  font-size: 0.6875rem;
  font-weight: 600;
}

.template-card__source::before {
  content: '';
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border: 1.5px solid currentColor;
  border-radius: 50%;
  vertical-align: -1px;
  opacity: 0.7;
}

/* 底部操作：左「使用模板」主操作 + 右侧小按钮 */
.template-card__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: auto;
  padding: var(--space-2) var(--space-3) var(--space-3);
  border-top: 1px solid var(--color-border);
}

.template-card__use {
  padding: 6px 10px;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.8125rem;
  font-weight: 700;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.template-card__use:hover {
  background: var(--color-primary-soft);
}

.template-card__tools {
  display: flex;
  align-items: center;
  gap: 2px;
}

.template-card__more-wrap {
  position: relative;
}

.template-card__menu {
  position: absolute;
  right: 0;
  bottom: calc(100% + 6px);
  z-index: 20;
  display: flex;
  flex-direction: column;
  min-width: 6.5rem;
  padding: 4px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}

.template-card__menu .template-card__action {
  width: 100%;
  padding: 6px 8px;
  text-align: left;
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

/* ===== 模板文档预览 ===== */
.tpl-doc {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.tpl-doc__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.tpl-doc__chip {
  padding: 1px 9px;
  color: var(--color-primary-strong);
  font-size: 0.6875rem;
  font-weight: 650;
  background: var(--color-primary-soft);
  border-radius: var(--radius-pill);
}

.tpl-doc__chip--muted {
  color: var(--color-muted-foreground);
  background: var(--color-surface-muted);
}

.tpl-doc__file {
  color: var(--color-subtle-foreground);
  font-family: var(--font-mono);
  font-size: 0.6875rem;
}

/* 纸张感正文区：像打开一份文档 */
.tpl-doc__paper {
  min-height: 16rem;
  padding: var(--space-5) var(--space-6);
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.tpl-doc__body {
  font-size: 0.9375rem;
  line-height: 1.85;
}

.tpl-doc__state {
  margin: 0;
  padding: var(--space-6) 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  text-align: center;
}

.tpl-doc__state--error {
  color: var(--color-down);
}
</style>
