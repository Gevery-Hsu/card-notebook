import React from 'react'
import ReactDOM from 'react-dom/client'
import '@fontsource-variable/noto-sans-sc'
import '@fontsource-variable/noto-serif-sc'
import './theme.css'
import './styles.css'
import App from './App'
import { AccessGate } from './components/access-gate'
import { applyTheme, savedTheme } from './hooks/use-theme'
applyTheme(savedTheme())
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><AccessGate><App /></AccessGate></React.StrictMode>)
