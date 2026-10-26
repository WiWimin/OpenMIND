import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as knowledgeApi from '@/api/knowledge'
import KnowledgeUploader from '@/components/KnowledgeUploader.vue'
import KnowledgeView from '@/views/KnowledgeView.vue'
import type { ListData } from '@/types/api'
import type { KnowledgeDocument, KnowledgeSearchResult } from '@/types/knowledge'

vi.mock('@/api/knowledge', () => ({
  listDocuments: vi.fn(),
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
  searchKnowledge: vi.fn(),
}))

const document: KnowledgeDocument = {
  document_id: 'kdoc_1',
  file_name: 'notes.txt',
  type: 'txt',
  processing_status: 'processed',
  parse_error: null,
  created_at: '2026-10-01T09:00:00+08:00',
}

function listOf(items: KnowledgeDocument[]): ListData<KnowledgeDocument> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountView(): VueWrapper {
  return mount(KnowledgeView)
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('KnowledgeView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('lists documents', async () => {
    vi.mocked(knowledgeApi.listDocuments).mockResolvedValue(listOf([document]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('notes.txt')
    expect(wrapper.text()).toContain('已索引')
  })

  it('uploads a document and refreshes the list', async () => {
    vi.mocked(knowledgeApi.listDocuments)
      .mockResolvedValueOnce(listOf([]))
      .mockResolvedValue(listOf([document]))
    vi.mocked(knowledgeApi.uploadDocument).mockResolvedValue(document)
    const wrapper = mountView()
    await flushPromises()

    const file = new File(['alpha'], 'notes.txt')
    wrapper.findComponent(KnowledgeUploader).vm.$emit('upload', file)
    await flushPromises()

    expect(knowledgeApi.uploadDocument).toHaveBeenCalledWith(file)
    expect(knowledgeApi.listDocuments).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('notes.txt')
  })

  it('searches the knowledge base', async () => {
    vi.mocked(knowledgeApi.listDocuments).mockResolvedValue(listOf([]))
    const result: KnowledgeSearchResult = {
      items: [
        {
          document_id: 'kdoc_1',
          file_name: 'notes.txt',
          excerpt: 'alpha 相关内容',
          score: 0.91,
        },
      ],
    }
    vi.mocked(knowledgeApi.searchKnowledge).mockResolvedValue(result)
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#knowledge-query').setValue('alpha')
    await wrapper.get('form.knowledge-search').trigger('submit')
    await flushPromises()

    expect(knowledgeApi.searchKnowledge).toHaveBeenCalledWith({ query: 'alpha' })
    expect(wrapper.text()).toContain('alpha 相关内容')
    expect(wrapper.text()).toContain('0.91')
  })

  it('deletes a document after confirmation', async () => {
    vi.mocked(knowledgeApi.listDocuments).mockResolvedValue(listOf([document]))
    vi.mocked(knowledgeApi.deleteDocument).mockResolvedValue({
      deleted: true,
      document_id: 'kdoc_1',
    })
    const wrapper = mountView()
    await flushPromises()

    await button(wrapper, '删除')?.trigger('click')
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((item) => item.text() === '删除')
    await confirm?.trigger('click')
    await flushPromises()

    expect(knowledgeApi.deleteDocument).toHaveBeenCalledWith('kdoc_1')
  })
})
