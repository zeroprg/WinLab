import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// expose console errors for e2e checks
(function attachE2EErrorCapture(){
  if (typeof window !== 'undefined') {
    (window as any).__playwright_console_errors = []
    const orig = console.error.bind(console)
    console.error = (...args: any[]) => { (window as any).__playwright_console_errors.push(args.map(String).join(' ')); orig(...args) }
  }
})()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
