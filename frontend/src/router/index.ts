import { createRouter, createWebHistory, type RouteRecordRaw, type Router } from 'vue-router'

import { ROUTE_NAMES, ROUTE_PATHS } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guestOnly?: boolean
    label?: string
    module?: string
  }
}

const workspaceChildren: RouteRecordRaw[] = [
  {
    path: '',
    name: ROUTE_NAMES.root,
    redirect: { name: ROUTE_NAMES.dashboard },
  },
  {
    path: ROUTE_PATHS.dashboard.slice(1),
    name: ROUTE_NAMES.dashboard,
    component: () => import('@/views/DashboardView.vue'),
    meta: { label: '仪表盘', module: 'home' },
  },
  {
    path: ROUTE_PATHS.newMeeting.slice(1),
    name: ROUTE_NAMES.newMeeting,
    component: () => import('@/views/newMeeting/NewMeetingView.vue'),
    meta: { label: '会议总入口', module: 'new-meeting' },
  },
  {
    path: ROUTE_PATHS.preprocess.slice(1),
    name: ROUTE_NAMES.preprocess,
    component: () => import('@/views/newMeeting/PreprocessView.vue'),
    meta: { label: '资料预处理', module: 'new-meeting' },
  },
  {
    path: ROUTE_PATHS.asr.slice(1),
    name: ROUTE_NAMES.asr,
    component: () => import('@/views/newMeeting/AsrView.vue'),
    meta: { label: '录音转写', module: 'new-meeting' },
  },
  {
    path: ROUTE_PATHS.minutesGenerate.slice(1),
    name: ROUTE_NAMES.minutesGenerate,
    component: () => import('@/views/newMeeting/MinutesGenerateView.vue'),
    meta: { label: '纪要生成', module: 'new-meeting' },
  },
  {
    path: ROUTE_PATHS.meetings.slice(1),
    name: ROUTE_NAMES.meetings,
    component: () => import('@/views/meetings/MeetingManageView.vue'),
    meta: { label: '会议列表', module: 'meetings' },
  },
  {
    path: ROUTE_PATHS.templateManage.slice(1),
    name: ROUTE_NAMES.templateManage,
    component: () => import('@/views/meetings/TemplateManageView.vue'),
    meta: { label: '会议模板管理', module: 'meetings' },
  },
  {
    path: ROUTE_PATHS.meetingDetail.slice(1),
    name: ROUTE_NAMES.meetingDetail,
    component: () => import('@/views/meetings/MeetingDetailView.vue'),
    meta: { label: '会议详情', module: 'meetings' },
  },
  {
    path: ROUTE_PATHS.tasks.slice(1),
    name: ROUTE_NAMES.tasks,
    component: () => import('@/views/TasksView.vue'),
    meta: { label: '任务总览', module: 'tasks' },
  },
  {
    path: ROUTE_PATHS.taskArchive.slice(1),
    name: ROUTE_NAMES.taskArchive,
    component: () => import('@/views/tasks/TaskArchiveView.vue'),
    meta: { label: '已归档任务', module: 'tasks' },
  },
  // 旧设置/知识库页面已改为设置菜单中的弹窗，旧地址重定向到仪表盘
  {
    path: 'settings',
    redirect: { name: ROUTE_NAMES.dashboard },
  },
  {
    path: 'memory',
    redirect: { name: ROUTE_NAMES.dashboard },
  },
  {
    path: 'knowledge',
    redirect: { name: ROUTE_NAMES.dashboard },
  },
  {
    path: 'knowledge/search',
    redirect: { name: ROUTE_NAMES.dashboard },
  },
  {
    path: 'system/memory',
    redirect: { name: ROUTE_NAMES.dashboard },
  },
  {
    path: 'system/model',
    redirect: { name: ROUTE_NAMES.dashboard },
  },
]

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('@/layouts/WorkspaceLayout.vue'),
    meta: { requiresAuth: true },
    children: workspaceChildren,
  },
  {
    path: ROUTE_PATHS.login,
    name: ROUTE_NAMES.login,
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: ROUTE_PATHS.register,
    name: ROUTE_NAMES.register,
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: () => ({ path: ROUTE_PATHS.root }),
  },
]

export function createAppRouter(): Router {
  const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
  })

  router.beforeEach(async (to) => {
    const auth = useAuthStore()

    if (to.meta.requiresAuth && !auth.isAuthenticated) {
      return { name: ROUTE_NAMES.login, query: { redirect: to.fullPath } }
    }

    if (to.meta.guestOnly && auth.isAuthenticated) {
      return { name: ROUTE_NAMES.dashboard }
    }

    if (auth.isAuthenticated && !auth.user) {
      try {
        await auth.loadCurrentUser()
      } catch {
        await auth.logout()
        return { name: ROUTE_NAMES.login, query: { redirect: to.fullPath } }
      }
    }

    return true
  })

  return router
}

const router = createAppRouter()

export default router
