import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StartupIntro } from './StartupIntro'

describe('StartupIntro',()=>{
  afterEach(()=>vi.unstubAllGlobals())

  it('entra no Jarvis com tratamento padrão quando o nome não foi informado',async()=>{
    const fetchMock=vi.fn()
      .mockResolvedValueOnce({ok:true,json:async()=>({completed:false,user_name:'',backend:'online',ollama:'online',model_available:true,model:'qwen3.5:4b',gpu_detected:true,memory_behavior:{mode:'suggest'},migration_candidates:[],requires_account:false,external_transfer:false})})
      .mockResolvedValueOnce({ok:true,json:async()=>({completed:true,user_name:'Senhor',memory_mode:'suggest'})})
    vi.stubGlobal('fetch',fetchMock)
    render(<StartupIntro/>)

    await screen.findByRole('heading',{name:'Prepare o Jarvis'})
    fireEvent.click(screen.getByRole('button',{name:/Importar documentos/}))
    const enter=screen.getByRole('button',{name:'Entrar no Jarvis'})
    expect(enter).toBeEnabled()
    fireEvent.click(enter)

    await waitFor(()=>expect(screen.queryByRole('heading',{name:'Prepare o Jarvis'})).not.toBeInTheDocument())
    expect(fetchMock).toHaveBeenLastCalledWith(expect.stringMatching(/\/api\/onboarding\/complete$/),expect.objectContaining({method:'POST',body:JSON.stringify({user_name:'Senhor',memory_mode:'suggest'})}))
  })
})
