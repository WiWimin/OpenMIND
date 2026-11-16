<template>
  <button
    type="button"
    class="meeting-card"
    :class="`meeting-card--${meeting.status}`"
    :aria-label="`打开会议「${meeting.title}」`"
    @click="$emit('open', meeting)"
  >
    <!-- 状态色标 -->
    <span class="meeting-card__bar" aria-hidden="true" />

    <div class="meeting-card__body">
      <div class="meeting-card__head">
        <h3 class="meeting-card__title">{{ meeting.title }}</h3>
        <StatusBadge :label="meta.label" :tone="meta.tone" />
      </div>

      <p class="meeting-card__topic">{{ meeting.topic || '未填写会议主题' }}</p>

      <div class="meeting-card__meta">
        <span class="meeting-card__item">
          <NavIcon name="calendar" :size="13" aria-hidden="true" />
          {{ timeLabel }}
        </span>
        <span class="meeting-card__item">
          <NavIcon name="file" :size="13" aria-hidden="true" />
          {{ statsLabel }}
        </span>
        <span v-if="meeting.has_minutes" class="meeting-card__minutes">
          <NavIcon name="check" :size="12" aria-hidden="true" />
          有纪要
        </span>
      </div>
    </div>

    <span class="meeting-card__go" aria-hidden="true">
      <NavIcon name="chevron" :size="15" />
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

const props = defineProps<{
  meeting: Meeting
}>()

defineEmits<{ open: [meeting: Meeting] }>()

const meta = computed(() => meetingStatusMeta[props.meeting.status])

const timeLabel = computed(() =>
  props.meeting.meeting_time ? formatDateTime(props.meeting.meeting_time) : '时间未设置',
)

/** 资料统计：纪要标签之外的资料/记录/录音数量 */
const statsLabel = computed(() => {
  const parts: string[] = []
  const { material_count: materials = 0, record_count: records = 0, audio_count: audio = 0 } =
    props.meeting
  if (materials > 0) parts.push(`${materials} 份资料`)
  if (records > 0) parts.push(`${records} 条记录`)
  if (audio > 0) parts.push(`${audio} 段录音`)
  return parts.length > 0 ? parts.join(' · ') : '暂无资料'
})
</script>

<style scoped>
.meeting-card {
  position: relative;
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-3) var(--space-3) 0;
  overflow: hidden;
  color: inherit;
  font: inherit;
  text-align: left;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.meeting-card:hover {
  border-color: var(--color-border-strong, var(--color-border));
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.meeting-card:focus-visible {
  outline: none;
  box-shadow: var(--focus-ring);
}

/* 状态色标：左缘 4px 竖条 */
.meeting-card__bar {
  flex: 0 0 auto;
  align-self: stretch;
  width: 4px;
  margin: calc(-1 * var(--space-3)) 0 calc(-1 * var(--space-3)) calc(-1 * var(--space-3));
  background: var(--color-primary);
  border-radius: var(--radius-md) 0 0 var(--radius-md);
}

.meeting-card--archived .meeting-card__bar {
  background: var(--color-border-strong, #94a3b8);
}

.meeting-card__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.meeting-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.meeting-card__title {
  margin: 0;
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meeting-card__topic {
  margin: 0;
  overflow: hidden;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meeting-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.meeting-card__item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.meeting-card__minutes {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  color: var(--color-ok, #047857);
  font-size: 0.6875rem;
  font-weight: 600;
  background: rgba(5, 150, 105, 0.1);
  border: 1px solid rgba(5, 150, 105, 0.22);
  border-radius: var(--radius-pill);
}

.meeting-card__go {
  display: inline-flex;
  align-items: center;
  align-self: center;
  flex: 0 0 auto;
  color: var(--color-muted-foreground);
  opacity: 0;
  transform: translateX(-4px);
  transition:
    opacity var(--transition-fast),
    transform var(--transition-fast);
}

.meeting-card:hover .meeting-card__go,
.meeting-card:focus-visible .meeting-card__go {
  opacity: 1;
  transform: translateX(0);
}
</style>
