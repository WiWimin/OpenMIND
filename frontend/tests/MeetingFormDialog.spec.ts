import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MeetingFormDialog from '@/components/MeetingFormDialog.vue'
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

describe('MeetingFormDialog', () => {
  it('titles the create dialog and requires a title', async () => {
    const wrapper = mount(MeetingFormDialog, { props: { open: true } })
    expect(wrapper.get('.meeting-form__title').text()).toBe('新建会议')
    expect(wrapper.text()).toContain('我来帮你记录会议')

    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('请输入会议标题')
    expect(wrapper.emitted('submit')).toBeUndefined()
  })

  it('submits a trimmed create payload', async () => {
    const wrapper = mount(MeetingFormDialog, { props: { open: true } })

    await wrapper.get('#meeting-title').setValue('  项目周会  ')
    await wrapper.get('#meeting-topic').setValue('进度')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')).toEqual([
      [{ title: '项目周会', topic: '进度', meeting_time: undefined }],
    ])
  })

  it('prefills and titles the edit dialog', () => {
    const wrapper = mount(MeetingFormDialog, { props: { open: true, meeting } })

    expect(wrapper.get('.meeting-form__title').text()).toBe('编辑会议')
    expect(wrapper.text()).toContain('需要调整会议信息吗')
    expect((wrapper.get('#meeting-title').element as HTMLInputElement).value).toBe('项目周会')
    expect((wrapper.get('#meeting-topic').element as HTMLInputElement).value).toBe('进度与风险')
    expect((wrapper.get('#meeting-time').element as HTMLInputElement).value).toMatch(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/,
    )
  })

  it('renders a submission error and emits cancel on close', async () => {
    const wrapper = mount(MeetingFormDialog, {
      props: { open: true, error: { error_code: 'VALIDATION_ERROR', message: '标题重复' } },
    })
    expect(wrapper.get('[role="alert"]').text()).toContain('标题重复')

    await wrapper.get('.meeting-form__close').trigger('click')
    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })
})
