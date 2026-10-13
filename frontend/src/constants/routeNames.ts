// 路由名与路径的唯一来源（S2 接缝）：
// 切换路由命名/落点（如 /workspace → /meetings）时只改这里（决策 2 已落地）。
export const ROUTE_NAMES = {
  home: 'home',
  login: 'login',
  register: 'register',
  meetings: 'meetings',
  meetingDetail: 'meeting-detail',
} as const

export const ROUTE_PATHS = {
  home: '/',
  login: '/login',
  register: '/register',
  meetings: '/meetings',
  meetingDetail: '/meetings/:meetingId',
} as const
