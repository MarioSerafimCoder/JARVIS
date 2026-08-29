import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { StartupIntro } from './components/cognitive/StartupIntro'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode><StartupIntro/><App /></StrictMode>,
)
