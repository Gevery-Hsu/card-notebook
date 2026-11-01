import { useEffect, useRef, useState, type RefObject } from 'react'
import { Milkdown, MilkdownProvider, useEditor } from '@milkdown/react'
import { Editor, rootCtx, defaultValueCtx, editorViewOptionsCtx, editorViewCtx, serializerCtx } from '@milkdown/kit/core'
import { commonmark, toggleStrongCommand, toggleEmphasisCommand, wrapInHeadingCommand, wrapInBulletListCommand, wrapInBlockquoteCommand, toggleLinkCommand, turnIntoTextCommand } from '@milkdown/kit/preset/commonmark'
import { gfm } from '@milkdown/kit/preset/gfm'
import { history } from '@milkdown/kit/plugin/history'
import { clipboard } from '@milkdown/kit/plugin/clipboard'
import { callCommand, getMarkdown, $prose } from '@milkdown/kit/utils'
import { Plugin } from '@milkdown/kit/prose/state'
import { Bold, Italic, List, Quote, Link, Heading2, Pilcrow } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'

type EditorProps = { value: string; onChange: (value: string) => void; readBody: RefObject<(() => string) | null> }
function EditorInner({ value, onChange, readBody }: EditorProps) {
  const change = useRef(onChange); change.current = onChange
  const initial = useRef(value)
  const [linkOpen, setLinkOpen] = useState(false)
  const [url, setUrl] = useState('')
  const [linkError, setLinkError] = useState('')
  const { get, loading } = useEditor(root => {
    const synchronousDraft = $prose(ctx => new Plugin({ view: () => ({ update(view, previous) {
      if (!previous.doc.eq(view.state.doc)) change.current(ctx.get(serializerCtx)(view.state.doc))
    } }) }))
    return Editor.make().config(ctx => {
    ctx.set(rootCtx, root)
    ctx.set(defaultValueCtx, initial.current)
    ctx.update(editorViewOptionsCtx, prev => ({ ...prev, attributes: { role: 'textbox', 'aria-label': '笔记正文', 'aria-multiline': 'true', spellcheck: 'false' } }))
  }).use(commonmark).use(gfm).use(synchronousDraft).use(history).use(clipboard)
  }, [])
  useEffect(() => {
    if (!loading) readBody.current = () => get()?.action(getMarkdown()) ?? initial.current
    return () => { readBody.current = null }
  }, [get, loading, readBody])
  const toolbar = [
    { label: '正文', Icon: Pilcrow, run: () => get()?.action(callCommand(turnIntoTextCommand.key)) },
    { label: '二级标题', Icon: Heading2, run: () => get()?.action(callCommand(wrapInHeadingCommand.key, 2)) },
    { label: '粗体', Icon: Bold, run: () => get()?.action(callCommand(toggleStrongCommand.key)) },
    { label: '斜体', Icon: Italic, run: () => get()?.action(callCommand(toggleEmphasisCommand.key)) },
    { label: '引用', Icon: Quote, run: () => get()?.action(callCommand(wrapInBlockquoteCommand.key)) },
    { label: '无序列表', Icon: List, run: () => get()?.action(callCommand(wrapInBulletListCommand.key)) },
  ]
  return <div className="writing-editor">
    <div className="editor-toolbar" role="toolbar" aria-label="文字排版">
      {toolbar.map(({ label, Icon, run }) => <Button key={label} type="button" variant="ghost" size="icon" title={label} aria-label={label} disabled={loading} onMouseDown={e => e.preventDefault()} onClick={() => { run(); get()?.action(ctx => ctx.get(editorViewCtx).focus()) }}><Icon /></Button>)}
      <Button type="button" variant="ghost" size="icon" title="添加链接" aria-label="添加链接" disabled={loading} onMouseDown={e => e.preventDefault()} onClick={() => setLinkOpen(true)}><Link /></Button>
    </div>
    <Milkdown />
    <Dialog open={linkOpen} onOpenChange={setLinkOpen}><DialogContent><DialogHeader><DialogTitle>添加链接</DialogTitle><DialogDescription>先在正文中选中文字，再填写链接。</DialogDescription></DialogHeader>
      <Field><FieldLabel htmlFor="editor-link">网址</FieldLabel><Input id="editor-link" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://" />{linkError && <p className="form-error">{linkError}</p>}</Field>
      <DialogFooter><Button type="button" onClick={() => {
        if (!/^https?:\/\//i.test(url)) { setLinkError('请输入 http:// 或 https:// 链接'); return }
        get()?.action(callCommand(toggleLinkCommand.key, { href: url })); setLinkOpen(false); setUrl(''); setLinkError('')
      }}>插入链接</Button></DialogFooter>
    </DialogContent></Dialog>
  </div>
}
export default function RichEditor(props: EditorProps) {
  return <MilkdownProvider><EditorInner {...props} /></MilkdownProvider>
}
