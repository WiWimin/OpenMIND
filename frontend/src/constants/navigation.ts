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
    match: [ROUTE_NAMES.meetings, ROUTE_NAMES.meetingDetail],
    icon: 'video',
    items: [
      {
        label: '会议列表',
        routeName: ROUTE_NAMES.meetings,
        match: [ROUTE_NAMES.meetings, ROUTE_NAMES.meetingDetail],
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

export function findModuleByKey(key: string | undefined): NavModule | undefined {
  return NAV_MODULES.find((module) => module.key === key)
}

export function findModuleByRouteName(name: string | undefined): NavModule | undefined {
  if (!name) {
    return undefined
  }
  return NAV_MODULES.find((module) => module.match.includes(name))
}

export function findNavItem(
  module: NavModule | undefined,
  name: string | undefined,
): NavItem | undefined {
  if (!module || !name) {
    return undefined
  }
  return module.items.find((item) => item.match.includes(name))
}
