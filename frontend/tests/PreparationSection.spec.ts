import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as preparationsApi from '@/api/preparations'
import PreparationSection from '@/components/PreparationSection.vue'
import type { ListData } from '@/types/api'
import type { Preparation } from '@/types/preparation'

vi.mock('@/api/preparations', () => ({
  generatePreparation: vi.fn(),
  listPreparations: vi.fn(),
  getPreparation: vi.fn(),
  updatePreparation: vi.fn(),
  confirmPreparation: vi.fn(),
}))

const preparation: Preparation = {
  preparation_id: 'prep_1',
  meeting_id: 'mtg_1',
  summary: '会议背景摘要',
  checklist: ['确认里程碑'],
  status: 'draft',
  version: 1,
  created_at: '2026-10-01T09:20:00+08:00',
  updated_at: '2026-10-01T09:20:00+08:00',
}

function listOf(items: Preparation[]): ListData<Preparation> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountSection(): VueWrapper {
  return mount(PreparationSection, { props: { meetingId: 'mtg_1' } })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('PreparationSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('shows the empty state', async () => {
    vi.mocked(preparationsApi.listPreparations).mockResolvedValue(listOf([]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有准备稿')
  })

  it('edits a preparation', async () => {
    vi.mocked(preparationsApi.listPreparations).mockResolvedValue(listOf([preparation]))
    vi.mocked(preparationsApi.updatePreparation).mockResolvedValue(preparation)
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.preparation-section__item').trigger('click')
    await wrapper.get('#preparation-summary').setValue('新的摘要')
    await wrapper.get('#preparation-checklist').setValue('任务A\n任务B')
    await button(wrapper, '保存')?.trigger('click')
    await flushPromises()

    expect(preparationsApi.updatePreparation).toHaveBeenCalledWith('prep_1', {
      summary: '新的摘要',
      checklist: ['任务A', '任务B'],
    })
  })

  it('generates a preparation', async () => {
    vi.mocked(preparationsApi.listPreparations)
      .mockResolvedValueOnce(listOf([]))
      .mockResolvedValue(listOf([preparation]))
    vi.mocked(preparationsApi.generatePreparation).mockResolvedValue(preparation)
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('#preparation-goal').setValue('确认风险')
    await button(wrapper, '生成准备稿')?.trigger('click')
    await flushPromises()

    expect(preparationsApi.generatePreparation).toHaveBeenCalledWith('mtg_1', {
      include_history: true,
      user_goal: '确认风险',
    })
    expect(preparationsApi.listPreparations).toHaveBeenCalledTimes(2)
    expect(wrapper.find('#preparation-summary').exists()).toBe(true)
  })

  it('confirms a preparation', async () => {
    vi.mocked(preparationsApi.listPreparations).mockResolvedValue(listOf([preparation]))
    vi.mocked(preparationsApi.confirmPreparation).mockResolvedValue({
      ...preparation,
      status: 'confirmed',
    })
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.preparation-section__item').trigger('click')
    await button(wrapper, '确认')?.trigger('click')
    await flushPromises()

    expect(preparationsApi.confirmPreparation).toHaveBeenCalledWith('prep_1')
  })

  it('hides the confirm button once confirmed', async () => {
    vi.mocked(preparationsApi.listPreparations).mockResolvedValue(
      listOf([{ ...preparation, status: 'confirmed' }]),
    )
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.preparation-section__item').trigger('click')

    expect(button(wrapper, '确认')).toBeUndefined()
  })
})
