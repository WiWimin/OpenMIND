import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PageHeader from '@/components/PageHeader.vue'

describe('PageHeader', () => {
  it('renders the title and description', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '会议列表', description: '查看并管理你的会议' },
    })
    expect(wrapper.get('h1').text()).toBe('会议列表')
    expect(wrapper.text()).toContain('查看并管理你的会议')
  })

  it('omits the description when not provided', () => {
    const wrapper = mount(PageHeader, { props: { title: '会议列表' } })
    expect(wrapper.find('.page-header__description').exists()).toBe(false)
  })

  it('renders the actions slot', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '会议列表' },
      slots: { actions: '<button type="button">新建</button>' },
    })
    expect(wrapper.get('.page-header__actions').text()).toContain('新建')
  })

  it('renders the default slot under the title', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '会议列表' },
      slots: { default: '<span>3 个会议</span>' },
    })
    expect(wrapper.get('.page-header__text').text()).toContain('3 个会议')
  })
})
