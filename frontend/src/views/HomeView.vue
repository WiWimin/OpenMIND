<template>
  <main class="home">
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
      {{ isChecking ? '检测中…' : '重新检测' }}
    </button>
  </main>
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
  margin: 0 auto;
  max-width: 60rem;
  padding: var(--space-5) var(--space-4);
}

.home__header {
  margin-bottom: var(--space-5);
}

.home__title {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
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
  margin-top: var(--space-4);
  padding: var(--space-2) var(--space-4);
  min-height: 2.5rem;
  background: var(--color-primary);
  color: #ffffff;
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-sm);
  font: inherit;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.home__retry:hover:not(:disabled) {
  background: var(--color-primary-strong);
  border-color: var(--color-primary-strong);
}

.home__retry:disabled {
  background: var(--color-muted-foreground);
  border-color: var(--color-muted-foreground);
  cursor: not-allowed;
}
</style>
