import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MaterialUploader from '@/components/MaterialUploader.vue'
import type { MaterialUploadPayload } from '@/types/material'

async function selectFile(wrapper: VueWrapper, file: File): Promise<void> {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type="file"]').trigger('change')
}

describe('MaterialUploader', () => {
  it('rejects an unsupported file type', async () => {
    const wrapper = mount(MaterialUploader)
    await selectFile(wrapper, new File(['x'], 'bad.exe'))

    expect(wrapper.get('.material-uploader__error').text()).toContain('仅支持')
    expect(wrapper.get('.app-button').attributes('disabled')).toBeDefined()
  })

  it('rejects an oversized file', async () => {
    const wrapper = mount(MaterialUploader)
    const file = new File(['x'], 'big.pdf')
    Object.defineProperty(file, 'size', { value: 21 * 1024 * 1024 })
    await selectFile(wrapper, file)

    expect(wrapper.get('.material-uploader__error').text()).toContain('20 MB')
  })

  it('emits the upload payload for a valid file', async () => {
    const wrapper = mount(MaterialUploader)
    const file = new File(['x'], 'plan.pdf')
    await selectFile(wrapper, file)
    await wrapper.get('#material-source').setValue('会前材料')

    await wrapper.get('.app-button').trigger('click')

    const events = wrapper.emitted('upload') as unknown[][]
    expect(events).toHaveLength(1)
    const payload = events[0][0] as MaterialUploadPayload
    expect(payload.file).toBe(file)
    expect(payload.source).toBe('会前材料')
  })
})
