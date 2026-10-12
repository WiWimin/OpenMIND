const EMPTY_PLACEHOLDER = '—'

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function toDate(value: string | null | undefined): Date | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export interface FormatOptions {
  placeholder?: string
  withSeconds?: boolean
}

export function formatDateTime(
  value: string | null | undefined,
  options: FormatOptions = {},
): string {
  const { placeholder = EMPTY_PLACEHOLDER, withSeconds = false } = options
  const date = toDate(value)
  if (!date) {
    return placeholder
  }
  const base =
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}`
  return withSeconds ? `${base}:${pad(date.getSeconds())}` : base
}

export function formatDate(
  value: string | null | undefined,
  options: FormatOptions = {},
): string {
  const { placeholder = EMPTY_PLACEHOLDER } = options
  if (!value) {
    return placeholder
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (match) {
    return `${match[1]}-${match[2]}-${match[3]}`
  }
  return formatDateTime(value, { placeholder }).split(' ')[0] ?? placeholder
}
