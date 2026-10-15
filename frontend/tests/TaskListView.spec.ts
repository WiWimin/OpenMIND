import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as tasksApi from '@/api/tasks'
import type { ListData } from '@/types/api'
import type { PersonalTask } from '@/types/task'
import TaskListView from '@/views/tasks/TaskListView.vue'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: pushMock }) }))

vi.mock('@/api/tasks', () => ({
  listTasks: vi.fn(),
  getTask: vi.fn(),
  updateTask: vi.fn(),
  cancelTask: vi.fn(),
}))

const task: PersonalTask = {
  task_id: 'tsk_1',
  user_id: 'usr_1',
  meeting_id: 'mtg_1',
  action_id: 'act_1',
  title: '完成接口联调',
  status: 'todo',
  due_date: '2026-10-05',
  created_at: '2026-10-01T10:10:00+08:00',
  updated_at: '2026-10-01T10:10:00+08:00',
}

function listOf(items: PersonalTask[]): ListData<PersonalTask> {
  return {
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
  }
}

function mountView(): VueWrapper {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mount(TaskListView, { global: { plugins: [pinia] } })
}

function button(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('button').find((item) => item.text() === text)
}

describe('TaskListView', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders the tasks', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('完成接口联调')
    expect(wrapper.text()).toContain('待办')
  })

  it('shows the empty state', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有任务')
  })

  it('filters by status', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([]))
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#task-status-filter').setValue('completed')
    await flushPromises()

    expect(tasksApi.listTasks).toHaveBeenLastCalledWith({
      page: 1,
      page_size: 20,
      status: 'completed',
    })
  })

  it('updates a task status inline', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    vi.mocked(tasksApi.updateTask).mockResolvedValue({ ...task, status: 'completed' })
    const wrapper = mountView()
    await flushPromises()

    await wrapper.get('#task-status-tsk_1').setValue('completed')
    await flushPromises()

    expect(tasksApi.updateTask).toHaveBeenCalledWith('tsk_1', { status: 'completed' })
  })

  it('shows the task detail dialog and jumps to the source meeting', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    const wrapper = mountView()
    await flushPromises()

    await button(wrapper, '查看详情')?.trigger('click')

    const modal = wrapper.get('.modal')
    expect(modal.text()).toContain('完成接口联调')
    expect(modal.text()).toContain('mtg_1')

    const jump = modal.findAll('button').find((item) => item.text() === '跳转来源会议')
    await jump?.trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'meeting-detail',
      params: { meetingId: 'mtg_1' },
    })
  })

  it('edits a task title and due date', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    vi.mocked(tasksApi.updateTask).mockResolvedValue({ ...task, title: '更新后的任务' })
    const wrapper = mountView()
    await flushPromises()

    await button(wrapper, '编辑任务')?.trigger('click')
    await wrapper.get('#task-edit-title-tsk_1').setValue('更新后的任务')
    await wrapper.get('.task-item__edit').trigger('submit')
    await flushPromises()

    expect(tasksApi.updateTask).toHaveBeenCalledWith('tsk_1', {
      title: '更新后的任务',
      due_date: '2026-10-05',
    })
  })

  it('cancels a task after confirmation', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    vi.mocked(tasksApi.cancelTask).mockResolvedValue({ ...task, status: 'cancelled' })
    const wrapper = mountView()
    await flushPromises()

    await button(wrapper, '取消任务')?.trigger('click')
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((item) => item.text() === '取消任务')
    await confirm?.trigger('click')
    await flushPromises()

    expect(tasksApi.cancelTask).toHaveBeenCalledWith('tsk_1')
  })
})
