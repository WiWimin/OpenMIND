import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as audioApi from '@/api/audio'
import * as meetingsApi from '@/api/meetings'
import * as materialsApi from '@/api/materials'
import * as minutesApi from '@/api/minutes'
import * as recordsApi from '@/api/records'
import type { Meeting } from '@/types/meeting'
import MeetingManageView from '@/views/meetings/MeetingManageView.vue'

const { pushMock, routeState } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  routeState: { query: {} as Record<string, string> },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => routeState,
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('@/api/meetings', () => ({
  listMeetings: vi.fn(),
  createMeeting: vi.fn(),
  getMeeting: vi.fn(),
  updateMeeting: vi.fn(),
  deleteMeeting: vi.fn(),
  archiveMeeting: vi.fn(),
}))

vi.mock('@/api/materials', () => ({ listMaterials: vi.fn() }))
vi.mock('@/api/audio', () => ({ listAudio: vi.fn() }))
vi.mock('@/api/minutes', () => ({ listMinutes: vi.fn() }))
vi.mock('@/api/records', () => ({ listRecords: vi.fn() }))

const meetings: Meeting[] = [
  {
    meeting_id: 'mtg_1',
    title: '项目启动会',
    topic: '里程碑与分工',
    meeting_time: '2026-10-18T10:00:00+08:00',
    status: 'scheduled',
    has_minutes: true,
    material_count: 3,
    record_count: 2,
    audio_count: 1,
    created_at: '2026-10-01T09:00:00+08:00',
    updated_at: '2026-10-10T09:00:00+08:00',
    archived_at: null,
  },
  {
    meeting_id: 'mtg_2',
    title: '需求评审会',
    topic: null,
    meeting_time: null,
    status: 'archived',
    created_at: '2026-09-01T09:00:00+08:00',
    updated_at: '2026-09-10T09:00:00+08:00',
    archived_at: '2026-09-10T09:00:00+08:00',
  },
]

function listOf<T>(items: T[], total = items.length) {
  return {
    items,
    pagination: { page: 1, page_size: 100, total, total_pages: 1 },
  }
}

function mountView() {
  return mount(MeetingManageView)
}

/** 预置一个分类「周会」，mtg_1 归入其中 */
function seedCategory(): void {
  window.localStorage.setItem(
    'openmind.meeting.categories',
    JSON.stringify([{ id: 'cat_1', name: '周会', createdAt: '2026-10-01T00:00:00Z' }]),
  )
  window.localStorage.setItem(
    'openmind.meeting.categoryMap',
    JSON.stringify({ mtg_1: 'cat_1' }),
  )
}

describe('MeetingManageView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    window.localStorage.clear()
    routeState.query = {}
    vi.mocked(meetingsApi.listMeetings).mockResolvedValue(listOf(meetings))
    vi.mocked(materialsApi.listMaterials).mockResolvedValue(listOf([]))
    vi.mocked(audioApi.listAudio).mockResolvedValue(listOf([]))
    vi.mocked(minutesApi.listMinutes).mockResolvedValue(listOf([]))
    vi.mocked(recordsApi.listRecords).mockResolvedValue(listOf([]))
  })

  it('renders the folder tree beside the meeting card list', async () => {
    const wrapper = mountView()
    await flushPromises()

    // 左栏：文件夹树（全部会议 / 未分类 + 数量角标）
    expect(wrapper.find('.category-tree').exists()).toBe(true)
    const treeNames = wrapper.findAll('.tree-row__name').map((node) => node.text())
    expect(treeNames).toEqual(['全部会议', '未分类'])
    expect(wrapper.findAll('.tree-row__count').map((node) => node.text())).toEqual(['2', '2'])

    // 右栏：会议卡片直接平铺，根视图无裸露删除按钮
    expect(wrapper.findAll('.meeting-card').length).toBe(2)
    expect(wrapper.text()).toContain('项目启动会')
    expect(wrapper.text()).toContain('里程碑与分工')
    expect(wrapper.text()).not.toContain('删除分类')

    // 卡片带状态色标 / 时间 / 资料统计 / 纪要标签
    expect(wrapper.find('.meeting-card__bar').exists()).toBe(true)
    expect(wrapper.text()).toContain('3 份资料')
    expect(wrapper.find('.meeting-card__minutes').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无资料')
  })

  it('opens the meeting file list view from a meeting card', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAll('.meeting-card')[0].trigger('click')
    await flushPromises()

    expect(wrapper.find('.meeting-files-view__title').text()).toBe('项目启动会')
    // 会议操作（会议工作台/编辑/归档/删除）都在文件列表页
    expect(wrapper.findAll('.meeting-files-view__actions button').map((node) => node.text())).toEqual(
      ['会议工作台', '编辑', '归档', '删除'],
    )
    expect(wrapper.find('.file-explorer').exists()).toBe(true)
    expect(wrapper.find('.meeting-files-panel').exists()).toBe(true)
  })

  it('opens a meeting file list directly from the ?meeting= deep link', async () => {
    routeState.query = { meeting: 'mtg_2' }
    vi.mocked(meetingsApi.getMeeting).mockResolvedValue(meetings[1])

    const wrapper = mountView()
    await flushPromises()

    expect(meetingsApi.getMeeting).toHaveBeenCalledWith('mtg_2')
    expect(wrapper.find('.meeting-files-view__title').text()).toBe('需求评审会')
    expect(wrapper.find('.meeting-files-panel').exists()).toBe(true)
  })

  it('navigates back to the card list via the breadcrumb', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.findAll('.meeting-card')[0].trigger('click')
    await flushPromises()

    const backLink = wrapper
      .findAll('.app-breadcrumb__link')
      .find((node) => node.text() === '会议管理')
    await backLink?.trigger('click')
    await flushPromises()

    expect(wrapper.find('.meeting-card-grid').exists()).toBe(true)
    expect(wrapper.find('.meeting-files-panel').exists()).toBe(false)
  })

  it('expands a category to reveal nested meetings with indentation', async () => {
    seedCategory()
    const wrapper = mountView()
    await flushPromises()

    // 分类数量角标：周会 1、未分类 1
    const names = wrapper.findAll('.tree-row__name').map((node) => node.text())
    expect(names).toEqual(['全部会议', '周会', '未分类'])

    // 默认折叠：无子节点
    expect(wrapper.findAll('.tree-meeting').length).toBe(0)

    // 点击展开箭头 → 缩进显示该分类下的会议
    await wrapper.findAll('.tree-row__chevron')[0].trigger('click')
    await flushPromises()

    const children = wrapper.findAll('.tree-meeting')
    expect(children.length).toBe(1)
    expect(children[0].text()).toBe('项目启动会')
  })

  it('selects a category to filter the card list', async () => {
    seedCategory()
    const wrapper = mountView()
    await flushPromises()

    const categoryMain = wrapper.findAll('.tree-row__main')[1]
    await categoryMain.trigger('click')
    await flushPromises()

    expect(wrapper.find('.meeting-list__title').text()).toBe('周会')
    expect(wrapper.findAll('.meeting-card').length).toBe(1)
    expect(wrapper.find('.meeting-card').text()).toContain('项目启动会')
  })

  it('deletes a category from the hover more menu instead of a naked button', async () => {
    seedCategory()
    const wrapper = mountView()
    await flushPromises()

    // 无裸露删除按钮
    expect(wrapper.text()).not.toContain('删除分类')

    await wrapper.find('.tree-row__more').trigger('click')
    await flushPromises()

    const menu = wrapper.find('.tree-row__menu')
    expect(menu.exists()).toBe(true)
    expect(menu.text()).toContain('重命名')
    expect(menu.text()).toContain('删除分类')

    await menu.findAll('button').find((node) => node.text() === '删除分类')?.trigger('click')
    await flushPromises()

    // 确认弹窗 → 确认删除
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((node) => node.text() === '删除分类')
    await confirm?.trigger('click')
    await flushPromises()

    const names = wrapper.findAll('.tree-row__name').map((node) => node.text())
    expect(names).toEqual(['全部会议', '未分类'])
    // 会议归入未分类，数量角标更新
    expect(wrapper.findAll('.tree-row__count').map((node) => node.text())).toEqual(['2', '2'])
  })

  it('renames a category from the more menu', async () => {
    seedCategory()
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.tree-row__more').trigger('click')
    await wrapper
      .find('.tree-row__menu')
      .findAll('button')
      .find((node) => node.text() === '重命名')
      ?.trigger('click')
    await flushPromises()

    const input = wrapper.get('.tree-rename__input')
    await input.setValue('双周会')
    await wrapper.find('.tree-rename__save').trigger('click')
    await flushPromises()

    const names = wrapper.findAll('.tree-row__name').map((node) => node.text())
    expect(names).toEqual(['全部会议', '双周会', '未分类'])
  })

  it('filters meetings client-side by search keyword', async () => {
    const wrapper = mountView()
    await flushPromises()

    await wrapper.find('.search-box__input').setValue('需求')
    await flushPromises()

    expect(wrapper.findAll('.meeting-card').length).toBe(1)
    expect(wrapper.text()).toContain('需求评审会')
    expect(wrapper.text()).not.toContain('项目启动会')
  })

  it('filters meetings by status', async () => {
    const wrapper = mountView()
    await flushPromises()

    const chip = wrapper.findAll('button').find((button) => button.text() === '已归档')
    await chip?.trigger('click')
    await flushPromises()

    expect(meetingsApi.listMeetings).toHaveBeenCalledWith({
      page: 1,
      page_size: 100,
      status: 'archived',
    })
  })

  it('opens the create dialog when clicking 新建会议', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.meeting-form').exists()).toBe(false)

    const createButton = wrapper.findAll('button').find((button) => button.text() === '新建会议')
    await createButton?.trigger('click')
    await flushPromises()

    // 新建统一走创建会议窗口（弹窗），不再跳转创建页
    expect(wrapper.find('.meeting-form').exists()).toBe(true)
    expect(pushMock).not.toHaveBeenCalled()
  })
})
