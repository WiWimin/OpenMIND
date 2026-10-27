import { expect, test } from '@playwright/test'

import { createMeeting, openMeeting, register, uniqueName } from './support'

test.describe('本地会议工作区', () => {
  test('浏览器不支持目录访问时给出明确降级提示', async ({ page }) => {
    await page.addInitScript(() => {
      delete (window as Window & { showDirectoryPicker?: unknown }).showDirectoryPicker
    })

    const userName = uniqueName('e2e-local')
    const meetingTitle = `E2E 本地目录会议 ${Date.now()}`

    await register(page, userName)
    await createMeeting(page, meetingTitle)
    await openMeeting(page, meetingTitle)

    await expect(page.getByText('本地会议工作区', { exact: true })).toBeVisible()
    await expect(page.getByText('当前浏览器不支持本地文件夹访问', { exact: false })).toBeVisible()
    await expect(page.getByRole('button', { name: '选择本地文件夹', exact: true })).toHaveCount(0)
  })
})
