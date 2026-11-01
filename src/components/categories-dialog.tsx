import { useEffect, useRef, useState } from 'react'
import { Pencil, Trash2, GripVertical } from 'lucide-react'
import { DndContext, PointerSensor, KeyboardSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, arrayMove, sortableKeyboardCoordinates, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { toast } from 'sonner'
import { api, type Meta } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Field, FieldLabel } from '@/components/ui/field'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { categoryIcon, categoryIconId, IconPicker } from './category-icons'

function CategoryRow({ name, icon, disabled, onEdit, onRemove }: { name: string; icon: string; disabled: boolean; onEdit: () => void; onRemove: () => void }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id: name, disabled })
  const Icon = categoryIcon(icon)
  return <div ref={setNodeRef} className="category-row" data-dragging={isDragging || undefined} style={{ transform: CSS.Transform.toString(transform), transition }}>
    <Button ref={setActivatorNodeRef} variant="ghost" size="icon-sm" className="category-drag-handle" disabled={disabled} {...attributes} {...listeners} aria-label={`拖动排序：${name}`} title="拖动排序；也可按空格、方向键、空格"><GripVertical /></Button>
    <Button variant="ghost" size="icon-sm" disabled={disabled} aria-label={`修改${name}图标`} onClick={onEdit}><Icon /></Button>
    <span className="category-row-name">{name}</span>
    <div className="flex gap-1"><Button variant="ghost" size="icon-sm" disabled={disabled} aria-label={`编辑分类${name}`} onClick={onEdit}><Pencil /></Button>{name !== '其他' && <Button variant="ghost" size="icon-sm" disabled={disabled} aria-label={`删除分类${name}`} onClick={onRemove}><Trash2 /></Button>}</div>
  </div>
}

export function CategoriesDialog({ open, onOpenChange, meta, onChange }: { open: boolean; onOpenChange: (open: boolean) => void; meta: Meta; onChange: (meta: Meta) => void }) {
  const [items, setItems] = useState(meta.categories)
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('file-text')
  const [original, setOriginal] = useState<string | null>(null)
  const [remove, setRemove] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const saving = useRef(false)
  const [error, setError] = useState('')
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }))
  useEffect(() => { setItems(meta.categories) }, [meta.categories])
  const reset = () => { setName(''); setOriginal(null); setRemove(null); setIcon('file-text'); setError('') }
  const recoverMetadata = async () => { try { const latest = await api<Meta>('/api/meta'); setItems(latest.categories); onChange(latest) } catch { /* Keep the form for retry. */ } }
  const change = async (deleting = false) => {
    if (saving.current) return
    saving.current = true; setBusy(true); setError('')
    try {
      const result = await api<Meta>(`/api/categories${deleting ? '/' + encodeURIComponent(remove!) : original ? '/' + encodeURIComponent(original) : ''}`, { method: deleting ? 'DELETE' : original ? 'PUT' : 'POST', ...(!deleting ? { body: JSON.stringify({ name, icon, version: meta.category_version }) } : {}) })
      onChange(result); setItems(result.categories); reset(); toast.success('分类已更新')
    } catch (err) { setError((err as Error).message); await recoverMetadata() } finally { saving.current = false; setBusy(false) }
  }
  const reorder = async ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id || saving.current) return
    const from = items.indexOf(String(active.id)), to = items.indexOf(String(over.id))
    if (from < 0 || to < 0) return
    const reordered = arrayMove(items, from, to)
    saving.current = true; setBusy(true); setError(''); setItems(reordered)
    try {
      const result = await api<Meta>('/api/category-order', { method: 'PUT', body: JSON.stringify({ categories: reordered, version: meta.category_version }) })
      setItems(result.categories); onChange(result); toast.success('分类顺序已保存')
    } catch (err) { setItems(meta.categories); setError((err as Error).message); await recoverMetadata() } finally { saving.current = false; setBusy(false) }
  }
  const edit = (category: string) => { setOriginal(category); setName(category); setIcon(categoryIconId(category, meta.category_icons)); setRemove(null); setError('') }
  return <Dialog open={open} onOpenChange={next => { if (!busy) onOpenChange(next) }}><DialogContent className="categories-dialog"><DialogHeader><DialogTitle>管理分类</DialogTitle><DialogDescription>拖动左侧手柄排序，点击图标或编辑按钮修改。顺序自动保存。</DialogDescription></DialogHeader>
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={event => void reorder(event)} accessibility={{ screenReaderInstructions: { draggable: '按空格开始排序，用上下方向键移动，再按空格保存，按 Escape 取消。' }, announcements: { onDragStart: ({ active }) => `正在移动${active.id}`, onDragOver: ({ over }) => over ? `移至${over.id}的位置` : '', onDragEnd: () => '排序操作结束', onDragCancel: () => '已取消排序' } }}>
      <SortableContext items={items} strategy={verticalListSortingStrategy}><div className="category-manager" aria-label="分类排序列表">{items.map(c => <CategoryRow key={c} name={c} icon={categoryIconId(c, meta.category_icons)} disabled={busy} onEdit={() => edit(c)} onRemove={() => { setRemove(c); setError('') }} />)}</div></SortableContext>
    </DndContext>
    {remove ? <div className="flex flex-col gap-3"><p>删除“{remove}”后，其中的笔记将归入“其他”。</p><div className="flex gap-2"><Button variant="destructive" disabled={busy} onClick={() => void change(true)}>确认删除分类</Button><Button variant="outline" disabled={busy} onClick={() => setRemove(null)}>取消</Button></div></div> : <form onSubmit={e => { e.preventDefault(); void change() }}><Field><FieldLabel htmlFor="category-name">{original ? `编辑“${original}”` : '新分类'}</FieldLabel><Input id="category-name" value={name} maxLength={80} readOnly={original === '其他'} disabled={busy} onChange={e => setName(e.target.value)} placeholder="例如：旅行" /></Field><IconPicker value={icon} onChange={setIcon} disabled={busy} /><DialogFooter className="mt-4">{original && <Button type="button" variant="ghost" disabled={busy} onClick={reset}>取消编辑</Button>}<Button disabled={busy || !name.trim()}>{original ? '保存修改' : '添加分类'}</Button></DialogFooter></form>}
    {error && <p role="alert" className="form-error">{error}</p>}
  </DialogContent></Dialog>
}
