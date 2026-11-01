<template>
  <AppModal :open="open" title="新建模板" @close="emit('close')">
    <div class="template-form">
      <div class="template-form__tabs" role="tablist">
        <button
          type="button"
          class="template-form__tab"
          :class="{ 'template-form__tab--active': tab === 'manual' }"
          role="tab"
          :aria-selected="tab === 'manual'"
          @click="tab = 'manual'"
        >
          手动创建
        </button>
        <button
          type="button"
          class="template-form__tab"
          :class="{ 'template-form__tab--active': tab === 'ai' }"
          role="tab"
          :aria-selected="tab === 'ai'"
          @click="tab = 'ai'"
        >
          AI 生成
        </button>
      </div>

      <template v-if="tab === 'manual'">
        <FormField id="template-form-name" v-model="name" label="模板名称" placeholder="例如：评审会纪要" />
        <div class="template-form__row">
          <label class="template-form__field">
            <span class="template-form__label">分类</span>
            <select v-model="category" class="template-form__select">
              <option v-for="option in TEMPLATE_CATEGORIES" :key="option" :value="option">
                {{ option }}
              </option>
            </select>
          </label>
          <FormField
            id="template-form-desc"
            v-model="description"
            label="模板描述"
            placeholder="可选，说明适用场景"
          />
        </div>
        <FormTextarea
          id="template-form-content"
          v-model="content"
          label="模板内容"
          :rows="8"
          placeholder="用编号列表写出文档应包含的结构要点，每条说明该部分要写什么"
        />
      </template>

      <template v-else>
        <FormField
          id="template-form-ai-desc"
          v-model="aiDescription"
          label="模板需求描述"
          placeholder="例如：每周例会的复盘模板，包含数据回顾、风险与改进项"
        />
        <div class="template-form__ai-actions">
          <AppButton :loading="generating" @click="generate">生成草稿</AppButton>
        </div>
        <p v-if="aiGenerated" class="template-form__ai-note">
          已生成草稿，可直接编辑下方内容后保存。
        </p>
        <FormField id="template-form-ai-name" v-model="name" label="模板名称" placeholder="模板名称" />
        <div class="template-form__row">
          <label class="template-form__field">
            <span class="template-form__label">分类</span>
            <select v-model="category" class="template-form__select">
              <option v-for="option in TEMPLATE_CATEGORIES" :key="option" :value="option">
                {{ option }}
              </option>
            </select>
          </label>
          <FormField
            id="template-form-ai-desc-field"
            v-model="description"
            label="模板描述"
            placeholder="可选"
          />
        </div>
        <FormTextarea
          id="template-form-ai-content"
          v-model="content"
          label="模板内容"
          :rows="8"
          placeholder="生成后可在此编辑"
        />
      </template>

      <p v-if="formError" class="template-form__error" role="alert">{{ formError }}</p>
    </div>

    <template #footer>
      <AppButton variant="ghost" :disabled="submitting" @click="emit('close')">取消</AppButton>
      <AppButton
        :disabled="tab === 'ai' && !aiGenerated"
        :loading="submitting"
        @click="submit"
      >
        保存模板
      </AppButton>
    </template>
  </AppModal>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

import { createTemplateText, generateTemplate } from '@/api/templates'
import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import FormField from '@/components/FormField.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import { useToast } from '@/composables/useToast'
import { TEMPLATE_CATEGORIES, type TemplateCategory } from '@/types/template'

const props = defineProps<{ open: boolean; initialTab?: 'manual' | 'ai' }>()
const emit = defineEmits<{ close: []; created: [] }>()

const toast = useToast()

const tab = ref<'manual' | 'ai'>('manual')
const name = ref('')
const description = ref('')
const category = ref<TemplateCategory>('通用')
const content = ref('')
const aiDescription = ref('')
const aiGenerated = ref(false)
const generating = ref(false)
const submitting = ref(false)
const formError = ref('')

watch(
  () => props.open,
  (open) => {
    if (open) {
      tab.value = props.initialTab ?? 'manual'
      resetForm()
    }
  },
  { immediate: true },
)

function resetForm(): void {
  name.value = ''
  description.value = ''
  category.value = '通用'
  content.value = ''
  aiDescription.value = ''
  aiGenerated.value = false
  formError.value = ''
}

async function generate(): Promise<void> {
  const text = aiDescription.value.trim()
  if (!text) {
    formError.value = '请先描述模板需求'
    return
  }
  generating.value = true
  formError.value = ''
  try {
    const draft = await generateTemplate({ description: text })
    name.value = draft.name
    description.value = draft.description ?? ''
    category.value = draft.category ?? '通用'
    content.value = draft.content_text
    aiGenerated.value = true
  } catch (err) {
    formError.value = err instanceof Error ? err.message : 'AI 生成失败，请稍后重试'
  } finally {
    generating.value = false
  }
}

async function submit(): Promise<void> {
  if (!name.value.trim() || !content.value.trim()) {
    formError.value = '请填写模板名称与内容'
    return
  }
  submitting.value = true
  formError.value = ''
  try {
    await createTemplateText({
      name: name.value.trim(),
      description: description.value.trim() || undefined,
      category: category.value,
      content_text: content.value.trim(),
    })
    toast.success('模板已创建')
    emit('created')
    emit('close')
  } catch (err) {
    formError.value = err instanceof Error ? err.message : '保存失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.template-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.template-form__tabs {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  background: var(--color-surface-muted);
  border-radius: var(--radius-md);
  align-self: flex-start;
}

.template-form__tab {
  padding: 5px 14px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.8125rem;
  font-weight: 600;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.template-form__tab--active {
  color: var(--color-primary-strong);
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}

.template-form__row {
  display: grid;
  grid-template-columns: 9rem 1fr;
  gap: var(--space-3);
}

.template-form__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.template-form__label {
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 600;
}

.template-form__select {
  min-height: 2.6rem;
  padding: 0 var(--space-2);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.875rem;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.template-form__select:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: var(--focus-ring);
}

.template-form__ai-actions {
  display: flex;
}

.template-form__ai-note {
  margin: 0;
  color: var(--color-primary-strong);
  font-size: 0.8125rem;
}

.template-form__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}
</style>
