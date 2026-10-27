import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as memoryApi from '@/api/memory'
import MemoryView from '@/views/MemoryView.vue'
import type { UserMemory } from '@/types/memory'

vi.mock('@/api/memory', () => ({
  getMemory: vi.fn(),
  saveMemory: vi.fn(),
  clearMemory: vi.fn(),
}))

const memory: UserMemory = {
  role: '产品经理',
  work_scenarios: 'B2B SaaS',
  communication_style: '结论先行',
  preferred_minutes_template: 'concise',
  updated_at: '2026-10-01T09:00:00+08:00',
}

const emptyMemory: UserMemory = {
  role: '',
  work_scenarios: '',
  communication_style: '',
  preferred_minutes_template: null,
  updated_at: null,
}

function mountView(): VueWrapper {
  return mount(MemoryView)
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text().includes(text))
}

describe('MemoryView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('loads and renders memory', async () => {
    vi.mocked(memoryApi.getMemory).mockResolvedValue(memory)
    const wrapper = mountView()
    await flushPromises()

    expect((wrapper.get('#memory-role').element as HTMLInputElement).value).toBe('产品经理')
    expect((wrapper.get('#memory-style').element as HTMLTextAreaElement).value).toBe(
      '结论先行',
    )
    expect((wrapper.get('#memory-minutes-template').element as HTMLSelectElement).value).toBe(
      'concise',
    )
  })

  it('saves memory', async () => {
    vi.mocked(memoryApi.getMemory).mockResolvedValue(emptyMemory)
    vi.mocked(memoryApi.saveMemory).mockResolvedValue(memory)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#memory-role').setValue('产品经理')
    await wrapper.get('#memory-style').setValue('结论先行')
    await wrapper.get('#memory-minutes-template').setValue('concise')
    await wrapper.get('form.memory-form').trigger('submit')
    await flushPromises()

    expect(memoryApi.saveMemory).toHaveBeenCalledWith({
      role: '产品经理',
      work_scenarios: '',
      communication_style: '结论先行',
      preferred_minutes_template: 'concise',
    })
  })

  it('clears memory after confirmation', async () => {
    vi.mocked(memoryApi.getMemory).mockResolvedValue(memory)
    vi.mocked(memoryApi.clearMemory).mockResolvedValue({ deleted: true })
    const wrapper = mountView()
    await flushPromises()

    await button(wrapper, '清除记忆')?.trigger('click')
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((item) => item.text() === '清除')
    await confirm?.trigger('click')
    await flushPromises()

    expect(memoryApi.clearMemory).toHaveBeenCalledTimes(1)
    expect((wrapper.get('#memory-role').element as HTMLInputElement).value).toBe('')
  })
})
