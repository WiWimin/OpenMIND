import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import PolishDiffPanel from '@/components/PolishDiffPanel.vue'
import type { PolishSuggestion } from '@/types/chat'

vi.mock('@/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}))

const suggestions: PolishSuggestion[] = [
  {
    location: '今天下午两',
    original: '今天下午两点的会一',
    suggested: '今天下午两点的会议',
    reason: '语音识别错误',
    confidence: 'high',
  },
  {
    location: '下周三我们',
    original: '下周三我们再对一',
    suggested: '下周三我们再对一下',
    reason: '语句不通顺',
    confidence: 'medium',
  },
]

describe('PolishDiffPanel', () => {
  it('renders suggestion rows with diff and confidence', () => {
    const wrapper = mount(PolishDiffPanel, { props: { suggestions } })

    expect(wrapper.text()).toContain('今天下午两点的会一')
    expect(wrapper.text()).toContain('今天下午两点的会议')
    expect(wrapper.text()).toContain('语音识别错误')
    expect(wrapper.text()).toContain('高置信')
    // 默认全部勾选
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes).toHaveLength(2)
    for (const checkbox of checkboxes) {
      expect((checkbox.element as HTMLInputElement).checked).toBe(true)
    }
  })

  it('emits only the checked suggestions on apply', async () => {
    const wrapper = mount(PolishDiffPanel, { props: { suggestions } })
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(false)

    const applyButton = wrapper.findAll('button').find((button) => button.text().includes('采纳选中'))
    await applyButton?.trigger('click')

    expect(wrapper.emitted('apply')).toHaveLength(1)
    expect(wrapper.emitted('apply')![0][0]).toEqual([suggestions[0]])
  })

  it('disables editing in readonly mode and hides apply buttons', () => {
    const wrapper = mount(PolishDiffPanel, {
      props: { suggestions, readonly: true, readonlyHint: '录音进行中，暂不能采纳修改。' },
    })

    expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('采纳选中')
    expect(wrapper.text()).toContain('录音进行中，暂不能采纳修改。')
  })

  it('shows empty hint when there is nothing to fix', () => {
    const wrapper = mount(PolishDiffPanel, { props: { suggestions: [] } })

    expect(wrapper.text()).toContain('未发现需要修改的口误或识别错误。')
  })

  it('collapses to dismissed note after ignoring all', async () => {
    const wrapper = mount(PolishDiffPanel, { props: { suggestions } })
    const ignoreButton = wrapper.findAll('button').find((button) => button.text().includes('忽略全部'))
    await ignoreButton?.trigger('click')

    expect(wrapper.text()).toContain('已忽略全部修改建议。')
  })
})
