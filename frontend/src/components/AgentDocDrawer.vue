<template>
  <Teleport to="body">
    <div v-if="open" class="doc-drawer" role="dialog" aria-modal="true" :aria-label="label">
      <div class="doc-drawer__backdrop" @click="emit('close')" />
      <aside class="doc-drawer__panel" :class="{ 'doc-drawer__panel--full': isFull }">
        <!-- 头部卡片：左侧文件名，右侧全屏与关闭 -->
        <header class="doc-drawer__card">
          <span class="doc-drawer__title">{{ label }}</span>
          <div class="doc-drawer__controls">
            <button
              type="button"
              class="doc-drawer__expand"
              :aria-label="isFull ? '退出全屏' : '全屏展示与编辑'"
              :title="isFull ? '退出全屏' : '全屏展示与编辑'"
              @click="isFull = !isFull"
            >
              <svg
                v-if="!isFull"
                viewBox="0 0 24 24"
                width="15"
                height="15"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M9 4H4v5M15 4h5v5M9 20H4v-5M15 20h5v-5"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              <svg v-else viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
                <path
                  d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </button>
            <button
              ref="closeEl"
              type="button"
              class="doc-drawer__close"
              aria-label="关闭"
              @click="emit('close')"
            >
              ×
            </button>
          </div>
        </header>

        <div class="doc-drawer__body">
          <ActionItemSection
            v-if="kind === 'action_items'"
            :key="`actions-${meetingId}-${reloadKey}`"
            :meeting-id="meetingId"
          />
          <MinutesSection
            v-else
            :key="`minutes-${meetingId}-${reloadKey}`"
            :meeting-id="meetingId"
          />
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import ActionItemSection from '@/components/ActionItemSection.vue'
import MinutesSection from '@/components/MinutesSection.vue'
import type { MinutesDocMeta } from '@/types/agent'

const props = defineProps<{
  open: boolean
  meetingId: string
  kind: 'minutes' | 'action_items'
  meta?: MinutesDocMeta
}>()

const emit = defineEmits<{ close: [] }>()

const closeEl = ref<HTMLElement | null>(null)
/** 每次打开重新加载，避免展示上一次会话的陈旧内容 */
const reloadKey = ref(0)
/** 全屏：编辑区铺满整个视口 */
const isFull = ref(false)

const label = computed(() => {
  if (props.kind === 'action_items') {
    return '行动项确认'
  }
  return props.meta?.title ? `${props.meta.title} · v${props.meta.version}` : '会议纪要'
})

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape' && props.open) {
    event.stopPropagation()
    emit('close')
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      reloadKey.value += 1
      isFull.value = false
      document.addEventListener('keydown', onKeydown)
      document.body.style.overflow = 'hidden'
      await nextTick()
      closeEl.value?.focus()
      return
    }
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = ''
  },
  { immediate: true },
)

// 卸载（路由跳转）时恢复页面滚动并解除监听
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.doc-drawer {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  justify-content: flex-end;
}

.doc-drawer__backdrop {
  position: absolute;
  inset: 0;
  background: rgb(15 23 42 / 35%);
}

.doc-drawer__panel {
  position: relative;
  display: flex;
  flex-direction: column;
  width: min(46rem, 92vw);
  height: 100%;
  background: var(--color-surface-muted, #f8fafc);
  border-left: 1px solid var(--color-border);
  box-shadow: -12px 0 32px rgb(15 23 42 / 12%);
  transition: width var(--transition-fast);
}

/* 全屏：编辑区铺满视口 */
.doc-drawer__panel--full {
  width: 100vw;
  border-left: 0;
}

/* 头部卡片：文件名 + 全屏/关闭 */
.doc-drawer__card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex: none;
  margin: var(--space-4) var(--space-5) 0;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.doc-drawer__title {
  min-width: 0;
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 1.0625rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-drawer__controls {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex: none;
}

.doc-drawer__expand,
.doc-drawer__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: var(--color-muted-foreground);
  background: transparent;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.doc-drawer__close {
  font-size: 1.25rem;
  line-height: 1;
}

.doc-drawer__expand:hover,
.doc-drawer__close:hover {
  color: var(--color-foreground);
  background: var(--color-surface-muted);
}

.doc-drawer__body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: var(--space-4) var(--space-5) var(--space-6);
}

@media (max-width: 768px) {
  .doc-drawer__panel {
    width: 100vw;
    border-left: 0;
  }

  .doc-drawer__card {
    margin: var(--space-3) var(--space-3) 0;
  }

  .doc-drawer__body {
    padding: var(--space-3);
  }
}
</style>
