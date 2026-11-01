import { Download, Pencil, ArrowLeft, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Markdown } from './markdown'
import { SourceLine, NoteActions } from './note-card'
import { formatDate, type Note } from '@/lib/api'
export function NoteReader({ note, onAction }: { note: Note; onAction: (action: string, note: Note) => void }) {
  return <div className="detail-page"><div className="detail-breadcrumb"><Button variant="ghost" onClick={() => { window.location.hash = '' }}><ArrowLeft data-icon="inline-start" />全部笔记</Button><span>/</span><span>阅读笔记</span></div>
    <Card className="reading-sheet"><div className="reading-actions"><Button variant="ghost" onClick={() => onAction(note.trashed ? 'restore' : 'edit', note)}>{note.trashed ? <RotateCcw data-icon="inline-start" /> : <Pencil data-icon="inline-start" />}{note.trashed ? '恢复笔记' : '编辑'}</Button><Button variant="ghost" onClick={() => onAction('export', note)}><Download data-icon="inline-start" />导出 Markdown</Button><NoteActions note={note} onAction={onAction} /></div>
      <CardHeader><CardTitle role="heading" aria-level={1} className="reader-title">{note.title || '无标题笔记'}</CardTitle><CardDescription className="reader-meta">{note.category} · {formatDate(note.created_at)}{note.trashed ? ' · 回收站' : ''}</CardDescription></CardHeader>
      <CardContent><Markdown body={note.body} /></CardContent>
      <CardFooter className="reader-footer">{(note.source || note.source_url) && <><Separator /><SourceLine note={note} /></>}<div className="flex flex-wrap gap-2">{note.tags.map(t => <Badge key={t} variant="secondary">{t}</Badge>)}</div></CardFooter>
    </Card>
  </div>
}
