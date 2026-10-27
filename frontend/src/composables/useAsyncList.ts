import { ref, shallowRef, type Ref } from 'vue'

import type { Pagination } from '@/types/pagination'

export interface AsyncListParams {
  page: number
  page_size: number
}

export interface AsyncListResult<T> {
  items: T[]
  pagination: Pagination
}

export interface AsyncListOptions<T> {
  fetcher: (params: AsyncListParams) => Promise<AsyncListResult<T>>
  pageSize?: number
}

export interface AsyncList<T> {
  items: Ref<T[]>
  pagination: Ref<Pagination>
  loading: Ref<boolean>
  error: Ref<unknown>
  load: (page?: number) => Promise<void>
  setPage: (page: number) => Promise<void>
  loadMore: () => Promise<void>
}

export function useAsyncList<T>(options: AsyncListOptions<T>): AsyncList<T> {
  const pageSize = options.pageSize ?? 20
  const items = ref<T[]>([]) as Ref<T[]>
  const pagination = ref<Pagination>({
    page: 1,
    page_size: pageSize,
    total: 0,
    total_pages: 1,
  })
  const loading = ref(false)
  // 错误保持为原始 ApiError 对象（shallowRef 保留引用），展示策略由 ErrorMessage 接缝决定（决策 1）
  const error = shallowRef<unknown>(null)

  async function load(page: number = pagination.value.page): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const result = await options.fetcher({ page, page_size: pagination.value.page_size })
      items.value = result.items
      pagination.value = result.pagination
    } catch (caught) {
      error.value = caught
    } finally {
      loading.value = false
    }
  }

  async function setPage(page: number): Promise<void> {
    await load(page)
  }

  async function loadMore(): Promise<void> {
    const next = pagination.value.page + 1
    if (next > pagination.value.total_pages || loading.value) {
      return
    }
    loading.value = true
    error.value = null
    try {
      const result = await options.fetcher({
        page: next,
        page_size: pagination.value.page_size,
      })
      items.value = [...items.value, ...result.items]
      pagination.value = result.pagination
    } catch (caught) {
      error.value = caught
    } finally {
      loading.value = false
    }
  }

  return { items, pagination, loading, error, load, setPage, loadMore }
}
