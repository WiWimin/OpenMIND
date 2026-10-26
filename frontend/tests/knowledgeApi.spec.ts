import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import {
  deleteDocument,
  listDocuments,
  searchKnowledge,
  uploadDocument,
} from '@/api/knowledge'
import type { ListData } from '@/types/api'
import type { KnowledgeDocument, KnowledgeSearchResult } from '@/types/knowledge'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const del = vi.mocked(http.delete)

const document: KnowledgeDocument = {
  document_id: 'kdoc_1',
  file_name: 'notes.txt',
  type: 'txt',
  processing_status: 'processed',
  parse_error: null,
  created_at: '2026-10-01T09:00:00+08:00',
}

describe('knowledge api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('lists documents with pagination', async () => {
    const list: ListData<KnowledgeDocument> = {
      items: [document],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    get.mockResolvedValue(response(list))

    await expect(listDocuments({ page: 1 })).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/knowledge/documents', { params: { page: 1 } })
  })

  it('uploads a document as multipart form data', async () => {
    post.mockResolvedValue(response(document))
    const file = new File(['alpha'], 'notes.txt', { type: 'text/plain' })

    await expect(uploadDocument(file)).resolves.toEqual(document)

    const [path, body, options] = post.mock.calls[0]
    expect(path).toBe('/knowledge/documents')
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('file')).toBe(file)
    expect(options).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
  })

  it('searches the knowledge base', async () => {
    const result: KnowledgeSearchResult = {
      items: [
        {
          document_id: 'kdoc_1',
          file_name: 'notes.txt',
          excerpt: 'alpha',
          score: 0.9,
        },
      ],
    }
    post.mockResolvedValue(response(result))

    await expect(searchKnowledge({ query: 'alpha' })).resolves.toEqual(result)
    expect(post).toHaveBeenCalledWith('/knowledge/search', { query: 'alpha' })
  })

  it('deletes a document', async () => {
    const deleted = { deleted: true as const, document_id: 'kdoc_1' }
    del.mockResolvedValue(response(deleted))

    await expect(deleteDocument('kdoc_1')).resolves.toEqual(deleted)
    expect(del).toHaveBeenCalledWith('/knowledge/documents/kdoc_1')
  })
})
