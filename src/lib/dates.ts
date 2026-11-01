/** Native date inputs can emit partial or five-digit years during keyboard editing. */
export function isCalendarDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000-')) return false
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value
}

export const beijingDate = (value = new Date()) => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(value)

export function formatDate(value: unknown): string {
  if (typeof value !== 'string' || !value) return '日期待修改'
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return '日期待修改'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric',
  }).format(date)
}

export function formatDraftDate(value: unknown): string {
  return isCalendarDate(value) ? formatDate(`${value}T00:00:00+08:00`) : '日期待修改'
}
