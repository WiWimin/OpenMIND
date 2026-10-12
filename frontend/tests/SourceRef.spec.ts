import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SourceRef from '@/components/SourceRef.vue'

describe('SourceRef', () => {
  it('renders the excerpt with the default label', () => {
    const wrapper = mount(SourceRef, { props: { excerpt: '张三负责下周完成联调' } })
    expect(wrapper.get('.source-ref__label').text()).toContain('来源')
    expect(wrapper.get('.source-ref__excerpt').text()).toBe('张三负责下周完成联调')
  })

  it('renders an optional reference', () => {
    const wrapper = mount(SourceRef, {
      props: { excerpt: '片段', reference: 'rec_123' },
    })
    expect(wrapper.get('.source-ref__reference').text()).toContain('rec_123')
  })

  it('supports a custom label', () => {
    const wrapper = mount(SourceRef, { props: { excerpt: '片段', label: '原文' } })
    expect(wrapper.get('.source-ref__label').text()).toContain('原文')
  })
})
