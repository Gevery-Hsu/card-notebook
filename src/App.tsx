import { useCallback, useEffect, useRef, useState } from 'react'
import { Menu, Search, BookOpen, AlertCircle, ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { api, defaultFilters, download, type Filters, type Note } from '@/lib/api'
import { useTheme } from '@/hooks/use-theme'
import { useNotebook } from '@/hooks/use-notebook'
import { getDraftIds, readSavedDraft } from '@/hooks/use-draft'
import { Sidebar } from '@/components/sidebar'
import { NoteComposer } from '@/components/note-composer'
import { NoteCard } from '@/components/note-card'
import { NoteReader } from '@/components/note-reader'
import { FilterBar } from '@/components/filters'
import { CategoriesDialog, ExportDialog } from '@/components/dialogs'
import { Button } from '@/components/ui/button'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from '@/components/ui/empty'
import { InputGroup, InputGroupInput, InputGroupAddon } from '@/components/ui/input-group'
import { Skeleton } from '@/components/ui/skeleton'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Toaster } from '@/components/ui/sonner'

function currentRoute() {
  const [view, id] = window.location.hash.slice(1).split('/')
  return { view: view === 'note' || view === 'edit' ? view : 'home', id: id || '' }
}

export default function App() {
  const { theme, toggleTheme } = useTheme()
  const [filters, setFilters] = useState<Filters>(defaultFilters)
  const updateFilters = (change: Partial<Filters>) => setFilters(current => ({ ...current, ...change }))
  const notebook = useNotebook(filters)
  const [route, setRoute] = useState(currentRoute)
  const [selected, setSelected] = useState<Note | null>(null)
  const [detailError, setDetailError] = useState('')
  const [detailRefresh, setDetailRefresh] = useState(0)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [manageOpen, setManageOpen] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [trashTarget, setTrashTarget] = useState<Note | null>(null)
  const [busy, setBusy] = useState(false)
  const search = useRef<HTMLInputElement>(null)
  useEffect(() => { const change = () => { setRoute(currentRoute()); window.scrollTo(0, 0) }; window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change) }, [])
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); window.location.hash = ''; setTimeout(() => search.current?.focus(), 30) }
      if (event.key === 'Escape') setMobileOpen(false)
    }
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key)
  }, [])
  useEffect(() => {
    if (route.view !== 'note') return
    const refresh = () => setDetailRefresh(x => x + 1)
    window.addEventListener('focus', refresh); return () => window.removeEventListener('focus', refresh)
  }, [route.view])
  useEffect(() => {
    if (route.view === 'home') { setSelected(null); return }
    const controller = new AbortController()
    setSelected(null); setDetailError('')
    api<Note>(`/api/notes/${encodeURIComponent(route.id)}`, { signal: controller.signal }).then(setSelected).catch(err => { if (!controller.signal.aborted) setDetailError(err.message) })
    return () => controller.abort()
  }, [route.id, route.view, detailRefresh])
  const action = useCallback(async (kind: string, note: Note) => {
    if (kind === 'read') { window.location.hash = `note/${note.id}`; return }
    if (kind === 'edit') { window.location.hash = `edit/${note.id}`; return }
    if (kind === 'trash') { setTrashTarget(note); return }
    try {
      if (kind === 'export') await download(`/api/notes/${note.id}/export`, note.filename)
      if (kind === 'restore') { await api(`/api/notes/${note.id}/restore`, { method: 'POST', body: JSON.stringify({ version: note.version }) }); toast.success('笔记已恢复'); notebook.refresh(); setDetailRefresh(x => x + 1) }
    } catch (err) { toast.error((err as Error).message) }
  }, [notebook.refresh])
  const remove = async () => {
    if (!trashTarget) return
    setBusy(true)
    try {
      await api(`/api/notes/${trashTarget.id}/trash`, { method: 'POST', body: JSON.stringify({ version: trashTarget.version }) })
      setTrashTarget(null); notebook.refresh(); window.location.hash = ''; toast.success('已移入回收站')
    } catch (err) { toast.error((err as Error).message) } finally { setBusy(false) }
  }
  const title = filters.trash ? '回收站' : filters.category || '全部笔记'
  const draftIds = getDraftIds()
  const recovered = route.id ? readSavedDraft(route.id) : null
  const recoveryNote: Note | null = recovered ? { ...recovered, id: route.id, version: recovered.version || 'missing', created_at: new Date().toISOString(), updated_at: new Date().toISOString(), trashed: false, filename: '' } : null
  return <div className="app-layout">
    <Sidebar theme={theme} onToggleTheme={toggleTheme} meta={notebook.meta} filters={filters} update={updateFilters} onManage={() => setManageOpen(true)} onExport={() => setExportOpen(true)} mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
    <main className="main-pane"><div className="mobile-bar"><Button variant="ghost" size="icon" aria-label="打开导航" onClick={() => setMobileOpen(true)}><Menu /></Button><span>私人卡片本</span></div>
      {route.view === 'home' ? <>
        <header className="home-header"><InputGroup className="global-search"><InputGroupAddon><Search /></InputGroupAddon><InputGroupInput ref={search} aria-label="搜索笔记" placeholder="搜索笔记、标签或来源…" value={filters.q} onChange={e => updateFilters({ q: e.target.value })} /><InputGroupAddon align="inline-end"><kbd>Ctrl K</kbd></InputGroupAddon></InputGroup>
          <div className="home-title"><h1>{title}</h1><p>{notebook.total} 条记录{notebook.loading && <span className="loading-label"> · 读取中</span>}</p></div>
          {!filters.trash && <NoteComposer categories={notebook.meta.categories} allTags={notebook.meta.tags} onSaved={() => notebook.refresh()} footerTools={<FilterBar filters={filters} update={updateFilters} refresh={notebook.refresh} />} />}
          {draftIds.length > 0 && !filters.trash && <div className="draft-recovery"><span>有 {draftIds.length} 条未完成的编辑</span>{draftIds.slice(0, 3).map((id, i) => <Button variant="link" size="sm" key={id} onClick={() => { window.location.hash = `edit/${id}` }}>继续草稿 {i + 1}</Button>)}</div>}
        </header>
        {filters.trash && <FilterBar filters={filters} update={updateFilters} refresh={notebook.refresh} />}
        <section className="notes-feed" aria-label="已记录内容">
          {notebook.error && <Alert variant="destructive"><AlertCircle /><AlertTitle>读取失败</AlertTitle><AlertDescription>{notebook.error}<Button variant="outline" size="sm" onClick={notebook.refresh}>重试</Button></AlertDescription></Alert>}
          {notebook.meta.errors.length > 0 && <Alert><AlertCircle /><AlertTitle>部分文件需要检查，原文件已保留</AlertTitle><AlertDescription>{notebook.meta.errors.map(e => <p key={e.file}>{e.file}：{e.message}</p>)}</AlertDescription></Alert>}
          {!notebook.loading && !notebook.error && !notebook.notes.length && <Empty><EmptyHeader><EmptyMedia variant="icon"><BookOpen /></EmptyMedia><EmptyTitle>{filters.trash ? '回收站是空的' : notebook.meta.total ? '没有找到相符的笔记' : '从一个念头开始'}</EmptyTitle><EmptyDescription>{filters.trash ? '移入回收站的笔记会保留在这里，随时可以恢复。' : notebook.meta.total ? '换个关键词，或放宽分类、标签和日期条件。' : '一句灵感、一段摘抄，或今天想写下的事。'}</EmptyDescription></EmptyHeader></Empty>}
          {notebook.loading && !notebook.notes.length && <Skeleton className="h-40 w-full" />}
          {notebook.notes.map(note => <NoteCard note={note} key={note.id} onAction={action} onTag={tag => updateFilters({ tags: filters.tags.includes(tag) ? filters.tags : [...filters.tags, tag] })} />)}
          {notebook.notes.length < notebook.total && <Button variant="outline" className="self-center" onClick={() => void notebook.loadMore()}>加载更多</Button>}
        </section>
      </> : detailError ? <div className="detail-page"><Alert variant="destructive"><AlertTitle>暂时无法打开笔记</AlertTitle><AlertDescription>{detailError}。浏览器中的编辑草稿仍会保留。</AlertDescription></Alert><Button variant="ghost" onClick={() => { window.location.hash = '' }}>返回列表</Button>{recoveryNote && <NoteComposer key={recoveryNote.id} note={recoveryNote} lostNote expanded categories={notebook.meta.categories} allTags={notebook.meta.tags} onSaved={note => { notebook.refresh(); window.location.hash = `note/${note.id}` }} />}</div> : !selected ? <div className="detail-page"><Skeleton className="h-96 w-full" /></div> : route.view === 'edit' && !selected.trashed ? <div className="detail-page"><div className="detail-breadcrumb"><Button variant="ghost" onClick={() => { window.location.hash = '' }}><ArrowLeft data-icon="inline-start" />全部笔记</Button><span>/ 编辑笔记</span></div><NoteComposer key={selected.id} note={selected} expanded categories={notebook.meta.categories} allTags={notebook.meta.tags} onSaved={note => { notebook.refresh(); window.location.hash = `note/${note.id}` }} onClose={() => { window.location.hash = `note/${selected.id}` }} /></div> : <NoteReader note={selected} onAction={action} />}
    </main>
    <CategoriesDialog open={manageOpen} onOpenChange={setManageOpen} meta={notebook.meta} onChange={meta => { notebook.updateMeta(meta); if (filters.category && !meta.categories.includes(filters.category)) updateFilters({ category: '' }); notebook.refresh() }} />
    <ExportDialog open={exportOpen} onOpenChange={setExportOpen} filters={filters} total={notebook.total} />
    <Dialog open={Boolean(trashTarget)} onOpenChange={x => { if (!x) setTrashTarget(null) }}><DialogContent><DialogHeader><DialogTitle>移入回收站？</DialogTitle><DialogDescription>“{trashTarget?.title || '这条笔记'}”会保留在回收站中，之后可以恢复。</DialogDescription></DialogHeader><DialogFooter><Button variant="outline" onClick={() => setTrashTarget(null)}>取消</Button><Button variant="destructive" disabled={busy} onClick={() => void remove()}>移入回收站</Button></DialogFooter></DialogContent></Dialog>
    <Toaster theme={theme} position="bottom-right" closeButton />
  </div>
}
