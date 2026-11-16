/**
 * 首次登录引导（记忆中心 → 本地文件夹配置）的完成标记。
 * 后端用户表暂无引导完成字段，按前端账号隔离记录在 localStorage：
 * 标记仅用于“本浏览器内该账号是否已走完首次引导”，不作为业务状态。
 */
const KEY_PREFIX = 'openmind.onboardingDone.'

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

/** 该账号是否已完成首次引导；无 userId 视为未完成。 */
export function isOnboardingDone(userId: string | null | undefined): boolean {
  if (!userId) {
    return false
  }
  return storage()?.getItem(KEY_PREFIX + userId) === '1'
}

/** 标记该账号已走完首次引导，后续登录不再弹出引导窗口。 */
export function markOnboardingDone(userId: string | null | undefined): void {
  if (!userId) {
    return
  }
  storage()?.setItem(KEY_PREFIX + userId, '1')
}
