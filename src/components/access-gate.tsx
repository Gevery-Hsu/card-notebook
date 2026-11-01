import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { LockKeyhole } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Field, FieldGroup, FieldLabel, FieldDescription, FieldError } from '@/components/ui/field'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'

type Status = { required: boolean; authenticated: boolean }

export function AccessGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [key, setKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [manage, setManage] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [generation, setGeneration] = useState(0)
  const check = () => {
    setError('')
    void api<Status>('/api/auth/status').then(value => {
      setStatus(value)
      if (value.authenticated) setMounted(true)
    }).catch(err => setError((err as Error).message))
  }
  useEffect(() => {
    const controller = new AbortController()
    void api<Status>('/api/auth/status', { signal: controller.signal }).then(value => {
      setStatus(value)
      if (value.authenticated) setMounted(true)
    }).catch(err => { if (!controller.signal.aborted) setError((err as Error).message) })
    const expired = () => { setManage(false); setMounted(false); setStatus({ required: true, authenticated: false }) }
    window.addEventListener('notebook:locked', expired)
    return () => { controller.abort(); window.removeEventListener('notebook:locked', expired) }
  }, [])
  const unlock = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    try {
      await api('/api/auth/unlock', { method: 'POST', body: JSON.stringify({ key }) })
      setKey(''); setStatus({ required: true, authenticated: true }); setMounted(true)
      setGeneration(x => x + 1)
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  const logout = async (allDevices: boolean) => {
    setBusy(true); setError('')
    try {
      await api(`/api/auth/logout${allDevices ? '?all_devices=true' : ''}`, { method: 'POST' })
      setManage(false); setMounted(false); setStatus({ required: true, authenticated: false })
    } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }
  const locked = !status?.authenticated
  return <>
    {mounted && <div key={generation} hidden={locked} inert={locked}>{children}</div>}
    {locked ? <main className="access-page">
      <section className="access-card" aria-labelledby="access-title">
        <LockKeyhole className="size-7 text-primary" />
        <h1 id="access-title">私人卡片本</h1>
        {!status ? <><p>{error || '正在确认设备…'}</p>{error && <Button variant="outline" onClick={check}>重新连接</Button>}</> : <form onSubmit={event => void unlock(event)}>
          <FieldGroup><Field data-invalid={Boolean(error)}>
            <FieldLabel htmlFor="access-key">访问密钥</FieldLabel>
            <Input id="access-key" type="password" autoComplete="current-password" autoFocus required maxLength={1024} value={key} onChange={event => setKey(event.target.value)} aria-invalid={Boolean(error)} aria-describedby="access-hint" />
            <FieldDescription id="access-hint">输入一次，在此浏览器记住一年。清除 Cookie 或撤销授权后需要重新输入。</FieldDescription>
            {error && <FieldError>{error}</FieldError>}
          </Field><Button type="submit" disabled={busy || !key}>{busy ? '正在解锁…' : '解锁卡片本'}</Button></FieldGroup>
          <p className="access-draft-hint">未提交的笔记草稿仍保留在当前浏览器。</p>
        </form>}
      </section>
    </main> : status.required ? <Button variant="outline" size="sm" className="access-manage" onClick={() => { setError(''); setManage(true) }}><LockKeyhole data-icon="inline-start" />设备授权</Button> : null}
    <Dialog open={manage && !locked} onOpenChange={setManage}><DialogContent><DialogHeader><DialogTitle>设备授权</DialogTitle><DialogDescription>退出后需重新输入密钥。尚未保存的草稿会留在当前浏览器；在共用设备上，请先处理好草稿。</DialogDescription></DialogHeader>
      {error && <p role="alert" className="form-error">{error}</p>}
      <DialogFooter><Button variant="outline" disabled={busy} onClick={() => void logout(false)}>退出当前浏览器</Button><Button variant="destructive" disabled={busy} onClick={() => void logout(true)}>撤销所有设备授权</Button></DialogFooter>
    </DialogContent></Dialog>
  </>
}
