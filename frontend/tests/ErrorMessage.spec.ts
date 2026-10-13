import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ErrorMessage from '@/components/ErrorMessage.vue'
import type { ApiError } from '@/types/api'

const apiError: ApiError = {
  status: 'error',
  error_code: 'VALIDATION_ERROR',
  message: '标题不能为空',
}

describe('ErrorMessage', () => {
  it('renders nothing without an error', () => {
    const wrapper = mount(ErrorMessage)
    expect(wrapper.find('.error-message').exists()).toBe(false)
  })

  it('renders the normalized api message', () => {
    const wrapper = mount(ErrorMessage, { props: { error: apiError } })
    expect(wrapper.get('[role="alert"]').text()).toContain('标题不能为空')
  })

  it('falls back for unknown errors', () => {
    const wrapper = mount(ErrorMessage, { props: { error: 'weird', fallback: '请求失败' } })
    expect(wrapper.get('[role="alert"]').text()).toContain('请求失败')
  })

  it('emits retry when retryable and clicked', async () => {
    const wrapper = mount(ErrorMessage, { props: { error: apiError, retryable: true } })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('does not render a retry button by default', () => {
    const wrapper = mount(ErrorMessage, { props: { error: apiError } })
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
