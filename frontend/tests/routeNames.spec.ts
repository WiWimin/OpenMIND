import { describe, expect, it } from 'vitest'

import { ROUTE_NAMES, ROUTE_PATHS } from '@/constants/routeNames'

describe('route constants', () => {
  it('maps the public and auth routes', () => {
    // 根路径 / 按登录态重定向（登录页 / 工作区），健康页挪至 /home
    expect(ROUTE_NAMES.root).toBe('root')
    expect(ROUTE_PATHS.root).toBe('/')
    expect(ROUTE_NAMES.home).toBe('home')
    expect(ROUTE_PATHS.home).toBe('/home')
    expect(ROUTE_NAMES.login).toBe('login')
    expect(ROUTE_PATHS.login).toBe('/login')
    expect(ROUTE_NAMES.register).toBe('register')
    expect(ROUTE_PATHS.register).toBe('/register')
  })

  it('exposes the authenticated landing and meeting routes', () => {
    // 决策 2：认证后落点由 /workspace 改为 /meetings
    expect(ROUTE_NAMES.meetings).toBe('meetings')
    expect(ROUTE_PATHS.meetings).toBe('/meetings')
    expect(ROUTE_NAMES.meetingDetail).toBe('meeting-detail')
    expect(ROUTE_PATHS.meetingDetail).toBe('/meetings/:meetingId')
  })
})
