import { expect, test, type Page } from '@playwright/test'

import { createMeeting, register, uniqueName } from './support'

/**
 * 实时录音 E2E（chromium-live 项目专用）。
 * 音源：伪麦克风 + 真实语音文件（playwright.config 注入
 * --use-file-for-fake-audio-capture，Chromium 专有 flags，仅 bundled Chromium 生效）。
 *
 * 覆盖：主链路（录制→分片→ffmpeg 转码→FunASR 转写→确认生成记录）+ 3 个异常用例。
 */

async function openAsrStage(page: Page): Promise<string> {
  const title = `E2E 实时录音 ${Date.now()}`
  await register(page, uniqueName('e2e-live'))
  await createMeeting(page, title)
  const meetingId = new URL(page.url()).searchParams.get('meetingId')
  expect(meetingId, 'createMeeting 后应携带 meetingId').toBeTruthy()
  await page.goto(`/new-meeting/asr?meetingId=${meetingId}`)
  return meetingId as string
}

function terminalBadge(page: Page, text: RegExp) {
  return page.locator('.status-badge').filter({ hasText: text }).first()
}

test('主链路：录制→分片转码转写→确认生成会议记录', async ({ page }) => {
  test.setTimeout(240_000)
  await openAsrStage(page)

  await page.getByRole('button', { name: '开始实时录音', exact: true }).click()
  const pill = page.locator('.recording-pill')
  await expect(pill).toBeVisible({ timeout: 30_000 })

  // 录制约 8 秒（分片周期 30s，末片在停止时上传）
  await page.waitForTimeout(8000)
  await pill.click()

  // 终态：已转写（ffmpeg 转码后 FunASR 出文本）
  await expect(terminalBadge(page, /已转写/)).toBeVisible({ timeout: 120_000 })

  // 转写正文来自 fixture 语音（“open mind 的语音转写测试…”）
  await expect(page.locator('.asr-page__main')).toContainText('open mind')
  await expect(page.locator('.asr-page__main')).toContainText(/转写内容流\s*1\s*条/)

  // 确认并生成会议记录
  await page.getByRole('button', { name: '确认并保存为记录', exact: true }).click()
  await expect(page.getByText('已保存为会议记录').first()).toBeVisible({ timeout: 30_000 })
})

test('异常①：麦克风权限被拒绝时给出明确提示', async ({ page }) => {
  test.setTimeout(120_000)
  await page.addInitScript(() => {
    const md = navigator.mediaDevices
    if (md) {
      md.getUserMedia = () =>
        Promise.reject(new DOMException('denied', 'NotAllowedError')) as never
    }
  })
  await openAsrStage(page)

  await page.getByRole('button', { name: '开始实时录音', exact: true }).click()

  await expect(
    page.getByText('无法访问麦克风，请检查浏览器权限设置').first(),
  ).toBeVisible({ timeout: 30_000 })
  // 会话未进入录音态
  await expect(page.locator('.recording-pill')).toHaveCount(0)
})

test('异常②：分片上传失败不中断会话，末段标记占位可重试', async ({ page }) => {
  test.setTimeout(240_000)
  await page.route('**/live/chunk', (route) => route.abort())
  await openAsrStage(page)

  await page.getByRole('button', { name: '开始实时录音', exact: true }).click()
  await expect(page.locator('.recording-pill')).toBeVisible({ timeout: 30_000 })
  await page.waitForTimeout(6000)
  await page.locator('.recording-pill').click()

  // 单片失败仅占位，不中断：占位分段 + 会话进入终态
  await expect(page.getByText('已标记占位').first()).toBeVisible({ timeout: 60_000 })
  await expect(
    terminalBadge(page, /已转写|转写失败/),
  ).toBeVisible({ timeout: 120_000 })
})

test('异常③：结束转写失败时展示失败原因且标记可重试', async ({ page }) => {
  test.setTimeout(240_000)
  await page.route('**/live/finish', (route) => {
    if (route.request().method() === 'OPTIONS') {
      return route.continue()
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: { 'access-control-allow-origin': '*' },
      body: JSON.stringify({
        status: 'success',
        data: {
          audio_id: 'aud_e2e_mock',
          meeting_id: 'mtg_e2e_mock',
          file_name: '实时录音-e2e-mock.webm',
          type: 'webm',
          status: 'failed',
          transcript: null,
          segments: [],
          error: '模拟转写失败，请稍后重试',
          created_at: '2026-11-03T00:00:00+08:00',
          updated_at: '2026-11-03T00:00:00+08:00',
        },
      }),
    })
  })
  await openAsrStage(page)

  await page.getByRole('button', { name: '开始实时录音', exact: true }).click()
  await expect(page.locator('.recording-pill')).toBeVisible({ timeout: 30_000 })
  await page.waitForTimeout(5000)
  await page.locator('.recording-pill').click()

  // 失败原因透出（ErrorMessage），状态终态为转写失败
  await expect(page.getByText('模拟转写失败，请稍后重试').first()).toBeVisible({
    timeout: 60_000,
  })
  await expect(terminalBadge(page, /转写失败/)).toBeVisible({ timeout: 60_000 })
})
