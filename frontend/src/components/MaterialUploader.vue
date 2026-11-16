<template>
  <div class="material-uploader" :class="{ 'material-uploader--error': hasError }">
    <div
      class="material-uploader__dropzone"
      :class="{
        'material-uploader__dropzone--active': dragging,
        'material-uploader__dropzone--disabled': uploading,
        'material-uploader__dropzone--error': hasError,
      }"
      role="button"
      tabindex="0"
      aria-label="上传资料：拖拽文件到此处，或点击选择文件（选中后自动上传并解析）"
      @click="openPicker"
      @keydown.enter.prevent="openPicker"
      @keydown.space.prevent="openPicker"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <input
        id="material-file"
        ref="inputEl"
        class="material-uploader__native"
        type="file"
        accept=".pdf,.docx,.txt"
        :disabled="uploading"
        @change="onFileChange"
      />
      <span class="material-uploader__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="26" height="26" fill="none">
          <path
            d="M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5Z"
            stroke="currentColor"
            stroke-width="1.5"
            stroke-linejoin="round"
          />
          <path d="M12 10.5v7M8.8 13.5 12 10.3l3.2 3.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </span>
      <p class="material-uploader__title">
        {{ uploading ? '正在上传并解析…' : '拖拽文件到此处上传，或点击选择文件' }}
      </p>
      <div class="material-uploader__types" aria-hidden="true">
        <span>PDF</span>
        <span>DOC</span>
        <span>TXT</span>
      </div>
    </div>

    <p v-if="shownFile" class="material-uploader__file-row">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
        <path
          d="M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5ZM14 3.5V8h4.5"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
      </svg>
      <span class="material-uploader__file-name">{{ shownFile.name }}</span>
      <span v-if="stateLabel" class="material-uploader__file-state" :class="stateTone">
        {{ stateLabel }}
      </span>
      <button
        v-if="canRetry"
        type="button"
        class="material-uploader__retry"
        :disabled="uploading"
        @click="retry"
      >
        重试
      </button>
      <button
        v-else-if="!uploading"
        type="button"
        class="material-uploader__remove"
        aria-label="移除已选文件"
        @click="clearSelected"
      >
        ×
      </button>
    </p>

    <p v-if="errorText" class="material-uploader__error" role="alert">
      <strong v-if="errorTitle" class="material-uploader__error-title">{{ errorTitle }}</strong>
      {{ errorText }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { MaterialUploadError, MaterialUploadPayload } from '@/types/material'
import { validateMaterialFile } from '@/utils/materialUpload'

const props = withDefaults(
  defineProps<{ uploading?: boolean; error?: MaterialUploadError | null }>(),
  { uploading: false, error: null },
)

const emit = defineEmits<{ upload: [payload: MaterialUploadPayload] }>()

const inputEl = ref<HTMLInputElement | null>(null)
const selected = ref<File | null>(null)
const localError = ref('')
const dragging = ref(false)

const uploading = computed(() => props.uploading)
const hasError = computed(() => props.error !== null || localError.value !== '')
const errorText = computed(() => props.error?.message ?? localError.value)
const errorTitle = computed(() => {
  if (props.error) {
    return props.error.kind === 'parse' ? '无法解析' : '上传失败'
  }
  return localError.value ? '上传失败' : ''
})
const shownFile = computed(() => selected.value)
const stateLabel = computed(() => {
  if (props.error) {
    return props.error.kind === 'parse' ? '无法解析' : '上传失败'
  }
  if (uploading.value) {
    return '上传中'
  }
  return ''
})
const stateTone = computed(() => (props.error ? 'material-uploader__file-state--down' : ''))
const canRetry = computed(() => props.error !== null && selected.value !== null)

function openPicker(): void {
  if (uploading.value) {
    return
  }
  inputEl.value?.click()
}

function acceptFile(file: File | null | undefined): void {
  if (!file) {
    return
  }
  const message = validateMaterialFile(file)
  if (message) {
    localError.value = message
    selected.value = null
    return
  }
  localError.value = ''
  selected.value = file
  emit('upload', { file })
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  acceptFile(input.files?.[0])
  input.value = ''
}

function onDrop(event: DragEvent): void {
  dragging.value = false
  if (uploading.value) {
    return
  }
  acceptFile(event.dataTransfer?.files?.[0])
}

function clearSelected(): void {
  selected.value = null
  localError.value = ''
}

function retry(): void {
  if (!selected.value || uploading.value) {
    return
  }
  localError.value = ''
  emit('upload', { file: selected.value })
}

// 上传结束（uploading true→false）：成功则清空文件行；失败保留文件与错误以便重试
watch(
  () => props.uploading,
  (up, was) => {
    if (was && !up && !props.error && !localError.value) {
      selected.value = null
    }
  },
)
</script>

<style scoped>
.material-uploader {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.material-uploader__dropzone {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-6) var(--space-4);
  text-align: center;
  background: var(--color-surface-strong);
  border: 1.5px dashed var(--color-border-strong);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.material-uploader__dropzone:hover,
.material-uploader__dropzone--active {
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.material-uploader__dropzone--disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.material-uploader__dropzone--error,
.material-uploader__dropzone--error:hover {
  background: var(--color-surface-strong);
  border-color: var(--color-down);
  box-shadow: none;
}

.material-uploader__native {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.material-uploader__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.8rem;
  height: 2.8rem;
  color: var(--color-primary-strong);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 50%;
  box-shadow: var(--shadow-sm);
}

.material-uploader__dropzone--error .material-uploader__icon {
  color: var(--color-down);
}

.material-uploader__title {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
}

.material-uploader__types {
  display: flex;
  gap: var(--space-2);
}

.material-uploader__types span {
  padding: 1px 8px;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
}

.material-uploader__file-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 6px 10px;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.material-uploader--error .material-uploader__file-row {
  border-color: rgba(220, 38, 38, 0.35);
}

.material-uploader__file-row svg {
  flex: 0 0 auto;
  color: var(--color-primary-strong);
}

.material-uploader__file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.material-uploader__file-state {
  flex: 0 0 auto;
  padding: 1px 8px;
  font-size: 0.6875rem;
  font-weight: 650;
  color: var(--color-muted-foreground);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
}

.material-uploader__file-state--down {
  color: var(--color-down);
  background: rgba(220, 38, 38, 0.06);
  border-color: rgba(220, 38, 38, 0.3);
}

.material-uploader__retry {
  flex: 0 0 auto;
  padding: 2px 10px;
  color: var(--color-primary-strong);
  font-size: 0.75rem;
  font-weight: 650;
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.3);
  border-radius: var(--radius-pill);
  cursor: pointer;
}

.material-uploader__retry:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.material-uploader__remove {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  color: var(--color-muted-foreground);
  font-size: 1rem;
  line-height: 1;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.material-uploader__remove:hover {
  color: var(--color-foreground);
  background: var(--color-surface-muted);
}

.material-uploader__error {
  margin: 0;
  padding: 8px 10px;
  color: var(--color-down);
  font-size: 0.8125rem;
  line-height: 1.6;
  background: rgba(220, 38, 38, 0.05);
  border: 1px solid rgba(220, 38, 38, 0.25);
  border-radius: var(--radius-md);
}

.material-uploader__error-title {
  margin-right: 4px;
  font-weight: 700;
}
</style>
