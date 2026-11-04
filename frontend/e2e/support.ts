import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const E2E_PASSWORD = 'openmind-e2e-123'

const TOKEN_KEY = 'openmind.auth.token'

export function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export function apiBase(): string {
  return process.env.E2E_API_BASE ?? 'http://localhost:8000/api/v1'
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
  // Dashboard 首屏为问候语一级标题（如「晚上好，<用户名>」）
  await expect(page.getByRole('heading', { level: 1, name })).toBeVisible()
}

async function authToken(page: Page): Promise<string> {
  const token = await page.evaluate((key) => window.localStorage.getItem(key), TOKEN_KEY)
  if (!token) {
    throw new Error('未找到登录令牌，无法调用后端接口')
  }
  return token
}

export { authToken }

/**
 * 打开左下角「设置」菜单（details 折叠面板）。
 * 导航重构后知识库/模型配置/记忆中心都是菜单内的 menuitem，不再是独立链接。
 */
export async function openSettingsMenu(page: Page): Promise<void> {
  const details = page.locator('details.workspace__settings')
  if ((await details.getAttribute('open')) === null) {
    await page.locator('summary[aria-label="设置菜单"]').click()
  }
  await expect(page.getByRole('menu', { name: '设置菜单' })).toBeVisible()
}

interface ModelConfigResponse {
  llm_source: string
  embedding_source: string
}

interface ProviderSettings {
  api_base: string
  api_key: string
  model: string
}

export interface ModelAccessResult {
  ready: boolean
  reason?: string
}

const MAX_CONFIG_ATTEMPTS = 3
const TRANSIENT_PROBE_MARKERS = ['网络异常', '超时', '限流']

function isTransientProbeFailure(status: number, body: string): boolean {
  if (status === 429 || status >= 500) {
    return true
  }
  if (body.includes('"retryable":true')) {
    return true
  }
  return TRANSIENT_PROBE_MARKERS.some((marker) => body.includes(marker))
}

function providerSettings(prefix: string): ProviderSettings {
  return {
    api_base: process.env[`${prefix}_API_BASE`] ?? '',
    api_key: process.env[`${prefix}_API_KEY`] ?? '',
    model: process.env[`${prefix}_MODEL`] ?? '',
  }
}

function isComplete(settings: ProviderSettings): boolean {
  return Boolean(settings.api_base && settings.api_key && settings.model)
}

/**
 * 登录用户若尚未拥有可用的 LLM / Embedding 配置：
 * - 后端启用全局回退时，直接返回 ready；
 * - 否则尝试使用 E2E_LLM_* / E2E_EMBEDDING_* 环境变量通过 BYOK 接口写入；
 * - 外部探测瞬断时重试；仍失败则返回 blocked 原因，由调用方跳过用例；
 * - 明确的配置错误（401/403/维度等）直接抛出，不掩盖产品问题。
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
  const current = (await response.json()).data as ModelConfigResponse
  const needsLlm = current.llm_source === 'none'
  const needsEmbedding = current.embedding_source === 'none'
  if (!needsLlm && !needsEmbedding) {
    return { ready: true }
  }
  // Embedding 不支持 BYOK（后端仅接受 LLM 三字段，向量模型由服务端 docker/.env 统一配置）
  if (needsEmbedding) {
    return {
      ready: false,
      reason: 'BLOCKED: Embedding 不支持自备，需服务端 docker/.env 配置 EMBEDDING_*',
    }
  }

  const llm = providerSettings('E2E_LLM')
  if (needsLlm && !isComplete(llm)) {
    return {
      ready: false,
      reason: 'BLOCKED: 需要后端启用 ALLOW_GLOBAL_FALLBACK，或提供 E2E_LLM_* 自备配置',
    }
  }

  const payload: Record<string, string> = {}
  if (needsLlm) {
    payload.llm_api_base = llm.api_base
    payload.llm_api_key = llm.api_key
    payload.llm_model = llm.model
  }

  let lastStatus = 0
  let lastBody = ''
  for (let attempt = 1; attempt <= MAX_CONFIG_ATTEMPTS; attempt += 1) {
    const saved = await request.put(`${apiBase()}/me/settings/model`, {
      headers,
      data: payload,
    })
    if (saved.ok()) {
      return { ready: true }
    }
    lastStatus = saved.status()
    lastBody = await saved.text()
    if (!isTransientProbeFailure(lastStatus, lastBody)) {
      throw new Error(`保存模型配置失败：HTTP ${lastStatus} ${lastBody}`)
    }
    if (attempt < MAX_CONFIG_ATTEMPTS) {
      await new Promise((resolve) => setTimeout(resolve, attempt * 1000))
    }
  }

  return {
    ready: false,
    reason: `BLOCKED: 外部模型服务暂不可用（HTTP ${lastStatus}）：${lastBody}`,
  }
}

export async function createMeeting(
  page: Page,
  title: string,
  topic = 'Playwright 端到端验收',
): Promise<void> {
  // 新建统一走独立创建页（含本地存储位置选择；未连接本地文件夹时选择器自动隐藏）
  await page.goto('/new-meeting/create')
  await expect(page).toHaveURL(/\/new-meeting\/create/)
  await page.locator('#meeting-title').fill(title)
  await page.locator('#meeting-topic').fill(topic)
  await page.getByRole('button', { name: '创建', exact: true }).click()
  // 创建成功 → 进入会议流程页（三个功能卡片）
  await expect(page).toHaveURL(/\/new-meeting\?meetingId=mtg_[0-9a-f]+/)
}

export async function openMeeting(page: Page, title: string): Promise<string> {
  const current = new URL(page.url())
  if (current.pathname === '/new-meeting') {
    // 创建后的流程页携带 meetingId，直接进入会议详情
    const meetingId = current.searchParams.get('meetingId')
    if (meetingId) {
      await page.goto(`/meetings/${meetingId}`)
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
      return page.url()
    }
  }
  await page
    .getByRole('button', { name: new RegExp(escapeRegExp(title)) })
    .first()
    .click()
  await expect(page).toHaveURL(/\/meetings\/[^/]+$/)
  await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
  return page.url()
}

export async function openTab(page: Page, label: string): Promise<void> {
  await page.getByRole('tab', { name: label, exact: true }).click()
}

export async function uploadTextMaterial(
  page: Page,
  fileName: string,
  content: string,
): Promise<void> {
  await page.locator('#material-file').setInputFiles({
    name: fileName,
    mimeType: 'text/plain',
    buffer: Buffer.from(content, 'utf-8'),
  })
  await page.getByRole('button', { name: '上传资料', exact: true }).click()
  await expect(page.getByText('已解析', { exact: true }).first()).toBeVisible({
    timeout: 120_000,
  })
  await expect(page.getByText(fileName, { exact: true })).toBeVisible()
}

export async function addRecord(page: Page, content: string): Promise<void> {
  await page.locator('#record-content').fill(content)
  await page.getByRole('button', { name: '保存记录', exact: true }).click()
  await expect(page.getByText(content, { exact: true })).toBeVisible()
}

export async function login(page: Page, name: string): Promise<void> {
  await page.goto('/login')
  await page.locator('#login-name').fill(name)
  await page.locator('#login-password').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
}
