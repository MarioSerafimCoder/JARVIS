import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { CognitiveGraph, CognitiveNode, CognitiveQuality, CognitiveState } from '../../types'
import { cognitiveNodeLimit, graphBounds, resolvedQuality } from './graphModel'

const COLORS: Record<string, number> = {
  core: 0xffa33a, projects: 0xf28c28, people: 0xd9a066, preferences: 0xffc46b, routine: 0xb87333,
  facts: 0xe09b45, instructions: 0xff7a1a, decisions: 0xc97b30, other: 0x9b7048,
  knowledge: 0xffd08a, operations: 0xe66b2e, tools: 0xa96b3c,
}
const STATE_COLOR: Record<CognitiveState, number> = { IDLE:0xc78645, THINKING:0xffa62b, SEARCHING_MEMORY:0xffbf58, SEARCHING_KNOWLEDGE:0xffd894, SEARCHING_WEB:0x65b9e8, BROWSING:0x4f91bd, USING_TOOL:0xff7628, WAITING_CONFIRMATION:0xeaa54d, ERROR:0xff4d3d, LISTENING:0xb9ef4a, TRANSCRIBING:0xf4bd62, SPEAKING:0xd78b41 }
export function CognitiveScene({ graph, state, highlighted, selectedId, onSelect, quality, resetKey, forceFallback = false }: { graph: CognitiveGraph; state: CognitiveState; highlighted: Set<string>; selectedId?: string; onSelect: (node?: CognitiveNode) => void; quality: CognitiveQuality; resetKey: number; forceFallback?: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const [fallback, setFallback] = useState(forceFallback)
  const live = useRef({state,highlighted,selectedId,onSelect})
  live.current={state,highlighted,selectedId,onSelect}
  const sceneGraph = useMemo(() => {
    const limit = cognitiveNodeLimit(quality, graph.nodes.length, window.innerWidth < 760)
    const nodes = graph.nodes.filter(node => node.kind === 'core').concat(graph.nodes.filter(node => node.kind !== 'core').slice(0, limit))
    const ids = new Set(nodes.map(node => node.id))
    return { ...graph, nodes, edges: graph.edges.filter(edge => ids.has(edge.source) && ids.has(edge.target)) }
  }, [graph, quality])

  useEffect(() => {
    const element = host.current
    if (!element || forceFallback) { setFallback(true); return }
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: resolvedQuality(quality, sceneGraph.nodes.length,window.innerWidth<760) !== 'LOW', alpha:true, powerPreference:'high-performance' }) }
    catch { setFallback(true); return }
    setFallback(false)
    const scene = new THREE.Scene(); scene.fog = new THREE.FogExp2(0x08090b, 0.022)
    const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 160); camera.position.set(0, 4, 26)
    const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping=true; controls.dampingFactor=.065; controls.minDistance=5; controls.maxDistance=72; controls.autoRotate=false
    const mode = resolvedQuality(quality, sceneGraph.nodes.length,window.innerWidth<760)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, mode === 'HIGH' ? 1.75 : mode === 'MEDIUM' ? 1.25 : 1))
    renderer.setClearColor(0x08090b, 1); renderer.domElement.setAttribute('aria-label','Mapa tridimensional da memória viva do Jarvis'); element.appendChild(renderer.domElement)
    scene.add(new THREE.AmbientLight(0x8c542c, .5)); const coreLight = new THREE.PointLight(STATE_COLOR[live.current.state], 14, 22, 2); scene.add(coreLight)

    const coreMaterial = new THREE.MeshStandardMaterial({color:STATE_COLOR[live.current.state],emissive:STATE_COLOR[live.current.state],emissiveIntensity:.72,roughness:.34,metalness:.45,wireframe:true})
    const core = new THREE.Mesh(new THREE.IcosahedronGeometry(1.55, 2), coreMaterial); scene.add(core)
    const substrate=new THREE.Group();const ringMaterial=new THREE.MeshBasicMaterial({color:0x6f3b1f,transparent:true,opacity:.12,wireframe:true})
    for(const [radius,tilt] of [[4.4,.3],[7.2,-.5],[10.5,.8]] as Array<[number,number]>){const ring=new THREE.Mesh(new THREE.TorusGeometry(radius,.018,3,96),ringMaterial);ring.rotation.x=Math.PI/2+tilt;ring.rotation.y=tilt*.7;substrate.add(ring)}
    const substratePositions:number[]=[];for(let i=0;i<260;i++){const angle=i*.618033*Math.PI*2,radius=3+(i%31)/31*13;substratePositions.push(Math.cos(angle)*radius,((i*17)%41)/41*12-6,Math.sin(angle)*radius)}
    const substrateGeometry=new THREE.BufferGeometry();substrateGeometry.setAttribute('position',new THREE.Float32BufferAttribute(substratePositions,3));const substratePoints=new THREE.Points(substrateGeometry,new THREE.PointsMaterial({color:0x7f4a29,size:.035,transparent:true,opacity:.2}));substrate.add(substratePoints);scene.add(substrate)
    const renderNodes = sceneGraph.nodes.filter(node => node.kind !== 'core')
    const sphere = new THREE.IcosahedronGeometry(.52, mode === 'LOW' ? 0 : 1)
    const nodeMaterial = new THREE.MeshStandardMaterial({roughness:.5,metalness:.28,transparent:true,opacity:.93,vertexColors:true})
    const instances = new THREE.InstancedMesh(sphere,nodeMaterial,renderNodes.length); instances.instanceMatrix.setUsage(THREE.DynamicDrawUsage)
    const dummy = new THREE.Object3D(); const color = new THREE.Color()
    renderNodes.forEach((node,index)=>{dummy.position.set(node.position.x,node.position.y,node.position.z);dummy.scale.setScalar(node.size);dummy.updateMatrix();instances.setMatrixAt(index,dummy.matrix);color.setHex(COLORS[node.cluster]||COLORS.other);instances.setColorAt(index,color)})
    instances.instanceMatrix.needsUpdate=true;if(instances.instanceColor)instances.instanceColor.needsUpdate=true;scene.add(instances)

    const byId=new Map(sceneGraph.nodes.map(node=>[node.id,node]));const edgePositions:number[]=[];const edgeColors:number[]=[]
    for(const edge of sceneGraph.edges){const a=byId.get(edge.source),b=byId.get(edge.target);if(!a||!b)continue;edgePositions.push(a.position.x,a.position.y,a.position.z,b.position.x,b.position.y,b.position.z);const base=edge.connection_class==='memory_relationship'?.22:edge.connection_class==='tool_connection'?.035:.08;const alpha=base+edge.weight*.18;edgeColors.push(.95*alpha,.48*alpha,.16*alpha,.95*alpha,.48*alpha,.16*alpha)}
    const linesGeometry=new THREE.BufferGeometry();linesGeometry.setAttribute('position',new THREE.Float32BufferAttribute(edgePositions,3));linesGeometry.setAttribute('color',new THREE.Float32BufferAttribute(edgeColors,3));const lines=new THREE.LineSegments(linesGeometry,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.72,blending:THREE.AdditiveBlending}));scene.add(lines)
    const pointsGeometry=new THREE.BufferGeometry();pointsGeometry.setAttribute('position',new THREE.Float32BufferAttribute(renderNodes.flatMap(node=>[node.position.x,node.position.y,node.position.z]),3));const points=new THREE.Points(pointsGeometry,new THREE.PointsMaterial({color:0xffb25c,size:mode==='LOW'?.07:.11,transparent:true,opacity:.32,blending:THREE.AdditiveBlending,sizeAttenuation:true}));scene.add(points)

    const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2()
    const click=(event:PointerEvent)=>{const rect=renderer.domElement.getBoundingClientRect();pointer.x=((event.clientX-rect.left)/rect.width)*2-1;pointer.y=-((event.clientY-rect.top)/rect.height)*2+1;raycaster.setFromCamera(pointer,camera);const hit=raycaster.intersectObject(instances)[0];live.current.onSelect(hit?.instanceId===undefined?undefined:renderNodes[hit.instanceId])}
    renderer.domElement.addEventListener('pointerup',click)
    const resize=()=>{const width=element.clientWidth,height=Math.max(260,element.clientHeight);camera.aspect=width/height;camera.updateProjectionMatrix();renderer.setSize(width,height,false)};const observer=new ResizeObserver(resize);observer.observe(element);resize()
    let frame=0,raf=0,last=performance.now(),fpsStart=last
    const animate=(now:number)=>{frame++;const elapsed=(now-last)/1000;last=now;const current=live.current;const active=current.state!=='IDLE';const stateColor=STATE_COLOR[current.state];coreMaterial.color.setHex(stateColor);coreMaterial.emissive.setHex(stateColor);coreLight.color.setHex(stateColor);core.rotation.y+=elapsed*(active ? .58 : .16);core.rotation.x+=elapsed*.08;const pulse=1+Math.sin(now*(active ? .004 : .0018))*(active ? .07 : .025);core.scale.setScalar(pulse);coreLight.intensity=(active?16:10)*(1+Math.sin(now*.003)*.08);points.rotation.y+=elapsed*.018;substrate.rotation.y+=elapsed*.006;renderNodes.forEach((node,index)=>{const boost=current.highlighted.has(node.id)?1.65:current.selectedId===node.id?1.38:1;dummy.position.set(node.position.x,node.position.y,node.position.z);dummy.scale.setScalar(node.size*boost);dummy.updateMatrix();instances.setMatrixAt(index,dummy.matrix);color.setHex(COLORS[node.cluster]||COLORS.other);if(current.highlighted.has(node.id)||current.selectedId===node.id)color.lerp(new THREE.Color(0xffe0a3),.58);instances.setColorAt(index,color)});instances.instanceMatrix.needsUpdate=true;if(instances.instanceColor)instances.instanceColor.needsUpdate=true;const focusNode=current.selectedId?byId.get(current.selectedId):undefined;if(focusNode){const target=new THREE.Vector3(focusNode.position.x,focusNode.position.y,focusNode.position.z);controls.target.lerp(target,.055);camera.position.lerp(target.clone().add(new THREE.Vector3(7,5,11)),.045)}controls.update();renderer.render(scene,camera);if(quality==='AUTO'&&now-fpsStart>2500){const fps=frame/((now-fpsStart)/1000);if(fps<27)renderer.setPixelRatio(.75);frame=0;fpsStart=now}raf=requestAnimationFrame(animate)};raf=requestAnimationFrame(animate)
    return()=>{cancelAnimationFrame(raf);observer.disconnect();renderer.domElement.removeEventListener('pointerup',click);controls.dispose();sphere.dispose();nodeMaterial.dispose();linesGeometry.dispose();pointsGeometry.dispose();substrateGeometry.dispose();ringMaterial.dispose();core.geometry.dispose();coreMaterial.dispose();renderer.dispose();renderer.domElement.remove()}
  },[sceneGraph,quality,resetKey,forceFallback])

  return <div className="cognitive-scene" ref={host}>{fallback&&<CognitiveFallback graph={sceneGraph} highlighted={highlighted} selectedId={selectedId} onSelect={onSelect}/>}</div>
}

export function CognitiveFallback({graph,highlighted,selectedId,onSelect}:{graph:CognitiveGraph;highlighted:Set<string>;selectedId?:string;onSelect:(node?:CognitiveNode)=>void}){
  const bounds=graphBounds(graph);const scale=26/Math.max(bounds.width,bounds.height);const point=(node:CognitiveNode)=>({x:50+node.position.x*scale,y:50-node.position.y*scale});const byId=new Map(graph.nodes.map(node=>[node.id,node]))
  return <svg className="cognitive-fallback" viewBox="0 0 100 100" role="img" aria-label="Mapa bidimensional acessível da memória viva do Jarvis"><g className="cognitive-substrate" aria-hidden="true"><circle cx="50" cy="50" r="12"/><circle cx="50" cy="50" r="24"/><circle cx="50" cy="50" r="38"/><path d="M8 50 Q28 18 50 50 T92 50"/><path d="M50 8 Q82 28 50 50 T50 92"/></g>{graph.edges.map((edge,index)=>{const a=byId.get(edge.source),b=byId.get(edge.target);if(!a||!b)return null;const pa=point(a),pb=point(b);return <line key={index} x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y} opacity={.18+edge.weight*.4}/>})}{graph.nodes.map(node=>{const p=point(node);return <circle key={node.id} cx={p.x} cy={p.y} r={node.kind==='core'?2.8:Math.max(.7,node.size)} className={`${node.kind} ${highlighted.has(node.id)?'highlighted':''} ${selectedId===node.id?'selected':''}`} onClick={()=>onSelect(node)}><title>{node.label}</title></circle>})}</svg>
}
