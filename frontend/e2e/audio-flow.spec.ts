import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { createMeeting, openMeeting, openTab, register, uniqueName } from './support'

const AUDIO_FIXTURE = fileURLToPath(new URL('./fixtures/sample-audio.wav', import.meta.url))
const EXPECT_ASR = process.env.E2E_EXPECT_ASR === '1'

test.describe('音频转写', () => {
  test('上传音频并按当前 ASR 配置转写或给出明确失败原因', async ({ page }) => {
    test.setTimeout(300_000)

    const userName = uniqueName('e2e-audio')
    const meetingTitle = `E2E 音频会议 ${Date.now()}`

    await register(page, userName)
    await createMeeting(page, meetingTitle)
    await openMeeting(page, meetingTitle)

    await openTab(page, '音频')
    await page.locator('#audio-file').setInputFiles(AUDIO_FIXTURE)
    await page.getByRole('button', { name: '上传并转写', exact: true }).click()

    const audioItem = page.locator('.audio-section__item').filter({ hasText: 'sample-audio.wav' })
    await expect(audioItem).toBeVisible({ timeout: 180_000 })
    await expect(audioItem.locator('.status-badge')).toHaveText(
      EXPECT_ASR ? /已转写/ : /转写失败/,
      { timeout: 180_000 },
    )

    if (!EXPECT_ASR) {
      await expect(page.locator('.audio-section__error')).toContainText('未配置音频转写服务')
      return
    }

    const transcript = await page.locator('#audio-transcript').inputValue()
    expect(transcript.trim().length).toBeGreaterThan(0)

    await page.getByRole('button', { name: '确认并保存为记录', exact: true }).click()
    await expect(page.getByText('已保存为会议记录', { exact: false })).toBeVisible()

    await openTab(page, '记录')
    await expect(page.getByText(transcript.slice(0, 40), { exact: false }).first()).toBeVisible()
  })
})
