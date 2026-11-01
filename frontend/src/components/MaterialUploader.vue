<template>
  <div class="material-uploader">
    <div
      class="material-uploader__dropzone"
      :class="{
        'material-uploader__dropzone--active': dragging,
        'material-uploader__dropzone--disabled': uploading,
      }"
      role="button"
      tabindex="0"
      aria-label="上传资料：拖拽文件到此处，或点击选择文件"
      @click="openPicker"
      @keydown.enter.prevent="openPicker"
      @keydown.space.prevent="openPicker"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <input
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
      <p class="material-uploader__title">拖拽文件到此处上传，或点击选择文件</p>
      <div class="material-uploader__types" aria-hidden="true">
        <span>PDF</span>
        <span>DOC</span>
        <span>TXT</span>
      </div>
    </div>

    <p v-if="selected" class="material-uploader__file-row">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" aria-hidden="true">
        <path
          d="M7 3.5h7.5L19 8v12.5H7A2.5 2.5 0 0 1 4.5 18V6A2.5 2.5 0 0 1 7 3.5ZM14 3.5V8h4.5"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
      </svg>
      <span class="material-uploader__file-name">{{ selected.name }}</span>
      <button
        type="button"
        class="material-uploader__remove"
        aria-label="移除已选文件"
        :disabled="uploading"
        @click="clearSelected"
      >
        ×
      </button>
    </p>

    <p class="material-uploader__hint">支持 PDF、Word、TXT，单个文件不超过 20 MB。</p>

    <p v-if="error" class="material-uploader__error" role="alert">{{ error }}</p>

    <AppButton v-if="selected" class="material-uploader__submit" :loading="uploading" @click="submit">
      上传资料
    </AppButton>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import type { MaterialUploadPayload } from '@/types/material'
import { validateMaterialFile } from '@/utils/materialUpload'

withDefaults(defineProps<{ uploading?: boolean }>(), { uploading: false })

const emit = defineEmits<{ upload: [payload: MaterialUploadPayload] }>()

const inputEl = ref<HTMLInputElement | null>(null)
const selected = ref<File | null>(null)
const error = ref('')
const dragging = ref(false)

function openPicker(): void {
  inputEl.value?.click()
}

function acceptFile(file: File | null | undefined): void {
  if (!file) {
    selected.value = null
    return
  }
  const message = validateMaterialFile(file)
  if (message) {
    error.value = message
    selected.value = null
    return
  }
  error.value = ''
  selected.value = file
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  acceptFile(input.files?.[0])
  input.value = ''
}

function onDrop(event: DragEvent): void {
  dragging.value = false
  if (inputEl.value?.disabled) {
    return
  }
  acceptFile(event.dataTransfer?.files?.[0])
}

function clearSelected(): void {
  selected.value = null
  error.value = ''
}

function submit(): void {
  if (!selected.value) {
    return
  }
  emit('upload', { file: selected.value })
  selected.value = null
}
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
  color: var(--color-down);
  font-size: 0.875rem;
}

.material-uploader__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
}

.material-uploader__submit {
  align-self: flex-end;
}
</style>
