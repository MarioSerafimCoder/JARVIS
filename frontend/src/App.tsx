import { ReactNode, useEffect, useMemo, useState } from 'react'
import { Activity, Brain, CalendarDays, CircleGauge, Command, Cpu, Home, Library, ListTodo, Menu, MessageSquare, Network, Orbit, Search, Settings, UserRoundCog, Zap } from 'lucide-react'
import { ContextPanel } from './components/ContextPanel'
import { Badge } from './components/Common'
import { ChatPage } from './pages/ChatPage'
import { ActivityPage, LibraryPage, MemoryPage, NowPage, PersonaPage, Placeholder, SystemPage, TasksPage } from './pages/DomainPages'
import { api } from './services/api'
import type { ContextEvidence, Health, NavItem, Page, SearchItem } from './types'
import { CognitiveMapPage } from './components/cognitive/CognitiveCore'

const nav: NavItem[] = [
  ['now','Agora',<Home/>],['core','Cognitive Core',<Orbit/>],['chat','Jarvis',<MessageSquare/>],['memory','Memória',<Brain/>],['library','Biblioteca',<Library/>],['tasks','Tarefas',<ListTodo/>],['calendar','Agenda',<CalendarDays/>],['automations','Automações',<Zap/>],['connections','Conexões',<Network/>],['persona','Personalidade',<UserRoundCog/>],['devices','Dispositivos',<Cpu/>],['activity','Atividade',<Activity/>],['usage','Uso',<CircleGauge/>],['settings','Configurações',<Settings/>],
]

function CommandPalette({close,go}:{close:()=>void;go:(page:Page)=>void}) {
  const[query,setQuery]=useState('');const[results,setResults]=useState<SearchItem[]>([])
  useEffect(()=>{const timer=setTimeout(()=>query.trim()?api<SearchItem[]>(`/search?query=${encodeURIComponent(query)}`).then(setResults).catch(()=>setResults([])):setResults([]),220);return()=>clearTimeout(timer)},[query])
  const shortcuts:Array<[string,Page]>=[['Abrir Cognitive Map','core'],['Nova conversa','chat'],['Criar tarefa','tasks'],['Adicionar arquivo','library'],['Ir para memória','memory'],['Abrir personalidade','persona'],['Ver atividade','activity'],['Abrir configurações','settings']]
  return <div className="overlay" onMouseDown={close}><div className="palette" onMouseDown={event=>event.stopPropagation()}><div className="palette-input"><Search/><input autoFocus value={query} onChange={event=>setQuery(event.target.value)} placeholder="Pesquisar ou executar um comando…"/><kbd>Esc</kbd></div><div className="palette-results">{query?results.map(item=><button key={`${item.type}-${item.id}`}><Badge>{item.type}</Badge><span>{item.title}</span></button>):shortcuts.map(([label,page])=><button key={label} onClick={()=>{go(page);close()}}><Command/><span>{label}</span></button>)}</div></div></div>
}

export default function App(){
  const[page,setPage]=useState<Page>('now');const[menuOpen,setMenuOpen]=useState(false);const[paletteOpen,setPaletteOpen]=useState(false);const[context,setContext]=useState<ContextEvidence>({});const[contextOpen,setContextOpen]=useState(true);const[health,setHealth]=useState<Health>()
  useEffect(()=>{api<Health>('/health').then(setHealth).catch(()=>setHealth({status:'offline',llm:{status:'offline'}}));const handler=(event:KeyboardEvent)=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();setPaletteOpen(true)}if(event.key==='Escape')setPaletteOpen(false)};addEventListener('keydown',handler);return()=>removeEventListener('keydown',handler)},[])
  const current=useMemo(()=>nav.find(item=>item[0]===page),[page]);const go=(target:Page)=>{setPage(target);setMenuOpen(false)}
  let content:ReactNode
  if(page==='now')content=<NowPage go={go}/>;else if(page==='core')content=<CognitiveMapPage/>;else if(page==='chat')content=<ChatPage context={context} setContext={value=>{setContext(value);setContextOpen(true)}}/>;else if(page==='memory')content=<MemoryPage/>;else if(page==='library')content=<LibraryPage/>;else if(page==='tasks')content=<TasksPage/>;else if(page==='persona')content=<PersonaPage/>;else if(page==='activity')content=<ActivityPage/>;else if(page==='calendar'||page==='automations')content=<Placeholder kind={page}/>;else content=<SystemPage kind={page as 'settings'|'usage'|'devices'|'connections'}/>
  const modelOnline=['ok','online'].includes(health?.llm?.status || '')
  return <div className="app-shell"><aside className={`sidebar ${menuOpen?'open':''}`}><div className="brand"><div className="brand-mark">J</div><div><strong>JARVIS</strong><small>LOCAL OS</small></div></div><nav>{nav.map(([id,label,icon])=><button key={id} className={page===id?'active':''} onClick={()=>go(id)}>{icon}<span>{label}</span></button>)}</nav><button className="command-hint" onClick={()=>setPaletteOpen(true)}><Command/><span>Buscar</span><kbd>Ctrl K</kbd></button><div className="privacy"><span className={health?.status==='ok'?'':'offline'}/><div><strong>{health?.status==='ok'?'100% local':'Serviço indisponível'}</strong><small>{modelOnline?'Modelo conectado':'Verifique o Ollama'}</small></div></div></aside><div className="workspace"><header className="mobile-bar"><button className="icon-button" onClick={()=>setMenuOpen(!menuOpen)}><Menu/></button><strong>{current?.[1]}</strong><button className="icon-button" onClick={()=>setPaletteOpen(true)}><Search/></button></header>{content}</div>{page==='chat'&&contextOpen&&<ContextPanel context={context} close={()=>setContextOpen(false)}/>} {paletteOpen&&<CommandPalette close={()=>setPaletteOpen(false)} go={go}/>}</div>
}
