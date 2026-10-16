<template>
  <div class="rich-editor">
    <label class="rich-editor__label" :for="id">{{ label }}</label>
    <div v-if="editor" class="rich-editor__toolbar" role="toolbar" aria-label="格式工具栏">
      <button
        type="button"
        class="rich-editor__tool"
        :class="{ 'rich-editor__tool--active': editor.isActive('heading', { level: 1 }) }"
        :disabled="!editor.isEditable"
        aria-label="一级标题"
        @click="editor.chain().focus().toggleHeading({ level: 1 }).run()"
      >
        H1
      </button>
      <button
        type="button"
        class="rich-editor__tool"
        :class="{ 'rich-editor__tool--active': editor.isActive('heading', { level: 2 }) }"
        :disabled="!editor.isEditable"
        aria-label="二级标题"
        @click="editor.chain().focus().toggleHeading({ level: 2 }).run()"
      >
        H2
      </button>
      <button
        type="button"
        class="rich-editor__tool"
        :class="{ 'rich-editor__tool--active': editor.isActive('bold') }"
        :disabled="!editor.isEditable"
        aria-label="加粗"
        @click="editor.chain().focus().toggleBold().run()"
      >
        B
      </button>
      <button
        type="button"
        class="rich-editor__tool"
        :class="{ 'rich-editor__tool--active': editor.isActive('italic') }"
        :disabled="!editor.isEditable"
        aria-label="斜体"
        @click="editor.chain().focus().toggleItalic().run()"
      >
        I
      </button>
      <button
        type="button"
        class="rich-editor__tool"
        :class="{ 'rich-editor__tool--active': editor.isActive('bulletList') }"
        :disabled="!editor.isEditable"
        aria-label="无序列表"
        @click="editor.chain().focus().toggleBulletList().run()"
      >
        • 列表
      </button>
      <button
        type="button"
        class="rich-editor__tool"
        :class="{ 'rich-editor__tool--active': editor.isActive('orderedList') }"
        :disabled="!editor.isEditable"
        aria-label="有序列表"
        @click="editor.chain().focus().toggleOrderedList().run()"
      >
        1. 列表
      </button>
    </div>
    <EditorContent :id="id" class="rich-editor__content" :editor="editor" />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'
import { Editor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'

const props = defineProps<{
  id: string
  modelValue: string
  label: string
  placeholder?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}

function toHtml(content: string): string {
  if (!content) {
    return '<p></p>'
  }
  const trimmed = content.trim()
  if (trimmed.startsWith('<')) {
    return trimmed
  }
  return trimmed
    .split('\n')
    .map((line) => `<p>${escapeHtml(line) || '<br>'}</p>`)
    .join('')
}

const editor = new Editor({
  extensions: [StarterKit],
  content: toHtml(props.modelValue),
  editable: true,
  onUpdate: () => {
    emit('update:modelValue', editor.getHTML())
  },
})

watch(
  () => props.modelValue,
  (value) => {
    const next = toHtml(value)
    if (next !== editor.getHTML()) {
      editor.commands.setContent(next, { emitUpdate: false })
    }
  },
)

onBeforeUnmount(() => {
  editor.destroy()
})
</script>

<style scoped>
.rich-editor {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rich-editor__label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--color-foreground);
}

.rich-editor__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.rich-editor__tool {
  padding: 0.25rem 0.6rem;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
  font-family: inherit;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    border-color var(--transition-fast);
}

.rich-editor__tool:hover:not(:disabled) {
  color: var(--color-foreground);
  border-color: var(--color-border-strong);
}

.rich-editor__tool--active {
  color: var(--color-primary-strong);
  background: rgba(59, 111, 212, 0.1);
  border-color: rgba(59, 111, 212, 0.4);
}

.rich-editor__tool:disabled {
  opacity: 0.5;
  cursor: default;
}

.rich-editor__content :deep(.rich-editor__content) {
  min-height: 12rem;
  padding: var(--space-3);
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 0.9375rem;
  line-height: 1.7;
  overflow-y: auto;
}

.rich-editor__content :deep(.ProseMirror) {
  min-height: 10rem;
  outline: none;
}

.rich-editor__content :deep(.ProseMirror p) {
  margin: 0 0 0.5em;
}

.rich-editor__content :deep(.ProseMirror h1) {
  font-size: 1.25rem;
  font-weight: 700;
}

.rich-editor__content :deep(.ProseMirror h2) {
  font-size: 1.0625rem;
  font-weight: 700;
}

.rich-editor__content :deep(.ProseMirror ul),
.rich-editor__content :deep(.ProseMirror ol) {
  padding-left: 1.25rem;
  margin: 0 0 0.5em;
}
</style>
