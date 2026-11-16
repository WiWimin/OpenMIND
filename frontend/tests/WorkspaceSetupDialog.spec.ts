import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import WorkspaceSetupDialog from '@/components/settings/WorkspaceSetupDialog.vue'

const status = ref<'unconfigured' | 'connected' | 'needs-permission'>('unconfigured')
const directoryName = ref('')
const connectMock = vi.fn()
const restoreMock = vi.fn()
const initMock = vi.fn()

vi.mock('@/composables/useLocalWorkspace', () => ({
  useLocalWorkspace: () => ({
    status,
    directoryName,
    connect: connectMock,
    restore: restoreMock,
    init: initMock,
  }),
}))

vi.mock('@/utils/localFileSystem', () => ({
  isLocalWorkspaceSupported: () => true,
}))

function mountDialog() {
  return mount(WorkspaceSetupDialog, { props: { open: true } })
}

describe('WorkspaceSetupDialog（首次引导·绑定本地文件夹）', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    status.value = 'unconfigured'
    directoryName.value = ''
  })

  it('renders the directory picker entry before binding', () => {
    const wrapper = mountDialog()

    const picker = wrapper.findAll('button').find((node) => node.text() === '选择本地文件夹')
    expect(picker).toBeTruthy()
    expect(wrapper.text()).not.toContain('已选择：')
  })

  it('calls connect when picking a directory and shows the bound directory', async () => {
    connectMock.mockResolvedValue(true)
    const wrapper = mountDialog()
    await flushPromises()

    const picker = wrapper.findAll('button').find((node) => node.text() === '选择本地文件夹')
    await picker?.trigger('click')
    await flushPromises()

    expect(connectMock).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('本地文件夹已绑定')
  })

  it('emits close when the user finishes', async () => {
    const wrapper = mountDialog()

    const finish = wrapper.findAll('button').find((node) => node.text() === '完成')
    await finish?.trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
