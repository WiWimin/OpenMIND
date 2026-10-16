import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import RichTextEditor from '@/components/RichTextEditor.vue'

describe('RichTextEditor', () => {
  it('renders the label and the editable area', () => {
    const wrapper = mount(RichTextEditor, {
      props: { id: 'editor-1', modelValue: '<p>正文</p>', label: '纪要内容' },
    })

    expect(wrapper.text()).toContain('纪要内容')
    expect(wrapper.find('#editor-1').exists()).toBe(true)
  })

  it('exposes format toolbar buttons', () => {
    const wrapper = mount(RichTextEditor, {
      props: { id: 'editor-1', modelValue: '', label: '纪要内容' },
    })

    const toolbar = wrapper.get('[role="toolbar"]')
    expect(toolbar.text()).toContain('H1')
    expect(toolbar.text()).toContain('H2')
    expect(toolbar.find('[aria-label="加粗"]').exists()).toBe(true)
    expect(toolbar.find('[aria-label="无序列表"]').exists()).toBe(true)
  })

  it('converts plain text content into paragraphs', () => {
    const wrapper = mount(RichTextEditor, {
      props: { id: 'editor-1', modelValue: '第一行\n第二行', label: '纪要内容' },
    })

    const html = (wrapper.vm as unknown as { editor: { getHTML: () => string } }).editor.getHTML()
    expect(html).toContain('第一行')
    expect(html).toContain('第二行')
  })

  it('destroys the editor on unmount', () => {
    const wrapper = mount(RichTextEditor, {
      props: { id: 'editor-1', modelValue: '', label: '纪要内容' },
    })
    const editor = (wrapper.vm as unknown as { editor: { isDestroyed: boolean } }).editor
    wrapper.unmount()
    expect(editor.isDestroyed).toBe(true)
  })
})
