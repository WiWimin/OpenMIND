// 路由名与路径的唯一来源（S2 接缝）：
// 切换路由命名/落点（如 / → 仪表盘、/workspace → /meetings）时只改这里（决策 3：认证后落点为仪表盘）。
export const ROUTE_NAMES = {
  root: 'root',
  dashboard: 'dashboard',
  login: 'login',
  register: 'register',
  newMeeting: 'new-meeting',
  preprocess: 'new-meeting-preprocess',
  asr: 'new-meeting-asr',
  minutesGenerate: 'new-meeting-minutes',
  meetings: 'meetings',
  meetingDetail: 'meeting-detail',
  templateManage: 'meeting-template-manage',
  tasks: 'tasks',
  taskArchive: 'task-archive',
} as const

export const ROUTE_PATHS = {
  root: '/',
  dashboard: '/dashboard',
  login: '/login',
  register: '/register',
  newMeeting: '/new-meeting',
  preprocess: '/new-meeting/preprocess',
  asr: '/new-meeting/asr',
  minutesGenerate: '/new-meeting/minutes',
  meetings: '/meetings',
  meetingDetail: '/meetings/:meetingId',
  templateManage: '/meetings/templates',
  tasks: '/tasks',
  taskArchive: '/tasks/archive',
} as const

export type RouteName = (typeof ROUTE_NAMES)[keyof typeof ROUTE_NAMES]
