import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as memoryApi from '@/api/memory'
import MemoryDialog from '@/components/settings/MemoryDialog.vue'
import type { UserMemory } from '@/types/memory'

vi.mock('@/api/memory', () => ({
  getMemory: vi.fn(),
  saveMemory: vi.fn(),
  clearMemory: vi.fn(),
}))

const memory: UserMemory = {
  role: '产品经理',
  work_scenarios: 'B2B SaaS 产品规划',
  communication_style: '结论先行',
  preferred_minutes_template: 'standard',
  updated_at: '2026-10-20T10:00:00+08:00',
}

function mountDialog() {
  return mount(MemoryDialog, { props: { open: true } })
}

describe('MemoryDialog', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(memoryApi.getMemory).mockResolvedValue(memory)
  })

  it('loads and renders the memory fields', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    expect(wrapper.find('#memory-role').element as HTMLInputElement).toBeTruthy()
    expect((wrapper.find('#memory-role').element as HTMLInputElement).value).toBe('产品经理')
    expect((wrapper.find('#memory-scenarios').element as HTMLTextAreaElement).value).toBe(
      'B2B SaaS 产品规划',
    )
    expect((wrapper.find('#memory-style').element as HTMLTextAreaElement).value).toBe('结论先行')
  })

  it('saves the memory fields', async () => {
    vi.mocked(memoryApi.saveMemory).mockResolvedValue(memory)
    const wrapper = mountDialog()
    await flushPromises()

    await wrapper.find('#memory-role').setValue('资深产品经理')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(memoryApi.saveMemory).toHaveBeenCalledWith({
      role: '资深产品经理',
      work_scenarios: 'B2B SaaS 产品规划',
      communication_style: '结论先行',
      preferred_minutes_template: 'standard',
    })
  })

  it('clears the memory after confirmation', async () => {
    vi.mocked(memoryApi.clearMemory).mockResolvedValue({ deleted: true })
    const wrapper = mountDialog()
    await flushPromises()

    const clearButton = wrapper.findAll('button').find((node) => node.text() === '清除记忆')
    await clearButton?.trigger('click')
    await flushPromises()

    const confirmButton = wrapper.findAll('button').find((node) => node.text() === '清除')
    await confirmButton?.trigger('click')
    await flushPromises()

    expect(memoryApi.clearMemory).toHaveBeenCalled()
    expect((wrapper.find('#memory-role').element as HTMLInputElement).value).toBe('')
  })
})
