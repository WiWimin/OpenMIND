import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as minutesApi from '@/api/minutes'
import MinutesSection from '@/components/MinutesSection.vue'
import type { ListData } from '@/types/api'
import type { Minutes } from '@/types/minutes'

vi.mock('@/api/minutes', () => ({
  listMinutes: vi.fn(),
  generateMinutes: vi.fn(),
  getMinutes: vi.fn(),
  updateMinutes: vi.fn(),
  confirmMinutes: vi.fn(),
}))

const minutes: Minutes = {
  minutes_id: 'min_1',
  meeting_id: 'mtg_1',
  content: '会议纪要草稿',
  status: 'draft',
  version: 1,
  source_record_ids: ['rec_1'],
  created_at: '2026-10-01T10:00:00+08:00',
  updated_at: '2026-10-01T10:00:00+08:00',
}

function listOf(items: Minutes[]): ListData<Minutes> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountSection(): VueWrapper {
  return mount(MinutesSection, { props: { meetingId: 'mtg_1' } })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('MinutesSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows the empty state', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有纪要')
  })

  it('lists and edits a minutes draft', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([minutes]))
    vi.mocked(minutesApi.updateMinutes).mockResolvedValue({ ...minutes, content: '改后' })
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.minutes-section__item').trigger('click')
    expect((wrapper.get('#minutes-content').element as HTMLTextAreaElement).value).toBe(
      '会议纪要草稿',
    )

    await wrapper.get('#minutes-content').setValue('改后')
    await button(wrapper, '保存')?.trigger('click')
    await flushPromises()

    expect(minutesApi.updateMinutes).toHaveBeenCalledWith('min_1', { content: '改后' })
  })

  it('generates a minutes draft', async () => {
    vi.mocked(minutesApi.listMinutes)
      .mockResolvedValueOnce(listOf([]))
      .mockResolvedValue(listOf([minutes]))
    vi.mocked(minutesApi.generateMinutes).mockResolvedValue(minutes)
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '生成会议纪要')?.trigger('click')
    await flushPromises()

    expect(minutesApi.generateMinutes).toHaveBeenCalledWith('mtg_1', {
      record_ids: [],
      include_action_items: true,
    })
    expect(minutesApi.listMinutes).toHaveBeenCalledTimes(2)
    expect(wrapper.find('#minutes-content').exists()).toBe(true)
  })

  it('confirms a minutes draft', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([minutes]))
    vi.mocked(minutesApi.confirmMinutes).mockResolvedValue({ ...minutes, status: 'confirmed' })
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.minutes-section__item').trigger('click')
    await button(wrapper, '确认')?.trigger('click')
    await flushPromises()

    expect(minutesApi.confirmMinutes).toHaveBeenCalledWith('min_1')
    expect(wrapper.text()).toContain('已确认')
  })
})
