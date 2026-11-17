import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { AccountProvider } from './components/AccountProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AccountProvider><App /></AccountProvider>
  </StrictMode>,
)
