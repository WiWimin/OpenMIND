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
  await expect(page.getByRole('heading', { name: 'OpenMIND', exact: true })).toBeVisible()
}

async function authToken(page: Page): Promise<string> {
  const token = await page.evaluate((key) => window.localStorage.getItem(key), TOKEN_KEY)
  if (!token) {
    throw new Error('未找到登录令牌，无法调用后端接口')
  }
  return token
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
 * - 后端启用全局回退时，直接返回 true；
 * - 否则尝试使用 E2E_LLM_* / E2E_EMBEDDING_* 环境变量通过 BYOK 接口写入；
 * - 都没有时返回 false，由调用方跳过用例。
 */
export async function prepareModelAccess(page: Page, request: APIRequestContext): Promise<boolean> {
  const headers = { Authorization: `Bearer ${await authToken(page)}` }
  const response = await request.get(`${apiBase()}/me/settings/model`, { headers })
  if (!response.ok()) {
    throw new Error(`读取模型配置失败：HTTP ${response.status()} ${await response.text()}`)
  }
  const current = (await response.json()).data as ModelConfigResponse
  const needsLlm = current.llm_source === 'none'
  const needsEmbedding = current.embedding_source === 'none'
  if (!needsLlm && !needsEmbedding) {
    return true
  }

  const llm = providerSettings('E2E_LLM')
  const embedding = providerSettings('E2E_EMBEDDING')
  if (needsLlm && !isComplete(llm)) {
    return false
  }
  if (needsEmbedding && !isComplete(embedding)) {
    return false
  }

  const payload: Record<string, string> = {}
  if (needsLlm) {
    payload.llm_api_base = llm.api_base
    payload.llm_api_key = llm.api_key
    payload.llm_model = llm.model
  }
  if (needsEmbedding) {
    payload.embedding_api_base = embedding.api_base
    payload.embedding_api_key = embedding.api_key
    payload.embedding_model = embedding.model
  }

  const saved = await request.put(`${apiBase()}/me/settings/model`, {
    headers,
    data: payload,
  })
  if (!saved.ok()) {
    throw new Error(`保存模型配置失败：HTTP ${saved.status()} ${await saved.text()}`)
  }
  return true
}

export async function createMeeting(
  page: Page,
  title: string,
  topic = 'Playwright 端到端验收',
): Promise<void> {
  await page.getByRole('button', { name: '新建会议', exact: true }).first().click()
  const dialog = page.getByRole('dialog', { name: '新建会议', exact: true })
  await expect(dialog).toBeVisible()
  await dialog.locator('#meeting-title').fill(title)
  await dialog.locator('#meeting-topic').fill(topic)
  await dialog.getByRole('button', { name: '保存', exact: true }).click()
  await expect(dialog).toBeHidden()
  await expect(
    page.getByRole('button', { name: new RegExp(escapeRegExp(title)) }).first(),
  ).toBeVisible()
}

export async function openMeeting(page: Page, title: string): Promise<string> {
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
