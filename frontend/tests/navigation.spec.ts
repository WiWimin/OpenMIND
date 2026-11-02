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

  it('keeps the meeting detail under meeting management', () => {
    expect(findModuleByRouteName('meeting-detail')?.key).toBe('meetings')
  })
})
