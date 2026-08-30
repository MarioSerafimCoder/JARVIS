import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { CognitiveGraph } from '../../types'
import { CognitiveScene } from './CognitiveScene'

const graph:CognitiveGraph={nodes:[{id:'core:jarvis',kind:'core',cluster:'core',label:'JARVIS',position:{x:0,y:0,z:0},size:2,intensity:1,metadata:{}},{id:'memory:real',kind:'memory',cluster:'facts',label:'Memória real',position:{x:2,y:1,z:0},size:.5,intensity:1,metadata:{content:'Memória real'}}],edges:[],clusters:[],state:{state:'IDLE',last_event_id:0},stats:{nodes:2,edges:0,memories:1,documents:0,tasks:0,tools:0,memory_relationships:0,structural_connections:0,tool_connections:0,relationship_provider:'deterministic'}}

describe('fallback cognitivo',()=>{
  it('mantém um mapa 2D acessível quando WebGL não está disponível',()=>{const select=vi.fn();render(<CognitiveScene graph={graph} state="IDLE" highlighted={new Set()} onSelect={select} quality="LOW" resetKey={0} forceFallback/>);const svg=screen.getByRole('img',{name:/Mapa bidimensional/});expect(svg).toBeInTheDocument();fireEvent.click(svg.querySelector('circle.memory')!);expect(select).toHaveBeenCalledWith(expect.objectContaining({id:'memory:real'}))})
})
