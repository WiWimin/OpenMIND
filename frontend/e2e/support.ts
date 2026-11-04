import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const E2E_PASSWORD = 'openmind-e2e-123'

const TOKEN_KEY = 'openmind.auth.token'
const STAGE_HEADINGS = {
  preprocess: '资料预处理',
  asr: '实时录音转写',
  minutes: '会后智能处理',
} as const

export type Stage = keyof typeof STAGE_HEADINGS

export function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function apiBase(): string {
  return process.env.E2E_API_BASE ?? 'http://localhost:8010/api/v1'
}

export function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export async function register(page: Page, name: string): Promise<void> {
  await page.goto('/register')
  await page.locator('#register-name').fill(name)
  await page.locator('#register-password').fill(E2E_PASSWORD)
  await page.locator('#register-confirm').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: '注册', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  // 5.0 概览页标题（旧版为“会议工作台”）
  await expect(page.getByRole('heading', { name: /OpenMIND 智能会议助手/ })).toBeVisible()
}

export async function login(page: Page, name: string): Promise<void> {
  await page.goto('/login')
  await page.locator('#login-name').fill(name)
  await page.locator('#login-password').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
}

/** 通过概览页“新建会议”对话框创建会议，返回 meetingId（创建后跳转 /new-meeting）。 */
export async function createMeeting(
  page: Page,
  title: string,
  topic = 'Playwright 端到端验收',
): Promise<string> {
  await page.getByRole('button', { name: '新建会议', exact: true }).first().click()
  const dialog = page.getByRole('dialog', { name: '新建会议', exact: true })
  await expect(dialog).toBeVisible()
  await dialog.locator('#meeting-title').fill(title)
  if (topic) {
    await dialog.locator('#meeting-topic').fill(topic)
  }
  // 5.0 新建时提交按钮为“创建”（编辑态才是“保存”）
  await dialog.getByRole('button', { name: '创建', exact: true }).click()
  await expect(dialog).toBeHidden()
  await page.waitForURL(/\/new-meeting\?meetingId=/)
  const meetingId = new URL(page.url()).searchParams.get('meetingId')
  if (!meetingId) {
    throw new Error('创建会议后未取得 meetingId')
  }
  return meetingId
}

/** 打开三段式工作区的某一阶段页并等待标题渲染。 */
export async function openStage(page: Page, meetingId: string, stage: Stage): Promise<void> {
  await page.goto(`/new-meeting/${stage}?meetingId=${meetingId}`)
  await expect(page.getByRole('heading', { name: STAGE_HEADINGS[stage], exact: true })).toBeVisible({
    timeout: 30_000,
  })
}

/** 在“资料预处理”页上传文本材料，等待解析完成。 */
export async function uploadMaterial(
  page: Page,
  fileName: string,
  content: string,
): Promise<void> {
  const input = page.locator('input[type=file][accept*=".txt"]').first()
  await input.setInputFiles({
    name: fileName,
    mimeType: 'text/plain',
    buffer: Buffer.from(content, 'utf-8'),
  })
  // 选择文件后需点击“上传资料”才真正提交
  await page.getByRole('button', { name: '上传资料', exact: true }).first().click()
  await expect(page.getByText(fileName, { exact: true }).first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('已解析', { exact: true }).first()).toBeVisible({ timeout: 60_000 })
}

/** 打开左下角“设置菜单”，进入“模型配置”弹窗。 */
export async function openModelConfig(page: Page): Promise<void> {
  await page.getByLabel('设置菜单').first().click()
  await page.getByRole('menuitem', { name: '模型配置' }).click()
  await expect(page.getByRole('dialog', { name: '模型配置', exact: true })).toBeVisible()
}

/** 打开左下角“设置菜单”的指定菜单项。 */
export async function openSettingsItem(page: Page, name: string): Promise<void> {
  const item = page.getByRole('menuitem', { name, exact: true })
  if (!(await item.isVisible().catch(() => false))) {
    await page.getByLabel('设置菜单').first().click()
  }
  await item.click()
}

/** 打开“知识库”弹窗。 */
export async function openKnowledge(page: Page) {
  await openSettingsItem(page, '知识库')
  const dialog = page.getByRole('dialog', { name: '知识库', exact: true })
  await expect(dialog).toBeVisible()
  return dialog
}

/** 打开“记忆中心”弹窗。 */
export async function openMemory(page: Page) {
  await openSettingsItem(page, '记忆中心')
  const dialog = page.getByRole('dialog', { name: '记忆中心', exact: true })
  await expect(dialog).toBeVisible()
  return dialog
}

/** 关闭当前弹窗（AppModal 的关闭按钮）。 */
export async function closeModal(page: Page): Promise<void> {
  const close = page.getByRole('button', { name: '关闭', exact: true }).first()
  if (await close.count()) {
    await close.click()
  }
}

/** 上传知识库文档并等待索引完成。 */
export async function uploadKnowledge(
  page: Page,
  fileName: string,
  content: string,
): Promise<void> {
  const dialog = await openKnowledge(page)
  await dialog.locator('input[type=file]').setInputFiles({
    name: fileName,
    mimeType: 'text/plain',
    buffer: Buffer.from(content, 'utf-8'),
  })
  await expect(dialog.getByText(fileName, { exact: true })).toBeVisible({ timeout: 120_000 })
  await expect(dialog.getByText('已索引', { exact: true }).first()).toBeVisible({
    timeout: 120_000,
  })
}

/** 保存用户记忆并等待成功提示。 */
export async function saveMemory(
  page: Page,
  role: string,
  scenarios: string,
  style: string,
): Promise<void> {
  const dialog = await openMemory(page)
  await dialog.locator('#memory-role').fill(role)
  await dialog.locator('#memory-scenarios').fill(scenarios)
  await dialog.locator('#memory-style').fill(style)
  await dialog.getByRole('button', { name: '保存记忆', exact: true }).click()
  await expect(page.getByText('记忆已保存', { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  })
}

/** 进入会议管理并在“未分类”文件夹中打开指定会议详情面板。 */
export async function openMeetingDetail(page: Page, title: string): Promise<void> {
  await page.goto('/meetings')
  await expect(page.getByRole('heading', { name: '会议管理', exact: true })).toBeVisible()
  const folder = page.getByRole('button', { name: /未分类/ }).first()
  if (await folder.count()) {
    await folder.click()
  }
  await page.getByRole('button', { name: new RegExp(escapeRegExp(title)) }).first().click()
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
}

const MEETING_TAB_LABELS = {
  materials: '材料',
  preparation: '会前准备',
  records: '记录',
  audio: '音频',
  minutes: '纪要',
  issues: '问题',
  checklist: '收尾',
} as const

/** 直接打开会议详情的指定标签页（会议详情路由 /meetings/:meetingId?tab=）。 */
export async function openMeetingTab(
  page: Page,
  meetingId: string,
  tab: keyof typeof MEETING_TAB_LABELS,
): Promise<void> {
  await page.goto(`/meetings/${meetingId}?tab=${tab}`)
  await expect(page.getByRole('tab', { name: MEETING_TAB_LABELS[tab], exact: true })).toBeVisible({
    timeout: 30_000,
  })
}

/** 在会议详情“记录”标签页新增一条记录。 */
export async function addRecord(page: Page, content: string): Promise<void> {
  await page.locator('#record-content').fill(content)
  await page.getByRole('button', { name: '保存记录', exact: true }).click()
  await expect(page.getByText(content, { exact: false }).first()).toBeVisible({ timeout: 30_000 })
}

/** 兼容旧用例：读取登录令牌（BYOK 配置时使用）。 */
export async function authToken(page: Page): Promise<string> {
  const token = await page.evaluate((key) => window.localStorage.getItem(key), TOKEN_KEY)
  if (!token) {
    throw new Error('未找到登录令牌，无法调用后端接口')
  }
  return token
}

export interface ModelAccessResult {
  ready: boolean
  reason?: string
}

/**
 * 登录用户是否已具备可用模型配置。
 * 5.0 的 Embedding 只能由服务端统一配置（用户不可自备），因此本函数只检查
 * LLM/Embedding 是否已有生效来源（测试环境通过全局 Mock + 回退开关满足）。
 */
export async function prepareModelAccess(
  page: Page,
  request: APIRequestContext,
): Promise<ModelAccessResult> {
  const headers = { Authorization: `Bearer ${await authToken(page)}` }
  const response = await request.get(`${apiBase()}/me/settings/model`, { headers })
  if (!response.ok()) {
    throw new Error(`读取模型配置失败：HTTP ${response.status()} ${await response.text()}`)
  }
  const current = (await response.json()).data as { llm_source: string; embedding_source: string }
  if (current.llm_source !== 'none' && current.embedding_source !== 'none') {
    return { ready: true }
  }
  return {
    ready: false,
    reason: 'BLOCKED: 测试环境未提供全局 LLM/Embedding Mock 配置',
  }
}
