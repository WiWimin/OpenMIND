import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RecordItem from '@/components/RecordItem.vue'
import type { MeetingRecord } from '@/types/record'

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

function button(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('RecordItem', () => {
  it('renders the content and type', () => {
    const wrapper = mount(RecordItem, { props: { record } })
    expect(wrapper.text()).toContain('讨论记录正文')
    expect(wrapper.text()).toContain('手动记录')
  })

  it('edits and emits the new content', async () => {
    const wrapper = mount(RecordItem, { props: { record } })

    await button(wrapper, '编辑')?.trigger('click')
    await wrapper.get('#record-edit').setValue('修改后的内容')
    await button(wrapper, '保存')?.trigger('click')

    expect(wrapper.emitted('save')).toEqual([['修改后的内容']])
  })

  it('rejects an empty edit', async () => {
    const wrapper = mount(RecordItem, { props: { record } })

    await button(wrapper, '编辑')?.trigger('click')
    await wrapper.get('#record-edit').setValue('   ')
    await button(wrapper, '保存')?.trigger('click')

    expect(wrapper.text()).toContain('记录内容不能为空')
    expect(wrapper.emitted('save')).toBeUndefined()
  })

  it('emits delete', async () => {
    const wrapper = mount(RecordItem, { props: { record } })
    await button(wrapper, '删除')?.trigger('click')
    expect(wrapper.emitted('delete')).toHaveLength(1)
  })

  it('renders the marker badge', () => {
    const wrapper = mount(RecordItem, {
      props: { record: { ...record, marker_type: 'decision' } },
    })

    expect(wrapper.text()).toContain('决议')
  })

  it('emits a marker when toggled', async () => {
    const wrapper = mount(RecordItem, { props: { record } })

    await button(wrapper, '疑问')?.trigger('click')

    expect(wrapper.emitted('marker')).toEqual([['question']])
  })

  it('clears an active marker', async () => {
    const wrapper = mount(RecordItem, {
      props: { record: { ...record, marker_type: 'decision' } },
    })

    await button(wrapper, '决议')?.trigger('click')

    expect(wrapper.emitted('marker')).toEqual([[null]])
  })

  it('hides marker controls when readonly', () => {
    const wrapper = mount(RecordItem, {
      props: { record: { ...record, marker_type: 'highlight' }, readonly: true },
    })
    const labels = wrapper.findAll('button').map((item) => item.text())

    expect(wrapper.text()).toContain('重点')
    expect(labels).not.toContain('决议')
    expect(labels).not.toContain('疑问')
  })
})
