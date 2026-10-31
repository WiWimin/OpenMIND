<template>
  <div class="record-item">
    <div class="record-item__meta">
      <AppTag :label="typeLabel" />
      <StatusBadge v-if="markerMeta" :label="markerMeta.label" :tone="markerMeta.tone" />
      <span class="record-item__time">{{ time }}</span>
    </div>

    <template v-if="editing">
      <FormTextarea id="record-edit" v-model="draft" label="修改记录" :rows="3" :error="error" />
      <div class="record-item__actions">
        <AppButton variant="ghost" :disabled="saving" @click="cancel">取消</AppButton>
        <AppButton :loading="saving" @click="save">保存</AppButton>
      </div>
    </template>

    <template v-else>
      <p class="record-item__content">{{ record.content }}</p>
      <div v-if="!readonly" class="record-item__marker-controls" role="group" aria-label="记录标记">
        <span class="record-item__marker-caption">标记：</span>
        <button
          v-for="option in MARKER_OPTIONS"
          :key="option.value"
          type="button"
          class="record-item__marker-button"
          :class="{
            'record-item__marker-button--active': record.marker_type === option.value,
          }"
          :aria-pressed="record.marker_type === option.value"
          :title="
            record.marker_type === option.value ? `取消${option.label}标记` : `设为${option.label}`
          "
          @click="toggleMarker(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
      <div v-if="!readonly" class="record-item__actions">
        <AppButton size="sm" variant="ghost" @click="startEdit">编辑</AppButton>
        <AppButton size="sm" variant="ghost" @click="emit('delete')">删除</AppButton>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppTag from '@/components/AppTag.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import type { MeetingRecord, RecordMarkerType, RecordType } from '@/types/record'
import { formatDateTime } from '@/utils/datetime'
import { recordMarkerMeta } from '@/utils/statusLabels'

const TYPE_LABELS: Record<RecordType, string> = {
  manual: '手动记录',
  transcript: '转写',
  imported: '导入',
}

const MARKER_OPTIONS: { value: RecordMarkerType; label: string }[] = [
  { value: 'highlight', label: '重点' },
  { value: 'decision', label: '决议' },
  { value: 'question', label: '疑问' },
]

const props = withDefaults(
  defineProps<{
    record: MeetingRecord
    saving?: boolean
    readonly?: boolean
  }>(),
  {
    saving: false,
    readonly: false,
  },
)

const emit = defineEmits<{
  save: [content: string]
  delete: []
  marker: [marker: RecordMarkerType | null]
}>()

const editing = ref(false)
const draft = ref('')
const error = ref('')

const typeLabel = computed(() => TYPE_LABELS[props.record.record_type])
const time = computed(() => formatDateTime(props.record.created_at))
const markerMeta = computed(() =>
  props.record.marker_type ? recordMarkerMeta[props.record.marker_type] : null,
)

function toggleMarker(marker: RecordMarkerType): void {
  emit('marker', props.record.marker_type === marker ? null : marker)
}

function startEdit(): void {
  draft.value = props.record.content
  error.value = ''
  editing.value = true
}

function cancel(): void {
  editing.value = false
  error.value = ''
}

function save(): void {
  const content = draft.value.trim()
  if (!content) {
    error.value = '记录内容不能为空'
    return
  }
  editing.value = false
  error.value = ''
  emit('save', content)
}
</script>

<style scoped>
.record-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast);
}

.record-item:hover {
  border-color: var(--color-border-strong);
}

.record-item__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.record-item__time {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.record-item__content {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.record-item__marker-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
}

.record-item__marker-caption {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.record-item__marker-button {
  padding: 0.15rem 0.6rem;
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    color var(--transition-fast);
}

.record-item__marker-button:hover {
  border-color: var(--color-border-strong);
  color: var(--color-foreground);
}

.record-item__marker-button--active {
  background: rgba(21, 94, 239, 0.1);
  border-color: rgba(21, 94, 239, 0.35);
  color: var(--color-primary-strong);
}

.record-item__actions {
  display: flex;
  gap: var(--space-2);
}
</style>
