import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ConfirmDialog from '@/components/ConfirmDialog.vue'

function actionButtons(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('.app-button')
}

describe('ConfirmDialog', () => {
  it('renders the message', () => {
    const wrapper = mount(ConfirmDialog, { props: { open: true, message: '确认删除该会议？' } })
    expect(wrapper.text()).toContain('确认删除该会议？')
  })

  it('emits confirm when the confirm button is clicked', async () => {
    const wrapper = mount(ConfirmDialog, { props: { open: true, message: 'm' } })
    await actionButtons(wrapper)[1].trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('emits cancel when the cancel button is clicked', async () => {
    const wrapper = mount(ConfirmDialog, { props: { open: true, message: 'm' } })
    await actionButtons(wrapper)[0].trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })

  it('maps overlay close to cancel', async () => {
    const wrapper = mount(ConfirmDialog, { props: { open: true, message: 'm' } })
    await wrapper.get('.modal').trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })

  it('uses the danger variant for the confirm action', () => {
    const wrapper = mount(ConfirmDialog, { props: { open: true, message: 'm', danger: true } })
    expect(actionButtons(wrapper)[1].classes()).toContain('app-button--danger')
  })

  it('disables both actions while loading', () => {
    const wrapper = mount(ConfirmDialog, { props: { open: true, message: 'm', loading: true } })
    const buttons = actionButtons(wrapper)
    expect(buttons[0].attributes('disabled')).toBeDefined()
    expect(buttons[1].attributes('disabled')).toBeDefined()
  })
})
