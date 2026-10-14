import { createRouter, createWebHistory, type RouteRecordRaw, type Router } from 'vue-router'

import { ROUTE_NAMES, ROUTE_PATHS } from '@/constants/routeNames'
import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guestOnly?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: ROUTE_PATHS.root,
    name: ROUTE_NAMES.root,
    redirect: () => ({
      name: useAuthStore().isAuthenticated ? ROUTE_NAMES.meetings : ROUTE_NAMES.login,
    }),
  },
  {
    path: ROUTE_PATHS.home,
    name: ROUTE_NAMES.home,
    component: () => import('@/views/HomeView.vue'),
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
    path: ROUTE_PATHS.meetings,
    component: () => import('@/layouts/WorkspaceLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: ROUTE_NAMES.meetings,
        component: () => import('@/views/meetings/MeetingListView.vue'),
      },
      {
        path: ':meetingId',
        name: ROUTE_NAMES.meetingDetail,
        component: () => import('@/views/meetings/MeetingDetailView.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: { name: ROUTE_NAMES.root },
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
      return { name: ROUTE_NAMES.meetings }
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
