import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MaterialUploader from '@/components/MaterialUploader.vue'
import type { MaterialUploadError } from '@/types/material'

function textFile(name: string): File {
  return new File(['content'], name, { type: 'text/plain' })
}

async function setSelected(wrapper: ReturnType<typeof mount>, file: File): Promise<void> {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type="file"]').trigger('change')
}

describe('MaterialUploader', () => {
  it('emits upload immediately on drop without a submit button', async () => {
    const wrapper = mount(MaterialUploader)
    const file = textFile('agenda.txt')

    const dropzone = wrapper.get('.material-uploader__dropzone')
    await dropzone.trigger('dragover')
    expect(dropzone.classes()).toContain('material-uploader__dropzone--active')

    await dropzone.trigger('drop', { dataTransfer: { files: [file] } })

    expect(dropzone.classes()).not.toContain('material-uploader__dropzone--active')
    expect(wrapper.emitted('upload')).toEqual([[{ file }]])
    expect(wrapper.text()).toContain('agenda.txt')
    // 不再有「上传资料」按钮
    expect(wrapper.find('.material-uploader__submit').exists()).toBe(false)
  })

  it('emits upload immediately when a file is picked', async () => {
    const wrapper = mount(MaterialUploader)
    const file = textFile('notes.txt')

    await setSelected(wrapper, file)

    expect(wrapper.emitted('upload')).toEqual([[{ file }]])
  })

  it('rejects unsupported or oversized files without emitting', async () => {
    const wrapper = mount(MaterialUploader)

    await wrapper.get('.material-uploader__dropzone').trigger('drop', {
      dataTransfer: { files: [new File(['x'], 'bad.exe')] },
    })
    expect(wrapper.get('.material-uploader__error').text()).toContain('仅支持')
    expect(wrapper.emitted('upload')).toBeUndefined()

    await wrapper.get('.material-uploader__dropzone').trigger('drop', {
      dataTransfer: { files: [new File([new ArrayBuffer(21 * 1024 * 1024)], 'big.pdf')] },
    })
    expect(wrapper.get('.material-uploader__error').text()).toContain('20 MB')
    expect(wrapper.emitted('upload')).toBeUndefined()
  })

  it('shows the parse failure reason in the box and retries with the same file', async () => {
    const wrapper = mount(MaterialUploader)
    const file = textFile('broken.pdf')
    await setSelected(wrapper, file)
    expect(wrapper.emitted('upload')).toHaveLength(1)

    const error: MaterialUploadError = {
      kind: 'parse',
      message: 'PDF 文件无法读取或已损坏：broken.pdf',
    }
    await wrapper.setProps({ uploading: false, error })

    expect(wrapper.text()).toContain('无法解析')
    expect(wrapper.text()).toContain('PDF 文件无法读取或已损坏')
    expect(wrapper.text()).toContain('broken.pdf')
    expect(wrapper.get('.material-uploader__dropzone').classes()).toContain(
      'material-uploader__dropzone--error',
    )

    await wrapper.get('.material-uploader__retry').trigger('click')
    expect(wrapper.emitted('upload')).toHaveLength(2)
    expect(wrapper.emitted('upload')?.[1]).toEqual([{ file }])
  })

  it('shows an upload failure with kind=upload', async () => {
    const wrapper = mount(MaterialUploader)
    const file = textFile('agenda.txt')
    await setSelected(wrapper, file)

    await wrapper.setProps({
      uploading: false,
      error: { kind: 'upload', message: '网络连接失败，请检查网络后重试' } satisfies MaterialUploadError,
    })

    expect(wrapper.text()).toContain('上传失败')
    expect(wrapper.text()).toContain('网络连接失败')
    expect(wrapper.find('.material-uploader__retry').exists()).toBe(true)
  })

  it('clears the file row after a successful upload', async () => {
    const wrapper = mount(MaterialUploader)
    const file = textFile('notes.txt')
    await setSelected(wrapper, file)
    expect(wrapper.text()).toContain('notes.txt')

    await wrapper.setProps({ uploading: true })
    await wrapper.setProps({ uploading: false })

    expect(wrapper.find('.material-uploader__file-row').exists()).toBe(false)
  })

  it('keeps the file row while uploading and shows the uploading state', async () => {
    const wrapper = mount(MaterialUploader)
    const file = textFile('notes.txt')
    await setSelected(wrapper, file)

    await wrapper.setProps({ uploading: true })

    expect(wrapper.text()).toContain('notes.txt')
    expect(wrapper.text()).toContain('上传中')
    expect(wrapper.text()).toContain('正在上传并解析')
  })

  it('clears the selected file via the remove button when idle', async () => {
    const wrapper = mount(MaterialUploader)
    await setSelected(wrapper, textFile('notes.txt'))
    expect(wrapper.text()).toContain('notes.txt')

    await wrapper.get('.material-uploader__remove').trigger('click')
    expect(wrapper.find('.material-uploader__file-row').exists()).toBe(false)
    expect(wrapper.find('.material-uploader__error').exists()).toBe(false)
  })
})
