import { Moon, Sun, BookCopy, FileText, Plus, Tag, Trash2, Download, Settings2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { cn } from '@/lib/utils'
import type { Meta, Filters } from '@/lib/api'
import { categoryIcon, categoryIconId } from './category-icons'
export function Sidebar({ meta, filters, update, onManage, onExport, mobileOpen, onClose, theme, onToggleTheme }: {
  meta: Meta; filters: Filters; update: (change: Partial<Filters>) => void; onManage: () => void; onExport: () => void; mobileOpen: boolean; onClose: () => void; theme: 'light' | 'dark'; onToggleTheme: () => void
}) {
  const pick = (change: Partial<Filters>) => { update(change); window.location.hash = ''; onClose() }
  return <>
    {mobileOpen && <button className="sidebar-backdrop" aria-label="关闭导航" onClick={onClose} />}
    <aside className={cn('app-sidebar', mobileOpen && 'sidebar-open')} aria-label="笔记导航">
      <div className="brand"><BookCopy /><span>私人卡片本</span><Button variant="ghost" size="icon" className="mobile-close" aria-label="关闭导航" onClick={onClose}><X /></Button></div>
      <nav className="category-nav"><Button variant="ghost" className={cn('nav-item', !filters.category && !filters.trash && 'nav-selected')} onClick={() => pick({ category: '', trash: false })}><FileText data-icon="inline-start" />全部笔记</Button>
        {meta.categories.map(c => { const Icon = categoryIcon(categoryIconId(c, meta.category_icons)); return <Button variant="ghost" key={c} className={cn('nav-item', filters.category === c && !filters.trash && 'nav-selected')} onClick={() => pick({ category: c, trash: false })}><Icon data-icon="inline-start" /><span className="truncate">{c}</span></Button> })}
        <Button variant="ghost" className="nav-item nav-muted" onClick={onManage}><Plus data-icon="inline-start" />添加分类<Settings2 data-icon="inline-end" className="ml-auto" /></Button>
      </nav>
      <Separator />
      <section className="sidebar-tags"><div className="sidebar-section-title"><Tag /><span>标签</span>{filters.tags.length > 0 && <Button variant="ghost" size="sm" className="ml-auto" onClick={() => update({ tags: [] })}>清除</Button>}</div>
        <div className="tag-cloud">{meta.tags.length ? meta.tags.map(t => <Badge variant={filters.tags.includes(t) ? 'default' : 'secondary'} key={t} asChild><button aria-pressed={filters.tags.includes(t)} onClick={() => pick({ tags: filters.tags.includes(t) ? filters.tags.filter(x => x !== t) : [...filters.tags, t] })}>{t}</button></Badge>) : <span className="sidebar-hint">记录时添加你的第一个标签</span>}</div>
      </section>
      <footer className="sidebar-footer"><Separator /><Button variant="ghost" className={cn('nav-item', filters.trash && 'nav-selected')} onClick={() => pick({ trash: true, category: '', tags: [] })}><Trash2 data-icon="inline-start" />回收站{meta.trash_total > 0 && <span className="ml-auto sidebar-count">{meta.trash_total}</span>}</Button><Button variant="ghost" className="nav-item" onClick={onExport}><Download data-icon="inline-start" />导出笔记</Button><Button variant="ghost" className="nav-item" onClick={onToggleTheme}>{theme === 'light' ? <Moon data-icon="inline-start" /> : <Sun data-icon="inline-start" />}{theme === 'light' ? '切换暗色' : '切换浅色'}</Button></footer>
    </aside>
  </>
}
