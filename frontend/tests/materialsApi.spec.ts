import { beforeEach, describe, expect, it, vi } from 'vitest'

import http from '@/api/client'
import { deleteMaterial, getMaterial, listMaterials, uploadMaterial } from '@/api/materials'
import type { ListData } from '@/types/api'
import type { Material } from '@/types/material'
import { response } from './support'

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}))

const get = vi.mocked(http.get)
const post = vi.mocked(http.post)
const del = vi.mocked(http.delete)

const material: Material = {
  material_id: 'mat_1',
  meeting_id: 'mtg_1',
  file_name: '方案.pdf',
  type: 'pdf',
  source: null,
  processing_status: 'uploaded',
  parse_error: null,
  created_at: '2026-10-01T09:00:00+08:00',
}

describe('materials api', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('lists materials with pagination params', async () => {
    const list: ListData<Material> = {
      items: [material],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    }
    get.mockResolvedValue(response(list))

    await expect(listMaterials('mtg_1', { page: 1 })).resolves.toEqual(list)
    expect(get).toHaveBeenCalledWith('/meetings/mtg_1/materials', { params: { page: 1 } })
  })

  it('unwraps a success envelope for a material', async () => {
    get.mockResolvedValue(response({ status: 'success', data: material }))

    await expect(getMaterial('mat_1')).resolves.toEqual(material)
    expect(get).toHaveBeenCalledWith('/materials/mat_1')
  })

  it('uploads a material as multipart form data', async () => {
    post.mockResolvedValue(response(material))
    const file = new File(['x'], 'a.pdf', { type: 'application/pdf' })

    await uploadMaterial('mtg_1', { file, source: '会前材料' })

    const [url, form, config] = post.mock.calls[0]
    expect(url).toBe('/meetings/mtg_1/materials')
    expect((form as FormData).get('file')).toBe(file)
    expect((form as FormData).get('source')).toBe('会前材料')
    expect(config).toEqual({ headers: { 'Content-Type': 'multipart/form-data' } })
  })

  it('deletes a material and returns the deleted id', async () => {
    const deleted = { deleted: true as const, material_id: 'mat_1' }
    del.mockResolvedValue(response({ status: 'success', data: deleted }))

    await expect(deleteMaterial('mat_1')).resolves.toEqual(deleted)
    expect(del).toHaveBeenCalledWith('/materials/mat_1')
  })
})
