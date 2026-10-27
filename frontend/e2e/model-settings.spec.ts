import { expect, test } from '@playwright/test'

import { register, uniqueName } from './support'

const llm = {
  apiBase: process.env.E2E_LLM_API_BASE ?? '',
  apiKey: process.env.E2E_LLM_API_KEY ?? '',
  model: process.env.E2E_LLM_MODEL ?? '',
}

const embedding = {
  apiBase: process.env.E2E_EMBEDDING_API_BASE ?? '',
  apiKey: process.env.E2E_EMBEDDING_API_KEY ?? '',
  model: process.env.E2E_EMBEDDING_MODEL ?? '',
}

function isComplete(settings: { apiBase: string; apiKey: string; model: string }): boolean {
  return Boolean(settings.apiBase && settings.apiKey && settings.model)
}

test.describe('模型设置（BYOK）', () => {
  test('保存自备 LLM/Embedding 配置并显示用户配置来源', async ({ page }) => {
    test.setTimeout(240_000)
    test.skip(
      !isComplete(llm) || !isComplete(embedding),
      'BLOCKED: 需要 E2E_LLM_* / E2E_EMBEDDING_* 环境变量',
    )

    await register(page, uniqueName('e2e-byok'))
    await page.getByRole('link', { name: '模型设置', exact: true }).click()
    await expect(page.getByRole('heading', { name: '模型设置', exact: true })).toBeVisible()

    await page.locator('#llm-api-base').fill(llm.apiBase)
    await page.locator('#llm-api-key').fill(llm.apiKey)
    await page.locator('#llm-model').fill(llm.model)
    await page.locator('#embedding-api-base').fill(embedding.apiBase)
    await page.locator('#embedding-api-key').fill(embedding.apiKey)
    await page.locator('#embedding-model').fill(embedding.model)

    let lastError = ''
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      await page.getByRole('button', { name: '保存配置', exact: true }).click()
      try {
        await expect(page.locator('.provider-card__source--user')).toHaveCount(2, {
          timeout: 60_000,
        })
        lastError = ''
        break
      } catch {
        lastError =
          (await page.locator('.error-message__text').last().textContent().catch(() => '')) ?? ''
        if (attempt === 3 || !/网络异常|超时|限流/.test(lastError)) {
          break
        }
        await page.waitForTimeout(2000)
      }
    }

    if (lastError && /网络异常|超时|限流/.test(lastError)) {
      test.skip(true, `BLOCKED: 外部模型服务不可用：${lastError}`)
      return
    }
    if (lastError) {
      throw new Error(`保存模型配置失败：${lastError}`)
    }
  })
})
