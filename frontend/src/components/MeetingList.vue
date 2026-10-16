<template>
  <ul class="meeting-list">
    <li v-for="meeting in items" :key="meeting.meeting_id" class="meeting-list__item">
      <MeetingCard :meeting="meeting" @select="emit('select', $event)" />
    </li>
  </ul>
</template>

<script setup lang="ts">
import MeetingCard from '@/components/MeetingCard.vue'
import type { Meeting } from '@/types/meeting'

defineProps<{ items: Meeting[] }>()
const emit = defineEmits<{ select: [meetingId: string] }>()
</script>

<style scoped>
.meeting-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.meeting-list__item {
  display: flex;
}

.meeting-list__item > * {
  flex: 1;
}
</style>
