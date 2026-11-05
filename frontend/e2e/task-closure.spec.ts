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

const TASK_TITLE = '完成灰度发布检查清单'

test.describe('任务业务闭环', () => {
  test('行动项确认→转任务→状态更新→刷新持久化', async ({ page, request }) => {
    test.setTimeout(600_000)

    await register(page, uniqueName('e2e-task'))
    const access = await prepareModelAccess(page, request)
    test.skip(!access.ready, access.reason ?? '模型配置不可用')

    const meetingTitle = `E2E 任务闭环 ${Date.now()}`
    await createMeeting(page, meetingTitle)
    const meetingId = meetingIdOf(await openMeeting(page, meetingTitle))

    // 1) 新增记录，作为行动项提取输入（阶段页「录音转写」）
    await openStage(page, 'asr', meetingId)
    await addRecord(page, '决议：周五前完成灰度发布检查清单，负责人李雷，截止日期本周五。')

    // 2) 阶段页「会后智能处理」经 Agent 提取行动项（产出区自动切到「行动项」标签）
    await openStage(page, 'minutes', meetingId)
    await page.locator('.agent-composer__input').fill('请提取待办任务与行动项。')
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    const firstItem = page.locator('.action-item').first()
    await expect(firstItem).toBeVisible({ timeout: 120_000 })
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
    const statusSelect = taskItem.locator('.task-item__status-select')
    await expect(statusSelect).toHaveValue('todo')
    await statusSelect.selectOption('in_progress')
    await expect(statusSelect).toHaveValue('in_progress')

    // 7) 刷新后验证已持久化
    await page.reload()
    const reloadedItem = page.locator('.task-item').filter({ hasText: TASK_TITLE }).first()
    await expect(reloadedItem).toBeVisible({ timeout: 30_000 })
    const reloadedStatus = reloadedItem.locator('.task-item__status-select')
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

    // 8) 行动项状态持久化：读取后端 action-items。
    //    原会议详情页已删除、产出区为会话态 UI，故以 API 断言替代原详情页 UI 回查。
    const itemsResponse = await page.request.get(`${apiBase()}/meetings/${meetingId}/action-items`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(itemsResponse.ok()).toBeTruthy()
    const itemsPayload = await itemsResponse.json()
    const converted = (
      itemsPayload.data.items as Array<{ content: string; status: string }>
    ).find((item) => item.content.includes(TASK_TITLE))
    expect(converted).toBeTruthy()
    expect(converted?.status).toBe('converted')
  })
})