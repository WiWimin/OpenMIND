<template>
  <button class="meeting-card" type="button" @click="emit('select', meeting.meeting_id)">
    <span class="meeting-card__head">
      <span class="meeting-card__title">{{ meeting.title }}</span>
      <StatusBadge :label="status.label" :tone="status.tone" />
    </span>
    <span v-if="meeting.topic" class="meeting-card__topic">{{ meeting.topic }}</span>
    <span class="meeting-card__time">{{ time }}</span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import StatusBadge from '@/components/StatusBadge.vue'
import type { Meeting } from '@/types/meeting'
import { formatDateTime } from '@/utils/datetime'
import { meetingStatusMeta } from '@/utils/statusLabels'

const props = defineProps<{ meeting: Meeting }>()
const emit = defineEmits<{ select: [meetingId: string] }>()

const status = computed(() => meetingStatusMeta[props.meeting.status])
const time = computed(() => formatDateTime(props.meeting.meeting_time))
</script>

<style scoped>
.meeting-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  text-align: left;
  font: inherit;
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.meeting-card:hover {
  border-color: var(--color-primary);
}

.meeting-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.meeting-card__title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-foreground);
}

.meeting-card__topic {
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
}

.meeting-card__time {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}
</style>
