import { describe, expect, it } from 'vitest'

import { formatDate, formatDateTime, fromDatetimeLocal, toDatetimeLocal } from '@/utils/datetime'

describe('formatDateTime', () => {
  it('formats a valid ISO timestamp to minute precision', () => {
    expect(formatDateTime('2026-10-01T09:00:00+08:00')).toMatch(
      /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/,
    )
  })

  it('includes seconds when requested', () => {
    expect(
      formatDateTime('2026-10-01T09:00:30+08:00', { withSeconds: true }),
    ).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/)
  })

  it('returns the placeholder for empty values', () => {
    expect(formatDateTime(null)).toBe('—')
    expect(formatDateTime(undefined)).toBe('—')
    expect(formatDateTime('')).toBe('—')
  })

  it('returns the placeholder for invalid values', () => {
    expect(formatDateTime('not-a-date')).toBe('—')
  })

  it('uses a custom placeholder', () => {
    expect(formatDateTime(null, { placeholder: '暂无' })).toBe('暂无')
  })
})

describe('formatDate', () => {
  it('keeps the calendar day of a date-only value', () => {
    expect(formatDate('2026-10-05')).toBe('2026-10-05')
  })

  it('extracts the date part of a timestamp string', () => {
    expect(formatDate('2026-10-05T14:30:00+08:00')).toBe('2026-10-05')
  })

  it('returns the placeholder for empty and invalid values', () => {
    expect(formatDate(null)).toBe('—')
    expect(formatDate('bad')).toBe('—')
  })
})

describe('datetime-local helpers', () => {
  it('round-trips an ISO timestamp through a local input value', () => {
    const iso = '2026-10-02T14:00:00+08:00'
    const local = toDatetimeLocal(iso)
    expect(local).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(fromDatetimeLocal(local)).toBe(new Date(iso).toISOString())
  })

  it('returns empty and undefined for missing values', () => {
    expect(toDatetimeLocal(null)).toBe('')
    expect(fromDatetimeLocal('')).toBeUndefined()
  })
})
