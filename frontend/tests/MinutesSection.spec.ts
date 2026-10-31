import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as minutesApi from '@/api/minutes'
import MinutesSection from '@/components/MinutesSection.vue'
import { useToast } from '@/composables/useToast'
import type { ListData } from '@/types/api'
import type { Minutes } from '@/types/minutes'
import * as minutesDocx from '@/utils/minutesDocx'

vi.mock('@/api/minutes', () => ({
  listMinutes: vi.fn(),
  generateMinutes: vi.fn(),
  getMinutes: vi.fn(),
  updateMinutes: vi.fn(),
  confirmMinutes: vi.fn(),
}))

const { mirrorConfirmedMinutes } = vi.hoisted(() => ({ mirrorConfirmedMinutes: vi.fn() }))

vi.mock('@/composables/useLocalWorkspace', () => ({
  useLocalWorkspace: () => ({ mirrorConfirmedMinutes }),
}))

vi.mock('@/components/RichTextEditor.vue', () => ({
  default: {
    props: { id: String, modelValue: String, label: String },
    emits: ['update:modelValue'],
    template:
      '<div><label :for="id">{{ label }}</label><textarea :id="id" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" /></div>',
  },
}))

vi.mock('@/utils/minutesDocx', () => ({
  buildMinutesDocxBlob: vi.fn(),
  downloadBlob: vi.fn(),
}))

const minutes: Minutes = {
  minutes_id: 'min_1',
  meeting_id: 'mtg_1',
  content: '会议纪要草稿',
  status: 'draft',
  version: 1,
  template: 'standard',
  source_record_ids: ['rec_1'],
  source_material_ids: [],
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
    mirrorConfirmedMinutes.mockResolvedValue('skipped')
    // toast 是模块级单例，清掉上一个用例遗留的提示，避免断言互相污染
    for (const toast of [...useToast().toasts.value]) {
      useToast().dismiss(toast.id)
    }
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

    expect(minutesApi.generateMinutes).toHaveBeenCalledWith(
      'mtg_1',
      {
        record_ids: [],
        include_action_items: true,
        include_materials: true,
      },
      expect.anything(),
    )
    expect(minutesApi.listMinutes).toHaveBeenCalledTimes(2)
    expect(wrapper.find('#minutes-content').exists()).toBe(true)
  })

  it('can generate without materials', async () => {
    vi.mocked(minutesApi.listMinutes)
      .mockResolvedValueOnce(listOf([]))
      .mockResolvedValue(listOf([minutes]))
    vi.mocked(minutesApi.generateMinutes).mockResolvedValue(minutes)
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.minutes-section__materials input').setValue(false)
    await button(wrapper, '生成会议纪要')?.trigger('click')
    await flushPromises()

    expect(minutesApi.generateMinutes).toHaveBeenCalledWith(
      'mtg_1',
      {
        record_ids: [],
        include_action_items: true,
        include_materials: false,
      },
      expect.anything(),
    )
  })

  it('generates with the selected template and displays it', async () => {
    vi.mocked(minutesApi.listMinutes)
      .mockResolvedValueOnce(listOf([]))
      .mockResolvedValue(listOf([{ ...minutes, template: 'concise' }]))
    vi.mocked(minutesApi.generateMinutes).mockResolvedValue({
      ...minutes,
      template: 'concise',
    })
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('#minutes-template').setValue('concise')
    await button(wrapper, '生成会议纪要')?.trigger('click')
    await flushPromises()

    expect(minutesApi.generateMinutes).toHaveBeenCalledWith(
      'mtg_1',
      {
        record_ids: [],
        include_action_items: true,
        include_materials: true,
        template: 'concise',
      },
      expect.anything(),
    )
    expect(wrapper.text()).toContain('简洁记录')
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

  it('mirrors confirmed minutes to the local folder and reports success', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([minutes]))
    const confirmed = { ...minutes, status: 'confirmed' as const, content: '确认后的纪要' }
    vi.mocked(minutesApi.confirmMinutes).mockResolvedValue(confirmed)
    mirrorConfirmedMinutes.mockResolvedValue('written')
    const wrapper = mount(MinutesSection, {
      props: { meetingId: 'mtg_1', meetingTitle: '项目周会' },
    })
    await flushPromises()

    await wrapper.get('.minutes-section__item').trigger('click')
    await button(wrapper, '确认')?.trigger('click')
    await flushPromises()

    expect(mirrorConfirmedMinutes).toHaveBeenCalledWith('mtg_1', '确认后的纪要', '项目周会')
    expect(useToast().toasts.value.some((toast) => toast.message.includes('已同步到本地文件夹'))).toBe(
      true,
    )
  })

  it('warns when the local folder sync fails', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([minutes]))
    vi.mocked(minutesApi.confirmMinutes).mockResolvedValue({ ...minutes, status: 'confirmed' })
    mirrorConfirmedMinutes.mockResolvedValue('failed')
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.minutes-section__item').trigger('click')
    await button(wrapper, '确认')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已确认')
    expect(useToast().toasts.value.some((toast) => toast.message.includes('本地文件夹同步失败'))).toBe(
      true,
    )
  })

  it('stays silent when the local workspace is not connected', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([minutes]))
    vi.mocked(minutesApi.confirmMinutes).mockResolvedValue({ ...minutes, status: 'confirmed' })
    mirrorConfirmedMinutes.mockResolvedValue('skipped')
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.minutes-section__item').trigger('click')
    await button(wrapper, '确认')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('已确认')
    expect(
      useToast().toasts.value.some((toast) => toast.message.includes('已同步到本地文件夹')),
    ).toBe(false)
  })

  it('exports the selected draft as docx', async () => {
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([minutes]))
    const blob = new Blob(['docx'], { type: 'application/octet-stream' })
    vi.mocked(minutesDocx.buildMinutesDocxBlob).mockResolvedValue(blob)
    const wrapper = mount(MinutesSection, {
      props: { meetingId: 'mtg_1', meetingTitle: '项目周会' },
    })
    await flushPromises()

    await wrapper.get('.minutes-section__item').trigger('click')
    await button(wrapper, '导出 DOCX')?.trigger('click')
    await flushPromises()

    expect(minutesDocx.buildMinutesDocxBlob).toHaveBeenCalledWith(
      '项目周会 · 会议纪要',
      '会议纪要草稿',
    )
    expect(minutesDocx.downloadBlob).toHaveBeenCalledWith(blob, '项目周会 · 会议纪要.docx')
  })
})
