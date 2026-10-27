import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from '@/api/chat'
import * as recordsApi from '@/api/records'
import RecordSection from '@/components/RecordSection.vue'
import type { ListData } from '@/types/api'
import type { MeetingRecord } from '@/types/record'

vi.mock('@/api/records', () => ({
  listRecords: vi.fn(),
  createRecord: vi.fn(),
  updateRecord: vi.fn(),
  deleteRecord: vi.fn(),
}))

vi.mock('@/api/chat', () => ({
  askMeeting: vi.fn(),
  organizeRecords: vi.fn(),
}))

const record: MeetingRecord = {
  record_id: 'rec_1',
  meeting_id: 'mtg_1',
  content: '讨论记录正文',
  record_type: 'manual',
  marker_type: null,
  source_material_id: null,
  created_at: '2026-10-01T09:15:00+08:00',
  updated_at: '2026-10-01T09:15:00+08:00',
}

function listOf(items: MeetingRecord[]): ListData<MeetingRecord> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountSection(): VueWrapper {
  return mount(RecordSection, { props: { meetingId: 'mtg_1' } })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('RecordSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders the records', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([record]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('讨论记录正文')
  })

  it('shows the empty state', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有记录')
  })

  it('adds a record then refreshes', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([]))
    vi.mocked(recordsApi.createRecord).mockResolvedValue(record)
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('#record-content').setValue('新的记录')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(recordsApi.createRecord).toHaveBeenCalledWith('mtg_1', {
      content: '新的记录',
      record_type: 'manual',
    })
    expect(recordsApi.listRecords).toHaveBeenCalledTimes(2)
  })

  it('imports transcript text as a transcript record', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([]))
    vi.mocked(recordsApi.createRecord).mockResolvedValue({ ...record, record_type: 'transcript' })
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '导入转写文本')?.trigger('click')
    await wrapper.get('#record-import-content').setValue('甲：先对齐一下进度。乙：测试通过了。')
    await wrapper.get('form.record-section__import').trigger('submit')
    await flushPromises()

    expect(recordsApi.createRecord).toHaveBeenCalledWith('mtg_1', {
      content: '甲：先对齐一下进度。乙：测试通过了。',
      record_type: 'transcript',
    })
    expect(wrapper.find('form.record-section__import').exists()).toBe(false)
  })

  it('imports external text as an imported record', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([]))
    vi.mocked(recordsApi.createRecord).mockResolvedValue({ ...record, record_type: 'imported' })
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '导入转写文本')?.trigger('click')
    await wrapper.get('#record-import-content').setValue('外部纪要草稿')
    await wrapper.get('#record-import-type').setValue('imported')
    await wrapper.get('form.record-section__import').trigger('submit')
    await flushPromises()

    expect(recordsApi.createRecord).toHaveBeenCalledWith('mtg_1', {
      content: '外部纪要草稿',
      record_type: 'imported',
    })
  })

  it('rejects an empty import', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([]))
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '导入转写文本')?.trigger('click')
    await wrapper.get('form.record-section__import').trigger('submit')
    await flushPromises()

    expect(recordsApi.createRecord).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('导入内容不能为空')
  })

  it('updates a record', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([record]))
    vi.mocked(recordsApi.updateRecord).mockResolvedValue({ ...record, content: '改' })
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '编辑')?.trigger('click')
    await wrapper.get('#record-edit').setValue('改')
    await button(wrapper, '保存')?.trigger('click')
    await flushPromises()

    expect(recordsApi.updateRecord).toHaveBeenCalledWith('rec_1', { content: '改' })
  })

  it('updates a record marker', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([record]))
    vi.mocked(recordsApi.updateRecord).mockResolvedValue({
      ...record,
      marker_type: 'decision',
    })
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '决议')?.trigger('click')
    await flushPromises()

    expect(recordsApi.updateRecord).toHaveBeenCalledWith('rec_1', {
      marker_type: 'decision',
    })
  })

  it('deletes a record after confirmation', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([record]))
    vi.mocked(recordsApi.deleteRecord).mockResolvedValue({ deleted: true, record_id: 'rec_1' })
    const wrapper = mountSection()
    await flushPromises()

    await button(wrapper, '删除')?.trigger('click')
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((item) => item.text() === '删除')
    await confirm?.trigger('click')
    await flushPromises()

    expect(recordsApi.deleteRecord).toHaveBeenCalledWith('rec_1')
  })

  it('organizes the selected records and shows an editable result', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([record]))
    vi.mocked(chatApi.organizeRecords).mockResolvedValue({
      organized_content: '主要议题：进度对齐；待确认：上线时间。',
      source_record_ids: ['rec_1'],
    })
    const wrapper = mountSection()
    await flushPromises()

    const checkbox = wrapper.get('.record-section__checkbox')
    await checkbox.setValue(true)
    await button(wrapper, 'AI 整理所选（1）')?.trigger('click')
    await flushPromises()

    expect(chatApi.organizeRecords).toHaveBeenCalledWith('mtg_1', { record_ids: ['rec_1'] })
    const result = wrapper.get('#record-organized-content').element as HTMLTextAreaElement
    expect(result.value).toBe('主要议题：进度对齐；待确认：上线时间。')
    expect(wrapper.text()).toContain('AI 整理结果')
  })

  it('saves the edited organize result as a new record', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([record]))
    vi.mocked(chatApi.organizeRecords).mockResolvedValue({
      organized_content: '整理稿',
      source_record_ids: ['rec_1'],
    })
    vi.mocked(recordsApi.createRecord).mockResolvedValue({ ...record, record_id: 'rec_2' })
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.record-section__checkbox').setValue(true)
    await button(wrapper, 'AI 整理所选（1）')?.trigger('click')
    await flushPromises()

    await wrapper.get('#record-organized-content').setValue('用户修改后的整理稿')
    await button(wrapper, '另存为记录')?.trigger('click')
    await flushPromises()

    expect(recordsApi.createRecord).toHaveBeenCalledWith('mtg_1', {
      content: '用户修改后的整理稿',
      record_type: 'manual',
    })
    expect(wrapper.find('.record-section__result').exists()).toBe(false)
  })

  it('disables the organize button when nothing is selected', async () => {
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([record]))
    const wrapper = mountSection()
    await flushPromises()

    const organizeButton = button(wrapper, 'AI 整理所选（0）')
    expect(organizeButton?.attributes('disabled')).toBeDefined()
  })
})
