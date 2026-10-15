<template>
  <button class="meeting-card" type="button" @click="emit('select', meeting.meeting_id)">
    <span class="meeting-card__head">
      <span class="meeting-card__title">{{ meeting.title }}</span>
      <StatusBadge :label="status.label" :tone="status.tone" />
    </span>
    <span v-if="meeting.topic" class="meeting-card__topic">{{ meeting.topic }}</span>
    <span class="meeting-card__time">{{ time }}</span>
    <span class="meeting-card__enter" aria-hidden="true">进入会议 →</span>
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
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  padding: var(--space-4);
  overflow: hidden;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  text-align: left;
  font: inherit;
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.meeting-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: linear-gradient(90deg, var(--color-accent), var(--color-primary));
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.meeting-card:hover {
  transform: translateY(-2px);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-glow);
}

.meeting-card:hover::before {
  opacity: 1;
}

.meeting-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.meeting-card__title {
  font-family: var(--font-display);
  font-size: 1.0625rem;
  font-weight: 600;
  color: var(--color-foreground);
}

.meeting-card__topic {
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
}

.meeting-card__time {
  margin-top: var(--space-1);
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
}

.meeting-card__enter {
  margin-top: var(--space-1);
  color: var(--color-primary-strong);
  font-size: 0.8125rem;
  font-weight: 600;
  opacity: 0;
  transform: translateX(-4px);
  transition:
    opacity var(--transition-fast),
    transform var(--transition-fast);
}

.meeting-card:hover .meeting-card__enter,
.meeting-card:focus-visible .meeting-card__enter {
  opacity: 1;
  transform: translateX(0);
}
</style>
