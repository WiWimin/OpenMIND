import { describe, expect, it } from 'vitest'

import { resolveEnvironmentLabel } from '@/utils/environment'

describe('resolveEnvironmentLabel', () => {
  it('maps the known environment values', () => {
    expect(resolveEnvironmentLabel('development')).toBe('开发环境')
    expect(resolveEnvironmentLabel('production')).toBe('生产环境')
  })

  it('keeps custom environment values as-is', () => {
    expect(resolveEnvironmentLabel('staging')).toBe('staging')
    expect(resolveEnvironmentLabel('qa.internal')).toBe('qa.internal')
  })

  it('falls back to the raw value for an empty environment', () => {
    expect(resolveEnvironmentLabel('')).toBe('')
  })
})
