import type { CognitiveEdge, CognitiveGraph, CognitiveNode, CognitiveQuality } from '../../types'

const LIMITS: Record<CognitiveQuality, number> = { AUTO:5000, HIGH:5000, MEDIUM:2500, LOW:1000 }

export function resolvedQuality(requested: CognitiveQuality, count: number, mobile = false): CognitiveQuality {
  if (requested !== 'AUTO') return requested
  if (mobile || count > 2500) return 'LOW'
  if (count > 900) return 'MEDIUM'
  return 'HIGH'
}

export function cognitiveNodeLimit(requested: CognitiveQuality, count: number, mobile = false): number {
  return LIMITS[resolvedQuality(requested,count,mobile)]
}

export function filterCognitiveGraph(graph: CognitiveGraph, query: string, kinds: Set<string>): CognitiveGraph {
  const normalized = query.trim().toLocaleLowerCase('pt-BR')
  const visible = new Set(graph.nodes.filter(node => node.kind === 'core' || (kinds.has(node.kind) && (!normalized || node.label.toLocaleLowerCase('pt-BR').includes(normalized) || node.cluster.includes(normalized)))).map(node => node.id))
  return { ...graph, nodes: graph.nodes.filter(node => visible.has(node.id)), edges: graph.edges.filter(edge => visible.has(edge.source) && visible.has(edge.target)) }
}

export function relatedNodes(graph: CognitiveGraph, nodeId: string): Array<{ node: CognitiveNode; edge: CognitiveEdge }> {
  const nodes = new Map(graph.nodes.map(node => [node.id, node]))
  return graph.edges.flatMap(edge => {
    const relatedId = edge.source === nodeId ? edge.target : edge.target === nodeId ? edge.source : undefined
    const node = relatedId ? nodes.get(relatedId) : undefined
    return node ? [{ node, edge }] : []
  }).sort((a, b) => b.edge.weight - a.edge.weight)
}

export function graphBounds(graph: CognitiveGraph): { width: number; height: number } {
  if (!graph.nodes.length) return { width: 1, height: 1 }
  const xs = graph.nodes.map(node => node.position.x), ys = graph.nodes.map(node => node.position.y)
  return { width: Math.max(...xs) - Math.min(...xs) || 1, height: Math.max(...ys) - Math.min(...ys) || 1 }
}
