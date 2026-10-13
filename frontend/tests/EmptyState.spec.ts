import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import EmptyState from '@/components/EmptyState.vue'

describe('EmptyState', () => {
  it('renders the title and optional description', () => {
    const wrapper = mount(EmptyState, {
      props: { title: '还没有会议', description: '创建后可见' },
    })
    expect(wrapper.text()).toContain('还没有会议')
    expect(wrapper.text()).toContain('创建后可见')
  })

  it('omits the description when not provided', () => {
    const wrapper = mount(EmptyState, { props: { title: '空' } })
    expect(wrapper.find('.empty-state__description').exists()).toBe(false)
  })

  it('renders actions from the default slot', () => {
    const wrapper = mount(EmptyState, {
      props: { title: '空' },
      slots: { default: '<button type="button">新建</button>' },
    })
    expect(wrapper.get('.empty-state__actions').text()).toContain('新建')
  })
})
