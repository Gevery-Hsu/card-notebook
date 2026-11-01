import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react'
import { CalendarDays, Expand, Link, Plus, Tag, LoaderCircle, FileCode2 } from 'lucide-react'
import { toast } from 'sonner'
import { api, ApiError, beijingDate, formatDraftDate, isCalendarDate, type Note, type NoteInput } from '@/lib/api'
import { useDraft } from '@/hooks/use-draft'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectGroup, SelectItem } from '@/components/ui/select'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
const RichEditor = lazy(() => import('./editor'))

export function CategorySelect({ value, values, onChange }: { value: string; values: string[]; onChange: (v: string) => void }) {
  return <Select value={value} onValueChange={onChange}><SelectTrigger aria-label="笔记分类" className="category-trigger"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{[...new Set([...values, value])].filter(Boolean).map(x => <SelectItem value={x} key={x}>{x}</SelectItem>)}</SelectGroup></SelectContent></Select>
}

export function NoteComposer({ note, categories, allTags, expanded = false, lostNote = false, onSaved, onClose, footerTools }: {
  note?: Note; categories: string[]; allTags: string[]; expanded?: boolean; lostNote?: boolean; onSaved: (n: Note) => void; onClose?: () => void; footerTools?: ReactNode
}) {
  const { draft, update, clear, status } = useDraft(note)
  const invalidDate = Boolean(draft.created_date && !isCalendarDate(draft.created_date))
  const [dateOpen, setDateOpen] = useState(invalidDate)
  const [full, setFull] = useState(expanded)
  const [sourceOpen, setSourceOpen] = useState(Boolean(draft.source || draft.source_url))
  const [tagsOpen, setTagsOpen] = useState(false)
  const [tag, setTag] = useState('')
  const [busy, setBusy] = useState(false)
  const saving = useRef(false)
  const [error, setError] = useState(lostNote ? '原笔记暂时无法读取，已找回浏览器草稿。可另存为新笔记。' : '')
  const [conflict, setConflict] = useState(lostNote)
  const [raw, setRaw] = useState(false)
  const [editorKey, setEditorKey] = useState(0)
  const readBody = useRef<(() => string) | null>(null)
  const [reloadOpen, setReloadOpen] = useState(false)
  const loadLatest = async () => {
    if (!note) return
    try {
      const latest = await api<Note>(`/api/notes/${note.id}`)
      update({ title: latest.title, body: latest.body, category: latest.category, tags: latest.tags, source: latest.source, source_url: latest.source_url, version: latest.version, created_date: latest.created_date || beijingDate(new Date(latest.created_at)) })
      setEditorKey(x => x + 1); setError(''); setConflict(false); setReloadOpen(false)
    } catch (err) { setError((err as Error).message); setReloadOpen(false) }
  }
  const addTag = (value: string) => {
    const additions = value.split(/[,，\n]/).map(x => x.trim()).filter(Boolean)
    update({ tags: [...new Set([...draft.tags, ...additions])] }); setTag('')
  }
  const save = async (asNew = false) => {
    if (saving.current) return
    if (invalidDate) { setDateOpen(true); setError('请将创建日期改为有效的年月日（年份为 0001–9999），草稿已保留。'); return }
    const currentBody = readBody.current?.() ?? draft.body
    if (!currentBody.trim()) { setError('先写下想记住的内容。'); return }
    saving.current = true; setBusy(true); setError('')
    const payload: NoteInput = { title: draft.title, body: currentBody, category: draft.category, tags: [...new Set([...draft.tags, ...tag.split(/[,，]/).map(x => x.trim()).filter(Boolean)])], source: draft.source, source_url: draft.source_url, created_date: draft.created_date || undefined }
    try {
      const result = await api<Note>(note && !asNew ? `/api/notes/${note.id}` : '/api/notes', {
        method: note && !asNew ? 'PUT' : 'POST', body: JSON.stringify(note && !asNew ? { ...payload, version: draft.version } : payload),
      })
      clear(); setTag(''); setError(''); setConflict(false); setEditorKey(x => x + 1)
      toast.success('已保存'); onSaved(result)
      if (!note) { setFull(false); setSourceOpen(false); setTagsOpen(false); setDateOpen(false) }
    } catch (err) { setError((err as Error).message); setConflict(err instanceof ApiError && [404, 409].includes(err.status)) }
    finally { saving.current = false; setBusy(false) }
  }
  const saveRef = useRef(save); saveRef.current = save
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.isComposing) { event.preventDefault(); void saveRef.current() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return <><section className={full ? 'composer composer-expanded' : 'composer'} aria-label="记录笔记" aria-busy={busy}>
    {full && <div className="composer-heading"><span className="draft-status" role="status">{status || (draft.savedAt ? '已恢复草稿' : note ? '编辑笔记' : '新笔记')}</span><div className="flex items-center gap-2">
      {note && !lostNote && <Button variant="ghost" size="sm" disabled={busy} onClick={() => setReloadOpen(true)}>读取文件版本</Button>}<Button variant="ghost" disabled={busy} onClick={() => onClose ? onClose() : setFull(false)}>收起</Button><Button disabled={busy} onClick={() => void save()}>{busy && <LoaderCircle data-icon="inline-start" className="animate-spin" />}保存</Button>
    </div></div>}
    {error && <Alert variant="destructive" className="composer-error"><AlertTitle>尚未保存</AlertTitle><AlertDescription><p>{error}</p>{conflict && <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => void save(true)}>另存为新笔记</Button>{note && <Button size="sm" variant="outline" onClick={() => { window.location.hash = `note/${note.id}` }}>查看最新版本</Button>}</div>}</AlertDescription></Alert>}
    <FieldGroup className="composer-fields" inert={busy}>
      {full && <Field><FieldLabel className="sr-only" htmlFor="note-title">标题（可选）</FieldLabel><Input id="note-title" className="title-input" placeholder="标题（可选）" value={draft.title} onChange={e => update({ title: e.target.value })} /></Field>}
      <Field><FieldLabel className="sr-only" htmlFor="quick-body">笔记正文</FieldLabel>
        {full && !raw ? <Suspense fallback={<Skeleton className="h-64 w-full" />}><RichEditor key={editorKey} value={draft.body} readBody={readBody} onChange={body => update({ body })} /></Suspense>
          : <Textarea id="quick-body" className={full ? 'raw-body' : 'quick-body'} placeholder="此刻，想记下什么？" value={draft.body} onChange={e => update({ body: e.target.value })} />}
      </Field>
    </FieldGroup>
    {(draft.tags.length > 0 || tagsOpen) && <div className="composer-tags" inert={busy}>
      {draft.tags.map(x => <Badge key={x} variant="secondary" asChild><button type="button" title={`移除标签 ${x}`} onClick={() => update({ tags: draft.tags.filter(t => t !== x) })}>{x} ×</button></Badge>)}
      {tagsOpen && <div className="tag-entry"><Input aria-label="添加标签" value={tag} placeholder="标签，按回车添加" list="known-tags" onChange={e => setTag(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); addTag(tag) } }} /><datalist id="known-tags">{allTags.map(t => <option value={t} key={t} />)}</datalist><Button size="sm" variant="ghost" aria-label="确认添加标签" onClick={() => addTag(tag)}><Plus /></Button></div>}
    </div>}
    {sourceOpen && <FieldGroup className="source-fields" inert={busy}><Field><FieldLabel htmlFor="source-text">来源</FieldLabel><Input id="source-text" placeholder="书名、作者、页码或其他来源" value={draft.source} onChange={e => update({ source: e.target.value })} /></Field><Field><FieldLabel htmlFor="source-url">来源链接（可选）</FieldLabel><Input id="source-url" placeholder="https://" value={draft.source_url} onChange={e => update({ source_url: e.target.value })} /></Field></FieldGroup>}
    <div className="composer-footer"><div className="composer-options" inert={busy}>
      <CategorySelect value={draft.category} values={categories} onChange={category => update({ category })} />
      <Button variant="ghost" size="sm" onClick={() => setTagsOpen(x => !x)}><Tag data-icon="inline-start" />标签</Button>
      <Button variant="ghost" size="sm" onClick={() => setSourceOpen(x => !x)}><Link data-icon="inline-start" />{sourceOpen ? '收起来源' : '添加来源'}</Button>
      {full && <Button variant="ghost" size="sm" onClick={() => setRaw(x => !x)}><FileCode2 data-icon="inline-start" />{raw ? '排版编辑' : 'Markdown'}</Button>}
    </div><div className="composer-submit">
      <span className="draft-status">{status || 'Ctrl + Enter'}</span>
      {!full && <Button variant="ghost" size="sm" disabled={busy} onClick={() => setFull(true)}><Expand data-icon="inline-start" />展开编辑</Button>}
      {!full && <Button disabled={busy} onClick={() => void save()}>{busy && <LoaderCircle data-icon="inline-start" className="animate-spin" />}保存</Button>}
      {full && <span className="muted-text">{draft.body.replace(/\s/g, '').length} 字</span>}
    </div></div>
    <Dialog open={reloadOpen} onOpenChange={setReloadOpen}><DialogContent><DialogHeader><DialogTitle>使用文件中的最新版本？</DialogTitle><DialogDescription>这会替换当前未保存的草稿。需要保留两份内容时，请先另存为新笔记。</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setReloadOpen(false)}>取消</Button><Button onClick={() => void loadLatest()}>读取最新版本</Button></DialogFooter></DialogContent></Dialog>
  </section>
    <div className={full ? 'creation-date-area expanded-date-area' : 'creation-date-area'}>
      <div className="creation-date-bar"><Button variant="ghost" size="sm" disabled={busy} aria-expanded={dateOpen} aria-controls="creation-date-field" onClick={() => { if (!dateOpen && !draft.created_date) update({ created_date: beijingDate() }); setDateOpen(x => !x) }}><CalendarDays data-icon="inline-start" />创建日期{draft.created_date && <span className="date-choice">{formatDraftDate(draft.created_date)}</span>}</Button>{footerTools}</div>
      {dateOpen && <Field className="creation-date-field" id="creation-date-field" data-invalid={invalidDate}><FieldLabel className="sr-only" htmlFor="note-date">创建日期</FieldLabel><Input id="note-date" aria-label="创建日期" aria-invalid={invalidDate} aria-describedby={invalidDate ? "date-error" : undefined} type="date" min="0001-01-01" max="9999-12-31" disabled={busy} value={draft.created_date || ''} onInput={e => update({ created_date: e.currentTarget.value })} onChange={e => update({ created_date: e.target.value })} />{invalidDate && <p id="date-error" role="alert" className="form-error">日期尚未完整或年份超出范围，请重新选择日期。正文和草稿仍已保留。</p>}</Field>}
    </div>
  </>
}
