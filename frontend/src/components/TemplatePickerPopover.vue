<template>
  <button
    type="button"
    class="template-picker__trigger"
    :class="{ 'template-picker__trigger--active': Boolean(selectedTemplateId) }"
    :title="triggerTitle"
    :aria-label="triggerTitle"
    :disabled="disabled"
    @click="navigate"
  >
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
      <path
        d="M8 4.5h8M8 4.5A1.5 1.5 0 0 0 6.5 6v13A1.5 1.5 0 0 0 8 20.5h8a1.5 1.5 0 0 0 1.5-1.5V6A1.5 1.5 0 0 0 16 4.5"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
      />
      <path
        d="M9 9.5h6M9 13h6M9 16.5h3.5"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
      />
    </svg>
    <span v-if="selectedTemplateId" class="template-picker__dot" aria-hidden="true" />
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { ROUTE_NAMES } from '@/constants/routeNames'

const props = withDefaults(
  defineProps<{
    disabled?: boolean
    selected?: string
    meetingId?: string
    returnTo?: 'preprocess' | 'minutes'
  }>(),
  { disabled: false, selected: '', meetingId: '', returnTo: 'preprocess' },
)

const router = useRouter()

const selectedTemplateId = computed(() => props.selected)

const triggerTitle = computed(() =>
  selectedTemplateId.value ? '已选择输出模板，点击管理模板' : '选择输出模板',
)

// 点击跳转模板管理页，携带回跳目标；在管理页点「使用」后原路返回并预选模板
function navigate(): void {
  void router.push({
    name: ROUTE_NAMES.templateManage,
    query: {
      returnTo: props.returnTo,
      ...(props.meetingId ? { meetingId: props.meetingId } : {}),
    },
  })
}
</script>

<style scoped>
.template-picker {
  display: inline-flex;
}

.template-picker__trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: var(--color-muted-foreground);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: 50%;
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.template-picker__trigger:hover:not(:disabled),
.template-picker__trigger--active {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-color: rgba(21, 94, 239, 0.28);
}

.template-picker__trigger:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.template-picker__dot {
  position: absolute;
  top: -1px;
  right: -1px;
  width: 0.5rem;
  height: 0.5rem;
  background: var(--color-primary);
  border: 1.5px solid #ffffff;
  border-radius: 50%;
}
</style>
