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

test.describe('会议核心闭环（真实后端 + 真实数据库）', () => {
  test('注册、建会、资料、记录标记、知识库与记忆', async ({ page, request }) => {
    test.setTimeout(300_000)

    const userName = uniqueName('e2e-core')
    const meetingTitle = `E2E 核心会议 ${Date.now()}`
    const recordText = '确认周五前完成上线检查清单，并在例会同步风险。'
    const knowledgeText =
      'OpenMIND 端到端资料：项目里程碑是十月完成集成验收，负责人是产品团队，风险是模型额度。'

    await register(page, userName)
    const modelReady = await prepareModelAccess(page, request)
    test.skip(
      !modelReady,
      '需要后端启用 ALLOW_GLOBAL_FALLBACK，或提供 E2E_LLM_* / E2E_EMBEDDING_* 自备模型配置',
    )

    await createMeeting(page, meetingTitle)
    await openMeeting(page, meetingTitle)

    await uploadTextMaterial(
      page,
      'e2e-material.txt',
      '会议资料：本周需要确认上线范围与风险。\n待确认：灰度发布是否在周五进行。\n里程碑：十月完成集成验收。',
    )

    await openTab(page, '记录')
    await addRecord(page, recordText)

    const recordItem = page.locator('.record-item').filter({ hasText: recordText })
    await recordItem.getByRole('button', { name: '重点', exact: true }).click()
    await expect(recordItem.locator('.status-badge').filter({ hasText: '重点' })).toBeVisible()

    await page.getByRole('link', { name: '知识库', exact: true }).click()
    await expect(page.getByRole('heading', { name: '个人知识库', exact: true })).toBeVisible()
    await page.locator('#knowledge-file').setInputFiles({
      name: 'e2e-knowledge.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(knowledgeText, 'utf-8'),
    })
    await page.getByRole('button', { name: '上传到知识库', exact: true }).click()
    await expect(page.getByText('已索引', { exact: true }).first()).toBeVisible({
      timeout: 120_000,
    })
    await expect(page.getByText('e2e-knowledge.txt', { exact: true })).toBeVisible()

    await page.locator('#knowledge-query').fill('项目里程碑')
    await page.getByRole('button', { name: '检索', exact: true }).click()
    await expect(page.locator('.knowledge-hits')).toBeVisible({ timeout: 60_000 })
    await expect(page.locator('.knowledge-hits')).toContainText('里程碑')

    await page.getByRole('link', { name: '记忆中心', exact: true }).click()
    await expect(page.getByRole('heading', { name: '记忆中心', exact: true })).toBeVisible()
    await page.locator('#memory-role').fill('产品经理')
    await page.locator('#memory-scenarios').fill('B2B SaaS 产品规划与跨团队项目推进')
    await page.locator('#memory-style').fill('结论先行、简洁')
    await page.getByRole('button', { name: '保存记忆', exact: true }).click()
    await expect(page.getByText('记忆已保存', { exact: true })).toBeVisible()
  })
})
