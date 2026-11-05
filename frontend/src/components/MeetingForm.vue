<template>
  <form class="meeting-form" novalidate @submit.prevent="submit">
    <header class="meeting-form__head">
      <div class="meeting-form__heading">
        <h2 class="meeting-form__title">{{ title }}</h2>
      </div>
      <button
        v-if="closable"
        class="meeting-form__close"
        type="button"
        aria-label="关闭"
        @click="emit('cancel')"
      >
        ×
      </button>
    </header>

    <FormField
      id="meeting-title"
      v-model="form.title"
      label="标题"
      required
      :error="errors.title"
    />
    <FormField id="meeting-topic" v-model="form.topic" label="主题" />
    <FormField
      id="meeting-time"
      v-model="form.meeting_time"
      label="会议时间"
      type="datetime-local"
    />

    <!-- 会议管理文件夹：单下拉 + 嵌套选项；未选择时以会议名为名自动建文件夹 -->
    <div class="form-field">
      <label class="form-field__label" for="meeting-folder">存储文件夹</label>
      <select id="meeting-folder" v-model="form.categoryId" class="form-field__select">
        <option value="">{{ isEditing ? '未分类' : '默认：以会议名新建文件夹' }}</option>
        <optgroup v-if="categories.length > 0" label="会议管理 / 已有文件夹">
          <option v-for="category in categories" :key="category.id" :value="category.id">
            &#12288;{{ category.name }}
          </option>
        </optgroup>
      </select>
    </div>

    <ErrorMessage v-if="error" :error="error" />

    <div class="meeting-form__actions">
      <AppButton v-if="closable" variant="ghost" :disabled="loading" @click="emit('cancel')">
        取消
      </AppButton>
      <AppButton type="submit" :loading="loading">{{ submitLabel }}</AppButton>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import AppButton from '@/components/AppButton.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import type { CreateMeetingPayload, Meeting } from '@/types/meeting'
import { fromDatetimeLocal, toDatetimeLocal } from '@/utils/datetime'
import { categoryOf, type MeetingCategory } from '@/utils/meetingCategories'

export interface MeetingFormPayload extends CreateMeetingPayload {
  /** 会议管理中的文件夹归属（未选择时由创建流程按会议名新建） */
  categoryId?: string
}

const props = withDefaults(
  defineProps<{
    /** 打开时重置表单（对话框形态传入；页面形态恒为 true） */
    open?: boolean
    meeting?: Meeting | null
    loading?: boolean
    error?: unknown
    categories?: MeetingCategory[]
    /** 是否显示关闭/取消（页面形态不显示） */
    closable?: boolean
  }>(),
  {
    open: true,
    meeting: null,
    loading: false,
    categories: () => [],
    closable: true,
  },
)

const emit = defineEmits<{ submit: [payload: MeetingFormPayload]; cancel: [] }>()

const form = reactive({
  title: '',
  topic: '',
  meeting_time: '',
  categoryId: '',
})
const errors = reactive({ title: '' })

const isEditing = computed(() => props.meeting !== null)
const title = computed(() => (isEditing.value ? '编辑会议' : '新建会议'))
const submitLabel = computed(() => (isEditing.value ? '保存' : '创建'))

function reset(): void {
  form.title = props.meeting?.title ?? ''
  form.topic = props.meeting?.topic ?? ''
  form.meeting_time = toDatetimeLocal(props.meeting?.meeting_time)
  form.categoryId =
    props.meeting?.meeting_id != null
      ? (categoryOf(props.meeting.meeting_id) ?? '')
      : (form.categoryId ?? '')
  errors.title = ''
}

watch(
  () => [props.open, props.meeting] as const,
  ([open]) => {
    if (open) {
      reset()
    }
  },
  { immediate: true },
)

function submit(): void {
  const titleValue = form.title.trim()
  if (!titleValue) {
    errors.title = '请输入会议标题'
    return
  }
  errors.title = ''
  emit('submit', {
    title: titleValue,
    topic: form.topic.trim() || undefined,
    meeting_time: fromDatetimeLocal(form.meeting_time),
    categoryId: form.categoryId || undefined,
  })
}
</script>

<style scoped>
.meeting-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: 1.75rem var(--space-5) var(--space-5);
}

.meeting-form__head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.meeting-form__heading {
  flex: 1;
}

.meeting-form__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--color-foreground);
}

.meeting-form__close {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: var(--color-muted-foreground);
  font-size: 1.375rem;
  line-height: 1;
  background: transparent;
  border: 0;
  border-radius: 50%;
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.meeting-form__close:hover {
  color: var(--color-foreground);
  background: var(--color-surface-strong);
}

.meeting-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field__label {
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 600;
}

.form-field__select {
  min-height: 2.6rem;
  padding: 0 var(--space-2);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.875rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.form-field__select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

@media (max-width: 480px) {
  .meeting-form {
    padding: 1.5rem var(--space-4) var(--space-4);
  }
}
</style>
