import { describe, expect, it } from 'vitest'

import { NAV_MODULES, findModuleByRouteName } from '@/constants/navigation'

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

  it('routes the top-level new-meeting entry to the create page', () => {
    const module = NAV_MODULES.find((item) => item.key === 'new-meeting')
    expect(module?.routeName).toBe('new-meeting-create')
    expect(findModuleByRouteName('new-meeting-create')?.key).toBe('new-meeting')
  })

  it('keeps the meeting detail under meeting management', () => {
    expect(findModuleByRouteName('meeting-detail')?.key).toBe('meetings')
  })
})
