import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as tasksApi from '@/api/tasks'
import TaskSection from '@/components/TaskSection.vue'
import type { ListData } from '@/types/api'
import type { PersonalTask } from '@/types/task'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: pushMock }) }))

vi.mock('@/api/tasks', () => ({
  listTasks: vi.fn(),
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
  priority: 'medium',
  due_date: '2026-10-05',
  meeting_title: '项目周会',
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
  return mount(TaskSection, { global: { plugins: [pinia] } })
}

/** 图标按钮无文本，按 aria-label 查找 */
function iconButton(wrapper: VueWrapper, label: string) {
  return wrapper
    .findAll('button')
    .find((item) => item.attributes('aria-label') === label)
}

describe('TaskSection', () => {
  beforeEach(() => {
    vi.resetAllMocks()
  })

  it('renders the tasks with meeting link and no inline priority badge', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('完成接口联调')
    expect(wrapper.text()).toContain('待办')

    // 列表行内不再展示优先级胶囊（优先级仅在详情弹窗中查看）
    expect(wrapper.find('.task-item__priority').exists()).toBe(false)

    // 关联会议跳转链接（列表接口附带会议标题）
    const meetingLink = wrapper.find('.task-item__meeting-link')
    expect(meetingLink.exists()).toBe(true)
    expect(meetingLink.text()).toBe('项目周会')
    await meetingLink.trigger('click')
    expect(pushMock).toHaveBeenCalledWith({
      name: 'meetings',
      query: { meeting: 'mtg_1' },
    })
  })

  it('shows the empty state', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([]))
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('还没有任务')
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

    await wrapper.find('.task-item__title')?.trigger('click')

    const modal = wrapper.get('.modal')
    expect(modal.text()).toContain('完成接口联调')
    expect(modal.text()).toContain('项目周会')

    const jump = modal.findAll('button').find((item) => item.text() === '跳转来源会议')
    await jump?.trigger('click')

    expect(pushMock).toHaveBeenCalledWith({
      name: 'meetings',
      query: { meeting: 'mtg_1' },
    })
  })

  it('edits a task title and due date', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    vi.mocked(tasksApi.updateTask).mockResolvedValue({ ...task, title: '更新后的任务' })
    const wrapper = mountView()
    await flushPromises()

    await iconButton(wrapper, '编辑任务')?.trigger('click')
    await wrapper.get('#task-edit-title-tsk_1').setValue('更新后的任务')
    await wrapper.get('.task-item__edit').trigger('submit')
    await flushPromises()

    expect(tasksApi.updateTask).toHaveBeenCalledWith('tsk_1', {
      title: '更新后的任务',
      due_date: '2026-10-05',
      priority: 'medium',
    })
  })

  it('marks an incomplete task with a past due date as overdue', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(
      listOf([{ ...task, due_date: '2020-01-01' }]),
    )
    const wrapper = mountView()
    await flushPromises()

    const overdue = wrapper.find('.task-item__overdue')
    expect(overdue.exists()).toBe(true)
    expect(overdue.text()).toBe('已逾期')
  })

  it('does not mark completed or future-due tasks as overdue', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(
      listOf([
        { ...task, task_id: 'tsk_done', status: 'completed', due_date: '2020-01-01' },
        { ...task, task_id: 'tsk_future', due_date: '2099-12-31' },
      ]),
    )
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.find('.task-item__overdue').exists()).toBe(false)
  })

  it('cancels a task after confirmation', async () => {
    vi.mocked(tasksApi.listTasks).mockResolvedValue(listOf([task]))
    vi.mocked(tasksApi.cancelTask).mockResolvedValue({ ...task, status: 'cancelled' })
    const wrapper = mountView()
    await flushPromises()

    await iconButton(wrapper, '删除任务')?.trigger('click')
    const confirm = wrapper
      .get('.modal')
      .findAll('button')
      .find((item) => item.text() === '删除')
    await confirm?.trigger('click')
    await flushPromises()

    expect(tasksApi.cancelTask).toHaveBeenCalledWith('tsk_1')
  })
})
