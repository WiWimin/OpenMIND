<template>
  <button class="meeting-card" type="button" @click="emit('select', meeting.meeting_id)">
    <span class="meeting-card__icon" aria-hidden="true">
      <NavIcon name="calendar" :size="16" />
    </span>

    <span class="meeting-card__body">
      <span class="meeting-card__title">{{ meeting.title }}</span>
      <span v-if="meeting.topic" class="meeting-card__topic">{{ meeting.topic }}</span>
    </span>

    <span class="meeting-card__time">{{ time }}</span>

    <span class="meeting-card__status">
      <StatusBadge :label="status.label" :tone="status.tone" />
    </span>

    <span class="meeting-card__enter">
      查看
      <NavIcon name="chevron" :size="13" />
    </span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import NavIcon from '@/components/NavIcon.vue'
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
  display: grid;
  grid-template-columns: 2.5rem minmax(0, 1fr) 10rem 7.5rem 4.5rem;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  color: inherit;
  text-align: left;
  font: inherit;
  background: transparent;
  border: 0;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.meeting-card:hover {
  background: var(--color-surface-muted);
}

.meeting-card:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: -2px;
}

.meeting-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.1rem;
  height: 2.1rem;
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  border-radius: 50%;
}

.meeting-card__body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.meeting-card__title {
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meeting-card__topic {
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meeting-card__time {
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.meeting-card__status {
  display: flex;
  justify-content: flex-start;
}

.meeting-card__enter {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  color: var(--color-primary-strong);
  font-size: 0.75rem;
  font-weight: 600;
}

@media (max-width: 720px) {
  .meeting-card {
    grid-template-columns: 2.1rem minmax(0, 1fr) auto;
    gap: var(--space-2);
    padding: var(--space-3);
  }

  .meeting-card__time,
  .meeting-card__enter {
    display: none;
  }
}
</style>
