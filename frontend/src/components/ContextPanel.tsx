import { ChevronDown, X } from 'lucide-react'
import { useState } from 'react'
import type { ContextEvidence } from '../types'

function Section({ title, children, count }: { title: string; children: React.ReactNode; count: number }) {
  const [open, setOpen] = useState(true)
  return <section><button className="context-section-head" onClick={() => setOpen(value => !value)}><span className="eyebrow">{title} ({count})</span><ChevronDown className={open ? 'open' : ''}/></button>{open && children}</section>
}

export function ContextPanel({ context, close }: { context: ContextEvidence; close: () => void }) {
  const memories = context.memories || [], documents = context.documents || [], tasks = context.tasks || [], actions = context.actions || []
  return <aside className="context-panel"><div className="panel-head"><div><span className="eyebrow">EVIDÊNCIAS</span><strong>Inspetor de contexto</strong></div><button aria-label="Fechar contexto" className="icon-button" onClick={close}><X/></button></div>
    {context.budget && <div className="context-budget"><span>{context.budget.estimated_tokens} tokens estimados</span><progress value={context.budget.used_chars} max={context.budget.max_chars}/></div>}
    <Section title="Memórias utilizadas" count={memories.length}>{memories.length ? memories.map(item => <article key={item.id}><strong>{item.category} · importância {item.importance}</strong><p>{item.content}</p></article>) : <small>Nenhuma memória recuperada.</small>}</Section>
    <Section title="Documentos utilizados" count={documents.length}>{documents.length ? documents.map((item, index) => <article key={`${item.document_id}-${index}`}><strong>{item.filename}</strong><small>{item.location || 'Localização indisponível'}</small><p>{item.relevant_text}</p></article>) : <small>Nenhum trecho recuperado.</small>}</Section>
    <Section title="Tarefas relacionadas" count={tasks.length}>{tasks.length ? tasks.map(item => <article key={item.id}><strong>{item.title}</strong><small>{item.priority} · {item.status}</small></article>) : <small>Nenhuma tarefa relacionada.</small>}</Section>
    <Section title="Ações" count={actions.length}>{actions.length ? actions.map((item, index) => <article key={item.action_id || index}><strong>{item.tool}</strong><small>{item.status}</small></article>) : <small>Nenhuma ação proposta.</small>}</Section>
  </aside>
}

