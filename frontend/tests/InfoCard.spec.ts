import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import InfoCard from '@/components/InfoCard.vue'
import type { InfoCardTone } from '@/types/ui'

const STATUS_TONES: InfoCardTone[] = ['ok', 'down', 'checking']

describe('InfoCard', () => {
  it('renders the label and the value', () => {
    const wrapper = mount(InfoCard, {
      props: { label: '项目名称', value: 'OpenMIND' },
    })

    expect(wrapper.text()).toContain('项目名称')
    expect(wrapper.text()).toContain('OpenMIND')
  })

  it('hides the status dot for the neutral tone', () => {
    const wrapper = mount(InfoCard, {
      props: { label: '当前环境', value: '开发环境' },
    })

    expect(wrapper.classes()).toContain('info-card--neutral')
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it.each(STATUS_TONES)('renders the %s tone with a status dot', (tone) => {
    const wrapper = mount(InfoCard, {
      props: { label: '后端连接状态', value: '检测中…', tone },
    })

    expect(wrapper.classes()).toContain(`info-card--${tone}`)
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('marks the status dot as decorative', () => {
    const wrapper = mount(InfoCard, {
      props: { label: '后端连接状态', value: '已连接', tone: 'ok' },
    })

    expect(wrapper.get('.info-card__dot').attributes('aria-hidden')).toBe('true')
  })

  it('renders the description only when provided', () => {
    const withDescription = mount(InfoCard, {
      props: { label: '当前环境', value: '开发环境', description: '环境标识：development' },
    })
    const withoutDescription = mount(InfoCard, {
      props: { label: '项目名称', value: 'OpenMIND' },
    })

    expect(withDescription.text()).toContain('环境标识：development')
    expect(withoutDescription.find('.info-card__description').exists()).toBe(false)
  })
})
