import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import FolderPathPicker from '@/components/FolderPathPicker.vue'

const listSubdirs = vi.fn<(root: unknown, segments: string[]) => Promise<string[]>>(
  async () => [],
)

vi.mock('@/utils/localFileSystem', () => ({
  listSubdirs: (root: unknown, segments: string[]) => listSubdirs(root, segments),
}))

vi.mock('@/composables/useLocalWorkspace', () => ({
  useLocalWorkspace: () => ({
    status: { value: 'connected' },
    rootHandle: { value: { name: 'demo' } },
    directoryName: { value: 'demo' },
  }),
}))

function mountPicker(modelValue: string[] = []): VueWrapper {
  return mount(FolderPathPicker, {
    props: {
      modelValue,
      defaultLabel: '默认：授权目录/项目周会/',
    },
  }) as VueWrapper
}

/** 模拟 v-model：选择后把最后 emit 的值写回 props */
async function pick(wrapper: VueWrapper, index: number, value: string): Promise<void> {
  await wrapper.findAll('select')[index].setValue(value)
  await flushPromises()
  const emitted = wrapper.emitted('update:modelValue')
  const last = emitted?.[emitted.length - 1]?.[0] as string[]
  await wrapper.setProps({ modelValue: last })
  await flushPromises()
}

describe('FolderPathPicker', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('lists root folders with the default option first', async () => {
    listSubdirs.mockResolvedValue(['A 文档', 'B 文档'])
    const wrapper = mountPicker()
    await flushPromises()

    const selects = wrapper.findAll('select')
    expect(selects).toHaveLength(1)
    const options = selects[0].findAll('option')
    expect(options[0].text()).toBe('默认：授权目录/项目周会/')
    expect(options[1].text()).toBe('A 文档')
    expect(wrapper.text()).toContain('默认：授权目录/项目周会/')
  })

  it('drills into subfolders level by level and emits the path', async () => {
    listSubdirs.mockImplementation(
      async (_root: unknown, segments: string[]) =>
        segments.length === 0 ? ['A 文档'] : ['子目录'],
    )
    const wrapper = mountPicker()
    await flushPromises()

    await pick(wrapper, 0, 'A 文档')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([['A 文档']])
    expect(wrapper.findAll('select')).toHaveLength(2)
    expect(wrapper.text()).toContain('会议文件夹：A 文档')

    await pick(wrapper, 1, '子目录')

    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([['A 文档', '子目录']])
    expect(wrapper.text()).toContain('会议文件夹：A 文档/子目录')
  })

  it('stops at the current level and truncates deeper selects', async () => {
    listSubdirs.mockImplementation(
      async (_root: unknown, segments: string[]) =>
        segments.length === 0 ? ['A 文档'] : ['子目录'],
    )
    const wrapper = mountPicker(['A 文档'])
    await flushPromises()

    // 预置路径应重建出两层（值绑定 + 可下钻层）
    expect(wrapper.findAll('select')).toHaveLength(2)

    // 下钻一层 → 三层
    await pick(wrapper, 1, '子目录')
    expect(wrapper.findAll('select')).toHaveLength(3)

    // 回到第 2 层选「用当前文件夹」→ 路径回退并截断第 3 层
    await pick(wrapper, 1, '__stop__')

    expect(wrapper.emitted('update:modelValue')?.[1]).toEqual([['A 文档']])
    expect(wrapper.findAll('select')).toHaveLength(2)
  })

  it('falls back to default when the first level stops', async () => {
    listSubdirs.mockResolvedValue(['A 文档'])
    const wrapper = mountPicker(['A 文档'])
    await flushPromises()

    await pick(wrapper, 0, '__stop__')

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([[]])
  })

  it('surfaces read failures without throwing', async () => {
    listSubdirs.mockRejectedValue(new Error('权限不足'))
    const wrapper = mountPicker()
    await flushPromises()

    expect(wrapper.text()).toContain('无法读取本地文件夹')
  })
})
