import { ROUTE_NAMES } from '@/constants/routeNames'

export interface NavItem {
  label: string
  routeName: string
  match: string[]
  icon: string
  hint?: string
}

export interface NavModule {
  key: string
  label: string
  routeName: string
  match: string[]
  icon: string
  items: NavItem[]
}

export const NAV_MODULES: NavModule[] = [
  {
    key: 'home',
    label: '主页',
    routeName: ROUTE_NAMES.dashboard,
    match: [ROUTE_NAMES.dashboard, ROUTE_NAMES.root],
    icon: 'home',
    items: [
      {
        label: '仪表盘',
        routeName: ROUTE_NAMES.dashboard,
        match: [ROUTE_NAMES.dashboard, ROUTE_NAMES.root],
        icon: 'grid',
        hint: '会议概览与待办',
      },
    ],
  },
  {
    key: 'new-meeting',
    label: '新建会议',
    // 该入口不走路由：顶部导航渲染为按钮，点击弹出创建会议窗口
    routeName: ROUTE_NAMES.newMeeting,
    match: [
      ROUTE_NAMES.newMeeting,
      ROUTE_NAMES.preprocess,
      ROUTE_NAMES.asr,
      ROUTE_NAMES.minutesGenerate,
    ],
    icon: 'plus',
    items: [
      {
        label: '会议总入口',
        routeName: ROUTE_NAMES.newMeeting,
        match: [ROUTE_NAMES.newMeeting],
        icon: 'calendar',
        hint: '三个阶段',
      },
      {
        label: '资料预处理',
        routeName: ROUTE_NAMES.preprocess,
        match: [ROUTE_NAMES.preprocess],
        icon: 'file',
        hint: '解析资料、提炼议题',
      },
      {
        label: '录音转写',
        routeName: ROUTE_NAMES.asr,
        match: [ROUTE_NAMES.asr],
        icon: 'mic',
        hint: '记录与标记',
      },
      {
        label: '纪要生成',
        routeName: ROUTE_NAMES.minutesGenerate,
        match: [ROUTE_NAMES.minutesGenerate],
        icon: 'clipboard',
        hint: '生成纪要与待办',
      },
    ],
  },
  {
    key: 'meetings',
    label: '会议管理',
    routeName: ROUTE_NAMES.meetings,
    match: [ROUTE_NAMES.meetings],
    icon: 'video',
    items: [
      {
        label: '会议列表',
        routeName: ROUTE_NAMES.meetings,
        match: [ROUTE_NAMES.meetings],
        icon: 'list',
        hint: '全部会议与材料',
      },
    ],
  },
  {
    key: 'tasks',
    label: '任务管理',
    routeName: ROUTE_NAMES.tasks,
    match: [ROUTE_NAMES.tasks, ROUTE_NAMES.taskArchive],
    icon: 'tasks',
    items: [
      {
        label: '任务总览',
        routeName: ROUTE_NAMES.tasks,
        match: [ROUTE_NAMES.tasks],
        icon: 'tasks',
        hint: '待办与进行中',
      },
      {
        label: '已归档任务',
        routeName: ROUTE_NAMES.taskArchive,
        match: [ROUTE_NAMES.taskArchive],
        icon: 'archive',
        hint: '已完成任务',
      },
    ],
  },
]

export function findModuleByRouteName(name: string | undefined): NavModule | undefined {
  if (!name) {
    return undefined
  }
  return NAV_MODULES.find((module) => module.match.includes(name))
}

/* ------------------------------------------------------------------ 侧边栏二级菜单 */

export interface SideLink {
  label: string
  routeName: string
  icon: string
  /** 命中高亮的路由名 */
  match: string[]
  /** 附加路由参数（如任务状态筛选） */
  query?: Record<string, string>
  /** 同路由下按 query.status 进一步区分高亮（任务分组使用） */
  matchStatus?: string
}

export type SideGroupKey = 'home' | 'meetings' | 'tasks'

/**
 * 侧边栏只展示当前一级下的二级内容，不再与顶部一级重复。
 * - 主页：概览 / 我的会议 / 待办任务
 * - 会议管理（含流程三页）：会议列表 / 模板中心 / 会议工作台
 * - 任务管理：全部任务 / 待处理 / 进行中 / 已完成 / 已归档任务
 */
export const SIDE_GROUPS: Record<SideGroupKey, SideLink[]> = {
  home: [
    {
      label: '概览',
      routeName: ROUTE_NAMES.dashboard,
      icon: 'grid',
      match: [ROUTE_NAMES.dashboard, ROUTE_NAMES.root],
    },
    {
      label: '我的会议',
      routeName: ROUTE_NAMES.meetings,
      icon: 'video',
      match: [ROUTE_NAMES.meetings],
    },
    {
      label: '待办任务',
      routeName: ROUTE_NAMES.tasks,
      icon: 'tasks',
      match: [ROUTE_NAMES.tasks, ROUTE_NAMES.taskArchive],
    },
  ],
  meetings: [
    {
      label: '会议列表',
      routeName: ROUTE_NAMES.meetings,
      icon: 'list',
      match: [ROUTE_NAMES.meetings],
    },
    {
      label: '模板中心',
      routeName: ROUTE_NAMES.templateManage,
      icon: 'folder',
      match: [ROUTE_NAMES.templateManage],
    },
    {
      label: '会议工作台',
      routeName: ROUTE_NAMES.minutesGenerate,
      icon: 'clipboard',
      match: [ROUTE_NAMES.minutesGenerate],
    },
  ],
  tasks: [
    {
      label: '全部任务',
      routeName: ROUTE_NAMES.tasks,
      icon: 'tasks',
      match: [ROUTE_NAMES.tasks],
      query: { status: '' },
      matchStatus: '',
    },
    {
      label: '待处理',
      routeName: ROUTE_NAMES.tasks,
      icon: 'clock',
      match: [ROUTE_NAMES.tasks],
      query: { status: 'todo' },
      matchStatus: 'todo',
    },
    {
      label: '进行中',
      routeName: ROUTE_NAMES.tasks,
      icon: 'check',
      match: [ROUTE_NAMES.tasks],
      query: { status: 'in_progress' },
      matchStatus: 'in_progress',
    },
    {
      label: '已完成',
      routeName: ROUTE_NAMES.tasks,
      icon: 'check',
      match: [ROUTE_NAMES.tasks],
      query: { status: 'completed' },
      matchStatus: 'completed',
    },
    {
      label: '已归档任务',
      routeName: ROUTE_NAMES.taskArchive,
      icon: 'archive',
      match: [ROUTE_NAMES.taskArchive],
    },
  ],
}

/** 根据当前路由归属到对应的侧边栏分组；流程三页归入会议管理分组 */
export function sideGroupForRoute(name: string | undefined): SideGroupKey {
  switch (name) {
    case ROUTE_NAMES.tasks:
    case ROUTE_NAMES.taskArchive:
      return 'tasks'
    case ROUTE_NAMES.meetings:
    case ROUTE_NAMES.templateManage:
    case ROUTE_NAMES.minutesGenerate:
    case ROUTE_NAMES.preprocess:
    case ROUTE_NAMES.asr:
      return 'meetings'
    case ROUTE_NAMES.dashboard:
    case ROUTE_NAMES.root:
    default:
      return 'home'
  }
}
