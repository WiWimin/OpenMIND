// 路由名与路径的唯一来源（S2 接缝）：
// 切换路由命名/落点（如 /workspace → /meetings）时只改这里。
export const ROUTE_NAMES = {
  home: 'home',
  login: 'login',
  register: 'register',
  workspace: 'workspace',
} as const

export const ROUTE_PATHS = {
  home: '/',
  login: '/login',
  register: '/register',
  workspace: '/workspace',
} as const
