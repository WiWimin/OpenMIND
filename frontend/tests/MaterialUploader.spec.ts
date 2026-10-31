import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MaterialUploader from '@/components/MaterialUploader.vue'

function textFile(name: string): File {
  return new File(['content'], name, { type: 'text/plain' })
}

async function setSelected(wrapper: ReturnType<typeof mount>, file: File): Promise<void> {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type="file"]').trigger('change')
}

describe('MaterialUploader', () => {
  it('accepts a dropped file and emits upload', async () => {
    const wrapper = mount(MaterialUploader)
    const file = textFile('agenda.txt')

    const dropzone = wrapper.get('.material-uploader__dropzone')
    await dropzone.trigger('dragover')
    expect(dropzone.classes()).toContain('material-uploader__dropzone--active')

    await dropzone.trigger('drop', { dataTransfer: { files: [file] } })
    expect(dropzone.classes()).not.toContain('material-uploader__dropzone--active')
    expect(wrapper.text()).toContain('agenda.txt')

    await wrapper.get('.app-button').trigger('click')

    expect(wrapper.emitted('upload')).toEqual([[{ file }]])
    expect(wrapper.text()).not.toContain('agenda.txt')
  })

  it('rejects unsupported or oversized files on drop', async () => {
    const wrapper = mount(MaterialUploader)

    await wrapper.get('.material-uploader__dropzone').trigger('drop', {
      dataTransfer: { files: [new File(['x'], 'bad.exe')] },
    })
    expect(wrapper.get('.material-uploader__error').text()).toContain('仅支持')

    await wrapper.get('.material-uploader__dropzone').trigger('drop', {
      dataTransfer: { files: [new File([new ArrayBuffer(21 * 1024 * 1024)], 'big.pdf')] },
    })
    expect(wrapper.get('.material-uploader__error').text()).toContain('20 MB')
  })

  it('clears the selected file via the remove button', async () => {
    const wrapper = mount(MaterialUploader)
    await setSelected(wrapper, textFile('notes.txt'))
    expect(wrapper.text()).toContain('notes.txt')

    await wrapper.get('.material-uploader__remove').trigger('click')
    expect(wrapper.find('.material-uploader__file-row').exists()).toBe(false)
    expect(wrapper.find('.app-button').exists()).toBe(false)
  })
})
