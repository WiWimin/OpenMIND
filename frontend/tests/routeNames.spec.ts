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

  it('exposes the new meeting stage routes', () => {
    expect(ROUTE_NAMES.newMeeting).toBe('new-meeting')
    expect(ROUTE_PATHS.newMeeting).toBe('/new-meeting')
    expect(ROUTE_NAMES.preprocess).toBe('new-meeting-preprocess')
    expect(ROUTE_PATHS.preprocess).toBe('/new-meeting/preprocess')
    expect(ROUTE_NAMES.asr).toBe('new-meeting-asr')
    expect(ROUTE_PATHS.asr).toBe('/new-meeting/asr')
    expect(ROUTE_NAMES.minutesGenerate).toBe('new-meeting-minutes')
    expect(ROUTE_PATHS.minutesGenerate).toBe('/new-meeting/minutes')
  })

  it('exposes the meeting and task sub-page routes', () => {
    expect(ROUTE_NAMES.taskArchive).toBe('task-archive')
    expect(ROUTE_PATHS.taskArchive).toBe('/tasks/archive')
  })
})
