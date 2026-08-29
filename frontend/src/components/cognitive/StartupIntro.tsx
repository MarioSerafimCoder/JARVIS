import { useEffect, useState } from 'react'
import { api } from '../../services/api'
import type { Health } from '../../types'

export function StartupIntro(){
  const[visible,setVisible]=useState(()=>localStorage.getItem('jarvis.skipCognitiveIntro')!=='true');const[health,setHealth]=useState<Health>();const[error,setError]=useState('')
  useEffect(()=>{if(visible)api<Health>('/health').then(setHealth).catch(err=>setError(err instanceof Error?err.message:String(err)))},[visible])
  if(!visible)return null
  const online=health?.status==='ok'&&['online','ok'].includes(health.llm?.status||'')
  const finish=(remember:boolean)=>{if(remember)localStorage.setItem('jarvis.skipCognitiveIntro','true');setVisible(false)}
  return <div className="startup-overlay"><div className={`startup-core ${error?'error':online?'online':'loading'}`}><i/><i/><i/><div>J</div></div><span className="eyebrow">JARVIS LOCAL OS</span><h1>Cognitive Core</h1><p>{error?'O núcleo local não respondeu. Você ainda pode abrir a interface.':health?(online?'Núcleo online. Modelo local disponível.':'Interface online; verifique a disponibilidade do modelo local.'):'Verificando o estado real do sistema…'}</p><div className="startup-status"><span className={health?.status==='ok'?'ok':''}>API {health?.status==='ok'?'ONLINE':error?'ERROR':'…'}</span><span className={online?'ok':''}>QWEN {online?'ONLINE':error?'OFFLINE':'…'}</span></div><div className="startup-actions"><button onClick={()=>finish(true)}>Pular nas próximas vezes</button><button className="primary" disabled={!health&&!error} onClick={()=>finish(false)}>Entrar no Jarvis</button></div></div>
}
