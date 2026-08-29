import { FormEvent, useEffect, useRef, useState } from 'react'
import { Bot, Check, Copy, MessageSquarePlus, Mic, Pencil, RotateCcw, Send, Square, Trash2 } from 'lucide-react'
import { API_URL, api, jsonRequest } from '../services/api'
import type { ChatResult, ContextEvidence, Conversation, Message, StreamEvent, ToolAction } from '../types'
import { Badge, Empty, formatDate, useLoad } from '../components/Common'

const localMessage = (role: Message['role'], content: string, status: Message['generation_status'] = 'complete'): Message => ({ id: crypto.randomUUID(), role, content, generation_status: status, created_at: new Date().toISOString() })

export function ChatPage({ setContext }: { context: ContextEvidence; setContext: (value: ContextEvidence) => void }) {
  const [conversations, refreshConversations] = useLoad<Conversation[]>('/conversations', [])
  const [conversationId, setConversationId] = useState<string>()
  const [messages, setMessages] = useState<Message[]>([])
  const [pending, setPending] = useState<ToolAction[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [lastPrompt, setLastPrompt] = useState('')
  const [error, setError] = useState('')
  const controller = useRef<AbortController | undefined>(undefined)
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, busy, pending])

  const newConversation = () => { controller.current?.abort(); setConversationId(undefined); setMessages([]); setPending([]); setContext({}); setError('') }
  const openConversation = async (id: string) => {
    const data = await api<Conversation & { messages: Message[] }>(`/conversations/${id}`)
    setConversationId(id); setMessages(data.messages); setContext(data.messages.at(-1)?.context || {})
    setPending((await api<ToolAction[]>('/tools/pending')).filter(action => action.conversation_id === id))
  }
  const rename = async (item: Conversation) => {
    const title = window.prompt('Novo título da conversa:', item.title)?.trim()
    if (title) { await api(`/conversations/${item.id}`, jsonRequest('PATCH', { title })); refreshConversations() }
  }
  const remove = async (item: Conversation) => {
    if (!window.confirm(`Excluir “${item.title}” e todo o histórico?`)) return
    await api(`/conversations/${item.id}`, { method: 'DELETE' }); if (conversationId === item.id) newConversation(); refreshConversations()
  }

  const stream = async (prompt: string) => {
    if (!prompt.trim() || busy) return
    setLastPrompt(prompt); setError(''); setBusy(true); setPending([])
    setMessages(current => [...current, localMessage('user', prompt), localMessage('assistant', '', 'complete')])
    const aborter = new AbortController(); controller.current = aborter
    try {
      const response = await fetch(`${API_URL}/chat/stream`, { ...jsonRequest('POST', { message: prompt, conversation_id: conversationId }), signal: aborter.signal })
      if (!response.ok || !response.body) throw new Error(`Não foi possível iniciar a resposta (${response.status}).`)
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
      while (true) {
        const { value, done } = await reader.read(); if (done) break
        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split('\n\n'); buffer = blocks.pop() || ''
        for (const block of blocks) {
          const line = block.split('\n').find(item => item.startsWith('data: ')); if (!line) continue
          const event = JSON.parse(line.slice(6)) as StreamEvent
          if (event.type === 'start') { setConversationId(event.conversation_id); setContext(event.context || {}) }
          if (event.type === 'token' && event.content) setMessages(current => current.map((item, index) => index === current.length - 1 ? { ...item, content: item.content + event.content } : item))
          if (event.type === 'action' && event.action) setPending(current => [...current, event.action!])
          if (event.type === 'done') { setContext(event.context || {}); setPending((event.actions || []).filter(action => action.status === 'pending_confirmation')); refreshConversations() }
          if (event.type === 'error') throw new Error(event.error?.message || 'Falha durante a geração.')
        }
      }
    } catch (err) {
      if (aborter.signal.aborted) setMessages(current => current.map((item, index) => index === current.length - 1 ? { ...item, generation_status: 'cancelled', content: item.content || 'Geração interrompida.' } : item))
      else { const message = err instanceof Error ? err.message : String(err); setError(message); setMessages(current => current.filter((_, index) => index !== current.length - 1)) }
    } finally { setBusy(false); controller.current = undefined }
  }
  const send = (event: FormEvent) => { event.preventDefault(); const prompt = input.trim(); if (!prompt) return; setInput(''); void stream(prompt) }
  const stop = () => controller.current?.abort()
  const confirm = async (actionId: string, approved: boolean) => {
    setError('')
    try {
      const result = await api<ChatResult & { status: string }>(`/tools/${actionId}/confirm`, jsonRequest('POST', { approved }))
      setPending(current => current.filter(item => item.action_id !== actionId)); setMessages(current => [...current, localMessage('assistant', result.message)]); setContext(result.context); refreshConversations()
    } catch (err) { setError(err instanceof Error ? err.message : String(err)) }
  }

  return <div className="chat-layout">
    <aside className="conversation-list"><div className="panel-head"><strong>Conversas</strong><button title="Nova conversa" className="icon-button" onClick={newConversation}><MessageSquarePlus/></button></div>{conversations.length ? conversations.map(item => <div className={`conversation-item ${conversationId === item.id ? 'active' : ''}`} key={item.id}><button onClick={() => void openConversation(item.id)}><strong>{item.title}</strong><small>{formatDate(item.updated_at)}</small></button><span><button title="Renomear" onClick={() => void rename(item)}><Pencil/></button><button title="Excluir" onClick={() => void remove(item)}><Trash2/></button></span></div>) : <Empty title="Sem conversas" body="Comece uma nova conversa."/>}</aside>
    <main className="chat-main"><header className="chat-head"><div><span className="eyebrow">MODELO LOCAL</span><strong>Qwen 3.5 4B</strong></div><Badge tone="success">Ollama</Badge></header>
      <div className="messages">{!messages.length && <div className="welcome"><div className="orb"><Bot/></div><h1>Em que posso ajudar?</h1><p>Conversa local, memória separada e ações verificáveis.</p></div>}
        {messages.map(message => <article key={message.id} className={`message ${message.role}`}><span>{message.role === 'user' ? 'VOCÊ' : message.role === 'assistant' ? 'JARVIS DISSE' : 'SISTEMA'} · {formatDate(message.created_at)}</span><p>{message.content}</p>{message.role === 'assistant' && message.content && <div className="message-actions"><button title="Copiar resposta" onClick={() => void navigator.clipboard.writeText(message.content)}><Copy/> Copiar</button>{message.generation_status === 'cancelled' && <Badge tone="warning">Interrompida</Badge>}</div>}</article>)}
        {pending.map(action => <div className="confirmation" key={action.action_id}><span className="eyebrow">JARVIS QUER EXECUTAR</span><h3>{action.tool}</h3><pre>{JSON.stringify(action.input, null, 2)}</pre><div><button onClick={() => void confirm(action.action_id, false)}>Cancelar</button><button className="primary" onClick={() => void confirm(action.action_id, true)}><Check/>Confirmar</button></div></div>)}
        {busy && <div className="typing"><i/><i/><i/></div>}{error && <div className="chat-error"><span>{error}</span><button onClick={() => void stream(lastPrompt)}><RotateCcw/>Tentar novamente</button></div>}<div ref={bottom}/>
      </div>
      <form className="composer" onSubmit={send}><button disabled type="button" className="icon-button" title="Voz será disponibilizada em uma fase futura"><Mic/></button><textarea value={input} onChange={event => setInput(event.target.value)} placeholder="Fale com o Jarvis local…" rows={1} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit() } }}/>{busy ? <button type="button" className="send stop" title="Parar geração" onClick={stop}><Square/></button> : <button className="send" disabled={!input.trim()} title="Enviar"><Send/></button>}</form>
    </main>
  </div>
}
