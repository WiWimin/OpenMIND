import { describe, expect, it } from 'vitest'

import {
  NAV_MODULES,
  SIDE_GROUPS,
  findModuleByRouteName,
  sideGroupForRoute,
} from '@/constants/navigation'

describe('navigation config', () => {
  it('defines the two-level navigation modules', () => {
    expect(NAV_MODULES.map((module) => module.label)).toEqual([
      '主页',
      '新建会议',
      '会议管理',
      '任务管理',
    ])
  })

  it('maps stage routes to the new-meeting module', () => {
    const module = findModuleByRouteName('new-meeting-preprocess')
    expect(module?.key).toBe('new-meeting')
  })

  it('keeps the new-meeting entry as a create-dialog action instead of a route', () => {
    const module = NAV_MODULES.find((item) => item.key === 'new-meeting')
    // 顶部导航渲染为按钮，点击弹出创建会议窗口；路由名仅作为模块归属参考
    expect(module?.routeName).toBe('new-meeting')
    expect(module?.match).toContain('new-meeting')
    expect(findModuleByRouteName('new-meeting-create')).toBeUndefined()
  })

  it('drops the removed meeting detail route from the meetings module', () => {
    const module = NAV_MODULES.find((item) => item.key === 'meetings')
    expect(module?.match).toEqual(['meetings'])
    expect(findModuleByRouteName('meeting-detail')).toBeUndefined()
  })

  it('groups sidebar secondary links by top-level module', () => {
    expect(SIDE_GROUPS.home.map((link) => link.label)).toEqual([
      '概览',
      '我的会议',
      '待办任务',
    ])
    expect(SIDE_GROUPS.meetings.map((link) => link.label)).toEqual([
      '会议列表',
      '模板中心',
      '会议工作台',
    ])
    expect(SIDE_GROUPS.tasks.map((link) => link.label)).toEqual([
      '全部任务',
      '待处理',
      '进行中',
      '已完成',
      '已归档任务',
    ])
  })

  it('maps stage and meeting routes to the meetings sidebar group', () => {
    expect(sideGroupForRoute('dashboard')).toBe('home')
    expect(sideGroupForRoute('meetings')).toBe('meetings')
    expect(sideGroupForRoute('meeting-template-manage')).toBe('meetings')
    expect(sideGroupForRoute('new-meeting-preprocess')).toBe('meetings')
    expect(sideGroupForRoute('new-meeting-asr')).toBe('meetings')
    expect(sideGroupForRoute('new-meeting-minutes')).toBe('meetings')
    expect(sideGroupForRoute('tasks')).toBe('tasks')
    expect(sideGroupForRoute('task-archive')).toBe('tasks')
  })
})
