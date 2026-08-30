import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { VoiceLab } from './VoiceLab'

describe('VoiceLab',()=>{
  afterEach(()=>vi.unstubAllGlobals())
  it('mostra o perfil real e não finge que o worker está pronto',async()=>{
    Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{enumerateDevices:vi.fn().mockResolvedValue([])}})
    vi.stubGlobal('fetch',vi.fn().mockImplementation((input:string)=>Promise.resolve({ok:true,json:async()=>String(input).includes('/voice/settings')?{resource_mode:'AUTO',speech_threshold:.018,silence_end_ms:850,echo_cancellation:true,noise_suppression:true,auto_gain_control:true,barge_in_sensitivity:.035,include_references_in_backup:false}:{profile_name:'Jarvis',status:'NOT_BUILT',provider:'XTTS-v2',reference_count:28,total_duration_seconds:104.38,fingerprint:'abc123',language:'pt-BR',worker:{status:'unavailable'},voice_dna:{}}})))
    render(<VoiceLab/>)
    await waitFor(()=>expect(screen.getByText('28')).toBeInTheDocument())
    expect(screen.getByText('NOT_BUILT')).toBeInTheDocument()
    expect(screen.getByText(/indisponível — chat textual preservado/)).toBeInTheDocument()
    expect(screen.getByRole('button',{name:/Gerar e ouvir/})).toBeDisabled()
  })
})
