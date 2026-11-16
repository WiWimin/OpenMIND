import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as authApi from '@/api/auth'
import * as meetingsApi from '@/api/meetings'
import * as memoryApi from '@/api/memory'
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

vi.mock('@/api/memory', () => ({
  getMemory: vi.fn(),
  saveMemory: vi.fn(),
  clearMemory: vi.fn(),
}))

vi.mock('@/composables/useLocalWorkspace', () => ({
  useLocalWorkspace: () => ({
    status: ref('unconfigured'),
    directoryName: ref(''),
    connect: vi.fn(),
    restore: vi.fn(),
    init: vi.fn(),
  }),
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

const emptyMemory = {
  role: '',
  work_scenarios: '',
  communication_style: '',
  preferred_minutes_template: null,
  updated_at: null,
}

describe('WorkspaceLayout', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.resetAllMocks()
    vi.mocked(memoryApi.getMemory).mockResolvedValue(emptyMemory)
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

  it('renders the home group sidebar links and the settings menu entries', () => {
    const { wrapper } = mountLayout()

    const links = wrapper.findAll('.workspace__quick-link').map((node) => node.text())
    expect(links).toEqual(['概览', '我的会议', '待办任务'])
    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).toContain('模型配置')
    expect(wrapper.text()).toContain('记忆中心')
    expect(wrapper.text()).toContain('知识库')
  })

  it('renders the meetings group sidebar links on meeting routes', () => {
    routeState.name = 'meetings'
    routeState.fullPath = '/meetings'
    const { wrapper } = mountLayout()

    const links = wrapper.findAll('.workspace__quick-link').map((node) => node.text())
    expect(links).toEqual(['会议列表', '模板中心', '会议工作台'])
  })

  it('renders the tasks group sidebar links on task routes', () => {
    routeState.name = 'tasks'
    routeState.fullPath = '/tasks'
    const { wrapper } = mountLayout()

    const links = wrapper.findAll('.workspace__quick-link').map((node) => node.text())
    expect(links).toEqual(['全部任务', '待处理', '进行中', '已完成', '已归档任务'])
  })

  it('highlights only the matching task status sidebar entry', () => {
    routeState.name = 'tasks'
    routeState.fullPath = '/tasks?status=todo'
    routeState.query = { status: 'todo' }
    const { wrapper } = mountLayout()

    const active = wrapper
      .findAll('.workspace__quick-link--active')
      .map((node) => node.text())
    expect(active).toEqual(['待处理'])
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

  it('runs the memory then local-folder onboarding once for a new user', async () => {
    const { wrapper } = mountLayout()
    await flushPromises()

    // 第一步：记忆中心引导窗（步进模式，含「下一步」）
    const nextMemory = wrapper.findAll('button').find((node) => node.text() === '下一步')
    expect(nextMemory).toBeTruthy()

    await nextMemory?.trigger('click')
    await flushPromises()

    // 第二步：本地文件夹配置窗
    expect(wrapper.text()).toContain('绑定本地文件夹')
    const finish = wrapper.findAll('button').find((node) => node.text() === '完成')
    expect(finish).toBeTruthy()

    await finish?.trigger('click')
    await flushPromises()

    // 走完后按账号写入完成标记
    expect(window.localStorage.getItem('openmind.onboardingDone.u1')).toBe('1')
  })

  it('does not show onboarding dialogs for a returning user', async () => {
    window.localStorage.setItem('openmind.onboardingDone.u1', '1')
    const { wrapper } = mountLayout()
    await flushPromises()

    expect(wrapper.text()).not.toContain('下一步')
    expect(wrapper.text()).not.toContain('绑定本地文件夹')
  })
})
