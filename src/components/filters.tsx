import { X, RefreshCw } from 'lucide-react'
import type { Filters } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

export function FilterBar({ filters, update, refresh }: { filters: Filters; update: (x: Partial<Filters>) => void; refresh: () => void }) {
  return <div className="filter-area"><div className="filter-bar">
    {(filters.q || filters.tags.length > 0) && <Button variant="ghost" size="sm" onClick={() => update({ q: '', tags: [] })}><X data-icon="inline-start" />清除筛选</Button>}
    <div className="ml-auto flex items-center gap-1"><Button variant="ghost" size="icon-sm" title="重新读取本地文件" aria-label="刷新笔记" onClick={refresh}><RefreshCw /></Button><Select value={filters.order} onValueChange={x => update({ order: x as Filters['order'] })}><SelectTrigger className="filter-select" aria-label="排列顺序"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="desc">最新在前</SelectItem><SelectItem value="asc">最早在前</SelectItem></SelectGroup></SelectContent></Select></div>
  </div></div>
}
