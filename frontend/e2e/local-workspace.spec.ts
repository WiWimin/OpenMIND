import { expect, test } from '@playwright/test'

import { createMeeting, openMeeting, register, uniqueName } from './support'

test.describe('本地会议工作区', () => {
  test('浏览器不支持目录访问时给出明确降级提示', async ({ page }) => {
    await page.addInitScript(() => {
      delete (window as Window & { showDirectoryPicker?: unknown }).showDirectoryPicker
    })

    const userName = uniqueName('e2e-local')
    const meetingTitle = `E2E 本地目录会议 ${Date.now()}`

    await register(page, userName)
    await createMeeting(page, meetingTitle)
    await openMeeting(page, meetingTitle)

    await expect(page.getByText('本地会议工作区', { exact: true })).toBeVisible()
    await expect(page.getByText('当前浏览器不支持本地文件夹访问', { exact: false })).toBeVisible()
    await expect(page.getByRole('button', { name: '选择本地文件夹', exact: true })).toHaveCount(0)
  })

  test('权限过期给出恢复入口并可一键恢复（无需重新选目录）', async ({ page }) => {
    // 合成目录句柄：权限状态由 window.__perm 控制（避免驱动系统目录选择框）
    await page.addInitScript(() => {
      const w = window as unknown as {
        __perm: PermissionState
        showDirectoryPicker?: () => Promise<unknown>
      }
      w.__perm = 'granted'
      const makeHandle = (): Record<string, unknown> => ({
        kind: 'directory',
        name: 'e2e-fixture-dir',
        values: async function* () {
          yield {
            kind: 'file',
            name: 'e2e-note.txt',
            getFile: async () => new File(['hello'], 'e2e-note.txt', { type: 'text/plain' }),
          }
        },
        getDirectoryHandle: async () => makeHandle(),
        getFileHandle: async () => ({
          createWritable: async () => ({ write: async () => {}, close: async () => {} }),
        }),
        queryPermission: async () => w.__perm,
        requestPermission: async () => w.__perm,
      })
      w.showDirectoryPicker = async () => makeHandle()
    })

    const userName = uniqueName('e2e-perm')
    const meetingTitle = `E2E 权限会议 ${Date.now()}`
    await register(page, userName)
    await createMeeting(page, meetingTitle)
    await openMeeting(page, meetingTitle)

    // 1) 正常授权 → 连接成功并列出文件
    await page.getByRole('button', { name: '选择本地文件夹', exact: true }).click()
    await expect(page.getByText('已选择：', { exact: false })).toBeVisible()
    await expect(page.getByText('e2e-note.txt')).toBeVisible()

    // 2) 权限被撤销 → 再次操作进入 needs-permission，出现恢复入口
    await page.evaluate(() => {
      ;(window as unknown as { __perm: PermissionState }).__perm = 'prompt'
    })
    await page.getByRole('button', { name: '更换文件夹', exact: true }).click()
    await expect(page.getByText('本地文件夹权限已过期或被撤销', { exact: false })).toBeVisible()

    // 3) 权限恢复（句柄仍在，无需重新选目录）
    await page.evaluate(() => {
      ;(window as unknown as { __perm: PermissionState }).__perm = 'granted'
    })
    await page.getByRole('button', { name: '恢复权限', exact: true }).click()
    await expect(page.getByText('本地文件夹权限已恢复', { exact: false })).toBeVisible()
    await expect(page.getByText('e2e-note.txt')).toBeVisible()
    await expect(page.getByText('本地文件夹权限已过期或被撤销', { exact: false })).toHaveCount(0)
  })
})
