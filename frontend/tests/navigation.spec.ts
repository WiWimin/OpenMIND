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
})
