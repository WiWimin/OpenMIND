import http from '@/api/client'
import { LONG_REQUEST_TIMEOUT_MS } from '@/api/timeouts'
import type { ApiSuccess, DeletedResult, ListData } from '@/types/api'
import type {
  KnowledgeDocument,
  KnowledgeSearchPayload,
  KnowledgeSearchResult,
} from '@/types/knowledge'
import type { PageParams } from '@/types/pagination'
import { unwrapData } from '@/utils/apiEnvelope'

const PATH = '/knowledge'

export async function listDocuments(
  params: PageParams = {},
): Promise<ListData<KnowledgeDocument>> {
  const { data } = await http.get<
    ApiSuccess<ListData<KnowledgeDocument>> | ListData<KnowledgeDocument>
  >(`${PATH}/documents`, { params })
  return unwrapData(data)
}

export async function uploadDocument(file: File): Promise<KnowledgeDocument> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<ApiSuccess<KnowledgeDocument> | KnowledgeDocument>(
    `${PATH}/documents`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: LONG_REQUEST_TIMEOUT_MS,
    },
  )
  return unwrapData(data)
}

export async function deleteDocument(
  documentId: string,
): Promise<DeletedResult<'document_id'>> {
  const { data } = await http.delete<
    ApiSuccess<DeletedResult<'document_id'>> | DeletedResult<'document_id'>
  >(`${PATH}/documents/${documentId}`)
  return unwrapData(data)
}

export async function searchKnowledge(
  payload: KnowledgeSearchPayload,
): Promise<KnowledgeSearchResult> {
  const { data } = await http.post<
    ApiSuccess<KnowledgeSearchResult> | KnowledgeSearchResult
  >(`${PATH}/search`, payload)
  return unwrapData(data)
}
