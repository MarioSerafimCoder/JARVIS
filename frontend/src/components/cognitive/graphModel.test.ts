import { describe, expect, it } from 'vitest'
import type { CognitiveGraph } from '../../types'
import { cognitiveNodeLimit, filterCognitiveGraph, relatedNodes, resolvedQuality } from './graphModel'

const graph:CognitiveGraph={nodes:[{id:'core:jarvis',kind:'core',cluster:'core',label:'JARVIS',position:{x:0,y:0,z:0},size:2,intensity:1,metadata:{}},{id:'memory:1',entity_id:'1',kind:'memory',cluster:'projects',label:'Projeto Jarvis',position:{x:1,y:2,z:0},size:.5,intensity:1,metadata:{}},{id:'task:1',entity_id:'1',kind:'task',cluster:'operations',label:'Revisar testes',position:{x:2,y:-2,z:0},size:.5,intensity:1,metadata:{}}],edges:[{source:'memory:1',target:'task:1',type:'context',weight:.8,evidence:{reason:'teste controlado'}}],clusters:[],state:{state:'IDLE',last_event_id:0},stats:{nodes:3,edges:1,memories:1,documents:0,tasks:1,tools:0,memory_relationships:1,structural_connections:0,tool_connections:0,relationship_provider:'deterministic'}}

describe('modelo do Cognitive Core',()=>{
  it('filtra por busca e tipo sem inventar entidades',()=>{const filtered=filterCognitiveGraph(graph,'Jarvis',new Set(['memory']));expect(filtered.nodes.map(node=>node.id)).toEqual(['core:jarvis','memory:1']);expect(filtered.edges).toHaveLength(0)})
  it('navega relações reais nos dois sentidos',()=>{const related=relatedNodes(graph,'task:1');expect(related[0].node.id).toBe('memory:1');expect(related[0].edge.evidence.reason).toBe('teste controlado')})
  it('aplica LOD previsível para datasets controlados',()=>{expect(resolvedQuality('AUTO',100)).toBe('HIGH');expect(cognitiveNodeLimit('AUTO',1000)).toBe(2500);expect(cognitiveNodeLimit('AUTO',5000)).toBe(1000);expect(cognitiveNodeLimit('HIGH',5000)).toBe(5000)})
})
