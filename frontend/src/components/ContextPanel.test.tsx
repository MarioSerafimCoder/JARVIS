import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ContextPanel } from './ContextPanel'

describe('ContextPanel', () => {
  it('mostra origem e localização dos documentos usados', () => {
    render(<ContextPanel close={() => undefined} context={{ documents: [{ document_id: '1', filename: 'manual.pdf', location: 'Página 7', relevant_text: 'trecho relevante' }], budget: { max_chars: 100, used_chars: 50, estimated_tokens: 13 } }}/>)
    expect(screen.getByText('manual.pdf')).toBeInTheDocument(); expect(screen.getByText('Página 7')).toBeInTheDocument(); expect(screen.getByText('13 tokens estimados')).toBeInTheDocument()
  })
  it('recolhe uma seção sem perder as demais', () => {
    render(<ContextPanel close={() => undefined} context={{ memories: [{ id:'m',content:'Prefere respostas breves',category:'preference',memory_type:'preference',status:'active',confidence:1,importance:4,source_type:'manual',created_at:'',updated_at:'' }] }}/>)
    fireEvent.click(screen.getByText(/Memórias utilizadas/)); expect(screen.queryByText('Prefere respostas breves')).not.toBeInTheDocument(); expect(screen.getByText(/Documentos utilizados/)).toBeInTheDocument()
  })
  it('aciona o fechamento do painel', () => {
    const close=vi.fn(); render(<ContextPanel close={close} context={{}}/>); fireEvent.click(screen.getByLabelText('Fechar contexto')); expect(close).toHaveBeenCalledOnce()
  })
})
