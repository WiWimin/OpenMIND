<template>
  <div class="record-item">
    <div class="record-item__meta">
      <AppTag :label="typeLabel" />
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
      <div v-if="!readonly" class="record-item__actions">
        <AppButton variant="ghost" @click="startEdit">编辑</AppButton>
        <AppButton variant="ghost" @click="emit('delete')">删除</AppButton>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppTag from '@/components/AppTag.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import type { MeetingRecord, RecordType } from '@/types/record'
import { formatDateTime } from '@/utils/datetime'

const TYPE_LABELS: Record<RecordType, string> = {
  manual: '手动记录',
  transcript: '转写',
  imported: '导入',
}

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

const emit = defineEmits<{ save: [content: string]; delete: [] }>()

const editing = ref(false)
const draft = ref('')
const error = ref('')

const typeLabel = computed(() => TYPE_LABELS[props.record.record_type])
const time = computed(() => formatDateTime(props.record.created_at))

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

.record-item__actions {
  display: flex;
  gap: var(--space-2);
}
</style>
