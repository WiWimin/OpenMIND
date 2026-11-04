import { expect, test } from '@playwright/test'

import {
  addRecord,
  createMeeting,
  openMeetingTab,
  openStage,
  prepareModelAccess,
  register,
  uniqueName,
  uploadMaterial,
} from './support'

const TASK_TITLE = '完成灰度发布检查清单'

test.describe('AI 核心链路（本地 Mock 模型，非真实供应商）', () => {
  test('会前准备、会议问答、纪要、行动项提取与问题提取', async ({ page, request }) => {
    test.setTimeout(600_000)

    await register(page, uniqueName('e2e-ai'))
    const access = await prepareModelAccess(page, request)
    expect(access.ready, access.reason ?? '模型配置不可用').toBeTruthy()

    const meetingId = await createMeeting(page, `E2E AI 会议 ${Date.now()}`)

    await openStage(page, meetingId, 'preprocess')
    await uploadMaterial(
      page,
      'e2e-ai-material.txt',
      '项目背景：十月完成集成验收。风险：模型额度可能不足，需提前检查。',
    )

    await openMeetingTab(page, meetingId, 'records')
    await addRecord(page, '决议：本周五前完成灰度发布检查清单，负责人李雷，截止日期本周五。')
    await addRecord(page, '待确认：灰度发布是否按计划在周五开始？需要产品与研发共同确认。')

    // 会前准备：生成草稿并确认有内容
    await openMeetingTab(page, meetingId, 'preparation')
    await page.getByRole('button', { name: '生成会前准备', exact: true }).click()
    await expect(page.locator('#preparation-summary')).not.toHaveValue('', { timeout: 120_000 })

    // 纪要：生成草稿并提取行动项
    await openMeetingTab(page, meetingId, 'minutes')
    await page.getByRole('button', { name: '生成会议纪要', exact: true }).click()
    const editor = page.locator('.minutes-section__editor')
    await expect(editor).toBeVisible({ timeout: 120_000 })
    await expect(editor.getByText('灰度发布', { exact: false }).first()).toBeVisible({
      timeout: 120_000,
    })
    await expect(editor.getByText('草稿', { exact: true }).first()).toBeVisible()

    await page.getByRole('button', { name: '提取行动项', exact: true }).click()
    const firstAction = page.locator('.action-item').first()
    await expect(firstAction).toBeVisible({ timeout: 120_000 })
    await expect(firstAction).toContainText(TASK_TITLE)

    // 会议问答：检索式回答应包含来源说明
    await openStage(page, meetingId, 'minutes')
    await page.locator('#agent-chat-input').fill('请检索本次会议资料，说明项目背景与风险。')
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    await expect(page.getByText(/根据会议记录与材料/).first()).toBeVisible({ timeout: 120_000 })

    // 问题提取
    await openMeetingTab(page, meetingId, 'issues')
    await page.getByRole('button', { name: '提取未解决问题', exact: true }).click()
    const firstIssue = page.locator('.issue-item').first()
    await expect(firstIssue).toBeVisible({ timeout: 120_000 })
    await expect(firstIssue).toContainText('灰度发布')
  })
})
