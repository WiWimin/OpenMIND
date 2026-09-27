import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { checkBackendHealth } from '@/api/health'
import HomeView from '@/views/HomeView.vue'
import type { ConnectionState } from '@/types/health'

vi.mock('@/api/health', () => ({
  checkBackendHealth: vi.fn(),
}))

const mockedCheck = vi.mocked(checkBackendHealth)

function findButton(wrapper: ReturnType<typeof mount>): ReturnType<typeof wrapper.get> {
  return wrapper.get('button.home__retry')
}

describe('HomeView', () => {
  beforeEach(() => {
    mockedCheck.mockReset()
  })

  it('renders the project name and the current environment card', async () => {
    mockedCheck.mockResolvedValue('up')
    const wrapper = mount(HomeView)
    await flushPromises()

    expect(wrapper.text()).toContain('OpenMIND')
    expect(wrapper.text()).toContain('当前环境')
  })

  it('shows the checking state before the first response arrives', async () => {
    mockedCheck.mockReturnValue(new Promise(() => {}))
    const wrapper = mount(HomeView)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('检测中…')
    expect(findButton(wrapper).attributes('disabled')).toBeDefined()
    expect(findButton(wrapper).text()).toBe('检测中…')
  })

  it('reports the backend as connected when the check succeeds', async () => {
    mockedCheck.mockResolvedValue('up')
    const wrapper = mount(HomeView)
    await flushPromises()

    expect(wrapper.text()).toContain('已连接')
  })

  it('reports the backend as disconnected when the check fails', async () => {
    mockedCheck.mockResolvedValue('down')
    const wrapper = mount(HomeView)
    await flushPromises()

    expect(wrapper.text()).toContain('未连接')
  })

  it('explains that the status covers the backend and the database', async () => {
    mockedCheck.mockResolvedValue('up')
    const wrapper = mount(HomeView)
    await flushPromises()

    expect(wrapper.text()).toContain('数据库不可用时同样显示为未连接')
  })

  it('exposes a keyboard reachable retry button that re-runs the check', async () => {
    mockedCheck.mockResolvedValue('up')
    const wrapper = mount(HomeView)
    await flushPromises()

    const button = findButton(wrapper)
    expect(button.attributes('type')).toBe('button')
    expect(button.attributes('disabled')).toBeUndefined()

    await button.trigger('click')
    await flushPromises()

    expect(mockedCheck).toHaveBeenCalledTimes(2)
  })

  it('ignores repeated clicks while a check is still in flight', async () => {
    let resolveCheck: (state: ConnectionState) => void = () => {}
    mockedCheck.mockReturnValue(
      new Promise<ConnectionState>((resolve) => {
        resolveCheck = resolve
      }),
    )
    const wrapper = mount(HomeView)
    await Promise.resolve()

    const button = findButton(wrapper)
    expect(button.attributes('disabled')).toBeDefined()

    await button.trigger('click')
    await button.trigger('click')
    await Promise.resolve()

    expect(mockedCheck).toHaveBeenCalledTimes(1)

    resolveCheck('up')
    await flushPromises()
    expect(wrapper.text()).toContain('已连接')
  })

  it('does not update state after the view is unmounted', async () => {
    let resolveCheck: (state: ConnectionState) => void = () => {}
    mockedCheck.mockReturnValue(
      new Promise<ConnectionState>((resolve) => {
        resolveCheck = resolve
      }),
    )
    const wrapper = mount(HomeView)
    await Promise.resolve()

    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    wrapper.unmount()
    resolveCheck('up')
    await flushPromises()

    expect(warn).not.toHaveBeenCalled()
    warn.mockRestore()
  })
})
