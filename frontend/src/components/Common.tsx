import { Archive, ChevronRight } from 'lucide-react'
import { ReactNode, useCallback, useEffect, useState } from 'react'
import { api } from '../services/api'

export function useLoad<T>(path: string, initial: T): [T, () => void, boolean, string] {
  const [data, setData] = useState<T>(initial)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(() => {
    setLoading(true); setError('')
    api<T>(path).then(setData).catch(err => setError(err instanceof Error ? err.message : String(err))).finally(() => setLoading(false))
  }, [path])
  useEffect(load, [load])
  return [data, load, loading, error]
}

export function Card({ title, icon, children, className = '' }: { title?: string; icon?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`card ${className}`}>{title && <header className="card-title">{icon}<span>{title}</span></header>}{children}</section>
}
export function Empty({ title, body }: { title: string; body: string }) { return <div className="empty"><Archive/><strong>{title}</strong><p>{body}</p></div> }
export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) { return <span className={`badge ${tone}`}>{children}</span> }
export function Row({ title, meta, action, onClick }: { title: string; meta?: string; action?: ReactNode; onClick?: () => void }) {
  return <div className={`row ${onClick ? 'clickable' : ''}`} onClick={onClick}><div><strong>{title}</strong>{meta && <small>{meta}</small>}</div>{action || <ChevronRight/>}</div>
}
export function PageFrame({ eyebrow, title, subtitle, children }: { eyebrow: string; title: string; subtitle: string; children: ReactNode }) {
  return <main className="page"><header className="page-head"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{subtitle}</p></header>{children}</main>
}
export const formatDate = (value?: string) => value ? new Date(value).toLocaleString('pt-BR') : '—'

