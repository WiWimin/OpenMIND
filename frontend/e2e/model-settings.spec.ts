import { expect, test } from '@playwright/test'

import { apiBase, authToken, openModelConfig, register, uniqueName } from './support'

const llm = {
  apiBase: process.env.E2E_LLM_API_BASE ?? 'http://mock-ai:9000/v1',
  apiKey: process.env.E2E_LLM_API_KEY ?? 'sk-e2e-mock-1234567890',
  model: process.env.E2E_LLM_MODEL ?? 'mock-llm',
}

test.describe('模型配置（LLM BYOK，5.0 仅 LLM 可自备）', () => {
  test('设置菜单保存自定义 LLM 配置并掩码回显', async ({ page }) => {
    test.setTimeout(180_000)

    await register(page, uniqueName('e2e-byok'))
    await openModelConfig(page)

    await page.locator('#model-provider').selectOption({ label: '自定义（OpenAI 兼容）' })
    await page.locator('#model-api-key').fill(llm.apiKey)
    await page.locator('#model-custom-base').fill(llm.apiBase)
    await page.locator('#model-custom-model').fill(llm.model)
    await page.getByRole('button', { name: '保存配置' }).click()
    await expect(page.getByText('模型配置已保存', { exact: false }).first()).toBeVisible({
      timeout: 60_000,
    })

    // 保存后 API Key 输入被清空，不显示明文
    await expect(page.locator('#model-api-key')).toHaveValue('')
    await expect(page.getByText(llm.apiKey)).toHaveCount(0)

    // 关闭并重新打开，验证配置回显（提供商=custom，密钥仍不回显）
    await page.getByRole('button', { name: '关闭' }).first().click()
    await openModelConfig(page)
    await expect(page.locator('#model-provider')).toHaveValue('custom')
    await expect(page.locator('#model-custom-base')).toHaveValue(llm.apiBase)
    await expect(page.locator('#model-custom-model')).toHaveValue(llm.model)
    await expect(page.locator('#model-api-key')).toHaveValue('')
    await expect(page.getByText(llm.apiKey)).toHaveCount(0)

    // 5.0 仅 LLM 可自备：界面不应出现 Embedding BYOK 字段
    await expect(page.locator('#embedding-api-base')).toHaveCount(0)
    await expect(page.locator('#embedding-api-key')).toHaveCount(0)

    // 直接读取后端：用户配置来源、密钥掩码、Embedding 仍为服务端配置
    const token = await authToken(page)
    const response = await page.request.get(`${apiBase()}/me/settings/model`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(response.ok()).toBeTruthy()
    const data = (await response.json()).data as {
      llm_source: string
      llm_api_key_masked: string
      embedding_source: string
    }
    expect(data.llm_source).toBe('user')
    expect(data.llm_api_key_masked).not.toBe(llm.apiKey)
    expect(data.llm_api_key_masked).toMatch(/\.\.\.|\*/)
    expect(data.llm_api_key_masked).toContain('7890')
    expect(data.embedding_source).not.toBe('user')
  })
})
