import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import StatusBadge from '@/components/StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders the label with the neutral tone by default', () => {
    const wrapper = mount(StatusBadge, { props: { label: '草稿' } })
    expect(wrapper.text()).toBe('草稿')
    expect(wrapper.classes()).toContain('status-badge--neutral')
  })

  it('applies the requested tone', () => {
    const wrapper = mount(StatusBadge, { props: { label: '解析失败', tone: 'danger' } })
    expect(wrapper.classes()).toContain('status-badge--danger')
  })
})
