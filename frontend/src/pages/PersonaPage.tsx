import { useEffect, useState } from 'react'
import { SlidersHorizontal, Sparkles } from 'lucide-react'
import { Card, Empty, PageFrame, useLoad } from '../components/Common'
import { VoiceLab } from '../components/VoiceLab'
import { api, jsonRequest } from '../services/api'

interface PersonaInfo {
  content: string
  default_persona_version?: number
  user_persona_version?: number
  update_available?: boolean
}

export function PersonaPage() {
  const [persona, reload] = useLoad<PersonaInfo>('/persona', { content: '' })
  const [content, setContent] = useState('')
  const [preview, setPreview] = useState('')
  const [defaultPreview, setDefaultPreview] = useState('')
  const [saved, setSaved] = useState('')
  useEffect(() => setContent(persona.content || ''), [persona])

  return <PageFrame eyebrow="Identidade textual e vocal" title="Personalidade" subtitle="A mesma identidade do Jarvis em texto e voz, sempre local.">
    {persona.update_available && <Card title="Nova persona padrão disponível" icon={<Sparkles/>}>
      <p>Sua personalização foi preservada. Compare a versão {persona.user_persona_version} com a padrão {persona.default_persona_version} antes de decidir.</p>
      <div className="actions">
        <button onClick={async () => setDefaultPreview((await api<{default:string}>('/persona/compare')).default)}>Comparar</button>
        <button onClick={async () => { await api('/persona/keep', { method: 'POST' }); reload(); setSaved('Sua versão foi mantida.') }}>Manter minha versão</button>
        <button className="primary" onClick={async () => { const result = await api<{content:string}>('/persona/update-default', { method: 'POST' }); setContent(result.content); reload(); setSaved('Persona padrão atualizada.') }}>Atualizar</button>
      </div>
      {defaultPreview && <details open><summary>Nova versão padrão</summary><pre>{defaultPreview}</pre></details>}
    </Card>}
    <div className="grid two">
      <Card title={`Instruções da persona · v${persona.user_persona_version || 1}`} icon={<SlidersHorizontal/>}>
        <textarea className="editor" value={content} onChange={event => setContent(event.target.value)}/>
        <div className="actions">
          <button onClick={async () => setPreview((await api<{message:string}>('/persona/preview', jsonRequest('POST', { content }))).message)}>Pré-visualizar</button>
          <button className="primary" onClick={async () => { await api('/persona', jsonRequest('PUT', { content })); reload(); setSaved('Salvo localmente.') }}>Salvar</button>
        </div>
        {saved && <small>{saved}</small>}
      </Card>
      <Card title="Prévia isolada" icon={<Sparkles/>}>{preview ? <div className="message assistant"><span>JARVIS DISSE</span><p>{preview}</p></div> : <Empty title="Sem prévia" body="A prévia não altera o histórico."/>}</Card>
    </div>
    <VoiceLab/>
  </PageFrame>
}
