<template>
  <section class="home">
    <header class="home__header">
      <h1 class="home__title">{{ appName }}</h1>
      <p class="home__subtitle">AI 会议个人助理 · 前端基础设施已就绪</p>
    </header>

    <div class="home__grid">
      <InfoCard label="项目名称" :value="appName" />
      <InfoCard
        label="当前环境"
        :value="environmentLabel"
        :description="`环境标识：${environmentValue}`"
      />
      <InfoCard
        label="后端连接状态"
        :value="connectionLabel"
        :tone="connectionTone"
        :description="connectionDescription"
        aria-live="polite"
      />
    </div>

    <button class="home__retry" type="button" :disabled="isChecking" @click="refresh">
      {{ isChecking ? '检测中…' : '检测后端连接' }}
    </button>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { checkBackendHealth } from '@/api/health'
import InfoCard from '@/components/InfoCard.vue'
import type { ConnectionState } from '@/types/health'
import type { InfoCardTone } from '@/types/ui'
import { resolveEnvironmentLabel } from '@/utils/environment'

const appName = 'OpenMIND'
const connectionDescription =
  '该状态来自后端与数据库的联合健康检查；数据库不可用时同样显示为未连接。'

const environmentValue: string = import.meta.env.VITE_APP_ENV ?? import.meta.env.MODE
const environmentLabel = computed(() => resolveEnvironmentLabel(environmentValue))

const connection = ref<ConnectionState>('checking')
const isChecking = ref(false)
let isActive = true

async function refresh(): Promise<void> {
  if (isChecking.value) return
  isChecking.value = true
  connection.value = 'checking'
  try {
    const state = await checkBackendHealth()
    if (isActive) {
      connection.value = state
    }
  } finally {
    if (isActive) {
      isChecking.value = false
    }
  }
}

const connectionLabel = computed(() => {
  if (connection.value === 'up') return '已连接'
  if (connection.value === 'down') return '未连接'
  return '检测中…'
})

const connectionTone = computed<InfoCardTone>(() => {
  if (connection.value === 'up') return 'ok'
  if (connection.value === 'down') return 'down'
  return 'checking'
})

onMounted(() => {
  void refresh()
})

onUnmounted(() => {
  isActive = false
})
</script>

<style scoped>
.home {
  margin: 0;
  padding: 0;
}

.home__header {
  margin-bottom: var(--space-5);
}

.home__title {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
}

.home__subtitle {
  margin: var(--space-1) 0 0;
  color: var(--color-muted-foreground);
}

.home__grid {
  display: grid;
  gap: var(--space-3);
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
}

.home__retry {
  margin-top: var(--space-5);
  padding: var(--space-2) var(--space-4);
  min-height: 2.5rem;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  color: var(--color-primary-contrast);
  border: 1px solid transparent;
  border-radius: var(--radius-pill);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(59, 111, 212, 0.26);
  transition:
    background var(--transition-fast),
    box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.home__retry:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(59, 111, 212, 0.34);
}

.home__retry:disabled {
  background: var(--color-surface-strong);
  color: var(--color-muted-foreground);
  border-color: var(--color-border);
  box-shadow: none;
  cursor: not-allowed;
}
</style>
