import { MoreHorizontal, Pencil, Download, Trash2, RotateCcw } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem } from '@/components/ui/dropdown-menu'
import { formatDate, plainText, type Note } from '@/lib/api'

export function NoteActions({ note, onAction }: { note: Note; onAction: (action: string, note: Note) => void }) {
  return <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label="笔记操作"><MoreHorizontal /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuGroup>
    {!note.trashed && <DropdownMenuItem onSelect={() => onAction('edit', note)}><Pencil />编辑</DropdownMenuItem>}
    <DropdownMenuItem onSelect={() => onAction('export', note)}><Download />导出 Markdown</DropdownMenuItem>
    {note.trashed ? <DropdownMenuItem onSelect={() => onAction('restore', note)}><RotateCcw />恢复笔记</DropdownMenuItem> : <DropdownMenuItem variant="destructive" onSelect={() => onAction('trash', note)}><Trash2 />移入回收站</DropdownMenuItem>}
  </DropdownMenuGroup></DropdownMenuContent></DropdownMenu>
}

export function SourceLine({ note }: { note: Note }) {
  if (!note.source && !note.source_url) return null
  return <p className="source-line">来源：{note.source_url ? <a href={note.source_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>{note.source || note.source_url}</a> : note.source}</p>
}

export function NoteCard({ note, onAction, onTag }: { note: Note; onAction: (action: string, note: Note) => void; onTag: (tag: string) => void }) {
  return <Card className="paper-card">
    <CardHeader className="note-card-header">
      <div className="note-card-info">{note.title && <CardTitle><button className="note-title-link" onClick={() => onAction('read', note)}>{note.title}</button></CardTitle>}
        <CardDescription className="note-meta"><time dateTime={note.created_at}>{formatDate(note.created_at)}</time><span className="meta-divider" /><Badge variant="secondary">{note.category}</Badge></CardDescription>
      </div><NoteActions note={note} onAction={onAction} />
    </CardHeader>
    <CardContent><button className="note-excerpt" onClick={() => onAction('read', note)} aria-label={`阅读：${note.title || plainText(note.body).slice(0, 30)}`}>{plainText(note.body).replace(/\s+/g, ' ')}</button><SourceLine note={note} /></CardContent>
    {note.tags.length > 0 && <CardFooter className="flex flex-wrap gap-2">{note.tags.map(t => <Badge variant="secondary" key={t} asChild><button onClick={() => onTag(t)}>{t}</button></Badge>)}</CardFooter>}
  </Card>
}
