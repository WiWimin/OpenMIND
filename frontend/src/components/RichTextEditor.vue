<template>
  <div class="rich-editor">
    <label
      class="rich-editor__label"
      :class="{ 'rich-editor__label--hidden': variant === 'document' }"
      :for="id"
    >
      {{ label }}
    </label>
    <div
      v-if="editor && editable !== false"
      class="rich-editor__toolbar"
      role="toolbar"
      aria-label="格式工具栏"
    >
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
      <button
        type="button"
        class="rich-editor__tool"
        :class="{ 'rich-editor__tool--active': editor.isActive('highlight') }"
        :disabled="!editor.isEditable"
        aria-label="高亮强调"
        @click="editor.chain().focus().toggleHighlight().run()"
      >
        高亮
      </button>
      <select
        class="rich-editor__font"
        aria-label="字体"
        :disabled="!editor.isEditable"
        :value="currentFont"
        @change="onFontChange"
      >
        <option value="">默认字体</option>
        <option v-for="font in fontOptions" :key="font.value" :value="font.value">
          {{ font.label }}
        </option>
      </select>
      <label class="rich-editor__color" aria-label="文字颜色">
        <span aria-hidden="true">颜色</span>
        <input
          type="color"
          class="rich-editor__color-input"
          :disabled="!editor.isEditable"
          :value="currentColor"
          @input="onColorChange"
        />
      </label>
      <div class="rich-editor__end"><slot name="toolbar-end" /></div>
    </div>
    <EditorContent
      :id="id"
      class="rich-editor__content"
      :class="{ 'rich-editor__content--document': variant === 'document' }"
      :editor="editor"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { Editor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Color from '@tiptap/extension-color'
import FontFamily from '@tiptap/extension-font-family'
import Highlight from '@tiptap/extension-highlight'
import { TextStyle } from '@tiptap/extension-text-style'

const props = withDefaults(
  defineProps<{
    id: string
    modelValue: string
    label: string
    placeholder?: string
    editable?: boolean
    /** document：文档纸张样式（隐藏字段标签，正文居中成页，供纪要文档编辑使用） */
    variant?: 'default' | 'document'
  }>(),
  {
    editable: true,
    variant: 'default',
  },
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const fontOptions = [
  { value: '宋体, SimSun, serif', label: '宋体' },
  { value: '黑体, SimHei, sans-serif', label: '黑体' },
  { value: '楷体, KaiTi, serif', label: '楷体' },
  { value: 'Arial, sans-serif', label: 'Arial' },
  { value: 'Georgia, serif', label: 'Georgia' },
  { value: '"Courier New", monospace', label: 'Courier New' },
]

const currentFont = ref('')
const currentColor = ref('#1f2937')

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
  extensions: [StarterKit, Color, TextStyle, FontFamily, Highlight],
  content: toHtml(props.modelValue),
  editable: props.editable !== false,
  onUpdate: () => {
    emit('update:modelValue', editor.getHTML())
  },
})

function onFontChange(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  currentFont.value = value
  if (value) {
    editor.chain().focus().setFontFamily(value).run()
  } else {
    editor.chain().focus().unsetFontFamily().run()
  }
}

function onColorChange(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  currentColor.value = value
  editor.chain().focus().setColor(value).run()
}

watch(
  () => props.modelValue,
  (value) => {
    const next = toHtml(value)
    if (next !== editor.getHTML()) {
      editor.commands.setContent(next, { emitUpdate: false })
    }
  },
)

watch(
  () => props.editable,
  (value) => {
    editor.setEditable(value !== false)
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

/* document 变体：文件名已在抽屉头部展示，标签仅保留给读屏 */
.rich-editor__label--hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
  border: 0;
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
  background: rgba(21, 94, 239, 0.1);
  border-color: rgba(21, 94, 239, 0.4);
}

.rich-editor__tool:disabled {
  opacity: 0.5;
  cursor: default;
}

.rich-editor__font {
  max-width: 8rem;
  padding: 0.25rem 0.4rem;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-family: inherit;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.rich-editor__color {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.25rem 0.6rem;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  font-weight: 600;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
}

.rich-editor__color:hover {
  color: var(--color-foreground);
  border-color: var(--color-border-strong);
}

.rich-editor__color-input {
  width: 1.25rem;
  height: 1.25rem;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
}

/* 工具栏右侧操作位（保存 / 确认 / 导出等） */
.rich-editor__end {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}

.rich-editor__content {
  min-height: 12rem;
  padding: var(--space-3);
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 0.9375rem;
  line-height: 1.7;
  overflow-y: auto;
}

/* document 变体：灰底工作区 + 居中白纸页（Word 文档风格） */
.rich-editor__content--document {
  min-height: 0;
  padding: var(--space-4) var(--space-3) var(--space-6);
  overflow: visible;
  background: transparent;
  border: 0;
  border-radius: 0;
  font-size: inherit;
  line-height: inherit;
}

.rich-editor__content :deep(.ProseMirror) {
  min-height: 10rem;
  outline: none;
}

.rich-editor__content--document :deep(.ProseMirror) {
  max-width: 46rem;
  min-height: 58vh;
  margin: 0 auto;
  padding: 2.75rem 3.25rem;
  background: #ffffff;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  font-size: 1rem;
  line-height: 1.8;
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

.rich-editor__content :deep(.ProseMirror mark) {
  background: rgba(250, 204, 21, 0.4);
  padding: 0 0.15em;
  border-radius: 2px;
}
</style>
