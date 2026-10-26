<template>
  <li class="material-item">
    <div class="material-item__main">
      <span class="material-item__name">{{ material.file_name }}</span>
      <div class="material-item__meta">
        <AppTag :label="material.type" />
        <AppTag v-if="material.source" :label="material.source" :title="material.source" />
        <StatusBadge :label="status.label" :tone="status.tone" />
      </div>
      <p v-if="material.parse_error" class="material-item__error">{{ material.parse_error }}</p>
    </div>

    <div class="material-item__actions">
      <AppButton variant="ghost" @click="emit('view', material.material_id)">查看详情</AppButton>
      <AppButton
        v-if="!readonly"
        variant="ghost"
        @click="emit('delete', material.material_id)"
      >
        删除
      </AppButton>
    </div>
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppTag from '@/components/AppTag.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import type { Material } from '@/types/material'
import { materialStatusMeta } from '@/utils/statusLabels'

const props = withDefaults(
  defineProps<{ material: Material; readonly?: boolean }>(),
  { readonly: false },
)
const emit = defineEmits<{ delete: [materialId: string]; view: [materialId: string] }>()

const status = computed(() => materialStatusMeta[props.material.processing_status])
</script>

<style scoped>
.material-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition: border-color var(--transition-fast);
}

.material-item:hover {
  border-color: var(--color-border-strong);
}

.material-item__main {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.material-item__name {
  font-weight: 600;
  color: var(--color-foreground);
  overflow-wrap: anywhere;
}

.material-item__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.material-item__error {
  margin: 0;
  color: var(--color-down);
  font-size: 0.8125rem;
}

.material-item__actions {
  display: flex;
  flex: 0 0 auto;
  gap: var(--space-1);
}
</style>
