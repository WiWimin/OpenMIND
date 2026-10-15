<template>
  <div class="material-uploader">
    <div class="material-uploader__fields">
      <div class="form-field">
        <label class="form-field__label" for="material-file">文件</label>
        <input
          id="material-file"
          class="material-uploader__file"
          type="file"
          accept=".pdf,.docx,.txt"
          @change="onFileChange"
        />
      </div>
      <FormField id="material-source" v-model="source" label="来源（可选）" />
    </div>

    <p v-if="error" class="material-uploader__error" role="alert">{{ error }}</p>

    <AppButton :loading="uploading" :disabled="!selected" @click="submit">上传材料</AppButton>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import FormField from '@/components/FormField.vue'
import type { MaterialUploadPayload } from '@/types/material'
import { validateMaterialFile } from '@/utils/materialUpload'

withDefaults(defineProps<{ uploading?: boolean }>(), { uploading: false })

const emit = defineEmits<{ upload: [payload: MaterialUploadPayload] }>()

const selected = ref<File | null>(null)
const source = ref('')
const error = ref('')

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  if (!file) {
    selected.value = null
    return
  }
  const message = validateMaterialFile(file)
  if (message) {
    error.value = message
    selected.value = null
    input.value = ''
    return
  }
  error.value = ''
  selected.value = file
}

function submit(): void {
  if (!selected.value) {
    return
  }
  emit('upload', {
    file: selected.value,
    source: source.value.trim() || undefined,
  })
  selected.value = null
  source.value = ''
}
</script>

<style scoped>
.material-uploader {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
}

.material-uploader__fields {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field__label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-foreground);
}

.material-uploader__file {
  min-height: 2.6rem;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font: inherit;
}

.material-uploader__file::file-selector-button {
  margin-right: var(--space-2);
  padding: 0.35rem 0.8rem;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  color: var(--color-foreground);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
}

.material-uploader__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.875rem;
}
</style>
