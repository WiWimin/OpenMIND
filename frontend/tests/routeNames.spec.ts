import { describe, expect, it } from 'vitest'

import { ROUTE_NAMES, ROUTE_PATHS } from '@/constants/routeNames'

describe('route constants', () => {
  it('maps the public and auth routes', () => {
    expect(ROUTE_NAMES.root).toBe('root')
    expect(ROUTE_PATHS.root).toBe('/')
    expect(ROUTE_NAMES.login).toBe('login')
    expect(ROUTE_PATHS.login).toBe('/login')
    expect(ROUTE_NAMES.register).toBe('register')
    expect(ROUTE_PATHS.register).toBe('/register')
  })

  it('exposes the authenticated landing and meeting routes', () => {
    // 决策 3：认证后落点为仪表盘（/dashboard），会议列表仍为 /meetings
    expect(ROUTE_NAMES.dashboard).toBe('dashboard')
    expect(ROUTE_PATHS.dashboard).toBe('/dashboard')
    expect(ROUTE_NAMES.meetings).toBe('meetings')
    expect(ROUTE_PATHS.meetings).toBe('/meetings')
    expect(ROUTE_NAMES.meetingDetail).toBe('meeting-detail')
    expect(ROUTE_PATHS.meetingDetail).toBe('/meetings/:meetingId')
  })

  it('exposes the knowledge base route', () => {
    expect(ROUTE_NAMES.knowledge).toBe('knowledge')
    expect(ROUTE_PATHS.knowledge).toBe('/knowledge')
  })

  it('exposes the model settings route', () => {
    expect(ROUTE_NAMES.settings).toBe('settings')
    expect(ROUTE_PATHS.settings).toBe('/settings')
  })
})
