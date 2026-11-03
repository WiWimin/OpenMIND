import { writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { expect, test } from '@playwright/test'

import { createMeeting, register, uniqueName } from './support'

test('capture-probe: 分析伪麦克风采集能量', async ({ page }) => {
  await page.goto('/register')
  const result = await page.evaluate(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const label = stream.getAudioTracks()[0]?.label ?? 'none'
    const rec = new MediaRecorder(stream)
    const parts: Blob[] = []
    rec.ondataavailable = (e) => parts.push(e.data)
    rec.start()
    await new Promise((r) => setTimeout(r, 4000))
    await new Promise<void>((r) => {
      rec.onstop = () => r()
      rec.stop()
    })
    const blob = new Blob(parts, { type: 'audio/webm' })
    const ac = new AudioContext()
    const buf = await ac.decodeAudioData(await blob.arrayBuffer())
    const ch = buf.getChannelData(0)
    let sum = 0
    for (let i = 0; i < ch.length; i++) sum += ch[i] * ch[i]
    const rms = Number(Math.sqrt(sum / ch.length).toFixed(4))

    // 页内转码为 16kHz 单声道 PCM WAV，供外部 FunASR 直接转写
    const rate = 16000
    const offline = new OfflineAudioContext(1, Math.ceil(buf.duration * rate), rate)
    const src = offline.createBufferSource()
    src.buffer = buf
    src.connect(offline.destination)
    src.start()
    const rendered = await offline.startRendering()
    const data = rendered.getChannelData(0)
    const bytes = new ArrayBuffer(44 + data.length * 2)
    const view = new DataView(bytes)
    const wstr = (off: number, s: string) => {
      for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i))
    }
    wstr(0, 'RIFF')
    view.setUint32(4, 36 + data.length * 2, true)
    wstr(8, 'WAVEfmt ')
    view.setUint32(16, 16, true)
    view.setUint16(20, 1, true)
    view.setUint16(22, 1, true)
    view.setUint32(24, rate, true)
    view.setUint32(28, rate * 2, true)
    view.setUint16(32, 2, true)
    view.setUint16(34, 16, true)
    wstr(36, 'data')
    view.setUint32(40, data.length * 2, true)
    for (let i = 0; i < data.length; i++) {
      const s = Math.max(-1, Math.min(1, data[i]))
      view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
    let binary = ''
    const u8 = new Uint8Array(bytes)
    for (let i = 0; i < u8.length; i += 0x8000) {
      binary += String.fromCharCode(...u8.subarray(i, i + 0x8000))
    }
    return {
      label,
      size: blob.size,
      duration: Number(buf.duration.toFixed(2)),
      rms,
      wavBase64: btoa(binary),
    }
  })
  const { wavBase64, ...summary } = result as {
    wavBase64?: string
    label: string
    size: number
    duration: number
    rms: number
  }
  console.log('[capture-probe] =', JSON.stringify(summary))
  if (wavBase64) {
    const out = join(tmpdir(), 'openmind-capture.wav')
    writeFileSync(out, Buffer.from(wavBase64, 'base64'))
    console.log('[capture-probe] wav saved =', out)
  }
})

/**
 * 实时录音 E2E（chromium-live 项目专用，伪麦克风 + 真实语音文件作音源）。
 * 阶段 0 探针：验证「getUserMedia → MediaRecorder 分片 → live/chunk 上传 →
 * 停止合并 → FunASR 转写」全链路适配性；通过后在本文件补充异常用例。
 */
test('实时录音：伪麦克风录制 → 分片上传 → 停止合并转写', async ({ page }) => {
  test.setTimeout(240_000)

  const title = `E2E 实时录音 ${Date.now()}`
  await register(page, uniqueName('e2e-live'))
  await createMeeting(page, title)

  const meetingId = new URL(page.url()).searchParams.get('meetingId')
  expect(meetingId, 'createMeeting 后应携带 meetingId').toBeTruthy()
  await page.goto(`/new-meeting/asr?meetingId=${meetingId}`)

  await page.getByRole('button', { name: '开始实时录音', exact: true }).click()
  const pill = page.locator('.recording-pill')
  await expect(pill).toBeVisible({ timeout: 30_000 })

  // 录制约 8 秒：期间按分片节奏上传（伪麦克风循环播放真实语音）
  await page.waitForTimeout(8000)
  await pill.click()

  // 等待「正在结束转写…」完成（录音 pill 消失）
  await expect(pill).toHaveCount(0, { timeout: 120_000 })

  // 等待终态徽标（已转写 / 转写失败）
  const terminal = page
    .locator('.status-badge')
    .filter({ hasText: /已转写|转写失败/ })
    .first()
  await expect(terminal).toBeVisible({ timeout: 120_000 })

  const badges = await page.locator('.status-badge').evaluateAll((els) =>
    els.map((el) => `${el.className}|${el.textContent?.trim()}`),
  )
  console.log('[probe] badges =', JSON.stringify(badges))
  const mainText = await page.locator('.asr-page__main').innerText()
  console.log('[probe] main =', mainText.replace(/\s+/g, ' ').slice(0, 800))
  const transcript = await page
    .locator('#audio-transcript, textarea')
    .first()
    .inputValue()
    .catch(() => '')
  console.log('[probe] transcript =', JSON.stringify(transcript.slice(0, 200)))
})
