import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppPagination from '@/components/AppPagination.vue'

function navButtons(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('.app-button')
}

describe('AppPagination', () => {
  it('shows the page info and computed total pages', () => {
    const wrapper = mount(AppPagination, { props: { page: 1, total: 45, pageSize: 20 } })
    expect(wrapper.text()).toContain('第 1 / 3 页')
    expect(wrapper.text()).toContain('共 45 条')
  })

  it('uses a default page size of 20', () => {
    const wrapper = mount(AppPagination, { props: { page: 1, total: 20 } })
    expect(wrapper.text()).toContain('第 1 / 1 页')
  })

  it('treats empty results as a single page', () => {
    const wrapper = mount(AppPagination, { props: { page: 1, total: 0 } })
    expect(wrapper.text()).toContain('第 1 / 1 页')
  })

  it('disables previous on the first page and next on the last page', () => {
    const first = mount(AppPagination, { props: { page: 1, total: 45, pageSize: 20 } })
    expect(navButtons(first)[0].attributes('disabled')).toBeDefined()
    expect(navButtons(first)[1].attributes('disabled')).toBeUndefined()

    const last = mount(AppPagination, { props: { page: 3, total: 45, pageSize: 20 } })
    expect(navButtons(last)[0].attributes('disabled')).toBeUndefined()
    expect(navButtons(last)[1].attributes('disabled')).toBeDefined()
  })

  it('emits update:page when navigating', async () => {
    const wrapper = mount(AppPagination, { props: { page: 2, total: 45, pageSize: 20 } })
    await navButtons(wrapper)[1].trigger('click')
    await navButtons(wrapper)[0].trigger('click')
    expect(wrapper.emitted('update:page')).toEqual([[3], [1]])
  })

  it('does not emit when the target page is out of range', async () => {
    const wrapper = mount(AppPagination, { props: { page: 1, total: 45, pageSize: 20 } })
    await navButtons(wrapper)[0].trigger('click')
    expect(wrapper.emitted('update:page')).toBeUndefined()
  })
})
