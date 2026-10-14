import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RecordItem from '@/components/RecordItem.vue'
import type { MeetingRecord } from '@/types/record'

const record: MeetingRecord = {
  record_id: 'rec_1',
  meeting_id: 'mtg_1',
  content: '讨论记录正文',
  record_type: 'manual',
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
})
