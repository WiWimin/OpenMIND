import { expect, test } from '@playwright/test'

import {
  addRecord,
  createMeeting,
  meetingIdOf,
  openMeeting,
  openStage,
  prepareModelAccess,
  register,
  uniqueName,
  uploadTextMaterial,
} from './support'

test.describe('AI 核心链路（真实模型）', () => {
  test('会前准备、会议问答、纪要与行动项转任务', async ({ page, request }) => {
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
    const meetingId = meetingIdOf(meetingUrl)

    // 1) 资料：原「材料」标签改到「资料预处理」页
    await openStage(page, 'preprocess', meetingId)
    await uploadTextMaterial(
      page,
      'e2e-ai-material.txt',
      '项目背景：十月完成集成验收。风险：模型额度可能不足，需提前检查。',
    )

    // 2) 记录：原「记录」标签改到「录音转写」页的转写内容流
    await openStage(page, 'asr', meetingId)
    await addRecord(page, decisionRecord)
    await addRecord(page, openQuestion)

    // 3) 会前准备：资料预处理页快捷气泡生成，产出显示在左侧「会前准备稿」
    await openStage(page, 'preprocess', meetingId)
    await page.getByRole('button', { name: '会议摘要', exact: true }).click()
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    await expect(page.locator('.prep-summary__text')).not.toBeEmpty({ timeout: 300_000 })

    // 4) 纪要：会后智能处理页快捷卡片 → 产出区的「纪要」标签（富文本编辑确认）
    await openStage(page, 'minutes', meetingId)
    await page.locator('.task-card').filter({ hasText: '帮我生成一篇会议纪要' }).click()
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    await expect(page.locator('#minutes-content')).toBeVisible({ timeout: 300_000 })
    await expect(page.locator('#minutes-content')).not.toHaveText('', { timeout: 300_000 })
    await expect(page.getByText('草稿', { exact: true }).first()).toBeVisible()

    // 5) 行动项：提取 → 确认 → 转为我的个人任务（产出区自动切到「行动项」标签）
    await page.locator('.agent-composer__input').fill('请提取待办任务与行动项。')
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
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

    // 6) 任务管理：转出的任务出现在个人任务列表
    await page.getByRole('link', { name: '任务管理', exact: true }).click()
    await expect(page.getByRole('heading', { name: '我的任务', exact: true })).toBeVisible()
    await expect(
      page.locator('.task-item').filter({ hasText: '完成灰度发布检查清单' }),
    ).toBeVisible()

    // 7) 会议问答：回到会后智能处理页提问，回答非空
    await openStage(page, 'minutes', meetingId)
    await page.locator('.agent-composer__input').fill('本次会议确定了哪些行动项和待确认问题？')
    await page.getByRole('button', { name: '发送消息', exact: true }).click()
    await expect(page.locator('.agent-message__content').last()).not.toBeEmpty({
      timeout: 300_000,
    })

    // 8) 回到会议文件列表（原会议详情页的替代入口）
    await page.goto(meetingUrl)
    await expect(page.getByRole('heading', { name: meetingTitle, exact: true })).toBeVisible()
  })
})
