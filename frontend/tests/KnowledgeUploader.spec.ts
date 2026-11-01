import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import KnowledgeUploader from '@/components/KnowledgeUploader.vue'

async function selectFile(wrapper: VueWrapper, file: File): Promise<void> {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type="file"]').trigger('change')
}

describe('KnowledgeUploader', () => {
  it('rejects an unsupported file type', async () => {
    const wrapper = mount(KnowledgeUploader)
    await selectFile(wrapper, new File(['x'], 'bad.exe'))

    expect(wrapper.get('.knowledge-uploader__error').text()).toContain('仅支持')
    expect(wrapper.find('.app-button').exists()).toBe(false)
  })

  it('emits the selected file', async () => {
    const wrapper = mount(KnowledgeUploader)
    const file = new File(['alpha'], 'notes.txt')
    await selectFile(wrapper, file)

    expect(wrapper.text()).toContain('notes.txt')
    await wrapper.get('.app-button').trigger('click')

    expect(wrapper.emitted('upload')).toEqual([[file]])
  })
})
