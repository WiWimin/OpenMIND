import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import * as meetingsApi from '@/api/meetings'
import * as tasksApi from '@/api/tasks'
import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'
import { useAuthStore } from '@/stores/auth'
import type { AuthUser } from '@/types/auth'

const { pushMock, routeState } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  routeState: {
    name: 'dashboard',
    fullPath: '/dashboard',
    query: {} as Record<string, string>,
    params: {} as Record<string, string>,
    meta: {} as Record<string, unknown>,
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => routeState,
}))

vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  fetchCurrentUser: vi.fn(),
}))

vi.mock('@/api/meetings', () => ({
  listMeetings: vi.fn(),
  createMeeting: vi.fn(),
}))

vi.mock('@/api/tasks', () => ({
  listTasks: vi.fn(),
}))

const user: AuthUser = {
  user_id: 'u1',
  name: 'Alice',
  created_at: '2026-10-01T00:00:00+08:00',
}

function emptyList(total = 0) {
  return { items: [], pagination: { page: 1, page_size: 1, total, total_pages: 0 } }
}

function resetRoute() {
  routeState.name = 'dashboard'
  routeState.fullPath = '/dashboard'
  routeState.query = {}
  routeState.params = {}
  routeState.meta = { label: '仪表盘' }
}

function mountLayout() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = user
  return {
    auth,
    wrapper: mount(WorkspaceLayout, {
      global: {
        plugins: [pinia],
        stubs: { RouterView: true, RouterLink: { template: '<a><slot /></a>' } },
      },
    }),
  }
}

describe('WorkspaceLayout', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.resetAllMocks()
    resetRoute()
  })

  it('shows the current user name', () => {
    const { wrapper } = mountLayout()
    expect(wrapper.text()).toContain('Alice')
  })

  it('renders the four top-level navigation entries without the settings and knowledge modules', () => {
    const { wrapper } = mountLayout()

    const labels = wrapper.findAll('.workspace__topnav-link').map((node) => node.text())
    expect(labels).toEqual(['主页', '新建会议', '会议管理', '任务管理'])
    expect(wrapper.text()).not.toContain('系统设置')
  })

  it('renders the sidebar quick links and the settings menu entries', () => {
    const { wrapper } = mountLayout()

    const links = wrapper.findAll('.workspace__quick-link').map((node) => node.text())
    expect(links).toEqual(['会议', '任务'])
    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).toContain('模型配置')
    expect(wrapper.text()).toContain('记忆中心')
    expect(wrapper.text()).toContain('知识库')
  })

  it('shows the notice badge based on todo tasks and scheduled meetings', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(emptyList(2))
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(emptyList(1))

    const { wrapper } = mountLayout()
    await flushPromises()

    expect(wrapper.find('.workspace__notice-badge').text()).toBe('3')
  })

  it('logs out and returns to the login page', async () => {
    vi.mocked(authApi.logout).mockResolvedValue(undefined)
    const { auth, wrapper } = mountLayout()

    const logout = wrapper.findAll('button').find((node) => node.text().includes('退出登录'))
    await logout?.trigger('click')
    await flushPromises()

    expect(authApi.logout).toHaveBeenCalledTimes(1)
    expect(auth.isAuthenticated).toBe(false)
    expect(pushMock).toHaveBeenCalledWith({ name: 'login' })
  })

  it('opens the create dialog from the top-nav 新建会议 entry', async () => {
    const { wrapper } = mountLayout()
    await flushPromises()

    expect(wrapper.find('.meeting-form').exists()).toBe(false)

    const entry = wrapper
      .findAll('.workspace__topnav-link')
      .find((node) => node.text() === '新建会议')
    await entry?.trigger('click')
    await flushPromises()

    // 顶部导航的「新建会议」不跳路由，直接弹出创建会议窗口
    expect(wrapper.find('.meeting-form').exists()).toBe(true)
    expect(pushMock).not.toHaveBeenCalled()
  })
})
