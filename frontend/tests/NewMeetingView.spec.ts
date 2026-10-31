import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import NewMeetingView from '@/views/newMeeting/NewMeetingView.vue'

const { routeState } = vi.hoisted(() => ({
  routeState: { query: {} as Record<string, string> },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState,
}))

function mountView() {
  return mount(NewMeetingView, {
    global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } },
  })
}

describe('NewMeetingView', () => {
  beforeEach(() => {
    routeState.query = {}
  })

  it('renders only the three stage cards with their features', () => {
    const wrapper = mountView()

    expect(wrapper.text()).toContain('资料预处理')
    expect(wrapper.text()).toContain('实时录音转写')
    expect(wrapper.text()).toContain('会后智能处理')

    expect(wrapper.text()).toContain('上传会议资料')
    expect(wrapper.text()).toContain('提取关键议题')
    expect(wrapper.text()).toContain('生成会议议程')

    expect(wrapper.text()).toContain('高清实时录音')
    expect(wrapper.text()).toContain('智能语音转写')
    expect(wrapper.text()).toContain('标记会议重点')

    expect(wrapper.text()).toContain('生成会议纪要')
    expect(wrapper.text()).toContain('生成会议摘要')
    expect(wrapper.text()).toContain('提取待办任务')

    // 整张卡片即链接，无独立进入按钮
    expect(wrapper.findAll('a.stage-card')).toHaveLength(3)
    expect(wrapper.find('.stage-card__enter').exists()).toBe(false)

    // 页面只保留三张卡片：无页头、流程条与创建弹窗
    expect(wrapper.find('.meeting-form').exists()).toBe(false)
    expect(wrapper.find('.new-meeting__flow').exists()).toBe(false)
  })

  it('carries the meeting id into the stage links', () => {
    routeState.query = { meetingId: 'mtg_1' }
    const wrapper = mount(NewMeetingView, {
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :data-to="JSON.stringify(to)"><slot /></a>',
          },
        },
      },
    })

    const targets = wrapper.findAll('a[data-to]').map((link) => link.attributes('data-to') ?? '')
    expect(targets).toHaveLength(3)
    expect(targets.every((target) => target.includes('mtg_1'))).toBe(true)
    expect(targets.some((target) => target.includes('new-meeting-minutes'))).toBe(true)
  })

  it('links the stage cards without a meeting id by default', () => {
    const wrapper = mount(NewMeetingView, {
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :data-to="JSON.stringify(to)"><slot /></a>',
          },
        },
      },
    })

    const targets = wrapper.findAll('a[data-to]').map((link) => link.attributes('data-to') ?? '')
    expect(targets.every((target) => !target.includes('meetingId'))).toBe(true)
  })
})
