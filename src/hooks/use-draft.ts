import { useCallback, useRef, useState } from 'react'
import { beijingDate, type Note, type NoteInput } from '@/lib/api'
import { toast } from 'sonner'

export type Draft = NoteInput & { version?: string; savedAt?: string }
const prefix = 'card-notebook:draft:v1:'
const blank: Draft = { title: '', body: '', category: '其他', tags: [], source: '', source_url: '' }
export function getDraftIds() {
  try { return Object.keys(localStorage).filter(k => k.startsWith(prefix) && k !== prefix + 'new').map(k => k.slice(prefix.length)) } catch { return [] }
}
export function readSavedDraft(id: string): Draft | null {
  try { const value = JSON.parse(localStorage.getItem(prefix + id) || 'null'); return value && typeof value.body === 'string' && Array.isArray(value.tags) ? { ...blank, ...value } : null } catch { return null }
}
export function useDraft(note?: Note) {
  const key = prefix + (note?.id || 'new')
  const [draft, setDraft] = useState<Draft>(() => {
    try {
      const raw = localStorage.getItem(key)
      if (raw) {
        const saved = JSON.parse(raw)
        if (typeof saved.body === 'string' && Array.isArray(saved.tags)) return { ...blank, ...(note ? { created_date: note.created_date || beijingDate(new Date(note.created_at)) } : {}), ...saved }
      }
    } catch { /* Keep the original stored value; do not remove recovery data. */ }
    return note ? { title: note.title, body: note.body, category: note.category, tags: note.tags, source: note.source, source_url: note.source_url, version: note.version, created_date: note.created_date || beijingDate(new Date(note.created_at)) } : { ...blank }
  })
  const [status, setStatus] = useState('')
  const currentDraft = useRef(draft)
  currentDraft.current = draft
  const update = useCallback((values: Partial<Draft>) => {
    const next = { ...currentDraft.current, ...values, savedAt: new Date().toISOString() }
    currentDraft.current = next
    try { localStorage.setItem(key, JSON.stringify(next)); setStatus('草稿已保留') }
    catch { setStatus('草稿暂未保留，请及时保存') }
    setDraft(next)
  }, [key])
  const clear = useCallback(() => {
    try { localStorage.removeItem(key) } catch { toast.error('无法清除浏览器草稿') }
    currentDraft.current = { ...blank }
    setDraft({ ...blank }); setStatus('')
  }, [key])
  return { draft, update, clear, status }
}
