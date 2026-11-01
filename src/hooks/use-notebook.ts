import { useCallback, useEffect, useRef, useState } from 'react'
import { api, queryString, type Filters, type Meta, type Note } from '@/lib/api'

export function useNotebook(filters: Filters) {
  const [meta, setMeta] = useState<Meta>({ categories: ['随笔', '灵感', '书摘', '其他'], tags: [], total: 0, trash_total: 0, errors: [] })
  const [notes, setNotes] = useState<Note[]>([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [resultQuery, setResultQuery] = useState('')
  const [revision, setRevision] = useState(0)
  const query = queryString(filters)
  const lastQuery = useRef(query)
  lastQuery.current = query
  const refresh = useCallback(() => setRevision(x => x + 1), [])
  useEffect(() => {
    const onFocus = () => refresh()
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [refresh])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    const timer = setTimeout(async () => {
      try {
        const [metadata, result] = await Promise.all([
          api<Meta>('/api/meta', { signal: controller.signal }),
          api<{ items: Note[]; total: number }>(`/api/notes?${query}&limit=30`, { signal: controller.signal }),
        ])
        if (!controller.signal.aborted) { setMeta(metadata); setNotes(result.items); setTotal(result.total); setResultQuery(query); setError('') }
      } catch (err) { if (!controller.signal.aborted) setError(err instanceof Error ? err.message : '连接失败') }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }, 180)
    return () => { clearTimeout(timer); controller.abort() }
  }, [query, revision])
  // The API caps each page at 100; subsequent pages are loaded explicitly.
  const loadMore = async () => {
    try {
      const result = await api<{ items: Note[]; total: number }>(`/api/notes?${query}&offset=${notes.length}&limit=30`)
      if (lastQuery.current !== query) return
      setNotes(old => [...old, ...result.items.filter(x => !old.some(n => n.id === x.id))]); setTotal(result.total)
    } catch (err) { setError((err as Error).message) }
  }
  return { meta, updateMeta: setMeta, notes: resultQuery === query ? notes : [], total: resultQuery === query ? total : 0, error, loading, refresh, loadMore }
}
