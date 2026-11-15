import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { createMeeting, meetingIdOf, openMeeting, openStage, register, uniqueName } from './support'

const AUDIO_FIXTURE_NAME = process.env.E2E_AUDIO_FIXTURE ?? 'sample-audio-zh.wav'
const AUDIO_FIXTURE = fileURLToPath(
  new URL(`./fixtures/${AUDIO_FIXTURE_NAME}`, import.meta.url),
)
const EXPECT_ASR = process.env.E2E_EXPECT_ASR === '1'

test.describe('音频转写', () => {
  test('上传音频并按当前 ASR 配置转写或给出明确失败原因', async ({ page }) => {
    test.setTimeout(300_000)

    const userName = uniqueName('e2e-audio')
    const meetingTitle = `E2E 音频会议 ${Date.now()}`

    await register(page, userName)
    await createMeeting(page, meetingTitle)
    const meetingUrl = await openMeeting(page, meetingTitle)
    const meetingId = meetingIdOf(meetingUrl)

    // 原会议详情页「音频」标签已删除：音频上传在「录音转写」页（选择文件即自动上传转写）
    await openStage(page, 'asr', meetingId)
    await page.locator('input[type=file]').setInputFiles(AUDIO_FIXTURE)

    const confirmBtn = page.getByRole('button', { name: '确认并保存为记录', exact: true })

    if (!EXPECT_ASR) {
      // 未配置 ASR：明确失败原因透出，且不会出现可确认的转写结果
      await expect(page.locator('.error-message').first()).toContainText(
        '未配置音频转写服务',
        { timeout: 180_000 },
      )
      await expect(confirmBtn).toHaveCount(0)
      return
    }

    // 转写文本进入「转写内容流」
    const firstSegment = page.locator('.stream__text').first()
    await expect(firstSegment).toBeVisible({ timeout: 180_000 })
    expect(((await firstSegment.textContent()) ?? '').trim().length).toBeGreaterThan(0)

    // 确认并生成会议记录：确认后工具条按钮收起、流内出现「转写」记录
    await expect(confirmBtn).toBeVisible({ timeout: 180_000 })
    await confirmBtn.click()
    await expect(confirmBtn).toBeHidden({ timeout: 30_000 })
    await expect(page.locator('.stream__tag').filter({ hasText: '转写' }).first()).toBeVisible({
      timeout: 30_000,
    })

    // 确认后的文稿也保留在会议文件列表的「会议记录」分组里
    await page.goto(meetingUrl)
    await expect(page.getByRole('heading', { name: meetingTitle, exact: true })).toBeVisible()
    await expect(page.locator('.file-group').filter({ hasText: '会议记录' })).toBeVisible()
  })
})
