import type { Page, SearchItem } from '../types'

export const basePaths:Record<Page,string>={now:'/now',core:'/cognitive',chat:'/chat',memory:'/memory',library:'/library',tasks:'/tasks',learning:'/learning',persona:'/personality',settings:'/settings',activity:'/activity',usage:'/usage',devices:'/devices',connections:'/connections',calendar:'/calendar',automations:'/automations'}

export function parseRoute(pathname:string):{page:Page;id?:string}{
  const [root,id]=pathname.split('/').filter(Boolean)
  const page=Object.entries(basePaths).find(([,path])=>path.slice(1)===root)?.[0] as Page|undefined
  return {page:page||'now',id}
}

export function searchResultPath(item:SearchItem):string{
  if(item.path)return item.path
  const page=item.type==='conversation'?'chat':item.type==='document'?'library':item.type as Page
  return `${basePaths[page]||basePaths.now}/${item.id}`
}
