<template>
  <section class="model-settings">
    <PageHeader
      title="模型设置"
      description="自备大模型与向量模型的 API 配置（BYOK）。用户配置优先，未设置时回退服务端默认。"
    />

    <template v-if="loadError">
      <ErrorMessage :error="loadError" retryable @retry="loadConfig" />
      <AppButton variant="ghost" :loading="store.saving" @click="resetDialogOpen = true">
        恢复服务端默认
      </AppButton>
      <ErrorMessage v-if="formError" :error="formError" />
    </template>
    <LoadingSpinner v-else-if="store.loading && !store.config" />

    <template v-else>
      <div class="model-settings__grid">
        <article v-for="card in cards" :key="card.key" class="provider-card">
          <header class="provider-card__head">
            <div class="provider-card__intro">
              <h2 class="provider-card__title">{{ card.title }}</h2>
              <p class="provider-card__hint">{{ card.hint }}</p>
            </div>
            <span
              class="provider-card__source"
              :class="`provider-card__source--${card.source}`"
            >
              {{ SOURCE_LABELS[card.source] }}
            </span>
          </header>

          <dl class="provider-card__current">
            <div>
              <dt>API 地址</dt>
              <dd>{{ card.apiBase || '—' }}</dd>
            </div>
            <div>
              <dt>模型</dt>
              <dd>{{ card.model || '—' }}</dd>
            </div>
            <div>
              <dt>密钥</dt>
              <dd>{{ card.masked || '—' }}</dd>
            </div>
          </dl>

          <div class="provider-card__form">
            <FormField
              :id="`${card.key}-api-base`"
              v-model="forms[card.key].apiBase"
              label="API 地址"
              placeholder="https://api.example.com/v1"
            />
            <FormField
              :id="`${card.key}-api-key`"
              v-model="forms[card.key].apiKey"
              label="API 密钥"
              type="password"
              placeholder="sk-..."
            />
            <FormField
              :id="`${card.key}-model`"
              v-model="forms[card.key].model"
              label="模型名"
              :placeholder="card.model || 'model-name'"
            />
            <p v-if="fieldErrors[card.key]" class="provider-card__error" role="alert">
              {{ fieldErrors[card.key] }}
            </p>
          </div>
        </article>
      </div>

      <ErrorMessage
        v-if="formError"
        :error="formError"
        :retryable="formErrorRetryable"
        @retry="handleSave"
      />

      <article class="purpose-card">
        <header class="provider-card__head">
          <div class="provider-card__intro">
            <h2 class="provider-card__title">按用途模型</h2>
            <p class="provider-card__hint">
              仅覆盖模型名，API 地址与密钥沿用上方大模型配置；留空使用默认模型。
            </p>
          </div>
        </header>

        <div class="purpose-card__grid">
          <FormField
            v-for="option in PURPOSE_OPTIONS"
            :key="option.key"
            :id="`purpose-${option.key}`"
            v-model="purposeModels[option.key]"
            :label="option.label"
            :placeholder="store.config?.llm_model || '默认模型'"
          />
        </div>

        <p v-if="store.config?.llm_source === 'none'" class="model-settings__note">
          请先保存大模型配置，再设置用途模型。
        </p>

        <div>
          <AppButton
            :loading="store.saving"
            :disabled="store.config?.llm_source === 'none'"
            @click="savePurposeModels"
          >
            保存用途模型
          </AppButton>
        </div>
      </article>

      <p class="model-settings__note">
        填写某一提供方的 API 地址、密钥与模型名后保存，将整体替换该提供方；留空该提供方则清除其自备配置并回退服务端默认。密钥加密存库，不回显明文。
      </p>

      <div class="model-settings__actions">
        <AppButton :loading="store.saving" @click="handleSave">保存配置</AppButton>
        <AppButton variant="ghost" :disabled="store.saving" @click="resetDialogOpen = true">
          恢复服务端默认
        </AppButton>
      </div>
    </template>

    <ConfirmDialog
      :open="resetDialogOpen"
      title="恢复服务端默认"
      message="将清除你自备的全部模型配置，后续使用服务端全局配置。确定继续？"
      confirm-text="恢复默认"
      danger
      :loading="store.saving"
      @confirm="confirmReset"
      @cancel="resetDialogOpen = false"
    />

    <ConfirmDialog
      :open="clearDialogOpen"
      title="确认清除提供方"
      :message="clearMessage"
      confirm-text="继续保存"
      danger
      :loading="store.saving"
      @confirm="doSave(pendingPayload)"
      @cancel="clearDialogOpen = false"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import AppButton from '@/components/AppButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useToast } from '@/composables/useToast'
import { useModelConfigStore } from '@/stores/modelConfig'
import type {
  ModelConfig,
  ModelConfigPayload,
  ModelConfigSource,
  ModelPurpose,
} from '@/types/modelConfig'

type ProviderKey = 'llm' | 'embedding'

interface ProviderForm {
  apiBase: string
  apiKey: string
  model: string
}

const SOURCE_LABELS: Record<ModelConfigSource, string> = {
  user: '用户配置',
  global: '服务端默认',
  none: '未配置',
}

const PURPOSE_OPTIONS: { key: ModelPurpose; label: string }[] = [
  { key: 'preparation', label: '会前准备' },
  { key: 'chat', label: '会议问答与整理' },
  { key: 'minutes', label: '纪要生成' },
  { key: 'extraction', label: '行动项与问题提取' },
]

const EMPTY_PURPOSE_MODELS: Record<ModelPurpose, string> = {
  preparation: '',
  chat: '',
  minutes: '',
  extraction: '',
}

const store = useModelConfigStore()
const toast = useToast()

const forms = reactive<Record<ProviderKey, ProviderForm>>({
  llm: { apiBase: '', apiKey: '', model: '' },
  embedding: { apiBase: '', apiKey: '', model: '' },
})

const purposeModels = reactive<Record<ModelPurpose, string>>({
  ...EMPTY_PURPOSE_MODELS,
})
const fieldErrors = reactive<Record<ProviderKey, string>>({ llm: '', embedding: '' })
const formError = ref<unknown>(null)
const loadError = ref<unknown>(null)
const resetDialogOpen = ref(false)
const clearDialogOpen = ref(false)
const clearMessage = ref('')
const pendingPayload = ref<ModelConfigPayload>({})

const formErrorRetryable = computed(() => {
  const error = formError.value
  return (
    typeof error === 'object' &&
    error !== null &&
    'retryable' in error &&
    Boolean((error as { retryable?: unknown }).retryable)
  )
})

const cards = computed(() => {
  const config = store.config
  return [
    {
      key: 'llm' as ProviderKey,
      title: '大模型（LLM）',
      hint: '用于纪要生成、会议问答、会前准备等文本生成。',
      source: config?.llm_source ?? 'none',
      apiBase: config?.llm_api_base ?? '',
      model: config?.llm_model ?? '',
      masked: config?.llm_api_key_masked ?? '',
    },
    {
      key: 'embedding' as ProviderKey,
      title: '向量模型（Embedding）',
      hint: '用于资料向量化与检索，维度固定 1024。',
      source: config?.embedding_source ?? 'none',
      apiBase: config?.embedding_api_base ?? '',
      model: config?.embedding_model ?? '',
      masked: config?.embedding_api_key_masked ?? '',
    },
  ]
})

function resetForms(): void {
  forms.llm = { apiBase: '', apiKey: '', model: '' }
  forms.embedding = { apiBase: '', apiKey: '', model: '' }
  fieldErrors.llm = ''
  fieldErrors.embedding = ''
}

function syncPurposeModels(config: ModelConfig | null): void {
  for (const purpose of Object.keys(EMPTY_PURPOSE_MODELS) as ModelPurpose[]) {
    purposeModels[purpose] = config?.llm_purpose_models?.[purpose] ?? ''
  }
}

async function loadConfig(): Promise<void> {
  loadError.value = null
  try {
    await store.load()
    syncPurposeModels(store.config)
  } catch (err) {
    loadError.value = err
  }
}

async function savePurposeModels(): Promise<void> {
  formError.value = null
  const models: Partial<Record<ModelPurpose, string>> = {}
  for (const purpose of Object.keys(EMPTY_PURPOSE_MODELS) as ModelPurpose[]) {
    const model = purposeModels[purpose].trim()
    if (model) {
      models[purpose] = model
    }
  }
  try {
    await store.savePurposes({ models })
    syncPurposeModels(store.config)
    toast.success('用途模型已保存')
  } catch (err) {
    formError.value = err
  }
}

function buildPayload(): ModelConfigPayload {
  const payload: ModelConfigPayload = {}
  for (const key of ['llm', 'embedding'] as ProviderKey[]) {
    fieldErrors[key] = ''
    const values = [forms[key].apiBase, forms[key].apiKey, forms[key].model].map((v) => v.trim())
    const filled = values.filter((value) => value !== '').length
    if (filled === 0) {
      continue
    }
    if (filled < 3) {
      fieldErrors[key] = '请完整填写 API 地址、密钥与模型名'
      continue
    }
    if (key === 'llm') {
      payload.llm_api_base = values[0]
      payload.llm_api_key = values[1]
      payload.llm_model = values[2]
    } else {
      payload.embedding_api_base = values[0]
      payload.embedding_api_key = values[1]
      payload.embedding_model = values[2]
    }
  }
  return payload
}

function includedProviders(payload: ModelConfigPayload): Set<ProviderKey> {
  const included = new Set<ProviderKey>()
  if (payload.llm_api_base) {
    included.add('llm')
  }
  if (payload.embedding_api_base) {
    included.add('embedding')
  }
  return included
}

async function doSave(payload: ModelConfigPayload): Promise<void> {
  clearDialogOpen.value = false
  formError.value = null
  try {
    await store.save(payload)
    resetForms()
    toast.success('模型配置已保存')
  } catch (err) {
    formError.value = err
  }
}

async function handleSave(): Promise<void> {
  formError.value = null
  const payload = buildPayload()
  if (fieldErrors.llm || fieldErrors.embedding) {
    return
  }
  if (Object.keys(payload).length === 0) {
    formError.value = {
      status: 'error',
      error_code: 'VALIDATION_ERROR',
      message: '请至少完整填写一个提供方，或使用「恢复服务端默认」。',
    }
    return
  }
  const included = includedProviders(payload)
  const cleared = cards.value.filter((card) => card.source === 'user' && !included.has(card.key))
  if (cleared.length > 0) {
    pendingPayload.value = payload
    clearMessage.value = `保存后将清除以下提供方的自备配置并回退服务端默认：${cleared
      .map((card) => card.title)
      .join('、')}。确定继续？`
    clearDialogOpen.value = true
    return
  }
  await doSave(payload)
}

async function confirmReset(): Promise<void> {
  formError.value = null
  try {
    await store.clear()
    loadError.value = null
    resetForms()
    syncPurposeModels(store.config)
    toast.success('已恢复服务端默认配置')
  } catch (err) {
    formError.value = err
  } finally {
    resetDialogOpen.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.model-settings {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.model-settings__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
  gap: var(--space-4);
}

.provider-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  backdrop-filter: var(--glass-blur);
  -webkit-backdrop-filter: var(--glass-blur);
}

.purpose-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.purpose-card__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: var(--space-3);
}

.provider-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.provider-card__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
}

.provider-card__hint {
  margin: 4px 0 0;
  color: var(--color-muted-foreground);
  font-size: 0.85rem;
}

.provider-card__source {
  flex-shrink: 0;
  padding: 0 0.6rem;
  border-radius: var(--radius-pill);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.6rem;
  border: 1px solid var(--color-border);
  color: var(--color-muted-foreground);
  background: var(--color-surface-strong);
}

.provider-card__source--user {
  color: var(--color-primary-strong);
  border-color: rgba(59, 111, 212, 0.35);
  background: rgba(59, 111, 212, 0.12);
}

.provider-card__source--global {
  color: #0f766e;
  border-color: rgba(13, 148, 136, 0.32);
  background: rgba(13, 148, 136, 0.12);
}

.provider-card__current {
  display: grid;
  gap: 6px;
  margin: 0;
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border-radius: var(--radius-md);
}

.provider-card__current div {
  display: flex;
  gap: var(--space-2);
  font-size: 0.85rem;
}

.provider-card__current dt {
  flex: 0 0 4.5rem;
  color: var(--color-muted-foreground);
}

.provider-card__current dd {
  margin: 0;
  color: var(--color-foreground);
  overflow-wrap: anywhere;
}

.provider-card__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.provider-card__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}

.model-settings__note {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.85rem;
}

.model-settings__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
