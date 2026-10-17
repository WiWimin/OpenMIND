<template>
  <section class="model-settings">
    <PageHeader
      title="模型设置"
      description="配置你自己的 LLM 与 Embedding 服务，AI 能力将优先使用这里的密钥。"
    />

    <div class="model-settings__note">
      <p>密钥经服务端加密保存，保存后只回显前后缀，不会明文返回浏览器。</p>
      <p>保存时只写入已勾选的提供方；未勾选的提供方会清除你的自备配置，回退服务端全局配置。</p>
    </div>

    <ErrorMessage :error="loadError" retryable @retry="load" />
    <LoadingSpinner v-if="loading" />

    <form v-else-if="model" class="model-settings__form" @submit.prevent="handleSave">
      <section class="provider">
        <header class="provider__header">
          <div>
            <h2 class="provider__title">LLM（生成纪要、问答、会前准备）</h2>
            <p class="provider__current">
              当前生效：<code>{{ model.llm_api_base || '未配置' }}</code>
              · <code>{{ model.llm_model || '未配置' }}</code>
              · 密钥 {{ model.llm_api_key_masked || '未配置' }}
            </p>
          </div>
          <label class="provider__toggle" for="use-llm">
            <input id="use-llm" v-model="useLlm" type="checkbox" />
            <span>使用我的配置</span>
          </label>
        </header>

        <fieldset class="provider__fields" :disabled="!useLlm">
          <FormField
            id="llm-api-base"
            v-model="llm.apiBase"
            label="API Base"
            placeholder="https://api.example.com/v1"
            :error="errors.llm_api_base"
          />
          <FormField
            id="llm-model"
            v-model="llm.model"
            label="模型名称"
            placeholder="gpt-4o-mini"
            :error="errors.llm_model"
          />
          <FormField
            id="llm-api-key"
            v-model="llm.apiKey"
            label="API Key"
            type="password"
            :placeholder="model.llm_api_key_masked || 'sk-...'"
            :error="errors.llm_api_key"
          />
        </fieldset>
      </section>

      <section class="provider">
        <header class="provider__header">
          <div>
            <h2 class="provider__title">Embedding（资料索引与 RAG 检索）</h2>
            <p class="provider__current">
              当前生效：<code>{{ model.embedding_api_base || '未配置' }}</code>
              · <code>{{ model.embedding_model || '未配置' }}</code>
              · 密钥 {{ model.embedding_api_key_masked || '未配置' }}
            </p>
          </div>
          <label class="provider__toggle" for="use-embedding">
            <input id="use-embedding" v-model="useEmbedding" type="checkbox" />
            <span>使用我的配置</span>
          </label>
        </header>

        <fieldset class="provider__fields" :disabled="!useEmbedding">
          <FormField
            id="embedding-api-base"
            v-model="embedding.apiBase"
            label="API Base"
            placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
            :error="errors.embedding_api_base"
          />
          <FormField
            id="embedding-model"
            v-model="embedding.model"
            label="模型名称"
            placeholder="text-embedding-v3"
            :error="errors.embedding_model"
          />
          <FormField
            id="embedding-api-key"
            v-model="embedding.apiKey"
            label="API Key"
            type="password"
            :placeholder="model.embedding_api_key_masked || 'sk-...'"
            :error="errors.embedding_api_key"
          />
        </fieldset>

        <p class="provider__hint">向量维度固定为 {{ model.embedding_dim }}，保存前会实测校验。</p>
      </section>

      <ErrorMessage :error="saveError" />

      <div class="model-settings__actions">
        <AppButton
          type="submit"
          :loading="saving"
          :disabled="!useLlm && !useEmbedding"
        >
          保存配置
        </AppButton>
        <AppButton
          variant="ghost"
          :disabled="!hasAnyConfig || saving || clearing"
          @click="showClear = true"
        >
          清除我的配置
        </AppButton>
      </div>
    </form>

    <ConfirmDialog
      :open="showClear"
      title="清除模型配置"
      message="将删除你自备的模型配置，AI 功能会回退到服务端全局配置。"
      confirm-text="清除"
      danger
      :loading="clearing"
      @cancel="showClear = false"
      @confirm="handleClear"
    />

    <ErrorMessage :error="clearError" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import {
  clearModelConfig,
  getModelConfig,
  saveModelConfig,
} from '@/api/settings'
import AppButton from '@/components/AppButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useToast } from '@/composables/useToast'
import type {
  ModelConfigRead,
  ModelConfigWrite,
} from '@/types/modelConfig'

interface ProviderForm {
  apiBase: string
  apiKey: string
  model: string
}

const toast = useToast()

const model = ref<ModelConfigRead | null>(null)
const loading = ref(false)
const loadError = ref<unknown>(null)
const saving = ref(false)
const saveError = ref<unknown>(null)
const clearing = ref(false)
const clearError = ref<unknown>(null)
const showClear = ref(false)
const useLlm = ref(false)
const useEmbedding = ref(false)

const llm = reactive<ProviderForm>({ apiBase: '', apiKey: '', model: '' })
const embedding = reactive<ProviderForm>({ apiBase: '', apiKey: '', model: '' })
const errors = reactive<Record<string, string>>({
  llm_api_base: '',
  llm_api_key: '',
  llm_model: '',
  embedding_api_base: '',
  embedding_api_key: '',
  embedding_model: '',
})

const hasAnyConfig = computed(
  () => Boolean(model.value?.llm_api_key_masked || model.value?.embedding_api_key_masked),
)

function applyConfig(data: ModelConfigRead): void {
  model.value = data
  llm.apiBase = data.llm_api_base
  llm.apiKey = ''
  llm.model = data.llm_model
  embedding.apiBase = data.embedding_api_base
  embedding.apiKey = ''
  embedding.model = data.embedding_model
}

function resetErrors(): void {
  for (const key of Object.keys(errors)) {
    errors[key] = ''
  }
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    applyConfig(await getModelConfig())
  } catch (error) {
    loadError.value = error
  } finally {
    loading.value = false
  }
}

function validateProvider(prefix: 'llm' | 'embedding', provider: ProviderForm): boolean {
  errors[`${prefix}_api_base`] = provider.apiBase.trim() ? '' : '请填写 API Base'
  errors[`${prefix}_api_key`] = provider.apiKey.trim() ? '' : '请填写 API Key'
  errors[`${prefix}_model`] = provider.model.trim() ? '' : '请填写模型名称'
  return Boolean(
    provider.apiBase.trim() && provider.apiKey.trim() && provider.model.trim(),
  )
}

function buildPayload(): ModelConfigWrite {
  const payload: ModelConfigWrite = {}
  if (useLlm.value) {
    payload.llm_api_base = llm.apiBase.trim()
    payload.llm_api_key = llm.apiKey.trim()
    payload.llm_model = llm.model.trim()
  }
  if (useEmbedding.value) {
    payload.embedding_api_base = embedding.apiBase.trim()
    payload.embedding_api_key = embedding.apiKey.trim()
    payload.embedding_model = embedding.model.trim()
  }
  return payload
}

async function handleSave(): Promise<void> {
  saveError.value = null
  resetErrors()

  if (!useLlm.value && !useEmbedding.value) {
    saveError.value = {
      error_code: 'VALIDATION_ERROR',
      message: '请至少勾选一个提供方后再保存。',
    }
    return
  }

  const llmValid = !useLlm.value || validateProvider('llm', llm)
  const embeddingValid =
    !useEmbedding.value || validateProvider('embedding', embedding)
  if (!llmValid || !embeddingValid) {
    return
  }

  saving.value = true
  try {
    applyConfig(await saveModelConfig(buildPayload()))
    useLlm.value = false
    useEmbedding.value = false
    toast.success('模型配置已保存并生效')
  } catch (error) {
    saveError.value = error
  } finally {
    saving.value = false
  }
}

async function handleClear(): Promise<void> {
  clearing.value = true
  clearError.value = null
  try {
    await clearModelConfig()
    showClear.value = false
    useLlm.value = false
    useEmbedding.value = false
    toast.success('已清除自备配置，回退服务端全局')
    await load()
  } catch (error) {
    clearError.value = error
  } finally {
    clearing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.model-settings {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.model-settings__note {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-3) var(--space-4);
  background: rgba(59, 111, 212, 0.06);
  border: 1px solid rgba(59, 111, 212, 0.18);
  border-radius: var(--radius-md);
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
}

.model-settings__note p {
  margin: 0;
}

.model-settings__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.provider {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  -webkit-backdrop-filter: var(--glass-blur);
  backdrop-filter: var(--glass-blur);
}

.provider__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.provider__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.provider__current {
  margin: var(--space-1) 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
  overflow-wrap: anywhere;
}

.provider__current code {
  color: var(--color-foreground);
  font-size: 0.8125rem;
}

.provider__toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  flex: 0 0 auto;
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
}

.provider__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  border: none;
  transition: opacity var(--transition-fast);
}

.provider__fields:disabled {
  opacity: 0.55;
}

.provider__hint {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.model-settings__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

@media (max-width: 720px) {
  .provider__header {
    flex-direction: column;
  }

  .model-settings__actions {
    flex-direction: column-reverse;
  }
}
</style>
