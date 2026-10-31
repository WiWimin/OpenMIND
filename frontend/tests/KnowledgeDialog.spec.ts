import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as knowledgeApi from '@/api/knowledge'
import KnowledgeDialog from '@/components/settings/KnowledgeDialog.vue'
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

async function openPanel(wrapper: ReturnType<typeof mountDialog>, label: string) {
  const bubble = wrapper.findAll('.knowledge-bubble').find((node) => node.text().includes(label))
  await bubble?.trigger('click')
}

describe('KnowledgeDialog', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(knowledgeApi.listDocuments).mockResolvedValue(listOf(documents))
  })

  it('renders the upload and search bubbles with the file list below', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const labels = wrapper.findAll('.knowledge-bubble').map((node) => node.text())
    expect(labels[0]).toContain('上传资料')
    expect(labels[1]).toContain('查找资料')
    // 面板默认收起，文件列表常驻显示
    expect(wrapper.find('input[type="file"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('已上传文件')
    expect(wrapper.text()).toContain('产品白皮书.pdf')
    expect(wrapper.text()).toContain('已索引')
  })

  it('shows the uploader when the upload bubble is clicked', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    await openPanel(wrapper, '上传资料')
    expect(wrapper.find('input[type="file"]').exists()).toBe(true)
  })

  it('uploads a document and refreshes the list', async () => {
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
    await openPanel(wrapper, '上传资料')

    const file = new File(['content'], '需求说明.docx', { type: 'application/msword' })
    const input = wrapper.get('input[type="file"]').element as HTMLInputElement
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    await wrapper.get('input[type="file"]').trigger('change')

    const uploadButton = wrapper
      .findAll('button')
      .find((node) => node.text().includes('上传到知识库'))
    await uploadButton?.trigger('click')
    await flushPromises()

    expect(knowledgeApi.uploadDocument).toHaveBeenCalledTimes(1)
    expect(knowledgeApi.listDocuments).toHaveBeenCalled()
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

  it('runs a search from the search bubble and renders hits with scores', async () => {
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
    await openPanel(wrapper, '查找资料')

    await wrapper.find('#knowledge-search-input').setValue('上线检查')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(knowledgeApi.searchKnowledge).toHaveBeenCalledWith({
      query: '上线检查',
      top_k: 5,
    })
    expect(wrapper.text()).toContain('产品白皮书.pdf')
    expect(wrapper.text()).toContain('0.870')
  })
})
