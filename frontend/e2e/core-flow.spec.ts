import { expect, test } from '@playwright/test'

import {
  addRecord,
  closeModal,
  createMeeting,
  openMeetingTab,
  openStage,
  prepareModelAccess,
  register,
  saveMemory,
  uniqueName,
  uploadKnowledge,
  uploadMaterial,
} from './support'

test.describe('会议核心闭环（真实后端 + 真实数据库）', () => {
  test('注册、建会、资料、记录标记、知识库与记忆', async ({ page, request }) => {
    test.setTimeout(420_000)

    await register(page, uniqueName('e2e-core'))
    const access = await prepareModelAccess(page, request)
    expect(access.ready, access.reason ?? '模型配置不可用').toBeTruthy()

    const meetingTitle = `E2E 核心会议 ${Date.now()}`
    const meetingId = await createMeeting(page, meetingTitle)

    // 资料预处理：上传文本材料并等待解析完成
    await openStage(page, meetingId, 'preprocess')
    await uploadMaterial(
      page,
      'e2e-material.txt',
      '会议资料：本周确认上线范围与风险。\n待确认：灰度发布是否在周五进行。\n里程碑：十月完成集成验收。',
    )
    await expect(page.getByText('e2e-material.txt', { exact: true }).first()).toBeVisible()

    // 记录与重点标记
    await openMeetingTab(page, meetingId, 'records')
    const recordText = '确认周五前完成上线检查清单，并在例会同步风险。'
    await addRecord(page, recordText)
    const recordItem = page.locator('.record-item').filter({ hasText: recordText }).first()
    await recordItem.getByRole('button', { name: '重点', exact: true }).click()
    await expect(recordItem.locator('.status-badge').filter({ hasText: '重点' })).toBeVisible()

    // 知识库上传与检索
    await uploadKnowledge(
      page,
      'e2e-knowledge.txt',
      'OpenMIND 端到端资料：项目里程碑是十月完成集成验收，负责人是产品团队，风险是模型额度。',
    )
    const knowledgeDialog = page.getByRole('dialog', { name: '知识库', exact: true })
    await knowledgeDialog.getByLabel('查找资料').fill('项目里程碑')
    await expect(knowledgeDialog.locator('.hit-item').first()).toBeVisible({ timeout: 60_000 })
    await expect(knowledgeDialog.locator('.hit-item').first()).toContainText('里程碑')
    await closeModal(page)

    // 记忆中心保存
    await saveMemory(page, '产品经理', 'B2B SaaS 产品规划与跨团队项目推进', '结论先行、简洁')
    await closeModal(page)

    // 任务总览
    await page.getByRole('link', { name: '任务管理', exact: true }).click()
    await expect(page.getByRole('heading', { name: '我的任务', exact: true })).toBeVisible()
  })
})
