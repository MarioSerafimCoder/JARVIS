import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { StartupIntro } from './components/cognitive/StartupIntro'
import { CognitiveProvider } from './components/cognitive/useCognitiveGraph'
import { VoiceSessionProvider } from './components/VoiceSessionProvider'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode><CognitiveProvider><VoiceSessionProvider><StartupIntro/><App /></VoiceSessionProvider></CognitiveProvider></StrictMode>,
)
