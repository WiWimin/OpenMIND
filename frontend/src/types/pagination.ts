export interface Pagination {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface PageParams {
  page?: number
  page_size?: number
}
