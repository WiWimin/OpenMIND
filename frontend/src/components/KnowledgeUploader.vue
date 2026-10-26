<template>
  <div class="knowledge-uploader">
    <div class="knowledge-uploader__field">
      <label class="knowledge-uploader__label" for="knowledge-file">文件</label>
      <input
        id="knowledge-file"
        class="knowledge-uploader__file"
        type="file"
        accept=".pdf,.docx,.txt"
        @change="onFileChange"
      />
    </div>

    <p v-if="selected" class="knowledge-uploader__selected">
      已选择：{{ selected.name }}
    </p>
    <p v-if="error" class="knowledge-uploader__error" role="alert">{{ error }}</p>

    <AppButton :loading="uploading" :disabled="!selected" @click="submit">
      上传到知识库
    </AppButton>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import { validateMaterialFile } from '@/utils/materialUpload'

withDefaults(defineProps<{ uploading?: boolean }>(), { uploading: false })

const emit = defineEmits<{ upload: [file: File] }>()

const selected = ref<File | null>(null)
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
  emit('upload', selected.value)
  selected.value = null
}
</script>

<style scoped>
.knowledge-uploader {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-lg);
}

.knowledge-uploader__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.knowledge-uploader__label {
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 600;
}

.knowledge-uploader__file {
  min-height: 2.6rem;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font: inherit;
}

.knowledge-uploader__file::file-selector-button {
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

.knowledge-uploader__selected {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.knowledge-uploader__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.875rem;
}
</style>
