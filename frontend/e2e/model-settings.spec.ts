import { expect, test } from '@playwright/test'

import { apiBase, authToken, openSettingsMenu, register, uniqueName } from './support'

const llm = {
  apiBase: process.env.E2E_LLM_API_BASE ?? '',
  apiKey: process.env.E2E_LLM_API_KEY ?? '',
  model: process.env.E2E_LLM_MODEL ?? '',
}

function isComplete(settings: { apiBase: string; apiKey: string; model: string }): boolean {
  return Boolean(settings.apiBase && settings.apiKey && settings.model)
}

test.describe('模型设置（BYOK）', () => {
  // 口径（docs/api.md 模型配置）：仅 LLM 支持用户自备；向量模型（Embedding）
  // 由服务端 docker/.env 统一配置，后端不接受 embedding_* 字段。
  test('保存自备 LLM 配置并显示用户配置来源', async ({ page, request }) => {
    test.setTimeout(240_000)
    test.skip(!isComplete(llm), 'BLOCKED: 需要 E2E_LLM_* 环境变量')

    await register(page, uniqueName('e2e-byok'))

    // 导航重构后：设置入口是左下角 details 菜单，模型配置是其中的 menuitem
    await openSettingsMenu(page)
    await page.getByRole('menuitem', { name: '模型配置', exact: true }).click()
    await expect(page.getByRole('dialog', { name: '模型配置', exact: true })).toBeVisible()

    // 新版 UI：单一「提供商 + API Key」表单，自定义（OpenAI 兼容）时展开地址/模型名
    await page.locator('#model-provider').selectOption({ label: '自定义（OpenAI 兼容）' })
    await page.locator('#model-api-key').fill(llm.apiKey)
    await page.locator('#model-custom-base').fill(llm.apiBase)
    await page.locator('#model-custom-model').fill(llm.model)

    // 保存（服务端可能限流 probe → 最多 3 次）
    let saved = false
    let lastError = ''
    for (let attempt = 1; attempt <= 3; attempt += 1) {
      await page.getByRole('button', { name: '保存配置', exact: true }).click()
      try {
        await expect(page.getByText(/模型配置已保存/)).toBeVisible({ timeout: 20_000 })
        saved = true
        break
      } catch {
        lastError =
          (await page.locator('.model-dialog__error').textContent().catch(() => '')) ?? ''
        if (attempt < 3 && /网络异常|超时|限流|429/.test(lastError)) {
          await page.waitForTimeout(2000)
          continue
        }
        break
      }
    }
    if (!saved) {
      throw new Error(`保存模型配置失败：${lastError || '未出现成功提示'}`)
    }

    // 来源断言：新 UI 无来源徽标，以接口响应为准
    // - llm_source=user（用户自备生效）
    // - embedding_source=global（服务端统一配置；产品口径：向量模型不支持 BYOK）
    const headers = { Authorization: `Bearer ${await authToken(page)}` }
    const final = await request.get(`${apiBase()}/me/settings/model`, { headers })
    expect(final.ok()).toBeTruthy()
    const sources = (await final.json()).data as {
      llm_source: string
      embedding_source: string
    }
    expect(sources.llm_source).toBe('user')
    expect(['global', 'none']).toContain(sources.embedding_source)
  })
})
