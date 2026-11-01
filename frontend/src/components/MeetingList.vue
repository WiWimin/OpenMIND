<template>
  <div class="meeting-table">
    <div class="meeting-table__head" aria-hidden="true">
      <span />
      <span>会议</span>
      <span>时间</span>
      <span>状态</span>
      <span>操作</span>
    </div>

    <ul class="meeting-list">
      <li v-for="meeting in items" :key="meeting.meeting_id" class="meeting-list__item">
        <MeetingCard :meeting="meeting" @select="emit('select', $event)" />
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import MeetingCard from '@/components/MeetingCard.vue'
import type { Meeting } from '@/types/meeting'

defineProps<{ items: Meeting[] }>()
const emit = defineEmits<{ select: [meetingId: string] }>()
</script>

<style scoped>
.meeting-table {
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.meeting-table__head {
  display: grid;
  grid-template-columns: 2.5rem minmax(0, 1fr) 10rem 7.5rem 4.5rem;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--color-surface-strong);
  border-bottom: 1px solid var(--color-border);
}

.meeting-list {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.meeting-list__item:last-child :deep(.meeting-card) {
  border-bottom: 0;
}

@media (max-width: 720px) {
  .meeting-table__head {
    display: none;
  }
}
</style>
