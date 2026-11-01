import { expect, test } from '@playwright/test'

import {
  addRecord,
  createMeeting,
  openMeeting,
  openTab,
  prepareModelAccess,
  register,
  uniqueName,
  uploadTextMaterial,
} from './support'

test.describe('AI 核心链路（真实模型）', () => {
  test('会前准备、会议问答、纪要、行动项转任务与问题提取', async ({ page, request }) => {
    test.setTimeout(900_000)

    const userName = uniqueName('e2e-ai')
    const meetingTitle = `E2E AI 会议 ${Date.now()}`
    const decisionRecord = '决议：本周五前完成灰度发布检查清单，负责人李雷，截止日期本周五。'
    const openQuestion = '待确认：灰度发布是否按计划在周五开始？需要产品与研发共同确认。'

    await register(page, userName)
    const modelAccess = await prepareModelAccess(page, request)
    test.skip(!modelAccess.ready, modelAccess.reason ?? '模型配置不可用')

    await createMeeting(page, meetingTitle)
    const meetingUrl = await openMeeting(page, meetingTitle)

    await uploadTextMaterial(
      page,
      'e2e-ai-material.txt',
      '项目背景：十月完成集成验收。风险：模型额度可能不足，需提前检查。',
    )

    await openTab(page, '记录')
    await addRecord(page, decisionRecord)
    await addRecord(page, openQuestion)

    await openTab(page, '会前准备')
    await page.getByRole('button', { name: '生成会前准备', exact: true }).click()
    await expect(page.locator('#preparation-summary')).toBeVisible({ timeout: 300_000 })
    await expect(page.locator('#preparation-summary')).not.toHaveValue('')

    await openTab(page, '记录')
    await page.locator('#chat-question').fill('本次会议确定了哪些行动项和待确认问题？')
    await page.getByRole('button', { name: '提问', exact: true }).click()
    await expect(page.locator('.chat-turn__answer')).toBeVisible({ timeout: 300_000 })
    await expect(page.locator('.chat-turn__answer')).toHaveText(/\S/)

    await openTab(page, '纪要')
    await page.getByRole('button', { name: '生成会议纪要', exact: true }).click()
    await expect(page.locator('#minutes-content .ProseMirror')).toBeVisible({
      timeout: 300_000,
    })
    await expect(page.locator('#minutes-content .ProseMirror')).toHaveText(/\S/)
    await expect(page.getByText('草稿', { exact: true }).first()).toBeVisible()

    await page.getByRole('button', { name: '提取行动项', exact: true }).click()
    const firstAction = page.locator('.action-item').first()
    await expect(firstAction).toBeVisible({ timeout: 300_000 })
    await firstAction.getByRole('button', { name: '确认', exact: true }).click()
    await firstAction.getByRole('button', { name: '转为我的个人任务', exact: true }).click()

    const convertDialog = page.getByRole('dialog', { name: '转为我的个人任务', exact: true })
    await expect(convertDialog).toBeVisible()
    await convertDialog.locator('#convert-title').fill('完成灰度发布检查清单')
    await convertDialog.getByRole('button', { name: '确定', exact: true }).click()
    await expect(convertDialog).toBeHidden()
    await expect(firstAction.locator('.action-item__done')).toHaveText('已转任务')

    await page.getByRole('link', { name: '任务管理', exact: true }).click()
    await expect(page.getByRole('heading', { name: '我的任务', exact: true })).toBeVisible()
    await expect(
      page.locator('.task-item').filter({ hasText: '完成灰度发布检查清单' }),
    ).toBeVisible()

    await page.goto(meetingUrl)
    await expect(page.getByRole('heading', { name: meetingTitle, exact: true })).toBeVisible()
    await openTab(page, '问题')
    await page.getByRole('button', { name: '提取未解决问题', exact: true }).click()
    await expect(page.locator('.issue-item').first()).toBeVisible({ timeout: 300_000 })
  })
})
