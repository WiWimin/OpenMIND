<template>
  <section class="agent-reasoning" :class="{ 'agent-reasoning--live': live }">
    <button
      type="button"
      class="agent-reasoning__toggle"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="emit('toggle')"
    >
      <svg
        class="agent-reasoning__icon"
        viewBox="0 0 24 24"
        width="14"
        height="14"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M12 3.5 13.6 8.4 18.5 10 13.6 11.6 12 16.5 10.4 11.6 5.5 10 10.4 8.4 12 3.5Z"
          stroke="currentColor"
          stroke-width="1.4"
          stroke-linejoin="round"
        />
        <path
          d="M18.4 15.4 19.1 17.5 21.2 18.2 19.1 18.9 18.4 21 17.7 18.9 15.6 18.2 17.7 17.5 18.4 15.4Z"
          fill="currentColor"
        />
      </svg>
      <span class="agent-reasoning__label">{{ label }}</span>
      <span v-if="live" class="agent-reasoning__pulse" aria-hidden="true" />
      <svg
        class="agent-reasoning__chevron"
        :class="{ 'agent-reasoning__chevron--open': open }"
        viewBox="0 0 24 24"
        width="14"
        height="14"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="m7 10 5 5 5-5"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>

    <div
      v-show="open"
      :id="panelId"
      class="agent-reasoning__body"
      role="region"
      aria-label="AI 思考过程"
    >
      <ol v-if="stages.length" class="agent-reasoning__stages">
        <li
          v-for="stage in stages"
          :key="stage.id"
          class="agent-stage"
          :class="`agent-stage--${stage.status}`"
          :aria-current="stage.status === 'running' ? 'step' : undefined"
        >
          <span class="agent-stage__marker" aria-hidden="true">
            <svg
              v-if="stage.status === 'done'"
              viewBox="0 0 24 24"
              width="13"
              height="13"
              fill="none"
            >
              <path
                d="m5 12.5 4.2 4.2L19 7"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
            <svg
              v-else-if="stage.status === 'error'"
              viewBox="0 0 24 24"
              width="13"
              height="13"
              fill="none"
            >
              <path
                d="M12 6.5v7m0 3.2v.1"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
              />
            </svg>
            <span v-else class="agent-stage__spinner" />
          </span>
          <span class="agent-stage__text">
            <span class="agent-stage__label">{{ stage.label }}</span>
            <span v-if="stage.detail" class="agent-stage__detail">{{ stage.detail }}</span>
            <span class="agent-stage__status">{{ statusText(stage.status) }}</span>
          </span>
        </li>
      </ol>

      <template v-if="reasoning">
        <p class="agent-reasoning__caption">模型推理</p>
        <div class="agent-reasoning__text" tabindex="0" aria-label="模型推理内容，可滚动查看">
          {{ reasoning }}
        </div>
      </template>
      <p v-else-if="hint" class="agent-reasoning__hint">{{ hint }}</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ChatTraceStage } from '@/types/chat'

withDefaults(
  defineProps<{
    /** 折叠区域 id，供按钮 aria-controls 关联 */
    panelId: string
    /** 折叠按钮文案，如「思考过程 · 已思考 2.4 秒」 */
    label: string
    open?: boolean
    stages?: ChatTraceStage[]
    reasoning?: string
    /** 无原生推理时的兜底说明 */
    hint?: string
    /** 是否仍在生成（显示呼吸点与动效） */
    live?: boolean
  }>(),
  {
    open: false,
    stages: () => [],
    reasoning: '',
    hint: '',
    live: false,
  },
)

const emit = defineEmits<{ toggle: [] }>()

function statusText(status: ChatTraceStage['status']): string {
  if (status === 'done') {
    return '完成'
  }
  if (status === 'error') {
    return '失败'
  }
  return '进行中'
}
</script>

<style scoped>
.agent-reasoning {
  margin-bottom: var(--space-2);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.agent-reasoning--live {
  border-color: var(--color-border-strong);
}

.agent-reasoning__toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  min-height: 2rem;
  padding: 6px 10px;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.75rem;
  text-align: left;
  background: transparent;
  border: 0;
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.agent-reasoning__toggle:hover {
  color: var(--color-foreground);
  background: var(--color-surface-muted);
}

.agent-reasoning__toggle:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: -2px;
}

.agent-reasoning__icon {
  flex: none;
  color: var(--color-primary);
}

.agent-reasoning__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 生成中的呼吸点：只作装饰，状态文字已在 label 内 */
.agent-reasoning__pulse {
  flex: none;
  width: 6px;
  height: 6px;
  background: var(--color-primary);
  border-radius: 50%;
  animation: agent-reasoning-pulse 1.2s ease-in-out infinite;
}

.agent-reasoning__chevron {
  flex: none;
  color: var(--color-subtle-foreground);
  transition: transform var(--transition-fast);
}

.agent-reasoning__chevron--open {
  transform: rotate(180deg);
}

.agent-reasoning__body {
  padding: var(--space-2) 10px 10px;
  border-top: 1px solid var(--color-border);
}

.agent-reasoning__stages {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0 0 var(--space-2);
  padding: 0;
  list-style: none;
}

.agent-stage {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: var(--space-2);
  align-items: start;
}

.agent-stage__marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-top: 1px;
  color: var(--color-ok);
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: 50%;
}

.agent-stage--error .agent-stage__marker {
  color: var(--color-down);
}

.agent-stage__spinner {
  width: 8px;
  height: 8px;
  border: 1.5px solid var(--color-border-strong);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: agent-reasoning-spin 0.9s linear infinite;
}

.agent-stage__text {
  display: flex;
  flex-wrap: wrap;
  gap: 2px var(--space-2);
  min-width: 0;
  font-size: 0.75rem;
  line-height: 1.5;
}

.agent-stage__label {
  color: var(--color-foreground);
  font-weight: 600;
}

.agent-stage__detail,
.agent-stage__status {
  color: var(--color-muted-foreground);
}

.agent-stage--error .agent-stage__status {
  color: var(--color-down);
}

.agent-reasoning__caption {
  margin: 0 0 4px;
  color: var(--color-subtle-foreground);
  font-size: 0.6875rem;
  letter-spacing: 0.02em;
}

.agent-reasoning__text {
  max-height: 14rem;
  padding: var(--space-2);
  overflow-y: auto;
  color: var(--color-muted-foreground);
  font-family: inherit;
  font-size: 0.75rem;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.agent-reasoning__text:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 1px;
}

.agent-reasoning__hint {
  margin: 0;
  color: var(--color-subtle-foreground);
  font-size: 0.6875rem;
  line-height: 1.6;
}

@keyframes agent-reasoning-pulse {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}

@keyframes agent-reasoning-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .agent-reasoning__pulse,
  .agent-stage__spinner {
    animation: none;
  }

  .agent-reasoning__chevron {
    transition: none;
  }
}

@media (max-width: 720px) {
  .agent-reasoning__text {
    max-height: 10rem;
  }
}
</style>
