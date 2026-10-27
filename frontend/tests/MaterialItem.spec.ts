import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MaterialItem from '@/components/MaterialItem.vue'
import type { Material } from '@/types/material'

const material: Material = {
  material_id: 'mat_1',
  meeting_id: 'mtg_1',
  file_name: '项目方案.pdf',
  type: 'pdf',
  source: '会前材料',
  processing_status: 'processed',
  parse_error: null,
  created_at: '2026-10-01T09:10:00+08:00',
}

describe('MaterialItem', () => {
  it('renders the material summary', () => {
    const wrapper = mount(MaterialItem, { props: { material } })
    expect(wrapper.text()).toContain('项目方案.pdf')
    expect(wrapper.text()).toContain('pdf')
    expect(wrapper.text()).toContain('会前材料')
    expect(wrapper.text()).toContain('已解析')
  })

  it('shows the parse error when present', () => {
    const wrapper = mount(MaterialItem, {
      props: { material: { ...material, processing_status: 'failed', parse_error: '无法解析' } },
    })
    expect(wrapper.text()).toContain('解析失败')
    expect(wrapper.text()).toContain('无法解析')
  })

  it('emits delete with the material id', async () => {
    const wrapper = mount(MaterialItem, { props: { material } })
    const deleteButton = wrapper.findAll('.app-button').find((node) => node.text() === '删除')
    await deleteButton?.trigger('click')
    expect(wrapper.emitted('delete')).toEqual([['mat_1']])
  })

  it('emits view with the material id', async () => {
    const wrapper = mount(MaterialItem, { props: { material } })
    const viewButton = wrapper.findAll('.app-button').find((node) => node.text() === '查看详情')
    await viewButton?.trigger('click')
    expect(wrapper.emitted('view')).toEqual([['mat_1']])
  })
})
