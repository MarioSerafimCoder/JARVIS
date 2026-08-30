import { useCallback, useMemo, useState } from 'react'
import { Expand, Filter, RotateCcw, Search, X } from 'lucide-react'
import type { CognitiveNode, CognitiveNodeKind, CognitiveQuality, Page } from '../../types'
import { Badge, Empty, PageFrame } from '../Common'
import { CognitiveScene } from './CognitiveScene'
import { filterCognitiveGraph, relatedNodes } from './graphModel'
import { useCognitiveGraph } from './useCognitiveGraph'

const STATE_LABELS: Record<string,string>={IDLE:'Em repouso',THINKING:'Pensando',SEARCHING_MEMORY:'Buscando memória',SEARCHING_KNOWLEDGE:'Buscando conhecimento',USING_TOOL:'Usando ferramenta',WAITING_CONFIRMATION:'Aguardando confirmação',ERROR:'Erro',LISTENING:'Escuta preparada',SPEAKING:'Fala preparada'}
const KIND_LABELS:Record<string,string>={core:'Núcleo',memory:'Memória',document:'Documento',task:'Tarefa',tool:'Ferramenta'}
const KINDS:CognitiveNodeKind[]=['memory','document','task','tool']

export function CognitiveCore({compact=false,onExpand}:{compact?:boolean;onExpand?:()=>void}){
  const{graph,state,highlighted,connected,error,reload}=useCognitiveGraph();const[selected,setSelected]=useState<CognitiveNode>();const[query,setQuery]=useState('');const[kinds,setKinds]=useState<Set<string>>(new Set(KINDS));const[quality,setQuality]=useState<CognitiveQuality>('AUTO');const[resetKey,setResetKey]=useState(0)
  const select=useCallback((node?:CognitiveNode)=>setSelected(node),[])
  const visible=useMemo(()=>graph?filterCognitiveGraph(graph,query,kinds):undefined,[graph,query,kinds])
  const toggle=(kind:string)=>setKinds(current=>{const next=new Set(current);if(next.has(kind))next.delete(kind);else next.add(kind);return next})
  if(error&&!graph)return <div className={`cognitive-core ${compact?'compact':''}`}><Empty title="Cognitive Core indisponível" body={error}/><button onClick={()=>void reload()}>Tentar novamente</button></div>
  if(!visible)return <div className={`cognitive-core ${compact?'compact':''}`}><div className="core-loading"><i/><span>Mapeando dados locais…</span></div></div>
  const related=selected?relatedNodes(visible,selected.id):[]
  const renderGraph=compact?{...visible,edges:visible.edges.filter(edge=>edge.connection_class!=='tool_connection')}:visible
  return <section className={`cognitive-core ${compact?'compact':'expanded'} state-${state.toLowerCase()}`}>
    <header className="core-toolbar"><div><span className={`state-dot ${connected?'connected':''}`}/><span className="eyebrow">COGNITIVE CORE</span><strong>{STATE_LABELS[state]||state}</strong></div>{!compact&&<><label className="core-search"><Search/><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Buscar no mapa cognitivo…"/></label><div className="quality"><span>Qualidade</span><select value={quality} onChange={event=>setQuality(event.target.value as CognitiveQuality)}>{['AUTO','HIGH','MEDIUM','LOW'].map(value=><option key={value}>{value}</option>)}</select></div><button title="Resetar câmera" className="icon-button" onClick={()=>setResetKey(value=>value+1)}><RotateCcw/></button></>}{compact&&<button className="core-expand" onClick={onExpand}><Expand/>Expandir mapa</button>}</header>
    {!compact&&<div className="core-filters"><Filter/>{KINDS.map(kind=><button key={kind} className={kinds.has(kind)?'active':''} onClick={()=>toggle(kind)}>{KIND_LABELS[kind]} <span>{graph?.stats[`${kind==='memory'?'memories':kind==='document'?'documents':kind==='task'?'tasks':'tools'}` as keyof typeof graph.stats]}</span></button>)}</div>}
    <CognitiveScene graph={renderGraph} state={state} highlighted={highlighted} selectedId={selected?.id} onSelect={select} quality={quality} resetKey={resetKey}/>
    <footer className="core-stats"><span><strong>{visible.stats.memories}</strong> memórias</span><span><strong>{visible.stats.memory_relationships}</strong> relações cognitivas</span><span><strong>{visible.stats.documents}</strong> documentos</span><span><strong>{visible.stats.tasks}</strong> tarefas</span><span><strong>{visible.stats.tools}</strong> ferramentas</span><small>substrato visual · {visible.stats.relationship_provider}</small></footer>
    {selected&&<aside className="node-details"><button aria-label="Fechar detalhes" className="icon-button" onClick={()=>setSelected(undefined)}><X/></button><span className="eyebrow">{KIND_LABELS[selected.kind]} · {selected.cluster}</span><h2>{selected.label}</h2><Badge>{selected.kind}</Badge><dl>{Object.entries(selected.metadata).filter(([,value])=>value!==null&&value!==''&&typeof value!=='object').slice(0,9).map(([key,value])=><div key={key}><dt>{key.replaceAll('_',' ')}</dt><dd>{String(value)}</dd></div>)}</dl>{related.length>0&&<><h3>Relações justificadas</h3><div className="related-nodes">{related.map(({node,edge})=><button key={`${node.id}-${edge.type}`} onClick={()=>setSelected(node)}><span>{node.label}</span><small>{edge.type} · {Math.round(edge.weight*100)}%{edge.evidence.shared_terms?.length?` · ${edge.evidence.shared_terms.join(', ')}`:''}</small></button>)}</div></>}</aside>}
  </section>
}

export function CognitiveMapPage(){return <PageFrame eyebrow="Memória viva" title="Cognitive Map" subtitle="Representação tridimensional baseada exclusivamente nos dados reais do Jarvis."><CognitiveCore/></PageFrame>}

export function CoreHome({go}:{go:(page:Page)=>void}){return <CognitiveCore compact onExpand={()=>go('core')}/>}
