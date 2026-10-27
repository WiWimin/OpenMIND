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

  it('exposes font, color, highlight and image controls', () => {
    const wrapper = mount(RichTextEditor, {
      props: { id: 'editor-1', modelValue: '', label: '纪要内容' },
    })

    const toolbar = wrapper.get('[role="toolbar"]')
    expect(toolbar.find('[aria-label="字体"]').exists()).toBe(true)
    expect(toolbar.find('[aria-label="文字颜色"]').exists()).toBe(true)
    expect(toolbar.find('[aria-label="高亮强调"]').exists()).toBe(true)
    expect(toolbar.find('input[type="file"]').exists()).toBe(true)
    expect(toolbar.text()).toContain('宋体')
    expect(toolbar.text()).toContain('黑体')
  })

  it('applies a font family from the select', async () => {
    const wrapper = mount(RichTextEditor, {
      props: { id: 'editor-1', modelValue: '<p>正文</p>', label: '纪要内容' },
    })
    const editor = (
      wrapper.vm as unknown as { editor: { commands: { selectAll: () => void }; getHTML: () => string } }
    ).editor

    editor.commands.selectAll()
    await wrapper.get('[aria-label="字体"]').setValue('Arial, sans-serif')

    expect(editor.getHTML()).toContain('Arial')
  })

  it('toggles highlight from the toolbar', async () => {
    const wrapper = mount(RichTextEditor, {
      props: { id: 'editor-1', modelValue: '<p>正文</p>', label: '纪要内容' },
    })
    const editor = (
      wrapper.vm as unknown as { editor: { commands: { selectAll: () => void }; getHTML: () => string } }
    ).editor

    editor.commands.selectAll()
    await wrapper.get('[aria-label="高亮强调"]').trigger('click')

    expect(editor.getHTML()).toContain('mark')
  })

  it('inserts an image from a file selection', async () => {
    const wrapper = mount(RichTextEditor, {
      props: { id: 'editor-1', modelValue: '<p>正文</p>', label: '纪要内容' },
    })
    const editor = (
      wrapper.vm as unknown as { editor: { commands: { selectAll: () => void }; getHTML: () => string } }
    ).editor

    editor.commands.selectAll()
    const file = new File(['fake-image'], 'chart.png', { type: 'image/png' })
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file] })
    await wrapper.get('input[type="file"]').trigger('change')
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(editor.getHTML()).toContain('<img')
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
