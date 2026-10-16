<template>
  <div class="workspace">
    <aside class="workspace__sidebar">
      <RouterLink class="workspace__brand" :to="{ name: ROUTE_NAMES.dashboard }">
        <span class="workspace__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
            <path
              d="M4 7.5A2.5 2.5 0 0 1 6.5 5h6.2c.4 0 .79.1 1.13.28l4.9 2.6c.78.42 1.27 1.24 1.27 2.13v6.49A2.5 2.5 0 0 1 17.5 19H6.5A2.5 2.5 0 0 1 4 16.5v-9Z"
              stroke="currentColor"
              stroke-width="1.6"
            />
            <path d="m13 9 4.5-2.4v7L13 11.2V9Z" fill="currentColor" opacity="0.9" />
          </svg>
        </span>
        <span class="workspace__wordmark">OpenMIND</span>
      </RouterLink>

      <RouterLink
        class="workspace__cta"
        :to="{ name: ROUTE_NAMES.dashboard, query: { create: '1' } }"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden="true">
          <path d="M12 5.5v13M5.5 12h13" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <span class="workspace__cta-label">新建会议</span>
      </RouterLink>

      <nav class="workspace__nav" aria-label="主导航">
        <p class="workspace__group">工作台</p>

        <RouterLink class="workspace__nav-link" :to="{ name: ROUTE_NAMES.dashboard }">
          <svg class="workspace__icon" viewBox="0 0 24 24" width="18" height="18" fill="none">
            <rect x="3.5" y="3.5" width="7" height="7" rx="1.8" stroke="currentColor" stroke-width="1.6" />
            <rect x="13.5" y="3.5" width="7" height="4.5" rx="1.8" stroke="currentColor" stroke-width="1.6" />
            <rect x="3.5" y="13.5" width="7" height="7" rx="1.8" stroke="currentColor" stroke-width="1.6" />
            <rect x="13.5" y="11" width="7" height="9.5" rx="1.8" stroke="currentColor" stroke-width="1.6" />
          </svg>
          <span class="workspace__nav-label">仪表盘</span>
        </RouterLink>

        <p class="workspace__group">我的</p>

        <RouterLink class="workspace__nav-link" :to="{ name: ROUTE_NAMES.tasks }">
          <svg class="workspace__icon" viewBox="0 0 24 24" width="18" height="18" fill="none">
            <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" stroke="currentColor" stroke-width="1.6" />
            <path
              d="m8 12.2 2.4 2.3L16 9.3"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <span class="workspace__nav-label">个人任务</span>
        </RouterLink>

        <RouterLink class="workspace__nav-link" :to="{ name: ROUTE_NAMES.settings }">
          <svg class="workspace__icon" viewBox="0 0 24 24" width="18" height="18" fill="none">
            <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.6" />
            <path
              d="M12 3.5v2M12 18.5v2M20.5 12h-2M5.5 12h-2M17.9 6.1l-1.4 1.4M7.5 16.5l-1.4 1.4M17.9 17.9l-1.4-1.4M7.5 7.5 6.1 6.1"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
            />
          </svg>
          <span class="workspace__nav-label">模型设置</span>
        </RouterLink>
      </nav>

      <p class="workspace__tagline">AI 会议个人助理</p>
    </aside>

    <div class="workspace__body">
      <header class="workspace__header">
        <div class="workspace__account">
          <span class="workspace__avatar" aria-hidden="true">{{ initial }}</span>
          <span class="workspace__user">{{ auth.user?.name ?? '当前用户' }}</span>
          <AppButton variant="ghost" :loading="isLoggingOut" @click="handleLogout">退出</AppButton>
        </div>
      </header>

      <main class="workspace__main">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>

    <ToastHost />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppButton from '@/components/AppButton.vue'
import ToastHost from '@/components/ToastHost.vue'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isLoggingOut = ref(false)

const initial = computed(() => (auth.user?.name ?? '?').slice(0, 1).toUpperCase())

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
  position: relative;
  display: flex;
  align-items: stretch;
  min-height: 100vh;
  background:
    /* 白纱：整体提亮 */
    linear-gradient(rgba(255, 255, 255, 0.42), rgba(255, 255, 255, 0.42)),
    /* 细网格纹理（对角淡线） */
    repeating-linear-gradient(
      -42deg,
      transparent,
      transparent 3px,
      rgba(59, 111, 212, 0.018) 3px,
      rgba(59, 111, 212, 0.018) 4px
    ),
    /* 浅蓝云纹（图1） */
    radial-gradient(58rem 42rem at 8% 18%, rgba(125, 180, 235, 0.45), transparent 62%),
    radial-gradient(46rem 34rem at 92% 88%, rgba(110, 190, 228, 0.38), transparent 58%),
    radial-gradient(40rem 28rem at 78% 8%, rgba(160, 205, 242, 0.34), transparent 52%),
    radial-gradient(34rem 26rem at 18% 92%, rgba(95, 180, 222, 0.28), transparent 52%),
    radial-gradient(30rem 22rem at 55% 52%, rgba(255, 255, 255, 0.65), transparent 60%),
    linear-gradient(135deg, #dceaf6 0%, #e7f1fa 30%, #eff5fb 55%, #e3edf8 80%, #dceaf5 100%);
}

/* 左侧侧栏：浅色毛玻璃 */
.workspace__sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  flex: 0 0 15rem;
  width: 15rem;
  height: 100vh;
  padding: var(--space-4) var(--space-3) var(--space-3);
  background: rgba(255, 255, 255, 0.66);
  border-right: 1px solid var(--color-border);
  -webkit-backdrop-filter: var(--glass-blur);
  backdrop-filter: var(--glass-blur);
  color: var(--color-foreground);
}

.workspace__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-2);
  text-decoration: none;
}

.workspace__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  border-radius: 10px;
  box-shadow: 0 8px 20px rgba(59, 111, 212, 0.4);
}

.workspace__wordmark {
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-foreground);
}

.workspace__cta {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  min-height: 2.4rem;
  color: #ffffff;
  font-size: 0.9375rem;
  font-weight: 600;
  text-decoration: none;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: var(--radius-pill);
  box-shadow: 0 10px 24px rgba(59, 111, 212, 0.35);
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast);
}

.workspace__cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(59, 111, 212, 0.5);
}

.workspace__nav {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
  overflow-y: auto;
}

.workspace__group {
  margin: var(--space-3) 0 var(--space-1);
  padding: 0 var(--space-2);
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.85;
}

.workspace__group:first-child {
  margin-top: 0;
}

.workspace__nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0.6rem 0.75rem;
  color: var(--color-muted-foreground);
  font-size: 0.9375rem;
  text-decoration: none;
  border-radius: var(--radius-md);
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    transform var(--transition-fast);
}

.workspace__nav-link:hover {
  background: rgba(59, 111, 212, 0.08);
  color: var(--color-foreground);
  transform: translateX(2px);
}

.workspace__nav-link.router-link-active {
  color: #ffffff;
  font-weight: 600;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  box-shadow: 0 10px 24px rgba(59, 111, 212, 0.3);
}

.workspace__icon {
  flex: 0 0 auto;
  opacity: 0.9;
}

.workspace__tagline {
  margin: 0;
  padding: 0 var(--space-2);
  color: var(--color-muted-foreground);
  font-size: 0.75rem;
  letter-spacing: 0.04em;
}

/* 右侧主体 */
.workspace__body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.workspace__header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  background: rgba(255, 255, 255, 0.78);
  border-bottom: 1px solid var(--color-border);
  -webkit-backdrop-filter: var(--glass-blur);
  backdrop-filter: var(--glass-blur);
}

.workspace__account {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.workspace__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  color: #ffffff;
  font-size: 0.8125rem;
  font-weight: 600;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  border-radius: 50%;
}

.workspace__user {
  color: var(--color-foreground);
  font-weight: 500;
  font-size: 0.9375rem;
}

.workspace__main {
  flex: 1;
  width: 100%;
  max-width: 76rem;
  margin: 0 auto;
  padding: var(--space-5) var(--space-5) var(--space-6);
}

/* 页面切换动效 */
.page-enter-active,
.page-leave-active {
  transition:
    opacity var(--transition) ease,
    transform var(--transition) ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 900px) {
  .workspace__sidebar {
    flex-basis: 4.75rem;
    width: 4.75rem;
    padding-left: var(--space-2);
    padding-right: var(--space-2);
    align-items: center;
  }

  .workspace__brand {
    padding: 0;
  }

  .workspace__wordmark,
  .workspace__nav-label,
  .workspace__tagline,
  .workspace__cta-label,
  .workspace__group {
    display: none;
  }

  .workspace__nav-link {
    justify-content: center;
  }

  .workspace__main {
    padding: var(--space-4) var(--space-3) var(--space-5);
  }
}
</style>
