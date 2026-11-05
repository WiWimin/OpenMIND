import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as knowledgeApi from '@/api/knowledge'
import KnowledgeDialog from '@/components/settings/KnowledgeDialog.vue'
import { useToast } from '@/composables/useToast'
import type { KnowledgeDocument } from '@/types/knowledge'

vi.mock('@/api/knowledge', () => ({
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
  searchKnowledge: vi.fn(),
}))

const documents: KnowledgeDocument[] = [
  {
    document_id: 'kb_1',
    file_name: '产品白皮书.pdf',
    type: 'pdf',
    processing_status: 'processed',
    parse_error: null,
    created_at: '2026-10-01T09:00:00+08:00',
  },
]

function listOf(items: KnowledgeDocument[], total = items.length) {
  return {
    items,
    pagination: { page: 1, page_size: 20, total, total_pages: 1 },
  }
}

function mountDialog() {
  return mount(KnowledgeDialog, { props: { open: true } })
}

async function chooseFile(wrapper: ReturnType<typeof mountDialog>, file: File) {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type="file"]').trigger('change')
  await flushPromises()
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(knowledgeApi.listDocuments).mockResolvedValue(listOf(documents))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('KnowledgeDialog', () => {
  it('renders the upload button, search input and the file list below', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const uploadButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('上传资料'))
    expect(uploadButton).toBeTruthy()
    expect(wrapper.get('.knowledge-search__input').attributes('placeholder')).toBe(
      '输入关键词查找资料',
    )
    // 文件列表常驻显示
    expect(wrapper.text()).toContain('已上传文件')
    expect(wrapper.text()).toContain('产品白皮书.pdf')
    expect(wrapper.text()).toContain('已索引')
  })

  it('uploads directly when a file is chosen and refreshes the list', async () => {
    vi.mocked(knowledgeApi.uploadDocument).mockResolvedValue({
      ...documents[0],
      document_id: 'kb_2',
      file_name: '需求说明.docx',
      type: 'docx',
      processing_status: 'processing',
      parse_error: null,
      created_at: '2026-10-31T09:00:00+08:00',
    })
    const wrapper = mountDialog()
    await flushPromises()

    const file = new File(['content'], '需求说明.docx', { type: 'application/msword' })
    await chooseFile(wrapper, file)

    expect(knowledgeApi.uploadDocument).toHaveBeenCalledTimes(1)
    expect(knowledgeApi.uploadDocument).toHaveBeenCalledWith(file)
    expect(knowledgeApi.listDocuments).toHaveBeenCalled()
    expect(useToast().toasts.value.some((t) => t.message.includes('资料已加入知识库'))).toBe(true)
  })

  it('rejects an unsupported file type without uploading', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const file = new File(['content'], '恶意.exe', { type: 'application/octet-stream' })
    await chooseFile(wrapper, file)

    expect(knowledgeApi.uploadDocument).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('支持')
  })

  it('runs a live search while typing and renders hits with scores', async () => {
    vi.useFakeTimers()
    vi.mocked(knowledgeApi.searchKnowledge).mockResolvedValue({
      items: [
        {
          document_id: 'kb_1',
          file_name: '产品白皮书.pdf',
          excerpt: '上线前必须完成回归测试与灰度发布检查。',
          score: 0.87,
        },
      ],
    })
    const wrapper = mountDialog()
    await flushPromises()

    await wrapper.get('.knowledge-search__input').setValue('上线检查')
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()

    expect(knowledgeApi.searchKnowledge).toHaveBeenCalledTimes(1)
    expect(knowledgeApi.searchKnowledge).toHaveBeenCalledWith({
      query: '上线检查',
      top_k: 5,
    })
    expect(wrapper.text()).toContain('检索结果')
    expect(wrapper.text()).toContain('产品白皮书.pdf')
    expect(wrapper.text()).toContain('0.870')
    // 文件列表仍常驻显示
    expect(wrapper.text()).toContain('已上传文件')
  })

  it('hides the results section when the query is cleared', async () => {
    vi.useFakeTimers()
    vi.mocked(knowledgeApi.searchKnowledge).mockResolvedValue({ items: [] })
    const wrapper = mountDialog()
    await flushPromises()

    await wrapper.get('.knowledge-search__input').setValue('上线检查')
    await vi.advanceTimersByTimeAsync(400)
    await flushPromises()
    expect(wrapper.text()).toContain('检索结果')

    await wrapper.get('.knowledge-search__input').setValue('')
    await flushPromises()
    expect(wrapper.text()).not.toContain('检索结果')
  })

  it('deletes a document after confirmation', async () => {
    vi.mocked(knowledgeApi.deleteDocument).mockResolvedValue({ deleted: true, document_id: 'kb_1' })
    const wrapper = mountDialog()
    await flushPromises()

    const deleteButton = wrapper.findAll('button').find((node) => node.text() === '删除')
    await deleteButton?.trigger('click')
    await flushPromises()

    const confirmButton = wrapper
      .findAll('button')
      .find((node) => node.text() === '删除' && node.classes().includes('app-button--danger'))
    await confirmButton?.trigger('click')
    await flushPromises()

    expect(knowledgeApi.deleteDocument).toHaveBeenCalledWith('kb_1')
  })
})
