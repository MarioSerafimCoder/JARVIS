import { createContext, createElement, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { API_URL, api } from '../../services/api'
import type { CognitiveEvent, CognitiveGraph, CognitiveState } from '../../types'

type CognitiveValue = { graph?: CognitiveGraph; state: CognitiveState; highlighted: Set<string>; connected: boolean; error: string; reload: () => Promise<void> }
const CognitiveContext = createContext<CognitiveValue | undefined>(undefined)

export function CognitiveProvider({ children }: { children: ReactNode }) {
  const [graph, setGraph] = useState<CognitiveGraph>()
  const [state, setState] = useState<CognitiveState>('IDLE')
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set())
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const highlightTimers = useRef(new Map<string, number>())
  const load = useCallback(async () => {
    try { const result = await api<CognitiveGraph>('/cognitive-graph'); setGraph(result); setState(result.state.state); setError('') }
    catch (err) { setError(err instanceof Error ? err.message : String(err)) }
  }, [])

  useEffect(() => { void load() }, [load])
  useEffect(() => {
    let source: EventSource | undefined
    let retryTimer: number | undefined
    let stopped = false
    let attempt = 0
    const connect = () => {
      if (stopped) return
      source = new EventSource(`${API_URL}/cognitive-events`)
      source.onopen = () => { attempt = 0; setConnected(true) }
      source.addEventListener('cognitive', raw => {
        const event = JSON.parse((raw as MessageEvent).data) as CognitiveEvent
        setState(event.state)
        if (event.type === 'GRAPH_CHANGED' || event.type === 'MEMORY_CREATED') void load()
        const ids = [...(event.payload.node_ids || []), ...(event.payload.node_id ? [event.payload.node_id] : [])]
        if (ids.length) {
          setHighlighted(current => new Set([...current, ...ids]))
          for (const id of ids) {
            const previous = highlightTimers.current.get(id); if (previous) window.clearTimeout(previous)
            highlightTimers.current.set(id, window.setTimeout(() => setHighlighted(current => { const next = new Set(current); next.delete(id); return next }), 5200))
          }
        }
      })
      source.onerror = () => {
        setConnected(false); source?.close()
        const delay = Math.min(30000, 750 * 2 ** attempt++) + Math.random() * 250
        retryTimer = window.setTimeout(connect, delay)
      }
    }
    connect()
    return () => {
      stopped = true; source?.close()
      if (retryTimer) window.clearTimeout(retryTimer)
      for (const timer of highlightTimers.current.values()) window.clearTimeout(timer)
    }
  }, [load])
  return createElement(CognitiveContext.Provider, { value: { graph, state, highlighted, connected, error, reload: load } }, children)
}

export function useCognitiveGraph() {
  const value = useContext(CognitiveContext)
  if (!value) throw new Error('useCognitiveGraph requer CognitiveProvider.')
  return value
}
