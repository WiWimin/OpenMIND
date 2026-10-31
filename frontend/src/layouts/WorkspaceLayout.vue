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
        <span class="workspace__tag">AI 会议助理</span>
      </RouterLink>

      <nav class="workspace__topnav" aria-label="一级导航">
        <RouterLink
          v-for="module in topModules"
          :key="module.key"
          class="workspace__topnav-link"
          :class="{ 'workspace__topnav-link--active': activeModule?.key === module.key }"
          :to="{ name: module.routeName }"
        >
          <NavIcon class="workspace__topnav-icon" :name="module.icon" :size="16" />
          {{ module.label }}
        </RouterLink>
      </nav>

      <div class="workspace__topbar-actions">
        <details ref="noticeEl" class="workspace__notice">
          <summary class="workspace__notice-summary" aria-label="消息提醒">
            <NavIcon name="bell" :size="19" />
            <span v-if="noticeCount > 0" class="workspace__notice-badge">
              {{ noticeCount > 99 ? '99+' : noticeCount }}
            </span>
          </summary>
          <div class="workspace__menu" role="menu" aria-label="消息提醒">
            <p class="workspace__menu-head">
              <strong>消息提醒</strong>
              <span>会议与任务的最新动态</span>
            </p>
            <RouterLink
              class="workspace__menu-item workspace__menu-item--stacked"
              role="menuitem"
              :to="{ name: ROUTE_NAMES.tasks }"
            >
              <strong>待办任务</strong>
              <span>{{ noticeTodo > 0 ? `${noticeTodo} 项待处理` : '暂无待办' }}</span>
            </RouterLink>
            <RouterLink
              class="workspace__menu-item workspace__menu-item--stacked"
              role="menuitem"
              :to="{ name: ROUTE_NAMES.meetings }"
            >
              <strong>会议安排</strong>
              <span>{{ noticeScheduled > 0 ? `${noticeScheduled} 场待进行` : '暂无安排' }}</span>
            </RouterLink>
          </div>
        </details>

        <details ref="menuEl" class="workspace__account">
          <summary class="workspace__account-summary" aria-label="账户菜单">
            <span class="workspace__avatar" aria-hidden="true">{{ initial }}</span>
            <span class="workspace__user">{{ auth.user?.name ?? '当前用户' }}</span>
            <svg
              class="workspace__chevron"
              viewBox="0 0 16 16"
              width="12"
              height="12"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="m4 6 4 4 4-4"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </summary>
          <div class="workspace__menu" role="menu" aria-label="账户菜单">
            <p class="workspace__menu-head">
              <strong>{{ auth.user?.name ?? '当前用户' }}</strong>
              <span>个人工作区</span>
            </p>
            <button
              type="button"
              class="workspace__menu-item workspace__menu-item--danger"
              role="menuitem"
              :disabled="isLoggingOut"
              @click="handleLogout"
            >
              {{ isLoggingOut ? '退出中…' : '退出登录' }}
            </button>
          </div>
        </details>
      </div>
    </header>

    <div class="workspace__body">
      <aside
        class="workspace__aside"
        :class="{ 'workspace__aside--collapsed': asideCollapsed }"
      >
        <button
          type="button"
          class="workspace__aside-toggle"
          :title="asideCollapsed ? '展开导航栏' : '收起导航栏'"
          :aria-expanded="!asideCollapsed"
          @click="toggleAside"
        >
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden="true">
            <path
              d="M9 5.5 15.5 12 9 18.5"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <span v-if="!asideCollapsed">收起导航</span>
        </button>

        <nav class="workspace__quicknav" aria-label="快捷入口">
          <RouterLink
            v-for="link in QUICK_LINKS"
            :key="link.key"
            class="workspace__quick-link"
            :class="{ 'workspace__quick-link--active': activeModule?.key === link.key }"
            :title="asideCollapsed ? link.label : undefined"
            :to="{ name: link.routeName }"
          >
            <NavIcon class="workspace__quick-icon" :name="link.icon" :size="17" />
            <span class="workspace__quick-label">{{ link.label }}</span>
          </RouterLink>
        </nav>

        <div class="workspace__aside-foot">
          <details ref="settingsEl" class="workspace__settings">
            <summary
              class="workspace__settings-summary"
              aria-label="设置菜单"
              title="设置"
            >
              <NavIcon name="settings" :size="17" />
              <span>设置</span>
            </summary>
            <div
              class="workspace__menu workspace__menu--up"
              role="menu"
              aria-label="设置菜单"
            >
              <button
                type="button"
                class="workspace__menu-item"
                role="menuitem"
                @click="openSettingsPanel('model')"
              >
                <NavIcon class="workspace__menu-icon" name="cpu" :size="15" />
                模型配置
              </button>
              <button
                type="button"
                class="workspace__menu-item"
                role="menuitem"
                @click="openSettingsPanel('memory')"
              >
                <NavIcon class="workspace__menu-icon" name="user" :size="15" />
                记忆中心
              </button>
              <button
                type="button"
                class="workspace__menu-item"
                role="menuitem"
                @click="openSettingsPanel('knowledge')"
              >
                <NavIcon class="workspace__menu-icon" name="book" :size="15" />
                知识库
              </button>
            </div>
          </details>
          <span class="workspace__version">v{{ appVersion }}</span>
        </div>
      </aside>

      <main
        class="workspace__main"
        :class="{ 'workspace__main--fill': route.meta.module === 'new-meeting' }"
      >
        <div class="workspace__content">
          <RouterView v-slot="{ Component }">
            <Transition name="page" mode="out-in">
              <component :is="Component" />
            </Transition>
          </RouterView>
        </div>
      </main>
    </div>

    <ModelConfigDialog :open="activePanel === 'model'" @close="closePanel()" />
    <MemoryDialog :open="activePanel === 'memory'" @close="closePanel()" />
    <KnowledgeDialog :open="activePanel === 'knowledge'" @close="closePanel()" />

    <ToastHost />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { version as appVersion } from '../../package.json'
import { listMeetings } from '@/api/meetings'
import { listTasks } from '@/api/tasks'
import KnowledgeDialog from '@/components/settings/KnowledgeDialog.vue'
import MemoryDialog from '@/components/settings/MemoryDialog.vue'
import ModelConfigDialog from '@/components/settings/ModelConfigDialog.vue'
import NavIcon from '@/components/NavIcon.vue'
import ToastHost from '@/components/ToastHost.vue'
import { NAV_MODULES, findModuleByRouteName } from '@/constants/navigation'
import { ROUTE_NAMES } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'
import { useSettingsPanels } from '@/composables/useSettingsPanels'

// 左侧固定快捷入口（跨模块跳转），与一级导航解耦
const QUICK_LINKS = [
  { key: 'meetings', label: '会议', icon: 'video', routeName: ROUTE_NAMES.meetings },
  { key: 'tasks', label: '任务', icon: 'tasks', routeName: ROUTE_NAMES.tasks },
] as const

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const { activePanel, openPanel, closePanel } = useSettingsPanels()

function openSettingsPanel(panel: 'model' | 'memory' | 'knowledge'): void {
  closeMenus()
  openPanel(panel)
}
const noticeEl = ref<HTMLDetailsElement | null>(null)
const menuEl = ref<HTMLDetailsElement | null>(null)
const settingsEl = ref<HTMLDetailsElement | null>(null)
const isLoggingOut = ref(false)

// 左侧导航栏折叠：全局生效，选择记忆在本地（默认展开）
const ASIDE_COLLAPSED_KEY = 'openmind.asideCollapsed'
const asideCollapsed = ref(readAsideCollapsed())

function readAsideCollapsed(): boolean {
  try {
    return window.localStorage.getItem(ASIDE_COLLAPSED_KEY) === '1'
  } catch {
    return false
  }
}

function toggleAside(): void {
  asideCollapsed.value = !asideCollapsed.value
  try {
    window.localStorage.setItem(ASIDE_COLLAPSED_KEY, asideCollapsed.value ? '1' : '0')
  } catch {
    // 本地存储不可用时仅本次会话内生效
  }
}

const initial = computed(() => (auth.user?.name ?? '?').slice(0, 1).toUpperCase())

const activeModule = computed(() => findModuleByRouteName(String(route.name ?? '')))

// 系统设置入口收纳进左下角“设置”菜单，顶部一级导航不再展示
const topModules = NAV_MODULES.filter((module) => module.key !== 'system')

const noticeTodo = ref(0)
const noticeScheduled = ref(0)
const noticeCount = computed(() => noticeTodo.value + noticeScheduled.value)

async function refreshNotices(): Promise<void> {
  try {
    const [todo, scheduled] = await Promise.all([
      listTasks({ status: 'todo', page: 1, page_size: 1 }),
      listMeetings({ status: 'scheduled', page: 1, page_size: 1 }),
    ])
    noticeTodo.value = todo.pagination.total
    noticeScheduled.value = scheduled.pagination.total
  } catch {
    // 消息提醒仅作快捷入口，拉取失败时静默保持为空
  }
}

function closeMenus(): void {
  for (const element of [noticeEl.value, menuEl.value, settingsEl.value]) {
    if (element) {
      element.open = false
    }
  }
}

watch(
  () => route.fullPath,
  () => {
    closeMenus()
    void refreshNotices()
  },
)

onMounted(() => {
  void refreshNotices()
})

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
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

/* 顶部一级导航（贯穿整个页面） */
.workspace__topbar {
  position: sticky;
  top: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  gap: var(--space-5);
  height: 56px;
  padding: 0 var(--space-5);
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid var(--color-border);
  -webkit-backdrop-filter: var(--glass-blur);
  backdrop-filter: var(--glass-blur);
}

.workspace__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  flex: 0 0 auto;
  text-decoration: none;
}

.workspace__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.9rem;
  height: 1.9rem;
  color: #ffffff;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  border-radius: 9px;
  box-shadow: 0 4px 12px rgba(21, 94, 239, 0.26);
}

.workspace__wordmark {
  font-family: var(--font-display);
  font-size: 1.0625rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-foreground);
}

.workspace__tag {
  padding: 2px 7px;
  color: var(--color-primary-strong);
  font-size: 0.625rem;
  font-weight: 650;
  letter-spacing: 0.02em;
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.14);
  border-radius: var(--radius-pill);
  white-space: nowrap;
}

.workspace__topnav {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-x: auto;
  scrollbar-width: none;
}

.workspace__topnav::-webkit-scrollbar {
  display: none;
}

.workspace__topnav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0.42rem var(--space-4);
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 550;
  white-space: nowrap;
  text-decoration: none;
  border-radius: var(--radius-pill);
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.workspace__topnav-icon {
  opacity: 0.82;
}

.workspace__topnav-link:hover {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.workspace__topnav-link--active,
.workspace__topnav-link--active:hover {
  color: #ffffff;
  background: var(--color-primary);
  box-shadow: 0 6px 16px rgba(21, 94, 239, 0.28);
}

.workspace__topnav-link--active .workspace__topnav-icon {
  color: #ffffff;
  opacity: 1;
}

.workspace__topbar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex: 0 0 auto;
}

/* 消息提醒 */
.workspace__notice {
  position: relative;
}

.workspace__notice-summary {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.35rem;
  height: 2.35rem;
  color: var(--color-muted-foreground);
  border-radius: 50%;
  cursor: pointer;
  list-style: none;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.workspace__notice-summary::-webkit-details-marker {
  display: none;
}

.workspace__notice-summary:hover,
.workspace__notice[open] .workspace__notice-summary {
  color: var(--color-foreground);
  background: var(--color-surface-muted);
}

.workspace__notice-badge {
  position: absolute;
  top: 1px;
  right: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.05rem;
  height: 1.05rem;
  padding: 0 4px;
  color: #ffffff;
  font-size: 0.625rem;
  font-weight: 700;
  line-height: 1;
  background: #ef4444;
  border-radius: var(--radius-pill);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.95);
}

.workspace__account {
  position: relative;
}

.workspace__account-summary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 2.5rem;
  padding: 3px 6px 3px 3px;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  list-style: none;
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast);
}

.workspace__account-summary::-webkit-details-marker {
  display: none;
}

.workspace__account-summary:hover {
  background: var(--color-surface-strong);
  border-color: var(--color-border);
}

.workspace__account[open] .workspace__account-summary {
  background: var(--color-surface-strong);
  border-color: var(--color-border);
}

.workspace__avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  color: var(--color-primary-strong);
  font-size: 0.75rem;
  font-weight: 700;
  background: var(--color-primary-soft);
  border: 1px solid rgba(21, 94, 239, 0.16);
  border-radius: 50%;
}

.workspace__user {
  max-width: 9rem;
  overflow: hidden;
  color: var(--color-foreground);
  font-size: 0.8125rem;
  font-weight: 550;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace__chevron {
  color: var(--color-muted-foreground);
  transition: transform var(--transition-fast);
}

.workspace__account[open] .workspace__chevron {
  transform: rotate(180deg);
}

/* 顶部弹出的下拉菜单（消息提醒 / 账户）与底部上拉菜单（设置）共用 */
.workspace__menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 70;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 13rem;
  padding: var(--space-2);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  animation: menu-in var(--transition-fast);
}

.workspace__menu--up {
  top: auto;
  bottom: calc(100% + 10px);
  right: auto;
  left: 0;
  min-width: 11rem;
}

@keyframes menu-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.workspace__menu-head {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin: 0 0 var(--space-1);
  padding: var(--space-2) var(--space-2) var(--space-2);
  border-bottom: 1px solid var(--color-border);
}

.workspace__menu-head strong {
  font-size: 0.8125rem;
  font-weight: 650;
}

.workspace__menu-head span {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.workspace__menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: 0.45rem var(--space-2);
  color: var(--color-foreground);
  font: inherit;
  font-size: 0.8125rem;
  text-align: left;
  text-decoration: none;
  background: transparent;
  border: 0;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.workspace__menu-item:hover {
  background: var(--color-surface-muted);
}

.workspace__menu-icon {
  color: var(--color-subtle-foreground);
}

.workspace__menu-item--stacked {
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  padding: 0.5rem var(--space-2);
}

.workspace__menu-item--stacked strong {
  font-size: 0.8125rem;
  font-weight: 650;
}

.workspace__menu-item--stacked span {
  color: var(--color-muted-foreground);
  font-size: 0.6875rem;
}

.workspace__menu-item--danger {
  color: var(--color-down);
}

.workspace__menu-item--danger:hover {
  background: rgba(220, 38, 38, 0.07);
}

.workspace__menu-item:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* 左侧快捷导航 */
.workspace__body {
  display: flex;
  flex: 1;
  align-items: stretch;
  min-height: 0;
}

.workspace__aside {
  position: sticky;
  top: 56px;
  display: flex;
  flex-direction: column;
  flex: 0 0 232px;
  width: 232px;
  height: calc(100vh - 56px);
  padding: var(--space-3) var(--space-3) var(--space-4);
  background: rgba(255, 255, 255, 0.7);
  border-right: 1px solid var(--color-border);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  transition:
    flex-basis var(--transition) ease,
    width var(--transition) ease,
    padding var(--transition) ease;
}

.workspace__aside-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  margin-bottom: var(--space-2);
  padding: 0.4rem 0.55rem;
  color: var(--color-muted-foreground);
  font: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  white-space: nowrap;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition:
    color var(--transition-fast),
    background var(--transition-fast);
}

.workspace__aside-toggle svg {
  flex: 0 0 auto;
  transform: rotate(180deg);
  transition: transform var(--transition-fast);
}

.workspace__aside-toggle:hover {
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
}

.workspace__aside--collapsed {
  flex: 0 0 64px;
  width: 64px;
  padding: var(--space-3) var(--space-2) var(--space-4);
}

.workspace__aside--collapsed .workspace__aside-toggle {
  justify-content: center;
  padding: 0.4rem 0;
}

.workspace__aside--collapsed .workspace__aside-toggle svg {
  transform: rotate(0deg);
}

.workspace__aside--collapsed .workspace__quick-link {
  justify-content: center;
  gap: 0;
  padding: 0.62rem 0;
}

.workspace__aside--collapsed .workspace__quick-label,
.workspace__aside--collapsed .workspace__settings-summary span,
.workspace__aside--collapsed .workspace__version {
  display: none;
}

.workspace__aside--collapsed .workspace__settings-summary {
  justify-content: center;
  padding: 0.45rem 0;
}

.workspace__aside--collapsed .workspace__aside-foot {
  justify-content: center;
}

.workspace__quicknav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.workspace__quick-link {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0.62rem 0.8rem;
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 550;
  text-decoration: none;
  border-radius: var(--radius-md);
  transition:
    color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.workspace__quick-link:hover {
  color: var(--color-primary-strong);
  background: var(--color-surface-muted);
}

.workspace__quick-icon {
  color: var(--color-subtle-foreground);
  transition: color var(--transition-fast);
}

.workspace__quick-label {
  font-size: 0.875rem;
}

.workspace__quick-link--active,
.workspace__quick-link--active:hover {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
  box-shadow: 0 6px 16px rgba(21, 94, 239, 0.1);
}

.workspace__quick-link--active::before {
  content: '';
  position: absolute;
  top: 22%;
  bottom: 22%;
  left: calc(-1 * var(--space-3));
  width: 3px;
  background: var(--color-primary);
  border-radius: 0 3px 3px 0;
}

.workspace__quick-link--active .workspace__quick-icon {
  color: var(--color-primary);
}

.workspace__quick-link--active .workspace__quick-label {
  font-weight: 650;
}

.workspace__aside-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: auto;
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
}

.workspace__settings {
  position: relative;
}

.workspace__settings-summary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0.45rem 0.75rem;
  color: var(--color-foreground);
  font-size: 0.875rem;
  font-weight: 550;
  border-radius: var(--radius-md);
  cursor: pointer;
  list-style: none;
  transition:
    background var(--transition-fast),
    color var(--transition-fast);
}

.workspace__settings-summary::-webkit-details-marker {
  display: none;
}

.workspace__settings-summary:hover,
.workspace__settings[open] .workspace__settings-summary {
  color: var(--color-primary-strong);
  background: var(--color-primary-soft);
}

.workspace__version {
  color: var(--color-subtle-foreground);
  font-size: 0.6875rem;
  white-space: nowrap;
}

/* 主内容 */
.workspace__main {
  flex: 1;
  min-width: 0;
  padding: var(--space-4) var(--space-6) var(--space-7);
}

.workspace__content {
  width: 100%;
  max-width: 82rem;
  margin: 0 auto;
}

/* 新建会议三步流页面：中间区域撑满视口高度，底边对齐页面下边框 */
@media (min-width: 1180px) {
  .workspace__main--fill {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 56px);
    padding-bottom: var(--space-4);
    overflow: hidden;
  }

  .workspace__main--fill .workspace__content {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
  }
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
  transform: translateY(6px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 1080px) {
  .workspace__aside {
    flex-basis: 208px;
    width: 208px;
  }

  .workspace__main {
    padding: var(--space-4) var(--space-5) var(--space-6);
  }
}

@media (max-width: 960px) {
  .workspace__topbar {
    gap: var(--space-3);
    padding: 0 var(--space-3);
  }

  .workspace__topnav {
    -webkit-mask-image: linear-gradient(90deg, #000 0, #000 calc(100% - 18px), transparent 100%);
    mask-image: linear-gradient(90deg, #000 0, #000 calc(100% - 18px), transparent 100%);
  }

  .workspace__tag {
    display: none;
  }

  .workspace__body {
    flex-direction: column;
  }

  .workspace__aside {
    position: sticky;
    top: 56px;
    z-index: 40;
    flex: 0 0 auto;
    flex-direction: row;
    align-items: center;
    width: 100%;
    height: auto;
    padding: var(--space-2) var(--space-3);
    background: rgba(255, 255, 255, 0.94);
    border-right: 0;
    border-bottom: 1px solid var(--color-border);
  }

  /* 小屏下侧栏为横向条，折叠态不再生效 */
  .workspace__aside--collapsed {
    flex: 0 0 auto;
    width: 100%;
    padding: var(--space-2) var(--space-3);
  }

  .workspace__aside-toggle {
    display: none;
  }

  .workspace__aside--collapsed .workspace__quick-label,
  .workspace__aside--collapsed .workspace__settings-summary span {
    display: inline;
  }

  .workspace__quicknav {
    flex-direction: row;
    flex: 1;
    gap: var(--space-1);
    overflow-x: auto;
    scrollbar-width: none;
  }

  .workspace__quicknav::-webkit-scrollbar {
    display: none;
  }

  .workspace__quick-link {
    flex: 0 0 auto;
    padding: 0.4rem 0.75rem;
    white-space: nowrap;
  }

  .workspace__quick-link--active::before {
    display: none;
  }

  .workspace__aside-foot {
    margin-top: 0;
    padding-top: 0;
    border-top: 0;
  }

  .workspace__version {
    display: none;
  }

  .workspace__main {
    padding: var(--space-3) var(--space-4) var(--space-6);
  }
}

@media (max-width: 640px) {
  .workspace__wordmark {
    display: none;
  }

  .workspace__user {
    display: none;
  }

  .workspace__menu-item {
    padding: 0.7rem var(--space-2);
  }

  .workspace__account-summary {
    padding-right: 3px;
  }

  .workspace__topnav-link {
    padding: 0 var(--space-2);
    font-size: 0.8125rem;
  }

  .workspace__main {
    padding: var(--space-3) var(--space-3) var(--space-5);
  }
}
</style>
