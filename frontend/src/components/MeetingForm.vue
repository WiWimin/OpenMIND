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

    <!-- 未连接本地文件夹：创建页内提供授权入口（首次用户也能完成“新建时选文件夹”） -->
    <div v-if="!isEditing && wsSupported && !storageVisible" class="meeting-form__storage-cta">
      <AppButton variant="ghost" :loading="connecting" @click="connectWorkspace">
        {{ wsNeedsPermission ? '恢复本地文件夹权限' : '选择本地文件夹' }}
      </AppButton>
      <p class="form-field__hint">
        {{
          wsNeedsPermission
            ? '权限已过期，恢复后可选择本地存储位置'
            : '选择后可指定会议资料的本地存储位置，并自动导入文件夹中已有资料'
        }}
      </p>
    </div>

    <!-- 本地存储位置：路径即会议根；未选择默认 <会议名>/（仅创建时） -->
    <FolderPathPicker
      v-if="!isEditing"
      v-model="form.localPath"
      :default-label="defaultStorageLabel"
      :visible="storageVisible"
    />

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
import { computed, reactive, ref, watch } from 'vue'

import AppButton from '@/components/AppButton.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FolderPathPicker from '@/components/FolderPathPicker.vue'
import FormField from '@/components/FormField.vue'
import { useLocalWorkspace } from '@/composables/useLocalWorkspace'
import { useToast } from '@/composables/useToast'
import type { CreateMeetingPayload, Meeting } from '@/types/meeting'
import { fromDatetimeLocal, toDatetimeLocal } from '@/utils/datetime'
import { isLocalWorkspaceSupported } from '@/utils/localFileSystem'
import { categoryOf, type MeetingCategory } from '@/utils/meetingCategories'

export interface MeetingFormPayload extends CreateMeetingPayload {
  /** 过渡期分类（localStorage），后端分类表上线后由 API 承接 */
  categoryId?: string
  /** 本地存储根路径段（新建会议时选择；缺省 = 授权目录/<会议名>/） */
  localPath?: string[]
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

const ws = useLocalWorkspace()
const toast = useToast()

const form = reactive({
  title: '',
  topic: '',
  meeting_time: '',
  categoryId: '',
  localPath: [] as string[],
})
const errors = reactive({ title: '' })

const isEditing = computed(() => props.meeting !== null)
const title = computed(() => (isEditing.value ? '编辑会议' : '新建会议'))
const submitLabel = computed(() => (isEditing.value ? '保存' : '创建'))
const defaultStorageLabel = computed(() =>
  form.title.trim()
    ? `默认：授权目录/${form.title.trim()}/`
    : '默认：授权目录/<会议名>/',
)
/** 已连接本地文件夹时才展示存储位置选择 */
const storageVisible = computed(() => ws.status.value === 'connected')
/** 已支持但未连接：创建页展示授权入口 */
const wsSupported = computed(() => isLocalWorkspaceSupported())
const wsNeedsPermission = computed(() => ws.status.value === 'needs-permission')
const connecting = ref(false)

/** 创建页内授权本地文件夹（新授权 / 权限过期一键恢复），成功后展示存储位置选择 */
async function connectWorkspace(): Promise<void> {
  connecting.value = true
  try {
    const granted = wsNeedsPermission.value ? await ws.restore() : await ws.connect()
    if (!granted) {
      toast.error('未获得本地文件夹权限，无法选择存储位置（可稍后重试）')
    }
  } catch (caught) {
    console.warn('[meeting-form] 本地文件夹授权失败', caught)
    toast.error('本地文件夹授权失败，请重试')
  } finally {
    connecting.value = false
  }
}

function reset(): void {
  form.title = props.meeting?.title ?? ''
  form.topic = props.meeting?.topic ?? ''
  form.meeting_time = toDatetimeLocal(props.meeting?.meeting_time)
  form.categoryId =
    props.meeting?.meeting_id != null
      ? (categoryOf(props.meeting.meeting_id) ?? '')
      : (form.categoryId ?? '')
  form.localPath = []
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
    ...(form.localPath.length > 0 ? { localPath: [...form.localPath] } : {}),
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

.meeting-form__storage-cta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
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

.form-field__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

@media (max-width: 480px) {
  .meeting-form {
    padding: 1.5rem var(--space-4) var(--space-4);
  }
}
</style>
