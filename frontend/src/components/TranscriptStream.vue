<template>
  <ul class="stream" aria-label="转写内容流">
    <li v-for="entry in entries" :key="entry.key" class="stream__row">
      <span class="stream__rail" aria-hidden="true">
        <span
          class="stream__dot"
          :class="{ 'stream__dot--selected': isSelected(entry.key) }"
        />
      </span>
      <span class="stream__time">{{ entry.time }}</span>
      <div
        class="stream__body"
        :class="[
          markerClass(entry.marker),
          {
            'stream__body--selected': isSelected(entry.key),
            'stream__body--static': !selectable,
          },
        ]"
        :role="selectable ? 'button' : undefined"
        :aria-pressed="selectable ? isSelected(entry.key) : undefined"
        :tabindex="selectable ? 0 : undefined"
        @click="selectable && emit('toggle-select', entry.key)"
        @keydown.enter.prevent="selectable && emit('toggle-select', entry.key)"
        @keydown.space.prevent="selectable && emit('toggle-select', entry.key)"
      >
        <div v-if="entry.tag" class="stream__meta">
          <span class="stream__tag">{{ entry.tag }}</span>
        </div>
        <p class="stream__text">{{ entry.text }}</p>
        <p v-if="entry.error" class="stream__error">
          <span>{{ entry.error }}</span>
          <button
            v-if="canRetrySegment && entry.seq !== null"
            type="button"
            class="stream__retry"
            @click.stop="emit('retry-segment', entry.seq)"
          >
            重试本段
          </button>
        </p>
        <div
          v-if="entry.kind === 'record' && $slots['record-actions']"
          class="stream__record-actions"
          @click.stop
          @keydown.enter.stop
          @keydown.space.stop
        >
          <slot name="record-actions" :entry="entry" />
        </div>
      </div>
    </li>
  </ul>
</template>

<script setup lang="ts">
import type { TranscriptEntry } from '@/types/audio'

const props = withDefaults(
  defineProps<{
    entries: TranscriptEntry[]
    selectedKeys?: string[]
    /** 是否允许点击选中（归档会议或已确认音频时关闭） */
    selectable?: boolean
    /** 是否显示失败分段的“重试本段”（仅实时会话进行中） */
    canRetrySegment?: boolean
  }>(),
  {
    selectedKeys: () => [],
    selectable: true,
    canRetrySegment: false,
  },
)

const emit = defineEmits<{
  'toggle-select': [key: string]
  'retry-segment': [seq: number]
}>()

function isSelected(key: string): boolean {
  return props.selectedKeys.includes(key)
}

function markerClass(marker: TranscriptEntry['marker']): string {
  if (marker === 'highlight') {
    return 'stream__body--highlight'
  }
  if (marker === 'decision') {
    return 'stream__body--decision'
  }
  if (marker === 'question') {
    return 'stream__body--question'
  }
  return ''
}
</script>

<style scoped>
.stream {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

/* 左侧时间线：贯穿各行的竖线由行内 rail 串联 */
.stream__row {
  display: grid;
  grid-template-columns: 14px 3.25rem minmax(0, 1fr);
  column-gap: var(--space-3);
  align-items: stretch;
}

.stream__rail {
  display: flex;
  justify-content: center;
  padding-top: 0.55rem;
  background: linear-gradient(
    to bottom,
    transparent 0,
    transparent 0.55rem,
    var(--color-border) 0.55rem,
    var(--color-border) calc(100% - 0.25rem),
    transparent calc(100% - 0.25rem)
  );
}

.stream__row:first-child .stream__rail {
  background: linear-gradient(
    to bottom,
    transparent 0,
    transparent 0.55rem,
    var(--color-border) 0.55rem
  );
}

.stream__row:last-child .stream__rail {
  background: linear-gradient(
    to bottom,
    transparent 0,
    transparent 0.55rem,
    var(--color-border) 0.55rem,
    var(--color-border) 55%
  );
}

.stream__dot {
  width: 9px;
  height: 9px;
  flex: 0 0 auto;
  background: var(--color-surface);
  border: 2px solid var(--color-border-strong);
  border-radius: 50%;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast);
}

.stream__dot--selected {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.stream__time {
  padding-top: 0.3rem;
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.stream__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.stream__body--static {
  cursor: default;
}

.stream__body:hover {
  border-color: var(--color-border-strong);
}

.stream__body--selected {
  border-color: rgba(21, 94, 239, 0.55);
  box-shadow: 0 0 0 1px rgba(21, 94, 239, 0.35);
}

/* 标记高亮：重点=黄、决议=蓝、疑问=紫（贴近设计稿底色） */
.stream__body--highlight {
  background: rgba(250, 204, 21, 0.18);
  border-color: rgba(202, 138, 4, 0.32);
}

.stream__body--decision {
  background: rgba(56, 130, 246, 0.1);
  border-color: rgba(21, 94, 239, 0.3);
}

.stream__body--question {
  background: rgba(139, 92, 246, 0.1);
  border-color: rgba(139, 92, 246, 0.3);
}

.stream__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.stream__tag {
  padding: 0.1rem 0.5rem;
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 600;
  background: var(--color-surface-muted);
  border-radius: var(--radius-pill);
}

.stream__text {
  margin: 0;
  color: var(--color-foreground);
  font-size: 0.875rem;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.stream__error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0;
  color: var(--color-down);
  font-size: 0.75rem;
}

.stream__retry {
  padding: 0.05rem 0.55rem;
  color: var(--color-primary-strong);
  font: inherit;
  font-size: 0.6875rem;
  font-weight: 600;
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.25);
  border-radius: var(--radius-pill);
  cursor: pointer;
}

.stream__record-actions {
  display: flex;
  gap: var(--space-2);
}
</style>
