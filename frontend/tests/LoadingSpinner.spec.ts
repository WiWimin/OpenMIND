import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import LoadingSpinner from '@/components/LoadingSpinner.vue'

describe('LoadingSpinner', () => {
  it('exposes an accessible status label', () => {
    const wrapper = mount(LoadingSpinner)
    expect(wrapper.get('[role="status"]').attributes('aria-label')).toBe('加载中')
  })

  it('supports a custom label and size', () => {
    const wrapper = mount(LoadingSpinner, { props: { label: '提交中', size: 'sm' } })
    const root = wrapper.get('[role="status"]')
    expect(root.attributes('aria-label')).toBe('提交中')
    expect(root.classes()).toContain('loading-spinner--sm')
  })
})
