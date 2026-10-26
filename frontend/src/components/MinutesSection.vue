<template>
  <div class="minutes-section">
    <div v-if="!readonly" class="minutes-section__toolbar">
      <AppButton :loading="generating" @click="generate">生成会议纪要</AppButton>
      <label class="minutes-section__template">
        <span>模板</span>
        <select id="minutes-template" v-model="template">
          <option v-for="option in TEMPLATE_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label class="minutes-section__materials">
        <input v-model="includeMaterials" type="checkbox" />
        <span>参考会议资料</span>
      </label>
      <AppButton v-if="generating" variant="ghost" @click="cancelGenerate">取消生成</AppButton>
    </div>

    <ErrorMessage v-if="actionError" :error="actionError" />

    <LoadingSpinner v-if="loading && items.length === 0" class="minutes-section__state" />

    <ErrorMessage v-else-if="error" :error="error" retryable @retry="refresh()" />

    <EmptyState
      v-else-if="items.length === 0"
      title="还没有纪要"
      description="基于会议记录生成会议纪要草稿，确认后可提取行动项。"
    />

    <div v-else class="minutes-section__body">
      <ul class="minutes-section__list">
        <li v-for="item in items" :key="item.minutes_id">
          <button
            type="button"
            class="minutes-section__item"
            :class="{ 'minutes-section__item--active': selected?.minutes_id === item.minutes_id }"
            @click="select(item)"
          >
            <span class="minutes-section__item-meta">
              <StatusBadge :label="statusOf(item).label" :tone="statusOf(item).tone" />
              <span class="minutes-section__template-label">{{ templateOf(item).label }}</span>
            </span>
            <span class="minutes-section__time">{{ timeOf(item) }}</span>
          </button>
        </li>
      </ul>

      <div v-if="selected" class="minutes-section__editor">
        <div class="minutes-section__editor-head">
          <StatusBadge :label="statusOf(selected).label" :tone="statusOf(selected).tone" />
          <span class="minutes-section__template-label">{{ templateOf(selected).label }}</span>
          <span class="minutes-section__version">v{{ selected.version }}</span>
        </div>

        <RichTextEditor
          id="minutes-content"
          v-model="draft"
          label="纪要内容"
          :editable="!readonly"
        />

        <div v-if="!readonly" class="minutes-section__actions">
          <AppButton :loading="saving" @click="save">保存</AppButton>
          <AppButton
            v-if="selected.status !== 'confirmed'"
            variant="ghost"
            :loading="confirming"
            @click="confirm"
          >
            确认
          </AppButton>
          <AppButton variant="ghost" :loading="exporting" @click="exportDocx">导出 DOCX</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as minutesApi from '@/api/minutes'
import AppButton from '@/components/AppButton.vue'
import EmptyState from '@/components/EmptyState.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useAsyncList } from '@/composables/useAsyncList'
import { useToast } from '@/composables/useToast'
import type { Minutes, MinutesTemplate } from '@/types/minutes'
import { formatDateTime } from '@/utils/datetime'
import { isRequestCancelled } from '@/utils/requests'
import { minutesStatusMeta, minutesTemplateMeta } from '@/utils/statusLabels'

const TEMPLATE_OPTIONS: { value: MinutesTemplate; label: string }[] = [
  { value: 'standard', label: '标准纪要' },
  { value: 'concise', label: '简洁记录' },
  { value: 'task_list', label: '任务清单' },
]

const props = withDefaults(
  defineProps<{
    meetingId: string
    meetingTitle?: string
    readonly?: boolean
  }>(),
  {
    meetingTitle: '',
    readonly: false,
  },
)

const toast = useToast()

const { items, loading, error, load } = useAsyncList<Minutes>({
  fetcher: ({ page, page_size }) => minutesApi.listMinutes(props.meetingId, { page, page_size }),
})

const selected = ref<Minutes | null>(null)
const draft = ref('')
const generating = ref(false)
const includeMaterials = ref(true)
const template = ref<MinutesTemplate>('standard')
const saving = ref(false)
const confirming = ref(false)
const exporting = ref(false)
const actionError = ref<unknown>(null)

function statusOf(minutes: Minutes) {
  return minutesStatusMeta[minutes.status]
}

function templateOf(minutes: Minutes) {
  return minutesTemplateMeta[minutes.template]
}

function timeOf(minutes: Minutes): string {
  return formatDateTime(minutes.created_at)
}

function select(minutes: Minutes): void {
  selected.value = minutes
  draft.value = minutes.content
}

function syncSelected(updated: Minutes): void {
  if (selected.value?.minutes_id === updated.minutes_id) {
    selected.value = updated
    draft.value = updated.content
  }
}

function refresh(): Promise<void> {
  return load()
}

onMounted(() => {
  void refresh()
})

let generateController: AbortController | null = null

async function generate(): Promise<void> {
  generating.value = true
  actionError.value = null
  const controller = new AbortController()
  generateController = controller
  try {
    const minutes = await minutesApi.generateMinutes(
      props.meetingId,
      {
        record_ids: [],
        include_action_items: true,
        include_materials: includeMaterials.value,
        template: template.value,
      },
      controller.signal,
    )
    await load(1)
    select(minutes)
    toast.success('已生成纪要草稿')
  } catch (caught) {
    if (isRequestCancelled(caught)) {
      toast.success('已取消生成')
    } else {
      actionError.value = caught
    }
  } finally {
    if (generateController === controller) {
      generateController = null
    }
    generating.value = false
  }
}

function cancelGenerate(): void {
  generateController?.abort()
}

async function save(): Promise<void> {
  if (!selected.value) {
    return
  }
  saving.value = true
  actionError.value = null
  try {
    const updated = await minutesApi.updateMinutes(selected.value.minutes_id, { content: draft.value })
    syncSelected(updated)
    await load()
    toast.success('纪要草稿已保存')
  } catch (caught) {
    actionError.value = caught
  } finally {
    saving.value = false
  }
}

async function confirm(): Promise<void> {
  if (!selected.value) {
    return
  }
  confirming.value = true
  actionError.value = null
  try {
    const updated = await minutesApi.confirmMinutes(selected.value.minutes_id)
    syncSelected(updated)
    await load()
    toast.success('纪要已确认')
  } catch (caught) {
    actionError.value = caught
  } finally {
    confirming.value = false
  }
}

async function exportDocx(): Promise<void> {
  if (!selected.value) {
    return
  }
  exporting.value = true
  actionError.value = null
  try {
    const { buildMinutesDocxBlob, downloadBlob } = await import('@/utils/minutesDocx')
    const title = props.meetingTitle ? `${props.meetingTitle} · 会议纪要` : '会议纪要'
    const blob = await buildMinutesDocxBlob(title, draft.value)
    downloadBlob(blob, `${title}.docx`)
    toast.success('纪要已导出为 DOCX')
  } catch (caught) {
    actionError.value = caught
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.minutes-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.minutes-section__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.minutes-section__template,
.minutes-section__materials {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.minutes-section__template {
  cursor: pointer;
}

.minutes-section__template select {
  min-height: 2rem;
  padding: 0 var(--space-2);
  background: var(--color-surface);
  color: var(--color-foreground);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font: inherit;
}

.minutes-section__template select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(59, 111, 212, 0.16);
}

.minutes-section__materials {
  cursor: pointer;
}

.minutes-section__materials input {
  accent-color: var(--color-primary);
}

.minutes-section__state {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
}

.minutes-section__body {
  display: grid;
  gap: var(--space-4);
  grid-template-columns: minmax(10rem, 16rem) 1fr;
}

.minutes-section__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.minutes-section__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font: inherit;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.minutes-section__item:hover {
  background: var(--color-surface-strong);
  border-color: var(--color-border-strong);
}

.minutes-section__item--active {
  border-color: var(--color-primary);
  background: rgba(59, 111, 212, 0.07);
}

.minutes-section__item-meta {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  min-width: 0;
}

.minutes-section__template-label {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  white-space: nowrap;
}

.minutes-section__time {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.minutes-section__editor {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.minutes-section__editor-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.minutes-section__version {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.minutes-section__actions {
  display: flex;
  gap: var(--space-2);
}

</style>
