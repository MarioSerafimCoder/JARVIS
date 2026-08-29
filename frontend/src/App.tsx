import { FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity, Archive, Bot, Brain, CalendarDays, Check, ChevronRight, CircleGauge,
  Clock3, Command, Cpu, FileText, Home, Library, ListTodo, MemoryStick, Menu,
  MessageSquare, Mic, Network, Plus, Search, Send, Settings, SlidersHorizontal,
  Sparkles, Upload, UserRoundCog, X, Zap,
} from 'lucide-react'
import { api, jsonRequest } from './services/api'

type Page = 'now' | 'chat' | 'memory' | 'library' | 'tasks' | 'calendar' | 'automations' | 'connections' | 'persona' | 'devices' | 'activity' | 'usage' | 'settings'
type AnyItem = Record<string, any>

const nav: Array<[Page, string, ReactNode]> = [
  ['now', 'Agora', <Home />], ['chat', 'Jarvis', <MessageSquare />], ['memory', 'Memória', <Brain />],
  ['library', 'Biblioteca', <Library />], ['tasks', 'Tarefas', <ListTodo />], ['calendar', 'Agenda', <CalendarDays />],
  ['automations', 'Automações', <Zap />], ['connections', 'Conexões', <Network />], ['persona', 'Personalidade', <UserRoundCog />],
  ['devices', 'Dispositivos', <Cpu />], ['activity', 'Atividade', <Activity />], ['usage', 'Uso', <CircleGauge />],
  ['settings', 'Configurações', <Settings />],
]

function useLoad<T>(path: string, initial: T): [T, () => void, boolean] {
  const [data, setData] = useState<T>(initial)
  const [loading, setLoading] = useState(true)
  const load = () => { setLoading(true); api<T>(path).then(setData).finally(() => setLoading(false)) }
  useEffect(load, [path])
  return [data, load, loading]
}

function Card({ title, icon, children, className = '' }: { title?: string, icon?: ReactNode, children: ReactNode, className?: string }) {
  return <section className={`card ${className}`}>{title && <header className="card-title">{icon}<span>{title}</span></header>}{children}</section>
}

function Empty({ title, body }: { title: string, body: string }) {
  return <div className="empty"><Archive /><strong>{title}</strong><p>{body}</p></div>
}

function Badge({ children, tone = 'neutral' }: { children: ReactNode, tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>
}

function NowPage({ go }: { go: (page: Page) => void }) {
  const [tasks] = useLoad<AnyItem[]>('/tasks', [])
  const [actions] = useLoad<AnyItem[]>('/tools/pending', [])
  const [activity] = useLoad<AnyItem[]>('/activity', [])
  const [memories] = useLoad<AnyItem[]>('/memory', [])
  const date = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'full', timeStyle: 'short' }).format(new Date())
  return <PageFrame eyebrow="Seu sistema pessoal" title="Agora" subtitle={date}>
    <div className="hero"><div><span className="eyebrow">O QUE MERECE ATENÇÃO</span><h2>{tasks.filter(t => !['done','cancelled'].includes(t.status)).length ? 'Há itens esperando por você.' : 'Tudo sob controle por enquanto.'}</h2></div><button className="primary" onClick={() => go('chat')}><Sparkles /> Conversar com Jarvis</button></div>
    <div className="grid two">
      <Card title="Tarefas prioritárias" icon={<ListTodo />}>{tasks.length ? tasks.filter(t => t.status !== 'done').slice(0,5).map(t => <Row key={t.id} title={t.title} meta={`${t.priority} · ${t.status}`} />) : <Empty title="Nada pendente" body="Tarefas reais aparecerão aqui." />}</Card>
      <Card title="Aguardando confirmação" icon={<Clock3 />}>{actions.length ? actions.map(a => <Row key={a.id} title={a.tool} meta="Ação apenas proposta" />) : <Empty title="Nenhuma ação pendente" body="O Jarvis pedirá sua autorização antes de escrever dados." />}</Card>
      <Card title="Atividade recente" icon={<Activity />}>{activity.length ? activity.slice(0,5).map(a => <Row key={a.id} title={a.tool} meta={a.status} />) : <Empty title="Sem atividade" body="Execuções verificadas serão registradas aqui." />}</Card>
      <Card title="Memórias recentes" icon={<Brain />}>{memories.length ? memories.slice(0,5).map(m => <Row key={m.id} title={m.content} meta={m.category} />) : <Empty title="Nenhuma memória registrada" body="Memória é separada do histórico de conversa." />}</Card>
    </div>
  </PageFrame>
}

function Row({ title, meta, action }: { title: string, meta?: string, action?: ReactNode }) {
  return <div className="row"><div><strong>{title}</strong>{meta && <small>{meta}</small>}</div>{action || <ChevronRight />}</div>
}

function ChatPage({ context, setContext }: { context: AnyItem, setContext: (value: AnyItem) => void }) {
  const [conversations, refreshConversations] = useLoad<AnyItem[]>('/conversations', [])
  const [conversationId, setConversationId] = useState<string | undefined>()
  const [messages, setMessages] = useState<AnyItem[]>([])
  const [pending, setPending] = useState<AnyItem[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, busy])
  const openConversation = async (id: string) => {
    const data = await api<AnyItem>(`/conversations/${id}`)
    setConversationId(id); setMessages(data.messages); setContext(data.messages.at(-1)?.context || {})
  }
  const send = async (event: FormEvent) => {
    event.preventDefault(); if (!input.trim() || busy) return
    const userMessage = input.trim(); setInput(''); setBusy(true)
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'user', content: userMessage }])
    try {
      const result = await api<AnyItem>('/chat', jsonRequest('POST', { message: userMessage, conversation_id: conversationId }))
      setConversationId(result.conversation_id); setMessages(current => [...current, { id: crypto.randomUUID(), role: 'assistant', content: result.message, context: result.context }])
      setContext(result.context); setPending(result.actions?.filter((a: AnyItem) => a.status === 'pending_confirmation') || [])
      refreshConversations()
    } catch (error) { setMessages(current => [...current, { id: crypto.randomUUID(), role: 'error', content: String(error) }]) }
    finally { setBusy(false) }
  }
  const confirm = async (actionId: string, approved: boolean) => {
    const result = await api<AnyItem>(`/tools/${actionId}/confirm`, jsonRequest('POST', { approved }))
    setPending(current => current.filter(item => item.action_id !== actionId))
    setMessages(current => [...current, { id: crypto.randomUUID(), role: 'system', content: approved && result.status === 'success' ? 'JARVIS EXECUTOU · A ação foi concluída e auditada.' : 'A ação foi cancelada.' }])
  }
  return <div className="chat-layout">
    <aside className="conversation-list"><div className="panel-head"><strong>Conversas</strong><button className="icon-button" onClick={() => { setConversationId(undefined); setMessages([]) }}><Plus /></button></div>{conversations.map(c => <button key={c.id} className={conversationId === c.id ? 'active' : ''} onClick={() => openConversation(c.id)}>{c.title}</button>)}</aside>
    <main className="chat-main"><header className="chat-head"><div><span className="eyebrow">MODELO LOCAL</span><strong>Qwen 3.5 4B</strong></div><Badge tone="success">Ollama</Badge></header>
      <div className="messages">{!messages.length && <div className="welcome"><div className="orb"><Bot /></div><h1>Em que posso ajudar?</h1><p>Conversa local, memória separada e ações verificáveis.</p></div>}
        {messages.map(message => <div key={message.id} className={`message ${message.role}`}><span>{message.role === 'user' ? 'VOCÊ' : message.role === 'assistant' ? 'JARVIS DISSE' : 'SISTEMA'}</span><p>{message.content}</p></div>)}
        {pending.map(action => <div className="confirmation" key={action.action_id}><span className="eyebrow">JARVIS QUER EXECUTAR</span><h3>{action.tool}</h3><pre>{JSON.stringify(action.input, null, 2)}</pre><div><button onClick={() => confirm(action.action_id, false)}>Cancelar</button><button className="primary" onClick={() => confirm(action.action_id, true)}><Check /> Confirmar</button></div></div>)}
        {busy && <div className="typing"><i/><i/><i/></div>}<div ref={bottom} />
      </div>
      <form className="composer" onSubmit={send}><button type="button" className="icon-button" title="Voz ainda não configurada"><Mic /></button><textarea value={input} onChange={e => setInput(e.target.value)} placeholder="Fale com o Jarvis local…" rows={1} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit() } }} /><button className="send" disabled={busy}><Send /></button></form>
    </main>
  </div>
}

function MemoryPage() {
  const [items, refresh] = useLoad<AnyItem[]>('/memory', [])
  const [content, setContent] = useState('')
  const create = async (event: FormEvent) => { event.preventDefault(); if (!content.trim()) return; await api('/memory', jsonRequest('POST', { content, category: 'other', importance: 3, source_type: 'manual' })); setContent(''); refresh() }
  return <PageFrame eyebrow="Contexto persistente" title="Memória" subtitle="Informações estruturadas; não é o histórico da conversa."><Card><form className="inline-form" onSubmit={create}><input value={content} onChange={e => setContent(e.target.value)} placeholder="Registre uma preferência, fato ou decisão…"/><button className="primary"><Plus/>Salvar memória</button></form></Card>{items.length ? <div className="grid three">{items.map(item => <Card key={item.id}><Badge>{item.category}</Badge><p className="item-copy">{item.content}</p><button className="danger-link" onClick={async () => { await api(`/memory/${item.id}`, { method: 'DELETE' }); refresh() }}>Excluir</button></Card>)}</div> : <Empty title="Nenhuma memória registrada" body="O Jarvis não transforma todas as conversas em memória automaticamente." />}</PageFrame>
}

function TasksPage() {
  const [items, refresh] = useLoad<AnyItem[]>('/tasks', [])
  const [title, setTitle] = useState('')
  const create = async (event: FormEvent) => { event.preventDefault(); if (!title.trim()) return; await api('/tasks', jsonRequest('POST', { title, description: '', status: 'inbox', priority: 'normal' })); setTitle(''); refresh() }
  const complete = async (item: AnyItem) => { await api(`/tasks/${item.id}`, jsonRequest('PUT', { ...item, status: 'done' })); refresh() }
  return <PageFrame eyebrow="Execução pessoal" title="Tarefas" subtitle="Inbox, planejamento e conclusão persistentes."><Card><form className="inline-form" onSubmit={create}><input value={title} onChange={e => setTitle(e.target.value)} placeholder="Nova tarefa…"/><button className="primary"><Plus/>Criar</button></form></Card>{items.length ? <Card>{items.map(item => <Row key={item.id} title={item.title} meta={`${item.priority} · ${item.status}`} action={item.status !== 'done' ? <button className="icon-button" onClick={() => complete(item)}><Check/></button> : <Badge tone="success">Concluída</Badge>} />)}</Card> : <Empty title="Nada pendente" body="Tarefas criadas manualmente ou confirmadas no chat aparecerão aqui." />}</PageFrame>
}

function LibraryPage() {
  const [items, refresh] = useLoad<AnyItem[]>('/library', [])
  const [busy, setBusy] = useState(false)
  const upload = async (file?: File) => { if (!file) return; setBusy(true); const body = new FormData(); body.append('file', file); try { await api('/library', { method: 'POST', body }); refresh() } finally { setBusy(false) } }
  return <PageFrame eyebrow="Knowledge vault local" title="Biblioteca" subtitle="PDF, DOCX, TXT e MD pesquisáveis por FTS5."><label className="dropzone"><Upload/><strong>{busy ? 'Processando…' : 'Adicionar arquivos'}</strong><span>Os arquivos permanecem neste computador. OCR ainda não está disponível.</span><input type="file" accept=".pdf,.docx,.txt,.md" onChange={e => upload(e.target.files?.[0])}/></label>{items.length ? <Card>{items.map(item => <Row key={item.id} title={item.original_name} meta={`${item.type.toUpperCase()} · ${item.status} · ${item.chunk_count} trechos`} />)}</Card> : <Empty title="Nenhum documento ainda" body="Adicione arquivos que você quer que o Jarvis consiga consultar." />}</PageFrame>
}

function PersonaPage() {
  const [persona] = useLoad<AnyItem>('/persona', { content: '' })
  const [content, setContent] = useState('')
  const [preview, setPreview] = useState('')
  useEffect(() => setContent(persona.content || ''), [persona])
  return <PageFrame eyebrow="Comportamento separado do código" title="Personalidade" subtitle="Edite as regras e faça uma inferência isolada antes de salvar."><div className="grid two"><Card title="Instruções da persona" icon={<SlidersHorizontal/>}><textarea className="editor" value={content} onChange={e => setContent(e.target.value)}/><div className="actions"><button onClick={async () => setPreview((await api<AnyItem>('/persona/preview', jsonRequest('POST', { content }))).message)}>Pré-visualizar</button><button className="primary" onClick={() => api('/persona', jsonRequest('PUT', { content }))}>Salvar</button></div></Card><Card title="Prévia isolada" icon={<Sparkles/>}>{preview ? <div className="message assistant"><span>JARVIS DISSE</span><p>{preview}</p></div> : <Empty title="Sem prévia" body="A prévia não altera o histórico principal." />}</Card></div></PageFrame>
}

function ActivityPage() {
  const [items] = useLoad<AnyItem[]>('/activity', [])
  return <PageFrame eyebrow="Auditoria local" title="Atividade" subtitle="Toda ação real, bloqueada ou cancelada.">{items.length ? <Card>{items.map(item => <Row key={item.id} title={item.tool} meta={`${item.status} · ${new Date(item.timestamp).toLocaleString('pt-BR')}`} action={<Badge tone={item.status === 'success' ? 'success' : item.status === 'failed' ? 'danger' : 'neutral'}>{item.status}</Badge>} />)}</Card> : <Empty title="Sem atividade" body="O log começará quando uma ação for executada." />}</PageFrame>
}

function SystemPage({ kind }: { kind: 'settings' | 'usage' | 'devices' | 'connections' }) {
  const path = kind === 'settings' ? '/system' : kind === 'connections' ? '/integrations' : `/${kind}`
  const [data] = useLoad<any>(path, kind === 'devices' || kind === 'connections' ? [] : {})
  const titles = { settings: 'Configurações', usage: 'Uso', devices: 'Dispositivos', connections: 'Conexões' }
  return <PageFrame eyebrow="Estado real" title={titles[kind]} subtitle="Sem dados fictícios ou serviços pagos."><Card><pre className="data-view">{JSON.stringify(data, null, 2)}</pre></Card></PageFrame>
}

function Placeholder({ kind }: { kind: 'calendar' | 'automations' }) {
  return <PageFrame eyebrow="Arquitetura preparada" title={kind === 'calendar' ? 'Agenda' : 'Automações'} subtitle={kind === 'calendar' ? 'Múltiplos calendários poderão ser conectados futuramente.' : 'Trigger + condição + ação, ainda sem engine de execução.'}><Empty title={kind === 'calendar' ? 'Nenhum calendário conectado' : 'Nenhuma automação'} body={kind === 'calendar' ? 'Conecte um calendário para visualizar seus compromissos aqui.' : 'A engine de automações será implementada em uma fase futura.'}/></PageFrame>
}

function PageFrame({ eyebrow, title, subtitle, children }: { eyebrow: string, title: string, subtitle: string, children: ReactNode }) {
  return <main className="page"><header className="page-head"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{subtitle}</p></header>{children}</main>
}

function ContextPanel({ context, close }: { context: AnyItem, close: () => void }) {
  const groups = [['Memórias utilizadas', context.memories], ['Documentos utilizados', context.documents], ['Tarefas', context.tasks], ['Ações', context.actions]] as const
  return <aside className="context-panel"><div className="panel-head"><div><span className="eyebrow">EVIDÊNCIAS</span><strong>Contexto</strong></div><button className="icon-button" onClick={close}><X/></button></div>{groups.map(([label, items]) => <section key={label}><span className="eyebrow">{label}</span>{items?.length ? items.map((item: AnyItem, index: number) => <p key={item.id || index}>{item.content || item.filename || item.title || item.tool}</p>) : <small>Nenhum.</small>}</section>)}</aside>
}

function CommandPalette({ close, go }: { close: () => void, go: (page: Page) => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<AnyItem[]>([])
  useEffect(() => { const timer = setTimeout(() => query.trim() ? api<AnyItem[]>(`/search?query=${encodeURIComponent(query)}`).then(setResults) : setResults([]), 220); return () => clearTimeout(timer) }, [query])
  const shortcuts: Array<[string, Page]> = [['Nova conversa', 'chat'], ['Criar tarefa', 'tasks'], ['Adicionar arquivo', 'library'], ['Ir para memória', 'memory'], ['Abrir personalidade', 'persona'], ['Ver atividade', 'activity'], ['Abrir configurações', 'settings']]
  return <div className="overlay" onMouseDown={close}><div className="palette" onMouseDown={e => e.stopPropagation()}><div className="palette-input"><Search/><input autoFocus value={query} onChange={e => setQuery(e.target.value)} placeholder="Pesquisar ou executar um comando…"/><kbd>Esc</kbd></div><div className="palette-results">{query ? results.map(item => <button key={`${item.type}-${item.id}`}><Badge>{item.type}</Badge><span>{item.title}</span></button>) : shortcuts.map(([label,page]) => <button key={label} onClick={() => { go(page); close() }}><Command/><span>{label}</span></button>)}</div></div></div>
}

export default function App() {
  const [page, setPage] = useState<Page>('now')
  const [menuOpen, setMenuOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [context, setContext] = useState<AnyItem>({})
  const [contextOpen, setContextOpen] = useState(true)
  useEffect(() => { const handler = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPaletteOpen(true) } if (event.key === 'Escape') setPaletteOpen(false) }; addEventListener('keydown', handler); return () => removeEventListener('keydown', handler) }, [])
  const current = useMemo(() => nav.find(item => item[0] === page), [page])
  const go = (target: Page) => { setPage(target); setMenuOpen(false) }
  return <div className="app-shell">
    <aside className={`sidebar ${menuOpen ? 'open' : ''}`}><div className="brand"><div className="brand-mark">J</div><div><strong>JARVIS</strong><small>LOCAL OS</small></div></div><nav>{nav.map(([id,label,icon]) => <button key={id} className={page === id ? 'active' : ''} onClick={() => go(id)}>{icon}<span>{label}</span></button>)}</nav><button className="command-hint" onClick={() => setPaletteOpen(true)}><Command/><span>Buscar</span><kbd>Ctrl K</kbd></button><div className="privacy"><span/><div><strong>100% local</strong><small>APIs externas: 0</small></div></div></aside>
    <div className="workspace"><header className="mobile-bar"><button className="icon-button" onClick={() => setMenuOpen(!menuOpen)}><Menu/></button><strong>{current?.[1]}</strong><button className="icon-button" onClick={() => setPaletteOpen(true)}><Search/></button></header>
      {page === 'now' && <NowPage go={go}/>} {page === 'chat' && <ChatPage context={context} setContext={value => { setContext(value); setContextOpen(true) }}/>} {page === 'memory' && <MemoryPage/>} {page === 'library' && <LibraryPage/>} {page === 'tasks' && <TasksPage/>} {page === 'persona' && <PersonaPage/>} {page === 'activity' && <ActivityPage/>} {(page === 'settings' || page === 'usage' || page === 'devices' || page === 'connections') && <SystemPage kind={page}/>} {(page === 'calendar' || page === 'automations') && <Placeholder kind={page}/>} 
    </div>
    {page === 'chat' && contextOpen && <ContextPanel context={context} close={() => setContextOpen(false)}/>} {paletteOpen && <CommandPalette close={() => setPaletteOpen(false)} go={go}/>} 
  </div>
}

