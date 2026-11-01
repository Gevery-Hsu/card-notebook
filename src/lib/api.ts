export type NoteInput = { title: string; body: string; category: string; tags: string[]; source: string; source_url: string; created_date?: string }
export type Note = NoteInput & { id: string; created_at: string; updated_at: string; version: string; trashed: boolean; filename: string }
export type FileError = { file: string; message: string }
export type Meta = { categories: string[]; category_icons?: Record<string, string>; category_version?: string; tags: string[]; total: number; trash_total: number; errors: FileError[] }
export type Filters = { q: string; category: string; tags: string[]; order: 'asc' | 'desc'; trash: boolean }
export const defaultFilters: Filters = { q: '', category: '', tags: [], order: 'desc', trash: false }
export class ApiError extends Error { constructor(message: string, public status: number) { super(message) } }
export async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } })
  if (!response.ok) {
    if (response.status === 401 && !url.startsWith('/api/auth/')) window.dispatchEvent(new Event('notebook:locked'))
    const error = await response.json().catch(() => null)
    const detail = error?.detail
    throw new ApiError(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: { msg: string }) => e.msg).join('；') : '服务暂时不可用，请确认卡片本已经启动', response.status)
  }
  return response.json()
}
export function queryString(filters: Filters) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (Array.isArray(value)) value.forEach(v => params.append(key, v))
    else if (value !== '' && value !== false) params.set(key, String(value))
  })
  return params.toString()
}
export async function download(url: string, filename: string) {
  const response = await fetch(url)
  if (!response.ok) { if (response.status === 401) window.dispatchEvent(new Event('notebook:locked')); const error = await response.json(); throw new Error(error.detail || '导出失败') }
  const objectUrl = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = objectUrl; anchor.download = filename; anchor.click()
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}
export { beijingDate, formatDate, formatDraftDate, isCalendarDate } from './dates'
export function plainText(body: string) {
  return body.replace(/<[^>]*>/g, '').replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/^\s{0,3}(#{1,6}|>|[-*+]\s)\s*/gm, '').replace(/[*_`~]/g, '').trim()
}
