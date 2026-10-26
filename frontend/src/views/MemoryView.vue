<template>
  <section class="memory-view">
    <PageHeader
      title="记忆中心"
      description="维护你的角色、工作场景、表达偏好和默认纪要模板。记忆只用于调整表达与重点，不覆盖事实、来源或业务规则。"
    />

    <LoadingSpinner v-if="loading" class="memory-view__state" />
    <ErrorMessage v-else-if="loadError" :error="loadError" retryable @retry="load" />

    <template v-else>
      <form class="memory-form" @submit.prevent="save">
        <FormField id="memory-role" v-model="role" label="职业 / 角色" placeholder="例如：产品经理" />
        <FormTextarea
          id="memory-scenarios"
          v-model="workScenarios"
          label="工作场景"
          :rows="3"
          placeholder="例如：B2B SaaS 产品规划、跨团队项目推进"
        />
        <FormTextarea
          id="memory-style"
          v-model="communicationStyle"
          label="表达偏好"
          :rows="3"
          placeholder="例如：结论先行、简洁、少用术语"
        />
        <FormSelect
          id="memory-minutes-template"
          v-model="preferredTemplate"
          label="默认纪要模板"
          :options="templateOptions"
        />

        <ErrorMessage v-if="formError" :error="formError" />

        <div class="memory-form__actions">
          <AppButton type="submit" :loading="saving">保存记忆</AppButton>
          <AppButton variant="ghost" :disabled="saving" @click="confirmClearOpen = true">
            清除记忆
          </AppButton>
        </div>

        <p v-if="updatedAt" class="memory-form__updated">上次更新：{{ updatedAt }}</p>
      </form>
    </template>

    <ConfirmDialog
      :open="confirmClearOpen"
      title="清除记忆"
      message="将删除角色、工作场景、表达偏好和默认模板，确定继续吗？"
      confirm-text="清除"
      danger
      :loading="clearing"
      @confirm="clear"
      @cancel="confirmClearOpen = false"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import * as memoryApi from '@/api/memory'
import AppButton from '@/components/AppButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorMessage from '@/components/ErrorMessage.vue'
import FormField from '@/components/FormField.vue'
import FormSelect from '@/components/FormSelect.vue'
import FormTextarea from '@/components/FormTextarea.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import PageHeader from '@/components/PageHeader.vue'
import { useToast } from '@/composables/useToast'
import type { MinutesTemplate } from '@/types/minutes'
import type { UserMemory } from '@/types/memory'
import { formatDateTime } from '@/utils/datetime'

const templateOptions = [
  { value: '', label: '使用标准模板' },
  { value: 'standard', label: '标准纪要' },
  { value: 'concise', label: '简洁记录' },
  { value: 'task_list', label: '任务清单' },
]

const toast = useToast()
const loading = ref(false)
const saving = ref(false)
const clearing = ref(false)
const loadError = ref<unknown>(null)
const formError = ref<unknown>(null)
const confirmClearOpen = ref(false)
const role = ref('')
const workScenarios = ref('')
const communicationStyle = ref('')
const preferredTemplate = ref('')
const updatedAt = ref('')

function applyMemory(memory: UserMemory): void {
  role.value = memory.role
  workScenarios.value = memory.work_scenarios
  communicationStyle.value = memory.communication_style
  preferredTemplate.value = memory.preferred_minutes_template ?? ''
  updatedAt.value = memory.updated_at ? formatDateTime(memory.updated_at) : ''
}

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    applyMemory(await memoryApi.getMemory())
  } catch (caught) {
    loadError.value = caught
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  saving.value = true
  formError.value = null
  try {
    const memory = await memoryApi.saveMemory({
      role: role.value.trim(),
      work_scenarios: workScenarios.value.trim(),
      communication_style: communicationStyle.value.trim(),
      preferred_minutes_template: (preferredTemplate.value || null) as MinutesTemplate | null,
    })
    applyMemory(memory)
    toast.success('记忆已保存')
  } catch (caught) {
    formError.value = caught
  } finally {
    saving.value = false
  }
}

async function clear(): Promise<void> {
  clearing.value = true
  formError.value = null
  try {
    await memoryApi.clearMemory()
    applyMemory({
      role: '',
      work_scenarios: '',
      communication_style: '',
      preferred_minutes_template: null,
      updated_at: null,
    })
    confirmClearOpen.value = false
    toast.success('记忆已清除')
  } catch (caught) {
    formError.value = caught
  } finally {
    clearing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.memory-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.memory-view__state {
  display: flex;
  justify-content: center;
  padding: var(--space-5);
}

.memory-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 44rem;
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.memory-form__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.memory-form__updated {
  margin: 0;
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}
</style>
