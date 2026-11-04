import { expect, test } from '@playwright/test'

import { createMeeting, openMeeting, prepareModelAccess, register, uniqueName } from './support'

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

  test('新建会议选择文件夹后自动导入其中已有资料', async ({ page, request }) => {
    // 合成目录树：根 → E2E 资料夹/ → e2e-auto.txt（避免驱动系统目录选择框）
    await page.addInitScript(() => {
      const w = window as unknown as {
        __perm: PermissionState
        showDirectoryPicker?: () => Promise<unknown>
      }
      w.__perm = 'granted'
      const makeFileHandle = (name: string, content: string) => ({
        kind: 'file',
        name,
        getFile: async () => new File([content], name, { type: 'text/plain' }),
        createWritable: async () => ({ write: async () => {}, close: async () => {} }),
      })
      const makeDirHandle = (name: string, node: Record<string, unknown>) => ({
        kind: 'directory',
        name,
        values: async function* () {
          for (const [key, value] of Object.entries(node)) {
            if (typeof value === 'string') {
              yield {
                kind: 'file',
                name: key,
                getFile: async () => new File([value], key, { type: 'text/plain' }),
              }
            } else {
              yield { kind: 'directory', name: key }
            }
          }
        },
        getDirectoryHandle: async (child: string) => {
          const value = node[child]
          if (!value || typeof value === 'string') {
            throw new DOMException('NotFound', 'NotFoundError')
          }
          return makeDirHandle(child, value as Record<string, unknown>)
        },
        getFileHandle: async (child: string) => makeFileHandle(child, String(node[child] ?? '')),
        queryPermission: async () => w.__perm,
        requestPermission: async () => w.__perm,
      })
      const tree: Record<string, unknown> = {
        'E2E 资料夹': { 'e2e-auto.txt': '自动导入验收：上线范围已确认，灰度在周五。' },
      }
      w.showDirectoryPicker = async () => makeDirHandle('', tree)
    })

    const userName = uniqueName('e2e-auto')
    const meetingTitle = `E2E 自动导入 ${Date.now()}`

    await register(page, userName)

    // 自动导入的上传后解析/向量索引依赖模型配置（与 core-flow 同口径）
    const modelAccess = await prepareModelAccess(page, request)
    test.skip(!modelAccess.ready, modelAccess.reason ?? '模型配置不可用')

    // 1) 创建页内授权本地文件夹 → 存储位置选择器出现
    await page.goto('/new-meeting/create')
    await page.getByRole('button', { name: '选择本地文件夹', exact: true }).click()
    await expect(page.getByText('本地存储位置', { exact: true })).toBeVisible()

    // 2) 级联选择 E2E 资料夹 作为会议存储根
    await page.locator('#folder-picker-0').selectOption('E2E 资料夹')

    // 3) 创建 → 自动导入其中已有资料（结果反馈 + 进入流程页）
    await page.locator('#meeting-title').fill(meetingTitle)
    await page.getByRole('button', { name: '创建', exact: true }).click()
    await expect(page.getByText(/已导入 1 个/)).toBeVisible({ timeout: 60_000 })
    await expect(page).toHaveURL(/\/new-meeting\?meetingId=mtg_[0-9a-f]+/)

    // 4) 会议详情材料列表出现自动导入的文件
    await openMeeting(page, meetingTitle)
    await expect(page.getByText('e2e-auto.txt')).toBeVisible()
  })
})
