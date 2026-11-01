import { useEffect, useState } from 'react'

type Theme = 'light' | 'dark'
const key = 'card-notebook:theme'
export function savedTheme(): Theme {
  try { return localStorage.getItem(key) === 'dark' ? 'dark' : 'light' } catch { return 'light' }
}
export function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle('dark', theme === 'dark')
  document.documentElement.style.colorScheme = theme
}
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(savedTheme)
  useEffect(() => { applyTheme(theme) }, [theme])
  useEffect(() => {
    const sync = (event: StorageEvent) => { if (event.key === key || event.key === null) setTheme(savedTheme()) }
    window.addEventListener('storage', sync)
    return () => window.removeEventListener('storage', sync)
  }, [])
  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light'
    applyTheme(next); setTheme(next)
    try { localStorage.setItem(key, next) } catch { /* Theme still works for this session. */ }
  }
  return { theme, toggleTheme }
}
