import { describe,expect,it } from 'vitest'
import { parseRoute, searchResultPath } from './routes'

describe('rotas reais e command palette',()=>{
  it.each([
    ['memory','m1','/memory/m1'],['document','d1','/library/d1'],['task','t1','/tasks/t1'],['conversation','c1','/chat/c1'],
  ])('navega resultado %s até a entidade', (type,id,path)=>{
    expect(searchResultPath({type,id,title:'resultado',path})).toBe(path)
    expect(parseRoute(path).id).toBe(id)
  })
  it('preserva rotas em navegação back/forward',()=>{
    expect(parseRoute('/chat/abc')).toEqual({page:'chat',id:'abc'})
    expect(parseRoute('/cognitive')).toEqual({page:'core',id:undefined})
  })
})
