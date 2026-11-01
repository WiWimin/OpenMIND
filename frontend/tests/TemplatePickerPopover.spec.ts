import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TemplatePickerPopover from '@/components/TemplatePickerPopover.vue'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

function mountPicker(
  props: {
    disabled?: boolean
    selected?: string
    meetingId?: string
    returnTo?: 'preprocess' | 'minutes'
  } = {},
) {
  return mount(TemplatePickerPopover, { props })
}

beforeEach(() => {
  push.mockReset()
})

describe('TemplatePickerPopover', () => {
  it('navigates to the template manage page with the return target', async () => {
    const wrapper = mountPicker({ meetingId: 'mtg_1', returnTo: 'minutes' })

    await wrapper.get('.template-picker__trigger').trigger('click')

    expect(push).toHaveBeenCalledWith({
      name: 'meeting-template-manage',
      query: { returnTo: 'minutes', meetingId: 'mtg_1' },
    })
  })

  it('omits meetingId when not provided', async () => {
    const wrapper = mountPicker()

    await wrapper.get('.template-picker__trigger').trigger('click')

    expect(push).toHaveBeenCalledWith({
      name: 'meeting-template-manage',
      query: { returnTo: 'preprocess' },
    })
  })

  it('marks the active state when a template is selected', () => {
    const wrapper = mountPicker({ selected: 'tpl_x' })

    expect(wrapper.find('.template-picker__trigger--active').exists()).toBe(true)
    expect(wrapper.find('.template-picker__dot').exists()).toBe(true)
    expect(wrapper.get('.template-picker__trigger').attributes('title')).toContain('已选择输出模板')
  })

  it('does not navigate when disabled', async () => {
    const wrapper = mountPicker({ disabled: true })

    await wrapper.get('.template-picker__trigger').trigger('click')

    expect(push).not.toHaveBeenCalled()
  })
})
