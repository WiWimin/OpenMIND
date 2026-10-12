<template>
  <nav class="pagination" aria-label="分页">
    <AppButton variant="ghost" :disabled="page <= 1" @click="go(page - 1)">上一页</AppButton>
    <span class="pagination__info">第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</span>
    <AppButton variant="ghost" :disabled="page >= totalPages" @click="go(page + 1)">
      下一页
    </AppButton>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import AppButton from '@/components/AppButton.vue'

const props = withDefaults(
  defineProps<{
    page: number
    total: number
    pageSize?: number
  }>(),
  {
    pageSize: 20,
  },
)

const emit = defineEmits<{ 'update:page': [page: number] }>()

const totalPages = computed(() =>
  Math.max(1, Math.ceil(props.total / Math.max(1, props.pageSize))),
)

function go(next: number): void {
  if (next < 1 || next > totalPages.value || next === props.page) {
    return
  }
  emit('update:page', next)
}
</script>

<style scoped>
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
}

.pagination__info {
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
}
</style>
