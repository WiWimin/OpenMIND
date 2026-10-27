import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import ToastHost from '@/components/ToastHost.vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()

afterEach(() => {
  for (const item of [...toast.toasts.value]) {
    toast.dismiss(item.id)
  }
})

describe('useToast', () => {
  it('pushes success and error toasts in order', () => {
    toast.success('资料已上传')
    toast.error('操作失败')

    expect(toast.toasts.value.map((item) => item.tone)).toEqual(['success', 'error'])
    expect(toast.toasts.value[0]?.message).toBe('资料已上传')
  })

  it('ignores empty messages', () => {
    toast.success('   ')

    expect(toast.toasts.value).toHaveLength(0)
  })

  it('dismisses a toast by id', () => {
    toast.success('已保存')
    const first = toast.toasts.value[0]
    expect(first).toBeTruthy()

    toast.dismiss(first!.id)

    expect(toast.toasts.value).toHaveLength(0)
  })

  it('renders queued toasts through ToastHost', async () => {
    const wrapper = mount(ToastHost)

    toast.success('资料已上传')
    await wrapper.vm.$nextTick()

    const node = wrapper.get('.toast')
    expect(node.text()).toContain('资料已上传')
    expect(node.classes()).toContain('toast--success')
  })
})
