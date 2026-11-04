import { basename } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { apiBase, authToken, createMeeting, openMeetingTab, openStage, register, uniqueName } from './support'

const AUDIO_FIXTURE_NAME = process.env.E2E_AUDIO_FIXTURE ?? 'sample-audio-zh.wav'
const AUDIO_FIXTURE = fileURLToPath(new URL(`./fixtures/${AUDIO_FIXTURE_NAME}`, import.meta.url))
const AUDIO_FILE_NAME = basename(AUDIO_FIXTURE)
const EXPECT_ASR = process.env.E2E_EXPECT_ASR === '1'

test.describe('音频转写', () => {
  test('上传音频→转写→编辑→确认生成会议记录', async ({ page }) => {
    test.setTimeout(300_000)

    await register(page, uniqueName('e2e-audio'))
    const meetingId = await createMeeting(page, `E2E 音频会议 ${Date.now()}`)
    await openStage(page, meetingId, 'asr')

    const fileInput = page.locator('input[type=file]').first()
    await fileInput.setInputFiles(AUDIO_FIXTURE)
    await expect(page.getByText(AUDIO_FILE_NAME, { exact: false }).first()).toBeVisible({
      timeout: 180_000,
    })

    if (!EXPECT_ASR) {
      await expect(page.getByText(/未配置音频转写服务|转写失败/).first()).toBeVisible({
        timeout: 180_000,
      })
      return
    }

    await expect(page.getByText('已转写', { exact: true }).first()).toBeVisible({ timeout: 180_000 })
    await expect(page.getByText(/Mock ASR 转写文本/).first()).toBeVisible()

    // 编辑转写内容（内联编辑）
    await page.getByRole('button', { name: '编辑文稿' }).first().click()
    await page.locator('#asr-transcript').fill('编辑后的转写文本：确认周五前完成检查清单。')
    await page.getByRole('button', { name: '保存修改' }).click()
    await expect(page.getByText('编辑后的转写文本', { exact: false }).first()).toBeVisible()

    // 确认并生成会议记录
    await page.getByRole('button', { name: '确认并保存为记录' }).first().click()
    await expect(page.getByText(/已保存为会议记录/).first()).toBeVisible({ timeout: 60_000 })

    // 直接读取后端，确认生成了 transcript 记录且内容持久化
    const token = await authToken(page)
    const response = await page.request.get(`${apiBase()}/meetings/${meetingId}/records`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(response.ok()).toBeTruthy()
    const payload = await response.json()
    const records = payload.data.items as Array<{ content: string; record_type: string }>
    expect(
      records.some(
        (record) =>
          record.record_type === 'transcript' && record.content.includes('编辑后的转写文本'),
      ),
    ).toBeTruthy()

    await openMeetingTab(page, meetingId, 'records')
    await expect(page.getByText('编辑后的转写文本', { exact: false }).first()).toBeVisible()
  })
})
