import { describe, expect, it } from 'vitest'

import { ROUTE_NAMES, ROUTE_PATHS } from '@/constants/routeNames'

describe('route constants', () => {
  it('maps the public and auth routes', () => {
    expect(ROUTE_NAMES.home).toBe('home')
    expect(ROUTE_PATHS.home).toBe('/')
    expect(ROUTE_NAMES.login).toBe('login')
    expect(ROUTE_PATHS.login).toBe('/login')
    expect(ROUTE_NAMES.register).toBe('register')
    expect(ROUTE_PATHS.register).toBe('/register')
  })

  it('exposes the current authenticated landing route', () => {
    // 决策 2 切换为 /meetings 时，此处与路由表将同步调整
    expect(ROUTE_NAMES.workspace).toBe('workspace')
    expect(ROUTE_PATHS.workspace).toBe('/workspace')
  })
})
