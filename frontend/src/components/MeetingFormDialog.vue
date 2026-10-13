<template>
  <AppModal :open="open" :title="title" @close="emit('cancel')">
    <form class="meeting-form" novalidate @submit.prevent="submit">
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

      <ErrorMessage v-if="error" :error="error" />

      <div class="meeting-form__actions">
        <AppButton variant="ghost" :disabled="loading" @click="emit('cancel')">取消</AppButton>
        <AppButton type="submit" :loading="loading">保存</AppButton>
      </div>
    </form>
  </AppModal>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import type { CreateMeetingPayload, Meeting } from '@/types/meeting'
import { fromDatetimeLocal, toDatetimeLocal } from '@/utils/datetime'

const props = withDefaults(
  defineProps<{
    open: boolean
    meeting?: Meeting | null
    loading?: boolean
    error?: unknown
  }>(),
  {
    meeting: null,
    loading: false,
  },
)

const emit = defineEmits<{ submit: [payload: CreateMeetingPayload]; cancel: [] }>()

const form = reactive({ title: '', topic: '', meeting_time: '' })
const errors = reactive({ title: '' })

const title = computed(() => (props.meeting ? '编辑会议' : '新建会议'))

function reset(): void {
  form.title = props.meeting?.title ?? ''
  form.topic = props.meeting?.topic ?? ''
  form.meeting_time = toDatetimeLocal(props.meeting?.meeting_time)
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
  })
}
</script>

<style scoped>
.meeting-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.meeting-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
