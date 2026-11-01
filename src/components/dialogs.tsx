import { useState } from 'react'
import { toast } from 'sonner'
import { download, queryString, type Filters } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
export { CategoriesDialog } from './categories-dialog'

export function ExportDialog({ open, onOpenChange, filters, total }: { open: boolean; onOpenChange: (x: boolean) => void; filters: Filters; total: number }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (all: boolean, backup = false) => {
    setBusy(true); setError('')
    try { await download(backup ? '/api/backup.zip' : '/api/export.zip' + (all ? '' : '?' + queryString({ ...filters, trash: false })), `私人卡片本${backup ? '-完整备份' : ''}-${new Date().toISOString().slice(0, 10)}.zip`); onOpenChange(false); toast.success('导出文件已准备好') }
    catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent><DialogHeader><DialogTitle>导出笔记</DialogTitle><DialogDescription>每条笔记对应一个 Markdown 文件，保留分类、标签、来源和时间，打包为 ZIP。回收站内容不在批量导出中。</DialogDescription></DialogHeader>
    <div className="flex flex-col gap-3"><Button disabled={busy} onClick={() => void run(true)}>导出全部笔记</Button><Button variant="outline" disabled={busy || filters.trash || total === 0} onClick={() => void run(false)}>导出当前筛选结果（{filters.trash ? 0 : total} 条）</Button><Button variant="outline" disabled={busy} onClick={() => void run(true, true)}>完整备份（含回收站与分类配置）</Button></div>{error && <p role="alert" className="form-error">{error}</p>}
  </DialogContent></Dialog>
}
