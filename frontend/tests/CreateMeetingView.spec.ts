import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as meetingsApi from '@/api/meetings'
import MeetingForm from '@/components/MeetingForm.vue'
import { useToast } from '@/composables/useToast'
import type { AutoImportResult } from '@/utils/autoImport'
import CreateMeetingView from '@/views/newMeeting/CreateMeetingView.vue'

const { pushMock, replaceMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock, back: vi.fn() }),
}))

vi.mock('@/api/meetings', () => ({
  createMeeting: vi.fn(),
}))

const createDefaultMeetingFolder = vi.fn(async () => {})
const listSubdirs = vi.fn(async (): Promise<string[]> => [])
const wsState = vi.hoisted(() => ({
  status: { value: 'unconfigured' as string },
  rootHandle: { value: null as unknown },
}))

vi.mock('@/composables/useLocalWorkspace', () => ({
  useLocalWorkspace: () => ({
    status: wsState.status,
    rootHandle: wsState.rootHandle,
    directoryName: { value: '' },
    createDefaultMeetingFolder,
    listSubdirs,
  }),
}))

vi.mock('@/utils/localFileSystem', () => ({
  storeMeetingRoot: vi.fn(async () => {}),
  listSubdirs: (...args: unknown[]) => listSubdirs(...(args as [])),
  isLocalWorkspaceSupported: () => true,
}))

const autoImportMeetingFiles = vi.fn()
vi.mock('@/utils/autoImport', () => ({
  AUTO_IMPORT_MAX_FILES: 50,
  autoImportMeetingFiles: (options: unknown) => autoImportMeetingFiles(options),
}))

const created = {
  meeting_id: 'mtg_new',
  title: '项目周会',
  topic: null,
  meeting_time: null,
  status: 'scheduled' as const,
  created_at: '2026-11-04T09:00:00+08:00',
  updated_at: '2026-11-04T09:00:00+08:00',
  archived_at: null,
}

const importedResult: AutoImportResult = {
  imported: ['a.pdf'],
  skipped: ['b.pdf'],
  unsupported: ['photo.png'],
  oversized: [],
  failed: [],
  truncated: false,
}

function mountView() {
  return mount(CreateMeetingView)
}

/** 通过表单组件直接提交（绕过级联选择器交互，聚焦视图接线） */
async function submitWithPath(wrapper: ReturnType<typeof mountView>, localPath: string[]) {
  await wrapper.findComponent(MeetingForm).vm.$emit('submit', {
    title: '项目周会',
    localPath,
  })
  await flushPromises()
}

describe('CreateMeetingView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    wsState.status.value = 'unconfigured'
    wsState.rootHandle.value = null
    useToast().toasts.value = []
    vi.mocked(meetingsApi.createMeeting).mockResolvedValue(created)
  })

  it('creates a meeting, uses the default folder and enters the flow page', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#meeting-title').setValue('  项目周会  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(meetingsApi.createMeeting).toHaveBeenCalledWith({
      title: '项目周会',
      topic: undefined,
      meeting_time: undefined,
    })
    // 未选择存储位置 → 不触发自动导入；已连接时落默认 <会议名>/，未连接时静默跳过
    expect(autoImportMeetingFiles).not.toHaveBeenCalled()
    expect(createDefaultMeetingFolder).toHaveBeenCalledWith('项目周会')
    expect(replaceMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })

  it('requires a title before submitting', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入会议标题')
    expect(meetingsApi.createMeeting).not.toHaveBeenCalled()
  })

  it('shows an authorize CTA when the workspace is not connected', async () => {
    const wrapper = mountView()
    await flushPromises()

    // 未连接：不渲染级联选择器，但提供创建页内授权入口（首次用户可完成选文件夹）
    expect(wrapper.findAll('select')).toHaveLength(0)
    const cta = wrapper.findAll('button').find((b) => b.text() === '选择本地文件夹')
    expect(cta).toBeTruthy()
  })

  it('shows the cascading storage picker once the workspace is connected', async () => {
    wsState.status.value = 'connected'
    wsState.rootHandle.value = { name: 'demo' }
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('本地存储位置')
    expect(wrapper.findAll('select').length).toBeGreaterThan(0)
    expect(
      wrapper.findAll('button').some((b) => b.text() === '选择本地文件夹'),
    ).toBe(false)
  })

  it('auto-imports folder files after creating with a chosen path', async () => {
    wsState.status.value = 'connected'
    wsState.rootHandle.value = { name: 'demo' }
    autoImportMeetingFiles.mockResolvedValue(importedResult)
    const wrapper = mountView()
    await flushPromises()

    await submitWithPath(wrapper, ['资料文件夹'])

    expect(autoImportMeetingFiles).toHaveBeenCalledWith(
      expect.objectContaining({
        meetingId: 'mtg_new',
        segments: ['资料文件夹'],
      }),
    )
    const toastText = useToast()
      .toasts.value.map((item) => item.message)
      .join(' | ')
    expect(toastText).toContain('已导入 1 个')
    expect(toastText).toContain('跳过 1 个已存在')
    expect(toastText).toContain('1 个格式不支持')
    expect(replaceMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })

  it('shows live progress while importing and navigates afterwards', async () => {
    wsState.status.value = 'connected'
    wsState.rootHandle.value = { name: 'demo' }
    let finishImport: ((result: AutoImportResult) => void) | undefined
    autoImportMeetingFiles.mockImplementation(
      (options: { onProgress?: (p: never) => void }) =>
        new Promise<AutoImportResult>((resolve) => {
          finishImport = resolve
          options.onProgress?.({
            done: 1,
            total: 2,
            fileName: 'a.pdf',
          } as never)
        }),
    )
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findComponent(MeetingForm).vm.$emit('submit', {
      title: '项目周会',
      localPath: ['资料文件夹'],
    })
    await flushPromises()

    expect(wrapper.text()).toContain('正在从本地文件夹导入资料 1/2：a.pdf')
    expect(replaceMock).not.toHaveBeenCalled()

    finishImport?.(importedResult)
    await flushPromises()

    expect(wrapper.text()).not.toContain('正在从本地文件夹导入资料')
    expect(replaceMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })

  it('warns without blocking when folder permission is lost', async () => {
    // 选择了文件夹但权限中途失效（未连接）
    autoImportMeetingFiles.mockResolvedValue(importedResult)
    const wrapper = mountView()
    await flushPromises()

    await submitWithPath(wrapper, ['资料文件夹'])

    expect(autoImportMeetingFiles).not.toHaveBeenCalled()
    const toastText = useToast()
      .toasts.value.map((item) => `${item.tone}:${item.message}`)
      .join(' | ')
    expect(toastText).toContain('权限未授予')
    expect(replaceMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })

  it('still navigates when the auto import fails', async () => {
    wsState.status.value = 'connected'
    wsState.rootHandle.value = { name: 'demo' }
    autoImportMeetingFiles.mockRejectedValue(new Error('目录读取失败'))
    const wrapper = mountView()
    await flushPromises()

    await submitWithPath(wrapper, ['资料文件夹'])

    const toastText = useToast()
      .toasts.value.map((item) => `${item.tone}:${item.message}`)
      .join(' | ')
    expect(toastText).toContain('未自动导入')
    expect(toastText).toContain('目录读取失败')
    expect(replaceMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })

  it('reports per-file failures with file names', async () => {
    wsState.status.value = 'connected'
    wsState.rootHandle.value = { name: 'demo' }
    autoImportMeetingFiles.mockResolvedValue({
      ...importedResult,
      imported: [],
      failed: [{ name: 'a.pdf', reason: '上传失败' }, { name: 'b.pdf', reason: '超时' }],
    })
    const wrapper = mountView()
    await flushPromises()

    await submitWithPath(wrapper, ['资料文件夹'])

    const toastText = useToast()
      .toasts.value.map((item) => `${item.tone}:${item.message}`)
      .join(' | ')
    expect(toastText).toContain('error:')
    expect(toastText).toContain('a.pdf（上传失败）')
    expect(toastText).toContain('b.pdf（超时）')
    expect(replaceMock).toHaveBeenCalledWith({
      name: 'new-meeting',
      query: { meetingId: 'mtg_new' },
    })
  })
})
