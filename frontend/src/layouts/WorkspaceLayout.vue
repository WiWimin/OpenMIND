<template>
  <div class="workspace">
    <header class="workspace__topbar">
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

      <nav class="workspace__nav" aria-label="主导航">
        <RouterLink class="workspace__nav-link" :to="{ name: ROUTE_NAMES.dashboard }">
          <svg class="workspace__icon" viewBox="0 0 24 24" width="16" height="16" fill="none">
            <rect x="3.5" y="3.5" width="7" height="7" rx="1.8" stroke="currentColor" stroke-width="1.6" />
            <rect x="13.5" y="3.5" width="7" height="4.5" rx="1.8" stroke="currentColor" stroke-width="1.6" />
            <rect x="3.5" y="13.5" width="7" height="7" rx="1.8" stroke="currentColor" stroke-width="1.6" />
            <rect x="13.5" y="11" width="7" height="9.5" rx="1.8" stroke="currentColor" stroke-width="1.6" />
          </svg>
          <span class="workspace__nav-label">仪表盘</span>
        </RouterLink>

        <RouterLink class="workspace__nav-link" :to="{ name: ROUTE_NAMES.tasks }">
          <svg class="workspace__icon" viewBox="0 0 24 24" width="16" height="16" fill="none">
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
      </nav>

      <div class="workspace__actions">
        <RouterLink
          class="workspace__cta"
          :to="{ name: ROUTE_NAMES.dashboard, query: { create: '1' } }"
        >
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
            <path d="M12 5.5v13M5.5 12h13" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          <span class="workspace__cta-label">新建会议</span>
        </RouterLink>

        <div class="workspace__account">
          <span class="workspace__avatar" aria-hidden="true">{{ initial }}</span>
          <span class="workspace__user">{{ auth.user?.name ?? '当前用户' }}</span>
          <AppButton variant="ghost" :loading="isLoggingOut" @click="handleLogout">退出</AppButton>
        </div>
      </div>
    </header>

    <main class="workspace__main">
      <RouterView v-slot="{ Component }">
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>

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
  flex-direction: column;
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
    /* 浅蓝云纹 */
    radial-gradient(58rem 42rem at 8% 18%, rgba(125, 180, 235, 0.45), transparent 62%),
    radial-gradient(46rem 34rem at 92% 88%, rgba(110, 190, 228, 0.38), transparent 58%),
    radial-gradient(40rem 28rem at 78% 8%, rgba(160, 205, 242, 0.34), transparent 52%),
    radial-gradient(34rem 26rem at 18% 92%, rgba(95, 180, 222, 0.28), transparent 52%),
    radial-gradient(30rem 22rem at 55% 52%, rgba(255, 255, 255, 0.65), transparent 60%),
    linear-gradient(135deg, #dceaf6 0%, #e7f1fa 30%, #eff5fb 55%, #e3edf8 80%, #dceaf5 100%);
}

/* 顶部导航栏 */
.workspace__topbar {
  position: sticky;
  top: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: 0 var(--space-5);
  height: 3.75rem;
  background: rgba(255, 255, 255, 0.82);
  border-bottom: 1px solid var(--color-border);
  -webkit-backdrop-filter: var(--glass-blur);
  backdrop-filter: var(--glass-blur);
}

.workspace__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  text-decoration: none;
  flex-shrink: 0;
}

.workspace__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.9rem;
  height: 1.9rem;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(59, 111, 212, 0.35);
}

.workspace__wordmark {
  font-family: var(--font-display);
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-foreground);
}

/* 中部导航 */
.workspace__nav {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex: 1;
}

.workspace__nav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.45rem 0.85rem;
  color: var(--color-muted-foreground);
  font-size: 0.9rem;
  font-weight: 500;
  text-decoration: none;
  border-radius: var(--radius-pill);
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.workspace__nav-link:hover {
  background: rgba(59, 111, 212, 0.07);
  color: var(--color-foreground);
}

.workspace__nav-link.router-link-active {
  color: var(--color-primary-strong);
  font-weight: 600;
  background: rgba(59, 111, 212, 0.1);
}

.workspace__icon {
  flex: 0 0 auto;
  opacity: 0.85;
}

/* 右侧操作区 */
.workspace__actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.workspace__cta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.45rem 1.1rem;
  color: #ffffff;
  font-size: 0.875rem;
  font-weight: 600;
  text-decoration: none;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: var(--radius-pill);
  box-shadow: 0 8px 20px rgba(59, 111, 212, 0.3);
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast);
}

.workspace__cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(59, 111, 212, 0.42);
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
  width: 1.85rem;
  height: 1.85rem;
  color: #ffffff;
  font-size: 0.75rem;
  font-weight: 600;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  border-radius: 50%;
}

.workspace__user {
  color: var(--color-foreground);
  font-weight: 500;
  font-size: 0.875rem;
}

/* 主内容区：全宽纵向滚动 */
.workspace__main {
  flex: 1;
  width: 100%;
  max-width: 78rem;
  margin: 0 auto;
  padding: var(--space-5) var(--space-5) var(--space-7);
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

@media (max-width: 768px) {
  .workspace__topbar {
    padding: 0 var(--space-3);
    gap: var(--space-3);
  }

  .workspace__nav-label,
  .workspace__cta-label,
  .workspace__user {
    display: none;
  }

  .workspace__main {
    padding: var(--space-4) var(--space-3) var(--space-5);
  }
}
</style>
