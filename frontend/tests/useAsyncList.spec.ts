import { describe, expect, it, vi } from 'vitest'

import { useAsyncList } from '@/composables/useAsyncList'
import type { Pagination } from '@/types/pagination'

const page1: Pagination = { page: 1, page_size: 20, total: 45, total_pages: 3 }

describe('useAsyncList', () => {
  it('starts empty and not loading', () => {
    const list = useAsyncList({ fetcher: vi.fn() })
    expect(list.items.value).toEqual([])
    expect(list.loading.value).toBe(false)
    expect(list.error.value).toBeNull()
    expect(list.pagination.value).toEqual({ page: 1, page_size: 20, total: 0, total_pages: 1 })
  })

  it('loads items and pagination', async () => {
    const fetcher = vi.fn(async () => ({ items: ['a'], pagination: page1 }))
    const list = useAsyncList({ fetcher })

    await list.load()

    expect(fetcher).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(list.items.value).toEqual(['a'])
    expect(list.pagination.value).toEqual(page1)
    expect(list.loading.value).toBe(false)
  })

  it('captures errors without throwing', async () => {
    const failure = { error_code: 'INTERNAL_ERROR' }
    const fetcher = vi.fn(async () => {
      throw failure
    })
    const list = useAsyncList({ fetcher })

    await list.load()

    expect(list.error.value).toBe(failure)
    expect(list.loading.value).toBe(false)
  })

  it('requests a specific page via setPage', async () => {
    const fetcher = vi.fn(async () => ({ items: [], pagination: { ...page1, page: 2 } }))
    const list = useAsyncList({ fetcher })

    await list.setPage(2)

    expect(fetcher).toHaveBeenCalledWith({ page: 2, page_size: 20 })
    expect(list.pagination.value.page).toBe(2)
  })

  it('respects a custom page size', async () => {
    const fetcher = vi.fn(async () => ({ items: [], pagination: { ...page1, page_size: 50 } }))
    const list = useAsyncList({ fetcher, pageSize: 50 })

    await list.load()

    expect(fetcher).toHaveBeenCalledWith({ page: 1, page_size: 50 })
  })

  it('clears a previous error on the next load', async () => {
    const fetcher = vi
      .fn()
      .mockRejectedValueOnce(new Error('x'))
      .mockResolvedValue({ items: [], pagination: page1 })
    const list = useAsyncList({ fetcher })

    await list.load()
    expect(list.error.value).toBeInstanceOf(Error)

    await list.load()
    expect(list.error.value).toBeNull()
  })
})
