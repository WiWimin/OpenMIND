<template>
  <ul class="material-list">
    <MaterialItem
      v-for="material in items"
      :key="material.material_id"
      :material="material"
      @delete="emit('delete', $event)"
      @view="emit('view', $event)"
    />
  </ul>
</template>

<script setup lang="ts">
import MaterialItem from '@/components/MaterialItem.vue'
import type { Material } from '@/types/material'

defineProps<{ items: Material[] }>()
const emit = defineEmits<{ delete: [materialId: string]; view: [materialId: string] }>()
</script>

<style scoped>
.material-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}
</style>
