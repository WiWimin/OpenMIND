/**
 * 会议分类的过渡存储（localStorage）。
 *
 * ⚠️ 过渡方案：后端 meeting_categories 表上线后，此模块的数据源将切换为 API，
 * 迁移逻辑在二期一并处理。所有会议与分类的归属仅保存在当前浏览器。
 */

export interface MeetingCategory {
  id: string
  name: string
  createdAt: string
}

const CATEGORIES_KEY = 'openmind.meeting.categories'
const MAP_KEY = 'openmind.meeting.categoryMap'

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) {
      return fallback
    }
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* 存储不可用时静默降级 */
  }
}

export function loadCategories(): MeetingCategory[] {
  const list = readJson<MeetingCategory[]>(CATEGORIES_KEY, [])
  return Array.isArray(list) ? list : []
}

function saveCategories(list: MeetingCategory[]): void {
  writeJson(CATEGORIES_KEY, list)
}

function loadMap(): Record<string, string> {
  const map = readJson<Record<string, string>>(MAP_KEY, {})
  return map && typeof map === 'object' ? map : {}
}

export function createCategory(name: string): MeetingCategory {
  const trimmed = name.trim()
  const category: MeetingCategory = {
    id: `cat_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: trimmed,
    createdAt: new Date().toISOString(),
  }
  const list = loadCategories()
  list.push(category)
  saveCategories(list)
  return category
}

/** 删除分类；其下会议自动归入未分类（仅清除映射） */
export function deleteCategory(categoryId: string): void {
  saveCategories(loadCategories().filter((category) => category.id !== categoryId))
  const map = loadMap()
  let changed = false
  for (const [meetingId, mapped] of Object.entries(map)) {
    if (mapped === categoryId) {
      delete map[meetingId]
      changed = true
    }
  }
  if (changed) {
    writeJson(MAP_KEY, map)
  }
}

export function renameCategory(categoryId: string, name: string): void {
  const list = loadCategories()
  const category = list.find((item) => item.id === categoryId)
  if (category) {
    category.name = name.trim()
    saveCategories(list)
  }
}

export function categoryOf(meetingId: string): string | null {
  return loadMap()[meetingId] ?? null
}

export function assignCategory(meetingId: string, categoryId: string | null): void {
  const map = loadMap()
  if (categoryId) {
    map[meetingId] = categoryId
  } else {
    delete map[meetingId]
  }
  writeJson(MAP_KEY, map)
}

export function categoryNameOf(categoryId: string | null): string | null {
  if (!categoryId) {
    return null
  }
  return loadCategories().find((category) => category.id === categoryId)?.name ?? null
}
