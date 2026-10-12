import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppTag from '@/components/AppTag.vue'

describe('AppTag', () => {
  it('renders the label prop', () => {
    const wrapper = mount(AppTag, { props: { label: '会前材料' } })
    expect(wrapper.text()).toBe('会前材料')
  })

  it('prefers slot content over the label', () => {
    const wrapper = mount(AppTag, {
      props: { label: 'fallback' },
      slots: { default: '手动记录' },
    })
    expect(wrapper.text()).toBe('手动记录')
  })

  it('exposes the title attribute', () => {
    const wrapper = mount(AppTag, { props: { label: 'x', title: '提示' } })
    expect(wrapper.attributes('title')).toBe('提示')
  })
})
