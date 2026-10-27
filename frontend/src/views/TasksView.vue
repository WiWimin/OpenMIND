<template>
  <section class="tasks-view">
    <PageHeader title="我的任务" description="跟进由已确认行动项转换而成的个人任务。" />
    <div class="tasks-view__panel">
      <TaskSection />
    </div>
  </section>
</template>

<script setup lang="ts">
import PageHeader from '@/components/PageHeader.vue'
import TaskSection from '@/components/TaskSection.vue'
</script>

<style scoped>
.tasks-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.tasks-view__panel {
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
</style>
