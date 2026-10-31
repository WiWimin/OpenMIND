<template>
  <AppModal
    :open="open"
    :label="title"
    overflow-visible
    @close="emit('cancel')"
  >
    <template #top>
      <div class="meeting-form__deco" aria-hidden="true">
        <span class="meeting-form__ribbon" />
        <img class="meeting-form__mascot" :src="dialogIpUrl" alt="" />
        <span class="meeting-form__bubble">{{ bubble }}</span>
      </div>
    </template>

    <form class="meeting-form" novalidate @submit.prevent="submit">
      <header class="meeting-form__head">
        <div class="meeting-form__heading">
          <h2 class="meeting-form__title">{{ title }}</h2>
          <p class="meeting-form__subtitle">{{ subtitle }}</p>
        </div>
        <button
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

      <div v-if="categories.length > 0" class="form-field">
        <label class="form-field__label" for="meeting-category">会议分类</label>
        <select id="meeting-category" v-model="form.categoryId" class="form-field__select">
          <option value="">未分类</option>
          <option v-for="category in categories" :key="category.id" :value="category.id">
            {{ category.name }}
          </option>
        </select>
        <p class="form-field__hint">分类决定会议在会议列表中的文件夹归属。</p>
      </div>

      <ErrorMessage v-if="error" :error="error" />

      <div class="meeting-form__actions">
        <AppButton variant="ghost" :disabled="loading" @click="emit('cancel')">取消</AppButton>
        <AppButton type="submit" :loading="loading">{{ submitLabel }}</AppButton>
      </div>
    </form>
  </AppModal>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import dialogIpUrl from '@/assets/new-meeting-ip.png'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import type { CreateMeetingPayload, Meeting } from '@/types/meeting'
import { fromDatetimeLocal, toDatetimeLocal } from '@/utils/datetime'
import { categoryOf, type MeetingCategory } from '@/utils/meetingCategories'

export interface MeetingFormPayload extends CreateMeetingPayload {
  /** 过渡期分类（localStorage），后端分类表上线后由 API 承接 */
  categoryId?: string
}

const props = withDefaults(
  defineProps<{
    open: boolean
    meeting?: Meeting | null
    loading?: boolean
    error?: unknown
    categories?: MeetingCategory[]
  }>(),
  {
    meeting: null,
    loading: false,
    categories: () => [],
  },
)

const emit = defineEmits<{ submit: [payload: MeetingFormPayload]; cancel: [] }>()

const form = reactive({ title: '', topic: '', meeting_time: '', categoryId: '' })
const errors = reactive({ title: '' })

const isEditing = computed(() => props.meeting !== null)
const title = computed(() => (isEditing.value ? '编辑会议' : '新建会议'))
const subtitle = computed(() =>
  isEditing.value ? '修改会议的基本信息，保存后立即生效' : '快速创建一场会议，后续可在会议管理中补充类型',
)
const bubble = computed(() => (isEditing.value ? '需要调整会议信息吗' : '我来帮你记录会议'))
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
  () => {
    if (props.open) {
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

/* 顶部装饰：渐变条 + 鹦鹉 IP + 气泡（锚定在面板上，可探出顶边） */
.meeting-form__deco {
  pointer-events: none;
}

.meeting-form__ribbon {
  position: absolute;
  top: 0;
  right: 0;
  left: 0;
  height: 0.875rem;
  background: linear-gradient(92deg, #155eef 0%, #4f7df6 55%, #a855f7 100%);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

.meeting-form__mascot {
  position: absolute;
  bottom: 100%;
  right: 4.4rem;
  z-index: 2;
  width: 6.2rem;
  height: auto;
  filter: drop-shadow(0 10px 18px rgba(21, 94, 239, 0.22));
  user-select: none;
}

.meeting-form__bubble {
  position: absolute;
  top: -5.1rem;
  right: 11.4rem;
  z-index: 2;
  padding: 0.5rem 0.95rem;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
  white-space: nowrap;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
}

.meeting-form__bubble::after {
  content: '';
  position: absolute;
  top: 50%;
  right: -5px;
  width: 9px;
  height: 9px;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  border-right: 1px solid var(--color-border);
  transform: translateY(-50%) rotate(45deg);
  border-radius: 1px;
}

/* 头部：标题 + 副标题 + 关闭 */
.meeting-form__head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.meeting-form__title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--color-foreground);
}

.meeting-form__subtitle {
  margin: 2px 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  line-height: 1.5;
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

/* 操作区 */
.meeting-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

/* 分类选择 */
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

.form-field__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

@media (max-width: 480px) {
  .meeting-form__mascot {
    bottom: 100%;
    right: 1.1rem;
    width: 4.8rem;
  }

  .meeting-form__bubble {
    display: none;
  }

  .meeting-form {
    padding: 1.5rem var(--space-4) var(--space-4);
  }
}
</style>
