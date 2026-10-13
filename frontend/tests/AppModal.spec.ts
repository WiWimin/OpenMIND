import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppModal from '@/components/AppModal.vue'

describe('AppModal', () => {
  it('renders nothing when closed', () => {
    const wrapper = mount(AppModal, { props: { open: false } })
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('renders the title and slot content when open', () => {
    const wrapper = mount(AppModal, {
      props: { open: true, title: '新建会议' },
      slots: { default: '<p>正文内容</p>' },
    })
    expect(wrapper.get('[role="dialog"]').attributes('aria-label')).toBe('新建会议')
    expect(wrapper.text()).toContain('正文内容')
  })

  it('emits close when the overlay is clicked', async () => {
    const wrapper = mount(AppModal, { props: { open: true } })
    await wrapper.get('.modal').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('does not close when the panel itself is clicked', async () => {
    const wrapper = mount(AppModal, { props: { open: true } })
    await wrapper.get('.modal__panel').trigger('click')
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('emits close when the close button is clicked', async () => {
    const wrapper = mount(AppModal, { props: { open: true, title: '标题' } })
    await wrapper.get('.modal__close').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits close on Escape while open', () => {
    const wrapper = mount(AppModal, { props: { open: true } })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('stops listening for Escape after it closes', async () => {
    const wrapper = mount(AppModal, { props: { open: true } })
    await wrapper.setProps({ open: false })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('renders the footer slot', () => {
    const wrapper = mount(AppModal, {
      props: { open: true },
      slots: { footer: '<span>底部操作</span>' },
    })
    expect(wrapper.get('.modal__footer').text()).toContain('底部操作')
  })
})
