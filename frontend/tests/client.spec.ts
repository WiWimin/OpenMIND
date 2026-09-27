import { describe, expect, it } from 'vitest'

import http from '@/api/client'

describe('api client', () => {
  it('configures a base url', () => {
    expect(http.defaults.baseURL).toBeTruthy()
  })

  it('configures a positive request timeout', () => {
    expect(http.defaults.timeout).toBeGreaterThan(0)
  })
})
