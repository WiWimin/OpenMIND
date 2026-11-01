import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ModePicker from '@/components/ModePicker.vue'

function mountPicker(props: { disabled?: boolean; modelValue?: 'plan' | 'build' } = {}) {
  return mount(ModePicker, { props })
}

describe('ModePicker', () => {
  it('shows the current mode label, defaulting to build', () => {
    const wrapper = mountPicker()
    expect(wrapper.get('.mode-picker__label').text()).toBe('Build')
  })

  it('shows the plan label when plan mode is active', () => {
    const wrapper = mountPicker({ modelValue: 'plan' })
    expect(wrapper.get('.mode-picker__label').text()).toBe('Plan')
    expect(wrapper.find('.mode-picker__trigger--plan').exists()).toBe(true)
  })

  it('opens an upward panel with both modes and emits the selection', async () => {
    const wrapper = mountPicker()
    await wrapper.get('.mode-picker__trigger').trigger('click')

    const labels = wrapper.findAll('.mode-picker__item').map((item) => item.text())
    expect(labels.length).toBe(2)
    expect(labels[0]).toBe('Plan')
    expect(labels[1]).toBe('Build')

    await wrapper.findAll('.mode-picker__item')[0].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['plan']])
    expect(wrapper.find('.mode-picker__panel').exists()).toBe(false)
  })

  it('marks the active mode as selected', async () => {
    const wrapper = mountPicker({ modelValue: 'plan' })
    await wrapper.get('.mode-picker__trigger').trigger('click')

    expect(wrapper.findAll('.mode-picker__item--selected').length).toBe(1)
  })

  it('does not open when disabled', async () => {
    const wrapper = mountPicker({ disabled: true })
    await wrapper.get('.mode-picker__trigger').trigger('click')

    expect(wrapper.find('.mode-picker__panel').exists()).toBe(false)
  })
})
