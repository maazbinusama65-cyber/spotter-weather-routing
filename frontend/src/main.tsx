import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './styles/tokens.css'
import './styles/base.css'
import { LEVELS, UNKNOWN_LEVEL } from './lib/risk'
import App from './App'

// Risk colours live in one place (lib/risk.ts); expose them to CSS from there.
for (const level of LEVELS) {
  document.documentElement.style.setProperty(`--risk-${level.value}`, level.color)
}
document.documentElement.style.setProperty('--risk-unknown', UNKNOWN_LEVEL.color)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
