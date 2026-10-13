import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as materialsApi from '@/api/materials'
import MaterialSection from '@/components/MaterialSection.vue'
import type { ListData } from '@/types/api'
import type { Material } from '@/types/material'

vi.mock('@/api/materials', () => ({
  listMaterials: vi.fn(),
  uploadMaterial: vi.fn(),
  getMaterial: vi.fn(),
  deleteMaterial: vi.fn(),
}))

const processed: Material = {
  material_id: 'mat_1',
  meeting_id: 'mtg_1',
  file_name: '项目方案.pdf',
  type: 'pdf',
  source: null,
  processing_status: 'processed',
  parse_error: null,
  created_at: '2026-10-01T09:10:00+08:00',
}

function listOf(items: Material[]): ListData<Material> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountSection(): VueWrapper {
  return mount(MaterialSection, { props: { meetingId: 'mtg_1' } })
}

async function selectFile(wrapper: VueWrapper, file: File): Promise<void> {
  const input = wrapper.get('input[type="file"]').element as HTMLInputElement
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  await wrapper.get('input[type="file"]').trigger('change')
}

describe('MaterialSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders the uploaded materials', async () => {
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(listOf([processed]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('项目方案.pdf')
  })

  it('shows the empty state when there are no materials', async () => {
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(listOf([]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有材料')
  })

  it('shows an error and retries', async () => {
    vi.mocked(materialsApi.listMaterials)
      .mockRejectedValueOnce({ error_code: 'INTERNAL_ERROR', message: '服务异常' })
      .mockResolvedValue(listOf([processed]))
    const wrapper = mountSection()
    await flushPromises()

    expect(wrapper.text()).toContain('服务异常')

    await wrapper.get('.error-message button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('项目方案.pdf')
  })

  it('uploads a material then refreshes', async () => {
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(listOf([]))
    vi.mocked(materialsApi.uploadMaterial).mockResolvedValue(processed)
    const wrapper = mountSection()
    await flushPromises()

    const file = new File(['x'], 'plan.pdf')
    await selectFile(wrapper, file)
    await wrapper.get('.material-uploader .app-button').trigger('click')
    await flushPromises()

    expect(materialsApi.uploadMaterial).toHaveBeenCalledWith(
      'mtg_1',
      expect.objectContaining({ file }),
    )
    expect(materialsApi.listMaterials).toHaveBeenCalledTimes(2)
  })

  it('deletes a material after confirmation', async () => {
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(listOf([processed]))
    vi.mocked(materialsApi.deleteMaterial).mockResolvedValue({ deleted: true, material_id: 'mat_1' })
    const wrapper = mountSection()
    await flushPromises()

    await wrapper.get('.material-item .app-button').trigger('click')
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((button) => button.text() === '删除')
    await confirm?.trigger('click')
    await flushPromises()

    expect(materialsApi.deleteMaterial).toHaveBeenCalledWith('mat_1')
  })

  it('polls while a material is processing', async () => {
    vi.useFakeTimers()
    const processing: Material = { ...processed, material_id: 'mat_2', processing_status: 'processing' }
    vi.mocked(materialsApi.listMaterials)
      .mockResolvedValueOnce(listOf([processing]))
      .mockResolvedValue(listOf([processed]))

    const wrapper = mountSection()
    await flushPromises()
    expect(materialsApi.listMaterials).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(3000)
    await flushPromises()

    expect(materialsApi.listMaterials).toHaveBeenCalledTimes(2)
    wrapper.unmount()
  })
})
