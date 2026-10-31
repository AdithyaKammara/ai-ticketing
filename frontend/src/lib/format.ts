const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 31536000],
  ['month', 2592000],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]

export function relativeTime(iso: string): string {
  const seconds = (Date.parse(iso) - Date.now()) / 1000
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit)
  }
  return rtf.format(Math.round(seconds), 'second')
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/** SLA countdown to a due time: human label plus whether it is already overdue. */
export function countdown(iso: string | null): { label: string; overdue: boolean } | null {
  if (!iso) return null
  const ms = Date.parse(iso) - Date.now()
  const overdue = ms < 0
  const mins = Math.round(Math.abs(ms) / 60000)
  const h = Math.floor(mins / 60)
  const d = Math.floor(h / 24)
  const label = d >= 1 ? `${d}d ${h % 24}h` : h >= 1 ? `${h}h ${mins % 60}m` : `${mins}m`
  return { label: overdue ? `${label} overdue` : label, overdue }
}
