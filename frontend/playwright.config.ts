import { copyFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
const channel = process.env.E2E_CHANNEL ?? 'msedge'

// 伪麦克风输入：把真实语音文件作为 getUserMedia 音源（Chromium 专有 flags）。
// 注意：必须使用纯 ASCII 路径——含中文的仓库路径会让 Chromium 静默回退到
// 默认正弦波假设备（表现为 VAD 无语音、转写为空）。
const fakeAudioSource = fileURLToPath(new URL('./e2e/fixtures/sample-audio-zh.wav', import.meta.url))
const fakeAudioFile = join(tmpdir(), 'openmind-e2e-fake-audio.wav')
copyFileSync(fakeAudioSource, fakeAudioFile)

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  timeout: 180_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL,
    locale: 'zh-CN',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      testIgnore: /live-recording\.spec\.ts$/,
      use: {
        ...devices['Desktop Chrome'],
        channel: channel === 'bundled' ? undefined : channel,
      },
    },
    {
      // 实时录音专用：bundled Chromium + 伪麦克风（真实语音文件作音源）。
      // 限制：--use-file-for-fake-audio-capture 为 Chromium 专有，非 Chromium 内核不支持。
      name: 'chromium-live',
      testMatch: /live-recording\.spec\.ts$/,
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: [
            '--use-fake-ui-for-media-stream',
            '--use-fake-device-for-media-stream',
            `--use-file-for-fake-audio-capture=${fakeAudioFile}`,
          ],
        },
      },
    },
  ],
})
