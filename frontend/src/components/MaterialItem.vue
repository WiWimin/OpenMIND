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

    <AppButton variant="ghost" @click="emit('delete', material.material_id)">删除</AppButton>
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/AppButton.vue'
import AppTag from '@/components/AppTag.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import type { Material } from '@/types/material'
import { materialStatusMeta } from '@/utils/statusLabels'

const props = defineProps<{ material: Material }>()
const emit = defineEmits<{ delete: [materialId: string] }>()

const status = computed(() => materialStatusMeta[props.material.processing_status])
</script>

<style scoped>
.material-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.material-item__main {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.material-item__name {
  font-weight: 500;
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
</style>
