import { ReactNode, useEffect, useMemo, useState } from 'react'
import { Activity, Brain, CalendarDays, CircleGauge, Command, Cpu, GraduationCap, Home, Library, ListTodo, Menu, MessageSquare, Network, Orbit, Search, Settings, UserRoundCog, Zap } from 'lucide-react'
import { ContextPanel } from './components/ContextPanel'
import { Badge } from './components/Common'
import { CognitiveMapPage } from './components/cognitive/CognitiveCore'
import { useCognitiveGraph } from './components/cognitive/useCognitiveGraph'
import { ChatPage } from './pages/ChatPage'
import { ActivityPage, LearningPage, LibraryPage, MemoryPage, NowPage, PersonaPage, Placeholder, SystemPage, TasksPage } from './pages/DomainPages'
import { api } from './services/api'
import { basePaths, parseRoute, searchResultPath } from './services/routes'
import type { ContextEvidence, Health, NavItem, Page, SearchItem } from './types'

const nav: NavItem[] = [
  ['now','Agora',<Home/>],['core','Cognitive Core',<Orbit/>],['chat','Jarvis',<MessageSquare/>],['memory','Memória',<Brain/>],['library','Biblioteca',<Library/>],['tasks','Tarefas',<ListTodo/>],['learning','Aprendizado',<GraduationCap/>],['calendar','Agenda',<CalendarDays/>],['automations','Automações',<Zap/>],['connections','Conexões',<Network/>],['persona','Personalidade',<UserRoundCog/>],['devices','Dispositivos',<Cpu/>],['activity','Atividade',<Activity/>],['usage','Uso',<CircleGauge/>],['settings','Configurações',<Settings/>],
]

function CommandPalette({close,navigate}:{close:()=>void;navigate:(page:Page,id?:string)=>void}) {
  const[query,setQuery]=useState('');const[results,setResults]=useState<SearchItem[]>([])
  useEffect(()=>{const timer=setTimeout(()=>query.trim()?api<SearchItem[]>(`/search?query=${encodeURIComponent(query)}`).then(setResults).catch(()=>setResults([])):setResults([]),220);return()=>clearTimeout(timer)},[query])
  const shortcuts:Array<[string,Page]>=[['Abrir Cognitive Map','core'],['Nova conversa','chat'],['Criar tarefa','tasks'],['Adicionar arquivo','library'],['Ir para memória','memory'],['Ver aprendizado','learning'],['Abrir personalidade','persona'],['Ver atividade','activity'],['Abrir configurações','settings']]
  const openResult=(item:SearchItem)=>{history.pushState({},'',searchResultPath(item));dispatchEvent(new PopStateEvent('popstate'));close()}
  return <div className="overlay" onMouseDown={close}><div className="palette" onMouseDown={event=>event.stopPropagation()}><div className="palette-input"><Search/><input autoFocus value={query} onChange={event=>setQuery(event.target.value)} placeholder="Pesquisar ou executar um comando…"/><kbd>Esc</kbd></div><div className="palette-results">{query?results.map(item=><button key={`${item.type}-${item.id}`} onClick={()=>openResult(item)}><Badge>{item.type}</Badge><span>{item.title}</span></button>):shortcuts.map(([label,page])=><button key={label} onClick={()=>{navigate(page);close()}}><Command/><span>{label}</span></button>)}</div></div></div>
}

function CognitiveIndicator({open}:{open:()=>void}){
  const{state,connected}=useCognitiveGraph()
  const short=state==='SEARCHING_MEMORY'?'MEMORY':state==='SEARCHING_KNOWLEDGE'?'KNOWLEDGE':state==='SEARCHING_WEB'?'WEB':state==='BROWSING'?'BROWSER':state==='USING_TOOL'?'TOOL':state==='WAITING_CONFIRMATION'?'WAITING':state
  return <button className={`cognitive-indicator state-${state.toLowerCase()}`} onClick={open} title="Abrir mapa cognitivo"><i className={connected?'online':''}/><span>{short}</span></button>
}

export default function App(){
  const[route,setRoute]=useState(()=>parseRoute(window.location.pathname));const[menuOpen,setMenuOpen]=useState(false);const[paletteOpen,setPaletteOpen]=useState(false);const[context,setContext]=useState<ContextEvidence>({});const[contextOpen,setContextOpen]=useState(true);const[health,setHealth]=useState<Health>()
  useEffect(()=>{api<Health>('/health').then(setHealth).catch(()=>setHealth({status:'offline',llm:{status:'offline'}}));const pop=()=>setRoute(parseRoute(window.location.pathname));const handler=(event:KeyboardEvent)=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setPaletteOpen(true)}if(event.key==='Escape')setPaletteOpen(false)};addEventListener('popstate',pop);addEventListener('keydown',handler);if(location.pathname==='/')history.replaceState({},'',basePaths.now);return()=>{removeEventListener('popstate',pop);removeEventListener('keydown',handler)}},[])
  const current=useMemo(()=>nav.find(item=>item[0]===route.page),[route.page]);const go=(target:Page,id?:string)=>{const path=basePaths[target]+(id?`/${id}`:'');history.pushState({},'',path);setRoute({page:target,id});setMenuOpen(false)}
  let content:ReactNode
  if(route.page==='now')content=<NowPage go={go}/>;else if(route.page==='core')content=<CognitiveMapPage/>;else if(route.page==='chat')content=<ChatPage context={context} initialConversationId={route.id} navigate={go} setContext={value=>{setContext(value);setContextOpen(true)}}/>;else if(route.page==='memory')content=<MemoryPage initialId={route.id} navigate={go}/>;else if(route.page==='library')content=<LibraryPage initialId={route.id} navigate={go}/>;else if(route.page==='tasks')content=<TasksPage initialId={route.id} navigate={go}/>;else if(route.page==='learning')content=<LearningPage/>;else if(route.page==='persona')content=<PersonaPage/>;else if(route.page==='activity')content=<ActivityPage/>;else if(route.page==='calendar'||route.page==='automations')content=<Placeholder kind={route.page}/>;else content=<SystemPage kind={route.page as 'settings'|'usage'|'devices'|'connections'}/>
  const modelOnline=health?.model?.status==='available'||health?.llm?.model_available||['ok','online'].includes(health?.llm?.status||'')
  return <div className="app-shell"><aside className={`sidebar ${menuOpen?'open':''}`}><div className="brand"><div className="brand-mark">J</div><div><strong>JARVIS</strong><small>LOCAL OS</small></div></div><CognitiveIndicator open={()=>go('core')}/><nav>{nav.map(([id,label,icon])=><button key={id} className={route.page===id?'active':''} onClick={()=>go(id)}>{icon}<span>{label}</span></button>)}</nav><button className="command-hint" onClick={()=>setPaletteOpen(true)}><Command/><span>Buscar</span><kbd>Ctrl K</kbd></button><div className="privacy"><span className={health?.status==='ok'?'':'offline'}/><div><strong>{health?.status==='ok'?'App online':'App offline'}</strong><small>{modelOnline?'Modelo disponível':'Ollama/modelo indisponível'}</small></div></div></aside><div className="workspace"><header className="mobile-bar"><button className="icon-button" onClick={()=>setMenuOpen(!menuOpen)}><Menu/></button><strong>{current?.[1]}</strong><CognitiveIndicator open={()=>go('core')}/><button className="icon-button" onClick={()=>setPaletteOpen(true)}><Search/></button></header>{content}</div>{route.page==='chat'&&contextOpen&&<ContextPanel context={context} close={()=>setContextOpen(false)}/>} {paletteOpen&&<CommandPalette close={()=>setPaletteOpen(false)} navigate={go}/>}</div>
}
