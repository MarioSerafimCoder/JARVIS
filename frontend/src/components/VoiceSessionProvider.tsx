import { createContext, type ReactNode, useContext, useState } from 'react'
import type { ToolAction } from '../types'
import { VoiceConversation } from './VoiceConversation'

type VoiceOptions = {
  conversationId?: string
  onTranscript: (text: string) => void
  onRefresh: (conversationId?: string) => void
  onAction: (action: ToolAction) => void
}
type VoiceContextValue = { active: boolean; start: (options: VoiceOptions) => void; stop: () => void }
const VoiceContext = createContext<VoiceContextValue | undefined>(undefined)

export function VoiceSessionProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<VoiceOptions>()
  return <VoiceContext.Provider value={{ active: Boolean(options), start: setOptions, stop: () => setOptions(undefined) }}>
    {children}
    {options && <VoiceConversation {...options} onClose={() => setOptions(undefined)} />}
  </VoiceContext.Provider>
}

export function useVoiceSession() {
  const value = useContext(VoiceContext)
  if (!value) throw new Error('useVoiceSession requer VoiceSessionProvider.')
  return value
}
