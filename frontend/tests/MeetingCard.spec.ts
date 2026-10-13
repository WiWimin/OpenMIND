import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MeetingCard from '@/components/MeetingCard.vue'
import type { Meeting } from '@/types/meeting'

const meeting: Meeting = {
  meeting_id: 'mtg_1',
  title: '项目周会',
  topic: '进度与风险',
  meeting_time: '2026-10-02T14:00:00+08:00',
  status: 'scheduled',
  created_at: '2026-10-01T09:00:00+08:00',
  updated_at: '2026-10-01T09:00:00+08:00',
  archived_at: null,
}

describe('MeetingCard', () => {
  it('renders the meeting summary', () => {
    const wrapper = mount(MeetingCard, { props: { meeting } })
    expect(wrapper.get('.meeting-card__title').text()).toBe('项目周会')
    expect(wrapper.text()).toContain('进度与风险')
    expect(wrapper.text()).toContain('已安排')
    expect(wrapper.get('.meeting-card__time').text()).toMatch(
      /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/,
    )
  })

  it('omits the topic when empty', () => {
    const wrapper = mount(MeetingCard, { props: { meeting: { ...meeting, topic: null } } })
    expect(wrapper.find('.meeting-card__topic').exists()).toBe(false)
  })

  it('emits select with the meeting id', async () => {
    const wrapper = mount(MeetingCard, { props: { meeting } })
    await wrapper.get('.meeting-card').trigger('click')
    expect(wrapper.emitted('select')).toEqual([['mtg_1']])
  })
})
