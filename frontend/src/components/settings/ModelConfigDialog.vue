<template>
  <AppModal :open="open" title="模型配置" @close="emit('close')">
    <div class="model-dialog">
      <LoadingSpinner v-if="store.loading && !store.config" class="model-dialog__state" />
      <ErrorMessage v-else-if="loadError" :error="loadError" retryable @retry="loadConfig" />

      <div v-else class="model-dialog__main">
        <div class="form-field">
          <label class="form-field__label" for="model-provider">提供商</label>
          <select id="model-provider" v-model="providerId" class="form-field__select">
            <option value="" disabled>请选择提供商</option>
            <option v-for="preset in MODEL_PROVIDER_PRESETS" :key="preset.id" :value="preset.id">
              {{ preset.name }}
            </option>
            <option :value="CUSTOM_PROVIDER_ID">自定义（OpenAI 兼容）</option>
          </select>
          <p v-if="activePreset?.hint" class="form-field__hint">密钥获取：{{ activePreset.hint }}</p>
        </div>

        <FormField
          id="model-api-key"
          v-model="apiKey"
          label="API Key"
          type="password"
          placeholder="sk-..."
        />

        <template v-if="isCustom">
          <FormField
            id="model-custom-base"
            v-model="customApiBase"
            label="API 地址"
            placeholder="https://api.example.com/v1"
          />
          <FormField
            id="model-custom-model"
            v-model="customModel"
            label="默认模型名"
            placeholder="model-name"
          />
        </template>

        <p class="model-dialog__note">
          保存后即可在会话时通过输入框旁的模型图标切换该提供商的模型；密钥加密存库，不会回显明文。
        </p>

        <p v-if="mainError" class="model-dialog__error" role="alert">{{ mainError }}</p>

        <dl v-if="store.config" class="model-dialog__current">
          <div>
            <dt>大模型</dt>
            <dd>{{ llmSummary }}</dd>
          </div>
          <div>
            <dt>向量模型</dt>
            <dd>{{ embeddingSummary }}</dd>
          </div>
        </dl>
      </div>
    </div>

    <template #footer>
      <AppButton
        variant="ghost"
        :disabled="store.saving"
        class="model-dialog__reset"
        @click="resetDialogOpen = true"
      >
        恢复服务端默认
      </AppButton>
      <AppButton :loading="store.saving" @click="saveMain">保存配置</AppButton>
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
      title="确认保存"
      :message="clearMessage"
      confirm-text="继续保存"
      danger
      :loading="store.saving"
      @confirm="doSave(pendingPayload)"
      @cancel="clearDialogOpen = false"
    />
  </AppModal>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppModal from '@/components/AppModal.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import { useToast } from '@/composables/useToast'
import {
  CUSTOM_PROVIDER_ID,
  MODEL_PROVIDER_PRESETS,
  findPresetByApiBase,
} from '@/constants/modelProviders'
import { useModelConfigStore } from '@/stores/modelConfig'
import type { ModelConfigPayload, ModelConfigSource } from '@/types/modelConfig'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const SOURCE_LABELS: Record<ModelConfigSource, string> = {
  user: '用户配置',
  global: '服务端默认',
  none: '未配置',
}

const store = useModelConfigStore()
const toast = useToast()

const providerId = ref('')
const apiKey = ref('')
const customApiBase = ref('')
const customModel = ref('')
const mainError = ref('')
const loadError = ref<unknown>(null)
const resetDialogOpen = ref(false)
const clearDialogOpen = ref(false)
const clearMessage = ref('')
const pendingPayload = ref<ModelConfigPayload>({})

const isCustom = computed(() => providerId.value === CUSTOM_PROVIDER_ID)
const activePreset = computed(
  () => MODEL_PROVIDER_PRESETS.find((preset) => preset.id === providerId.value) ?? null,
)

const llmSummary = computed(() => {
  const config = store.config
  if (!config || config.llm_source === 'none') {
    return '未配置'
  }
  return `${config.llm_model || '默认模型'}（${SOURCE_LABELS[config.llm_source]}）`
})

const embeddingSummary = computed(() => {
  const config = store.config
  if (!config || config.embedding_source === 'none') {
    return '未配置'
  }
  return `${config.embedding_model || '默认模型'}（${SOURCE_LABELS[config.embedding_source]}）`
})

function resetMainForm(): void {
  // 依据已保存配置回填提供商选择
  const config = store.config
  apiKey.value = ''
  mainError.value = ''
  if (config?.llm_source === 'user' && config.llm_api_base) {
    const preset = findPresetByApiBase(config.llm_api_base)
    providerId.value = preset?.id ?? CUSTOM_PROVIDER_ID
    if (!preset) {
      customApiBase.value = config.llm_api_base
      customModel.value = config.llm_model
    }
  }
}

async function loadConfig(): Promise<void> {
  loadError.value = null
  try {
    await store.load()
  } catch (err) {
    loadError.value = err
  }
}

function buildMainPayload(): ModelConfigPayload | null {
  mainError.value = ''
  const key = apiKey.value.trim()
  if (!providerId.value) {
    mainError.value = '请选择提供商'
    return null
  }
  if (!key) {
    mainError.value = '请输入 API Key'
    return null
  }
  if (isCustom.value) {
    const base = customApiBase.value.trim()
    const model = customModel.value.trim()
    if (!base || !model) {
      mainError.value = '自定义提供商需要完整填写 API 地址与默认模型名'
      return null
    }
    return { llm_api_base: base, llm_api_key: key, llm_model: model }
  }
  const preset = activePreset.value
  if (!preset) {
    mainError.value = '请选择提供商'
    return null
  }
  // 后端要求三字段齐全：未填模型名时自动采用该提供商的第一个推荐模型
  return {
    llm_api_base: preset.apiBase,
    llm_api_key: key,
    llm_model: preset.models[0] ?? '',
  }
}

async function saveMain(): Promise<void> {
  const payload = buildMainPayload()
  if (!payload) {
    return
  }
  if (store.config?.embedding_source === 'user') {
    pendingPayload.value = payload
    clearMessage.value =
      '你的向量模型为自备配置。本次保存会使其回退服务端默认（密钥无法回读）。确定继续？'
    clearDialogOpen.value = true
    return
  }
  await doSave(payload)
}

async function doSave(payload: ModelConfigPayload): Promise<void> {
  clearDialogOpen.value = false
  mainError.value = ''
  try {
    await store.save(payload)
    apiKey.value = ''
    resetMainForm()
    toast.success('模型配置已保存')
  } catch (err) {
    if (typeof err === 'object' && err !== null && 'message' in err) {
      mainError.value = String((err as { message: unknown }).message)
    } else {
      mainError.value = '保存失败，请稍后重试'
    }
  }
}

async function confirmReset(): Promise<void> {
  mainError.value = ''
  try {
    await store.clear()
    loadError.value = null
    providerId.value = ''
    apiKey.value = ''
    customApiBase.value = ''
    customModel.value = ''
    toast.success('已恢复服务端默认配置')
  } catch (err) {
    if (typeof err === 'object' && err !== null && 'message' in err) {
      mainError.value = String((err as { message: unknown }).message)
    } else {
      mainError.value = '操作失败，请稍后重试'
    }
  } finally {
    resetDialogOpen.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      void loadConfig().then(() => {
        resetMainForm()
      })
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.model-dialog {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: var(--space-1);
}

.model-dialog__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

.model-dialog__main {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
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

.model-dialog__note {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  line-height: 1.6;
}

.model-dialog__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}

.model-dialog__current {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
  margin: 0;
  padding: var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.model-dialog__current dt {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 600;
}

.model-dialog__current dd {
  margin: 2px 0 0;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  word-break: break-all;
}

.model-dialog__reset {
  margin-right: auto;
}
</style>
