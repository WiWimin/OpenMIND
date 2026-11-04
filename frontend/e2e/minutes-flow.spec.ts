import { expect, test } from '@playwright/test'

import {
  addRecord,
  apiBase,
  authToken,
  createMeeting,
  openMeetingTab,
  register,
  uniqueName,
} from './support'

test.describe('纪要生成闭环（本地 Mock 模型，非真实供应商）', () => {
  test('基于会议记录生成纪要草稿并确认', async ({ page }) => {
    test.setTimeout(300_000)

    await register(page, uniqueName('e2e-minutes'))
    const meetingId = await createMeeting(page, `E2E 纪要 ${Date.now()}`)

    await openMeetingTab(page, meetingId, 'records')
    await addRecord(page, '决议：周五前完成灰度发布检查清单，负责人李雷，截止日期本周五。')

    await openMeetingTab(page, meetingId, 'minutes')
    await page.getByRole('button', { name: '生成会议纪要', exact: true }).click()

    const editor = page.locator('.minutes-section__editor')
    await expect(editor).toBeVisible({ timeout: 120_000 })
    await expect(editor.getByText('灰度发布', { exact: false }).first()).toBeVisible({
      timeout: 120_000,
    })
    await expect(editor.getByText('草稿', { exact: true }).first()).toBeVisible()

    await editor.getByRole('button', { name: '确认', exact: true }).click()
    await expect(editor.getByText('已确认', { exact: true }).first()).toBeVisible({ timeout: 60_000 })

    // 刷新后点击列表项，确认状态已持久化
    await page.reload()
    const item = page.locator('.minutes-section__item').first()
    await expect(item).toBeVisible({ timeout: 30_000 })
    await item.click()
    await expect(
      page.locator('.minutes-section__editor').getByText('已确认', { exact: true }).first(),
    ).toBeVisible({ timeout: 30_000 })

    // 直接读取后端，确认“已确认”与内容来自持久化数据
    const token = await authToken(page)
    const response = await page.request.get(`${apiBase()}/meetings/${meetingId}/minutes`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(response.ok()).toBeTruthy()
    const payload = await response.json()
    const confirmed = (payload.data.items as Array<{ status: string; content: string }>).find(
      (minutes) => minutes.status === 'confirmed',
    )
    expect(confirmed).toBeTruthy()
    expect(confirmed?.content).toContain('灰度发布')
  })
})
