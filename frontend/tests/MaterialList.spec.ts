import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MaterialList from '@/components/MaterialList.vue'
import type { Material } from '@/types/material'

const materials: Material[] = [
  {
    material_id: 'mat_1',
    meeting_id: 'mtg_1',
    file_name: '方案.pdf',
    type: 'pdf',
    source: null,
    processing_status: 'processed',
    parse_error: null,
    created_at: '2026-10-01T09:10:00+08:00',
  },
  {
    material_id: 'mat_2',
    meeting_id: 'mtg_1',
    file_name: '记录.docx',
    type: 'docx',
    source: null,
    processing_status: 'uploaded',
    parse_error: null,
    created_at: '2026-10-01T09:11:00+08:00',
  },
]

describe('MaterialList', () => {
  it('renders one item per material', () => {
    const wrapper = mount(MaterialList, { props: { items: materials } })
    expect(wrapper.findAll('.material-item')).toHaveLength(2)
  })

  it('re-emits delete from an item', async () => {
    const wrapper = mount(MaterialList, { props: { items: materials } })
    const deleteButton = wrapper
      .findAll('.material-item')[1]
      .findAll('.app-button')
      .find((button) => button.text() === '删除')
    await deleteButton?.trigger('click')
    expect(wrapper.emitted('delete')).toEqual([['mat_2']])
  })

  it('re-emits view from an item', async () => {
    const wrapper = mount(MaterialList, { props: { items: materials } })
    const viewButton = wrapper
      .findAll('.material-item')[0]
      .findAll('.app-button')
      .find((button) => button.text() === '查看详情')
    await viewButton?.trigger('click')
    expect(wrapper.emitted('view')).toEqual([['mat_1']])
  })
})
