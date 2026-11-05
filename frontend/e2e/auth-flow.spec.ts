import { expect, test } from '@playwright/test'

import { E2E_PASSWORD, register, uniqueName } from './support'

test.describe('认证流程（真实后端 + 真实数据库）', () => {
  test('注册后清除令牌并重新登录', async ({ page }) => {
    test.setTimeout(180_000)

    const name = uniqueName('e2e-auth')
    await register(page, name)

    // 模拟退出登录：清除本地令牌并重新进入登录页
    await page.evaluate(() => window.localStorage.removeItem('openmind.auth.token'))
    await page.goto('/login')
    await expect(page.getByRole('heading', { name: '登录 OpenMIND', exact: true })).toBeVisible()

    await page.locator('#login-name').fill(name)
    await page.locator('#login-password').fill(E2E_PASSWORD)
    await page.getByRole('button', { name: '登录', exact: true }).click()

    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: /OpenMIND 智能会议助手/ })).toBeVisible()

    // 刷新后仍保持登录态（令牌已持久化到 localStorage）
    await page.reload()
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('heading', { name: /OpenMIND 智能会议助手/ })).toBeVisible()
  })
})
