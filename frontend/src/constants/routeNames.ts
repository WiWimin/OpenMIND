// 路由名与路径的唯一来源（S2 接缝）：
// 切换路由命名/落点（如 / → 仪表盘、/workspace → /meetings）时只改这里（决策 3：认证后落点为仪表盘）。
export const ROUTE_NAMES = {
  root: 'root',
  dashboard: 'dashboard',
  home: 'home',
  login: 'login',
  register: 'register',
  meetings: 'meetings',
  meetingDetail: 'meeting-detail',
  tasks: 'tasks',
} as const

export const ROUTE_PATHS = {
  root: '/',
  dashboard: '/dashboard',
  home: '/home',
  login: '/login',
  register: '/register',
  meetings: '/meetings',
  meetingDetail: '/meetings/:meetingId',
  tasks: '/tasks',
} as const
