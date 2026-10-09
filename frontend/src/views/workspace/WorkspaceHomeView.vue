<template>
  <section class="workspace-home">
    <header class="workspace-home__header">
      <h1 class="workspace-home__title">{{ greeting }}，{{ displayName }}</h1>
      <p class="workspace-home__subtitle">这里是你个人的会议工作区，会议、资料与任务都会归集在这里。</p>
    </header>

    <div class="workspace-home__empty">
      <h2 class="workspace-home__empty-title">还没有会议</h2>
      <p class="workspace-home__empty-text">
        会议管理（M02）上线后，你可以在本页创建会议并进入会前准备、会中记录与会后整理。
      </p>
    </div>

    <p class="workspace-home__links">
      <RouterLink class="workspace-home__link" :to="{ name: 'home' }">查看系统状态</RouterLink>
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const displayName = computed(() => auth.user?.name ?? '当前用户')

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})
</script>

<style scoped>
.workspace-home__header {
  margin-bottom: var(--space-5);
}

.workspace-home__title {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
}

.workspace-home__subtitle {
  margin: var(--space-1) 0 0;
  color: var(--color-muted-foreground);
}

.workspace-home__empty {
  padding: var(--space-5) var(--space-4);
  background: var(--color-surface);
  border: 1px dashed var(--color-border);
  border-radius: var(--radius-md);
  text-align: center;
}

.workspace-home__empty-title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
}

.workspace-home__empty-text {
  margin: var(--space-2) auto 0;
  max-width: 32rem;
  color: var(--color-muted-foreground);
}

.workspace-home__links {
  margin: var(--space-4) 0 0;
}

.workspace-home__link {
  color: var(--color-primary-strong);
  font-weight: 500;
}
</style>
