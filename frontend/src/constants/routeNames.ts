// 路由名与路径的唯一来源（S2 接缝）：
// 切换路由命名/落点（如 /workspace → /meetings、/ → 登录）时只改这里（决策 2 已落地）。
export const ROUTE_NAMES = {
  root: 'root',
  home: 'home',
  login: 'login',
  register: 'register',
  meetings: 'meetings',
  meetingDetail: 'meeting-detail',
  tasks: 'tasks',
} as const

export const ROUTE_PATHS = {
  root: '/',
  home: '/home',
  login: '/login',
  register: '/register',
  meetings: '/meetings',
  meetingDetail: '/meetings/:meetingId',
  tasks: '/tasks',
} as const
