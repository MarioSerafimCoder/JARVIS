import { useCallback, useEffect, useRef, useState } from 'react'
import { API_URL, api } from '../../services/api'
import type { CognitiveEvent, CognitiveGraph, CognitiveState } from '../../types'

export function useCognitiveGraph() {
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
    const source = new EventSource(`${API_URL}/cognitive-events`)
    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)
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
    return () => { source.close(); for (const timer of highlightTimers.current.values()) window.clearTimeout(timer) }
  }, [load])
  return { graph, state, highlighted, connected, error, reload: load }
}

