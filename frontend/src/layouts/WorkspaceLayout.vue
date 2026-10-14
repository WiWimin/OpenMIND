<template>
  <div class="workspace">
    <header class="workspace__header">
      <div class="workspace__brand">
        <RouterLink class="workspace__logo" :to="{ name: ROUTE_NAMES.meetings }">OpenMIND</RouterLink>
        <nav class="workspace__nav">
          <RouterLink class="workspace__nav-link" :to="{ name: ROUTE_NAMES.meetings }">
            会议
          </RouterLink>
          <RouterLink class="workspace__nav-link" :to="{ name: ROUTE_NAMES.tasks }">
            任务
          </RouterLink>
        </nav>
      </div>

      <div class="workspace__account">
        <span class="workspace__user">{{ auth.user?.name ?? '当前用户' }}</span>
        <AppButton variant="ghost" :loading="isLoggingOut" @click="handleLogout">退出</AppButton>
      </div>
    </header>

    <main class="workspace__main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isLoggingOut = ref(false)

async function handleLogout(): Promise<void> {
  isLoggingOut.value = true
  try {
    await auth.logout()
    await router.push({ name: ROUTE_NAMES.login })
  } finally {
    isLoggingOut.value = false
  }
}
</script>

<style scoped>
.workspace {
  min-height: 100vh;
}

.workspace__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
}

.workspace__brand {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}

.workspace__logo {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-primary-strong);
  text-decoration: none;
}

.workspace__nav {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}

.workspace__nav-link {
  color: var(--color-muted-foreground);
  font-size: 0.875rem;
  text-decoration: none;
}

.workspace__nav-link.router-link-active {
  color: var(--color-primary-strong);
  font-weight: 500;
}

.workspace__account {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.workspace__user {
  font-weight: 500;
}

.workspace__main {
  margin: 0 auto;
  max-width: 72rem;
  padding: var(--space-5) var(--space-4);
}
</style>
