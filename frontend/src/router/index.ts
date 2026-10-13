import { createRouter, createWebHistory, type RouteRecordRaw, type Router } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    guestOnly?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { guestOnly: true },
  },
  {
    path: '/workspace',
    component: () => import('@/layouts/WorkspaceLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'workspace',
        component: () => import('@/views/workspace/WorkspaceHomeView.vue'),
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: { name: 'home' },
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
      return { name: 'login', query: { redirect: to.fullPath } }
    }

    if (to.meta.guestOnly && auth.isAuthenticated) {
      return { name: 'workspace' }
    }

    if (auth.isAuthenticated && !auth.user) {
      try {
        await auth.loadCurrentUser()
      } catch {
        await auth.logout()
        return { name: 'login', query: { redirect: to.fullPath } }
      }
    }

    return true
  })

  return router
}

const router = createAppRouter()

export default router
