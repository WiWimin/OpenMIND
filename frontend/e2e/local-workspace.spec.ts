import { expect, test } from '@playwright/test'

import { createMeeting, register, uniqueName } from './support'

test.describe('本地会议工作区', () => {
  test('浏览器不支持目录访问时给出明确降级提示', async ({ page }) => {
    await page.addInitScript(() => {
      delete (window as Window & { showDirectoryPicker?: unknown }).showDirectoryPicker
    })

    await register(page, uniqueName('e2e-local'))
    const meetingId = await createMeeting(page, `E2E 本地目录会议 ${Date.now()}`)

    // 本地工作区面板位于会议详情“材料”标签页
    await page.goto(`/meetings/${meetingId}`)
    await expect(page.getByRole('tab', { name: '材料', exact: true })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByRole('heading', { name: '本地会议工作区', exact: true })).toBeVisible()
    await expect(page.getByText(/当前浏览器不支持本地文件夹访问/)).toBeVisible()
    await expect(page.getByRole('button', { name: '选择本地文件夹', exact: true })).toHaveCount(0)
  })
})
