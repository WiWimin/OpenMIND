<template>
  <div class="workspace">
    <header class="workspace__header">
      <div class="workspace__brand">
        <RouterLink class="workspace__logo" :to="{ name: 'workspace' }">OpenMIND</RouterLink>
        <span class="workspace__tagline">AI 会议个人助理</span>
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
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isLoggingOut = ref(false)

async function handleLogout(): Promise<void> {
  isLoggingOut.value = true
  try {
    await auth.logout()
    await router.push({ name: 'login' })
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
  gap: var(--space-2);
}

.workspace__logo {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-primary-strong);
  text-decoration: none;
}

.workspace__tagline {
  color: var(--color-muted-foreground);
  font-size: 0.8125rem;
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
