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

const TASK_TITLE = '完成灰度发布检查清单'

test.describe('任务业务闭环', () => {
  test('行动项确认→转任务→状态更新→刷新持久化', async ({ page }) => {
    test.setTimeout(300_000)

    await register(page, uniqueName('e2e-task'))
    const meetingId = await createMeeting(page, `E2E 任务闭环 ${Date.now()}`)

    // 1) 新增记录，作为行动项提取输入
    await openMeetingTab(page, meetingId, 'records')
    await addRecord(page, '决议：周五前完成灰度发布检查清单，负责人李雷，截止日期本周五。')

    // 2) “纪要”标签页提取行动项候选
    await openMeetingTab(page, meetingId, 'minutes')
    await page.getByRole('button', { name: '提取行动项', exact: true }).click()
    const firstItem = page.locator('.action-item').first()
    await expect(firstItem).toBeVisible({ timeout: 60_000 })
    await expect(firstItem).toContainText(TASK_TITLE)

    // 3) 用户确认行动项
    await firstItem.getByRole('button', { name: '确认', exact: true }).click()
    const convertButton = firstItem.getByRole('button', { name: '转为我的个人任务', exact: true })
    await expect(convertButton).toBeVisible({ timeout: 30_000 })

    // 4) 转换为个人任务
    await convertButton.click()
    const convertDialog = page.getByRole('dialog', { name: '转为我的个人任务', exact: true })
    await expect(convertDialog).toBeVisible()
    await convertDialog.locator('#convert-title').fill(TASK_TITLE)
    await convertDialog.getByRole('button', { name: '确定', exact: true }).click()
    await expect(convertDialog).toBeHidden()
    await expect(firstItem.locator('.action-item__done')).toHaveText('已转任务')

    // 5) 任务列表出现对应任务
    await page.getByRole('link', { name: '任务管理', exact: true }).click()
    await expect(page.getByRole('heading', { name: '我的任务', exact: true })).toBeVisible()
    const taskItem = page.locator('.task-item').filter({ hasText: TASK_TITLE }).first()
    await expect(taskItem).toBeVisible({ timeout: 30_000 })

    // 6) 更新任务状态（todo → in_progress）
    const statusSelect = taskItem.locator('select[aria-label="任务状态"]')
    await expect(statusSelect).toHaveValue('todo')
    await statusSelect.selectOption('in_progress')
    await expect(statusSelect).toHaveValue('in_progress')

    // 7) 刷新后验证已持久化
    await page.reload()
    const reloadedItem = page.locator('.task-item').filter({ hasText: TASK_TITLE }).first()
    await expect(reloadedItem).toBeVisible({ timeout: 30_000 })
    const reloadedStatus = reloadedItem.locator('select[aria-label="任务状态"]')
    await expect(reloadedStatus).toHaveValue('in_progress')

    // 7.1) 直接读取后端，确认状态不是前端提示或按钮态
    const selectId = (await reloadedStatus.getAttribute('id')) ?? ''
    const taskId = selectId.replace('task-status-', '')
    expect(taskId).not.toBe('')
    const token = await authToken(page)
    const taskResponse = await page.request.get(`${apiBase()}/tasks/${taskId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(taskResponse.ok()).toBeTruthy()
    const taskPayload = await taskResponse.json()
    expect(taskPayload.data.task_id).toBe(taskId)
    expect(taskPayload.data.title).toBe(TASK_TITLE)
    expect(taskPayload.data.status).toBe('in_progress')

    // 8) 回到会议详情确认行动项仍为“已转任务”
    await page.goto(`/meetings/${meetingId}?tab=minutes`)
    const convertedItem = page.locator('.action-item').filter({ hasText: TASK_TITLE }).first()
    await expect(convertedItem).toBeVisible({ timeout: 30_000 })
    await expect(convertedItem.locator('.action-item__done')).toHaveText('已转任务')
  })
})
