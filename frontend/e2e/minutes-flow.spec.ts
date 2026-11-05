import { expect, test } from '@playwright/test'

import {
  addRecord,
  apiBase,
  authToken,
  createMeeting,
  meetingIdOf,
  openMeeting,
  openStage,
  prepareModelAccess,
  register,
  uniqueName,
} from './support'

test.describe('纪要生成闭环（本地 Mock 模型，非真实供应商）', () => {
  test('基于会议记录生成纪要草稿并确认', async ({ page, request }) => {
    test.setTimeout(300_000)

    await register(page, uniqueName('e2e-minutes'))
    const access = await prepareModelAccess(page, request)
    test.skip(!access.ready, access.reason ?? '模型配置不可用')

    const meetingTitle = `E2E 纪要 ${Date.now()}`
    await createMeeting(page, meetingTitle)
    const meetingId = meetingIdOf(await openMeeting(page, meetingTitle))

    // 1) 记录：阶段页「录音转写」新增（原会议详情页已删除）
    await openStage(page, 'asr', meetingId)
    await addRecord(page, '决议：周五前完成灰度发布检查清单，负责人李雷，截止日期本周五。')

    // 2) 纪要：阶段页「会后智能处理」经快捷卡片生成；产出区在生成后出现并选中该纪要
    await openStage(page, 'minutes', meetingId)
    await page.locator('.task-card').filter({ hasText: '帮我生成一篇会议纪要' }).click()
    await page.getByRole('button', { name: '发送消息', exact: true }).click()

    const editor = page.locator('.minutes-section__editor')
    await expect(editor).toBeVisible({ timeout: 120_000 })
    await expect(editor.getByText('灰度发布', { exact: false }).first()).toBeVisible({
      timeout: 120_000,
    })
    await expect(editor.getByText('草稿', { exact: true }).first()).toBeVisible()

    // 3) 确认纪要（draft → confirmed）
    await editor.getByRole('button', { name: '确认', exact: true }).click()
    await expect(editor.getByText('已确认', { exact: true }).first()).toBeVisible({
      timeout: 60_000,
    })

    // 4) 持久化验证：直接读取后端，确认「已确认」与内容来自持久化数据。
    //    产出区是生成后才出现的会话态 UI（刷新即隐藏），故以 API 断言为准。
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