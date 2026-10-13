import { describe, expect, it } from 'vitest'

import type { ApiSuccess } from '@/types/api'
import { unwrapData } from '@/utils/apiEnvelope'

interface Payload {
  id: string
}

describe('unwrapData', () => {
  it('unwraps a success envelope', () => {
    const envelope: ApiSuccess<Payload> = { status: 'success', data: { id: 'a' } }
    expect(unwrapData<Payload>(envelope)).toEqual({ id: 'a' })
  })

  it('returns a plain payload unchanged', () => {
    expect(unwrapData<Payload>({ id: 'b' })).toEqual({ id: 'b' })
  })
})
