import { expect, test } from '@playwright/test'

import {
  addRecord,
  createMeeting,
  meetingIdOf,
  openMeeting,
  openSettingsMenu,
  openStage,
  prepareModelAccess,
  register,
  uniqueName,
  uploadTextMaterial,
} from './support'

test.describe('会议核心闭环（真实后端 + 真实数据库）', () => {
  test('注册、建会、资料、记录、知识库与记忆', async ({ page, request }) => {
    test.setTimeout(300_000)

    const userName = uniqueName('e2e-core')
    const meetingTitle = `E2E 核心会议 ${Date.now()}`
    const recordText = '确认周五前完成上线检查清单，并在例会同步风险。'
    const knowledgeText =
      'OpenMIND 端到端资料：项目里程碑是十月完成集成验收，负责人是产品团队，风险是模型额度。'

    await register(page, userName)
    const modelAccess = await prepareModelAccess(page, request)
    test.skip(!modelAccess.ready, modelAccess.reason ?? '模型配置不可用')

    await createMeeting(page, meetingTitle)
    const meetingUrl = await openMeeting(page, meetingTitle)
    const meetingId = meetingIdOf(meetingUrl)

    // 资料：原会议详情页已删除，上传改在「资料预处理」页
    await openStage(page, 'preprocess', meetingId)
    await uploadTextMaterial(
      page,
      'e2e-material.txt',
      '会议资料：本周需要确认上线范围与风险。\n待确认：灰度发布是否在周五进行。\n里程碑：十月完成集成验收。',
    )

    // 记录：原「记录」标签改到「录音转写」页的转写内容流
    await openStage(page, 'asr', meetingId)
    await addRecord(page, recordText)

    // 知识库：导航重构后入口是「设置」菜单内的 menuitem（不再是独立链接）
    await openSettingsMenu(page)
    await page.getByRole('menuitem', { name: '知识库', exact: true }).click()
    await expect(page.getByRole('dialog', { name: '知识库', exact: true })).toBeVisible()
    await page.locator('#knowledge-file').setInputFiles({
      name: 'e2e-knowledge.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(knowledgeText, 'utf-8'),
    })
    // 选中文件即自动上传并索引（无独立「上传到知识库」按钮）
    await expect(page.getByText('资料已加入知识库', { exact: true })).toBeVisible({
      timeout: 120_000,
    })
    await expect(page.getByText('e2e-knowledge.txt', { exact: true })).toBeVisible()

    // 输入即检索（400ms 防抖自动触发，无独立「检索」按钮）
    await page.getByRole('searchbox', { name: '查找资料' }).fill('项目里程碑')
    await expect(page.locator('.hit-item')).toBeVisible({ timeout: 60_000 })
    await expect(page.locator('.hit-list')).toContainText('里程碑')

    // 关闭知识库弹窗 → 设置菜单 → 记忆中心（弹窗打开时菜单被遮挡，需先关闭）
    await page.getByRole('button', { name: '关闭', exact: true }).click()
    await openSettingsMenu(page)
    await page.getByRole('menuitem', { name: '记忆中心', exact: true }).click()
    await expect(page.getByRole('heading', { name: '记忆中心', exact: true })).toBeVisible()
    await page.locator('#memory-role').fill('产品经理')
    await page.locator('#memory-scenarios').fill('B2B SaaS 产品规划与跨团队项目推进')
    await page.locator('#memory-style').fill('结论先行、简洁')
    await page.getByRole('button', { name: '保存记忆', exact: true }).click()
    await expect(page.getByText('记忆已保存', { exact: true })).toBeVisible()
  })
})
