import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, jsonRequest } from './api'

describe('cliente de API', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('retorna JSON de respostas válidas', async () => { vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok:true, json:async()=>({status:'ok'}) })); await expect(api('/health')).resolves.toEqual({status:'ok'}) })
  it('normaliza a mensagem de erro da API', async () => { vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok:false,status:503,json:async()=>({error:{message:'Ollama indisponível'}}) })); await expect(api('/chat')).rejects.toThrow('Ollama indisponível') })
  it('serializa corpos JSON', () => { expect(jsonRequest('POST',{title:'teste'})).toMatchObject({method:'POST',headers:{'Content-Type':'application/json'},body:'{"title":"teste"}'}) })
})

