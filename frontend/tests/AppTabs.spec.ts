import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppTabs from '@/components/AppTabs.vue'
import type { TabItem } from '@/types/ui'

const tabs: TabItem[] = [
  { value: 'materials', label: '材料' },
  { value: 'records', label: '记录' },
  { value: 'minutes', label: '纪要' },
]

describe('AppTabs', () => {
  it('renders every tab', () => {
    const wrapper = mount(AppTabs, { props: { tabs, modelValue: 'materials' } })
    const buttons = wrapper.findAll('[role="tab"]')
    expect(buttons).toHaveLength(3)
    expect(buttons.map((b) => b.text())).toEqual(['材料', '记录', '纪要'])
  })

  it('marks the active tab', () => {
    const wrapper = mount(AppTabs, { props: { tabs, modelValue: 'records' } })
    const buttons = wrapper.findAll('[role="tab"]')
    expect(buttons[1].attributes('aria-selected')).toBe('true')
    expect(buttons[1].classes()).toContain('tabs__tab--active')
    expect(buttons[0].attributes('aria-selected')).toBe('false')
  })

  it('emits update:modelValue when a tab is clicked', async () => {
    const wrapper = mount(AppTabs, { props: { tabs, modelValue: 'materials' } })
    await wrapper.findAll('[role="tab"]')[2].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['minutes']])
  })
})
