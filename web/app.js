import * as THREE from 'three/webgpu';
import {OrbitControls} from './vendor/OrbitControls.js';
import {RoomEnvironment} from './vendor/RoomEnvironment.js';
import {CADWorkbench} from './cad-workbench.js';
import {MOTIONS,TAU,motionById,sampleMotion,blendMotion} from './motion-engine.js';
import {MotionPanel} from './motion-panel.js';
import {MotionVisuals} from './motion-visuals.js';
import {PhysicsPanel} from './physics-panel.js';
import {PhysicsVisuals} from './physics-visuals.js';
import {EngineeringPanel} from './engineering-panel.js';

const $=id=>document.getElementById(id);
const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
const params=new URLSearchParams(location.search);
const state={mode:'studio',explosion:0,explodeTarget:0,xray:false,dimensions:false,
  playing:!reduced,phase:0,turntable:false,dirty:false,building:false,online:false,selected:null,ready:false,section:false,tour:null,
  motion:{id:'trot',speed:1,amplitude:1,paths:true,skeleton:false,joints:true,sequence:false,sequenceElapsed:0,transition:null},physics:{enabled:false,frame:null,meta:null,dirty:false}};
let model,spec,renderer,scene,camera,controls,robot,dimensionGroup,supportGroup,clipGroup,cadGroup,cadWorkbench;
let meshes=[],geometryCache={},materials={},feet=[],lastTime=0,frames=0,fpsTime=0;
let hover=null,pointerDown=null,cameraTween=null,sourceTab='yaml',kernelSource='';
let motionPanel,motionVisuals,motionFrame;
let physicsPanel,physicsVisuals,studioStage,lightingRig,engineeringPanel;
const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();
const stage=$('stage');
const CADtoThree=v=>new THREE.Vector3(v[0]*.001,v[2]*.001,-v[1]*.001);
const rotation=deg=>new THREE.Quaternion().setFromEuler(new THREE.Euler(deg[0]*Math.PI/180,deg[2]*Math.PI/180,-deg[1]*Math.PI/180,'XYZ'));
const fmt=(v,n=2)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:n,maximumFractionDigits:n});
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').classList.remove('show'),4000);}
function download(name,text,type='application/json'){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1500);}
function lineBetween(a,b,r,color,parent){
  const delta=new THREE.Vector3().subVectors(b,a);const obj=new THREE.Mesh(new THREE.CylinderGeometry(r,r,delta.length(),8),new THREE.MeshBasicMaterial({color}));
  obj.position.copy(a).add(b).multiplyScalar(.5);obj.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),delta.normalize());parent.add(obj);return obj;
}
function addRing(radius,y,width,color,parent,opacity=1){const ring=new THREE.Mesh(new THREE.TorusGeometry(radius,width,8,160),new THREE.MeshBasicMaterial({color,transparent:opacity<1,opacity,depthWrite:opacity===1}));ring.rotation.x=Math.PI/2;ring.position.y=y;parent.add(ring);return ring;}
function makeCanvasTexture(draw,w=1024,h=256){const c=document.createElement('canvas');c.width=w;c.height=h;draw(c.getContext('2d'),w,h);const tex=new THREE.CanvasTexture(c);tex.colorSpace=THREE.SRGBColorSpace;return tex;}

async function boot(){
  try{
    const integrated=params.get('integrated');
    const modelResponse=window.__FORGE_MODEL__?null:await fetch(integrated?'/api/integration/model?revision='+encodeURIComponent(integrated):'./default-model.json');
    if(modelResponse&&!modelResponse.ok)throw new Error('Không đọc được cấu hình robot. Dựng lại cấu hình tích hợp.');
    model=window.__FORGE_MODEL__||await modelResponse.json();spec={...model.spec};
    if(!window.__FORGE_MODEL__)try{const health=await fetch('/api/health',{signal:AbortSignal.timeout(2000)});state.online=health.ok&&(await health.json()).status==='ready';}catch{}
    $('connection').textContent=state.online?'Kernel CAD đang chạy':'Snapshot CAD đã kiểm chứng';
    $('boot-text').textContent='Khởi tạo ánh sáng và hình học…';
    renderer=new THREE.WebGPURenderer({antialias:true,alpha:false,forceWebGL:params.get('backend')==='webgl'});
    renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(stage.clientWidth,stage.clientHeight);renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=.94;
    renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;
    await renderer.init();
    $('backend').textContent=renderer.backend.isWebGPUBackend?'WebGPU':'WebGL2';
    $('viewport').appendChild(renderer.domElement);
    scene=new THREE.Scene();scene.background=new THREE.Color('#090909');scene.fog=new THREE.Fog('#090909',1.6,4.0);
    const pmrem=new THREE.PMREMGenerator(renderer);scene.environment=pmrem.fromScene(new RoomEnvironment(),.035).texture;pmrem.dispose();
    scene.environmentIntensity=.70;
    camera=new THREE.PerspectiveCamera(34,1,.01,20);camera.position.set(.66,.38,.74);
    controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,.13,0);controls.enableDamping=true;controls.dampingFactor=.065;controls.minDistance=.45;controls.maxDistance=2.4;controls.maxPolarAngle=Math.PI*.49;controls.minPolarAngle=.09;controls.enablePan=false;
    controls.addEventListener('start',()=>{cameraTween=null;state.turntable=false;$('turntable').classList.remove('active');});
    const hemisphere=new THREE.HemisphereLight('#ffffff','#101010',.65);scene.add(hemisphere);
    const key=new THREE.DirectionalLight('#ffffff',3.4);key.position.set(-.6,1.2,.6);key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-.75;key.shadow.camera.right=.75;key.shadow.camera.top=.7;key.shadow.camera.bottom=-.7;key.shadow.camera.near=.1;key.shadow.camera.far=3;key.shadow.bias=-.0003;key.shadow.normalBias=.001;scene.add(key);
    const rim=new THREE.DirectionalLight('#ffffff',3.2);rim.position.set(.7,.7,-.8);scene.add(rim);
    const fill=new THREE.DirectionalLight('#ffffff',.9);fill.position.set(1,.15,.5);scene.add(fill);
    lightingRig=new THREE.Group();scene.add(lightingRig);lightingRig.add(key,rim,fill);
    const lightTarget=new THREE.Object3D();lightingRig.add(lightTarget);for(const light of [key,rim,fill])light.target=lightTarget;
    createStage();robot=new THREE.Group();scene.add(robot);clipGroup=new THREE.ClippingGroup();robot.add(clipGroup);
    dimensionGroup=new THREE.Group();scene.add(dimensionGroup);supportGroup=new THREE.Group();scene.add(supportGroup);
    materials=createMaterials();cadGroup=new THREE.Group();cadGroup.visible=false;scene.add(cadGroup);
    cadWorkbench=new CADWorkbench({open:openCAD,close:()=>setMode('studio'),spec:()=>spec,dirty:()=>state.dirty,edit:editCAD,build:compile,select:selectCADPart,pane:setCADPane,message:toast,
      example:()=>{Object.assign(spec,{link_width:32,bore_diameter:14,link_thickness:5});updateUI();markDirty();},
      invalid:()=>{Object.assign(spec,{link_width:18,bore_diameter:10});updateUI();markDirty();},
      proof:()=>{setMode('engineering');},source:()=>showSource('python')});
    motionVisuals=new MotionVisuals(scene);
    motionPanel=new MotionPanel(state,{model:()=>model,select:selectMotion,paths:refreshMotionPaths,message:toast});
    physicsVisuals=new PhysicsVisuals(scene);
    physicsPanel=new PhysicsPanel(state,{model:()=>model,mode:()=>{if(state.mode!=='motion')setMode('motion');motionPanel.stopSequence();},kinematic:()=>{motionPanel.sync();resize();},
      frame:()=>{},reset:(_,terrain)=>{physicsVisuals.reset(terrain);resize();}});
    assemble(model);updateUI();bindUI();resize();
    engineeringPanel=new EngineeringPanel(state,{model:()=>model,pause:()=>physicsPanel.suspend(),install:installModel});
    if(params.has('record'))import('./capture-ui.js');
    new ResizeObserver(resize).observe(stage);
    renderer.setAnimationLoop(animate);
    if(!reduced){state.explosion=.45;state.explodeTarget=0;}
    state.ready=true;window.forge={state,get model(){return model;},get renderer(){return renderer;},setMode,build:compile,
      motion:{programs:MOTIONS,select:selectMotion,seek:phase=>{state.phase=phase;state.playing=false;state.motion.transition=null;motionPanel.sync();},sample:(id,phase,amplitude=1)=>sampleMotion(model.spec,id,phase,amplitude),export:type=>motionPanel.export(type),get frame(){return motionFrame;}},
      inspect:()=>({ready:state.ready,backend:renderer.backend.isWebGPUBackend?'webgpu':'webgl2',revision:model.revision,metrics:model.metrics,checks:model.proof.checks,frames,mode:state.mode,explosion:state.explosion,meshCount:meshes.length,
        motion:motionFrame?{program:state.motion.id,phase:motionFrame.phase,contacts:motionFrame.contactCount,maxErrorMm:motionFrame.maxErrorMm,minPadBottomMm:Math.min(...motionFrame.legs.map(l=>l.padBottomMm)),clamped:motionFrame.clamped}:null})};
    $('cad-open').disabled=!!model.integration;if(params.get('workspace')==='cad'&&!model.integration)openCAD();
    if(model.integration){$('engineering-open').disabled=true;document.querySelector('[data-mode="cad"]')?.setAttribute('disabled','');}
    if(params.get('workspace')==='motion'){setMode('motion');if(params.has('motion'))selectMotion(params.get('motion'));}
    if(params.get('workspace')==='physics'){state.motion.id=params.get('motion')||'stand';setMode('motion');physicsPanel.activate(true);setTimeout(()=>physicsPanel.start(),400);}
    if(params.get('workspace')==='ai'){await engineeringPanel.open();if(params.has('experiment'))await engineeringPanel.load(params.get('experiment'));}
    setTimeout(()=>$('boot').classList.add('gone'),reduced?0:250);
  }catch(e){console.error(e);$('boot-text').textContent='Không khởi tạo được: '+e.message;}
}

function createStage(){
  studioStage=new THREE.Group();scene.add(studioStage);
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(8,8),new THREE.MeshStandardMaterial({color:'#080808',roughness:.55,metalness:.18}));floor.rotation.x=-Math.PI/2;floor.position.y=-.028;floor.receiveShadow=true;studioStage.add(floor);
  const plinth=new THREE.Mesh(new THREE.CylinderGeometry(.42,.423,.017,160),new THREE.MeshPhysicalMaterial({color:'#171717',metalness:.38,roughness:.40,clearcoat:.35}));plinth.position.y=-.0085;plinth.receiveShadow=true;studioStage.add(plinth);
  addRing(.420,-.001,.0004,'#606060',studioStage,.25);
  addRing(.389,.0002,.0002,'#555555',studioStage,.15);
}

function createMaterials(){
  const carbonTexture=makeCanvasTexture((ctx,w,h)=>{
    ctx.fillStyle='#202020';ctx.fillRect(0,0,w,h);
    for(let i=-h;i<w;i+=12){ctx.strokeStyle='#292929';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(i,0);ctx.lineTo(i+h,h);ctx.stroke();}
  },64,64);carbonTexture.wrapS=carbonTexture.wrapT=THREE.RepeatWrapping;
  return {
    metal:new THREE.MeshPhysicalMaterial({color:'#b7b7b7',metalness:.86,roughness:.25,clearcoat:.25}),
    shell:new THREE.MeshPhysicalMaterial({color:'#ededeb',metalness:.16,roughness:.25,clearcoat:.9,clearcoatRoughness:.23}),
    carbon:new THREE.MeshPhysicalMaterial({color:'#aaaaaa',map:carbonTexture,metalness:.08,roughness:.48,clearcoat:.25}),
    motor:new THREE.MeshPhysicalMaterial({color:'#484848',metalness:.87,roughness:.23,clearcoat:.35}),
    dark:new THREE.MeshPhysicalMaterial({color:'#101010',metalness:.35,roughness:.20,clearcoat:.9}),
    rubber:new THREE.MeshStandardMaterial({color:'#141414',roughness:.83,metalness:0}),
    glass:new THREE.MeshPhysicalMaterial({color:'#080808',metalness:.75,roughness:.07,clearcoat:1}),
    battery:new THREE.MeshStandardMaterial({color:'#252525',metalness:.25,roughness:.42}),
    bolt:new THREE.MeshStandardMaterial({color:'#aaaaaa',metalness:.95,roughness:.24}),
    emission:new THREE.MeshBasicMaterial({color:'#dedede'}),
    trim:new THREE.MeshStandardMaterial({color:'#242424',metalness:.7,roughness:.30}),
  };
}

function disposeGroup(group){
  group.traverse(o=>{if(o.isMesh){if(o.userData.ownedGeometry||group===dimensionGroup||group===supportGroup)o.geometry.dispose();if(o.userData.ownedMaterial||group===dimensionGroup||group===supportGroup)o.material.dispose();}});group.clear();
}
function assemble(data){
  disposeGroup(clipGroup);Object.values(geometryCache).forEach(g=>g.dispose());geometryCache={};meshes=[];feet=[];
  materials.metal.color.set('#555555');materials.shell.color.set(data.materials[data.spec.material].color);
  if(data.spec.material==='pa12'){materials.metal.metalness=.12;materials.metal.roughness=.43;materials.shell.metalness=.08;materials.shell.roughness=.39;}else{materials.metal.metalness=.87;materials.metal.roughness=.27;materials.shell.metalness=.16;materials.shell.roughness=.25;}
  for(const [key,part]of Object.entries(data.parts)){
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(part.positions,3));g.setIndex(part.indices);g.setAttribute('uv',new THREE.Float32BufferAttribute(part.positions.flatMap((v,i,a)=>i%3===0?[v*60,a[i+1]*60]:[]),2));g.computeVertexNormals();g.computeBoundingSphere();geometryCache[key]=g;
  }
  for(const inst of data.instances){
    const part=data.parts[inst.part];const root=new THREE.Group();root.userData={instance:inst,part:inst.part};root.position.copy(CADtoThree(inst.position_mm));root.quaternion.copy(rotation(inst.rotation_deg));
    const mat=materials[part.role].clone();const mesh=new THREE.Mesh(geometryCache[inst.part],mat);mesh.castShadow=true;mesh.receiveShadow=true;mesh.userData={instance:inst,part:inst.part,ownedMaterial:true};root.add(mesh);clipGroup.add(root);
    meshes.push({root,mesh,instance:inst,base:root.position.clone(),quaternion:root.quaternion.clone(),explode:CADtoThree(inst.explode_mm)});
    if(inst.part==='foot')feet.push(root);
    embellish(root,inst,part,data.spec);
  }
  motionFrame=sampleMotion(data.spec,'stand',0);refreshMotionPaths();motionPanel?.chart();
  updateDimensions();updateProof();updateSupport();
}

function embellish(root,inst,part,s){
  // Fine graphics and fasteners are display accents; the hull and fairings are CAD.
  const simple=(g,mat,pos,rot)=>{const m=new THREE.Mesh(g,mat);m.position.set(...pos);if(rot)m.rotation.set(...rot);m.castShadow=true;m.userData.ownedGeometry=true;root.add(m);return m;};
  if(inst.part==='motor'){
    simple(new THREE.CylinderGeometry(.0218,.0218,.0006,64),materials.dark,[0,-.0085,0]);
    simple(new THREE.TorusGeometry(.0225,.0005,8,96),materials.bolt,[0,-.009,0],[Math.PI/2,0,0]);
    simple(new THREE.TorusGeometry(.008,.00035,8,48),materials.trim,[0,-.009,0],[Math.PI/2,0,0]);
    for(let i=0;i<6;i++){const a=i*Math.PI/3;simple(new THREE.CylinderGeometry(.0014,.0014,.0008,6),materials.bolt,[.017*Math.cos(a),-.0093,.017*Math.sin(a)]);}
  }
  if(inst.part==='cover'){
    const L=s.body_length*.001;
    const decal=makeCanvasTexture((ctx,w,h)=>{ctx.fillStyle='#bbbbbb';ctx.font='500 100px Helvetica';ctx.textAlign='center';ctx.fillText('Q4',w*.5,h*.65);},256,128);
    const mat=new THREE.MeshBasicMaterial({map:decal,transparent:true,depthWrite:false});
    const m=simple(new THREE.PlaneGeometry(.027,.0135),mat,[L*.29,.0017,0],[-Math.PI/2,0,Math.PI/2]);m.userData.ownedMaterial=true;
    for(const x of[-L*.4,L*.4])for(const z of[-s.body_width*.00034,s.body_width*.00034])simple(new THREE.CylinderGeometry(.0025,.0025,.0007,6),materials.bolt,[x,.0019,z]);
  }
  if(inst.part==='lens'){
    simple(new THREE.TorusGeometry(.0046,.0003,8,64),materials.bolt,[0,.0033,0],[Math.PI/2,0,0]);
    simple(new THREE.CylinderGeometry(.0025,.0025,.0004,48),materials.glass,[0,.0035,0]);
  }
  if(inst.part==='sensor')simple(new THREE.BoxGeometry(.0005,.0008,.024),materials.emission,[.0073,0,0]);
}

function updateTransforms(){
  studioStage.visible=!(state.mode==='motion'&&state.physics.enabled);
  if(state.mode==='motion'&&state.physics.enabled&&state.physics.frame){
    const base=state.physics.frame.base_position_m;lightingRig.position.set(base[0],0,-base[1]);
    robot.position.set(0,0,0);robot.quaternion.identity();
    const lookup=new Map(state.physics.frame.instances.map(i=>[i.id,i]));
    for(const item of meshes){const pose=lookup.get(item.instance.id);if(pose){item.root.position.fromArray(pose.position_m);item.root.quaternion.fromArray(pose.quaternion_xyzw);}}
    robot.updateMatrixWorld(true);motionVisuals.group.visible=false;
    physicsVisuals.update(state.physics.frame,true,state.motion.skeleton,state.motion.paths);return;
  }
  physicsVisuals.update(null,false,false);
  lightingRig.position.set(0,0,0);
  const moving=state.mode==='motion'&&state.explosion<.01;
  robot.position.set(0,.105*state.explosion,0);robot.quaternion.identity();
  if(moving){
    const next=sampleMotion(model.spec,state.motion.id,state.phase,state.motion.amplitude),transition=state.motion.transition;
    motionFrame=transition?blendMotion(model.spec,transition.from,next,Math.min(1,transition.elapsed/.65)):next;
    robot.position.fromArray(motionFrame.origin);robot.quaternion.fromArray(motionFrame.quaternion);
  }
  for(const item of meshes){
    let p=item.base.clone(),q=item.quaternion.clone();const id=item.instance.id;
    if(moving&&/^(front|rear)_/.test(id)){
      const leg=motionFrame.legs.find(l=>id.startsWith(l.id+'_')),part=item.instance.part;
      if(id.endsWith('_roll')||part==='shoulder'){p.fromArray(leg.anchor);q.premultiply(new THREE.Quaternion().fromArray(leg.rollQ));}
      else if(id.endsWith('_hip')){p.fromArray(leg.hipMotor);q.premultiply(new THREE.Quaternion().fromArray(leg.upperQ));}
      else if(id.endsWith('_knee')){p.fromArray(leg.kneeMotor);q.premultiply(new THREE.Quaternion().fromArray(leg.lowerQ));}
      else if(part==='upper'||part==='upper_fairing'){p.fromArray(leg.upper);q.fromArray(leg.upperQ);}
      else if(part==='lower'||part==='lower_fairing'){p.fromArray(leg.lower);q.fromArray(leg.lowerQ);}
      else if(part==='foot'){p.fromArray(leg.foot);q.fromArray(leg.footQ);}
    }
    item.root.position.copy(p).addScaledVector(item.explode,state.explosion);item.root.quaternion.copy(q);
  }
  robot.updateMatrixWorld(true);
  motionVisuals?.update(motionFrame,state.motion,moving);
}

function refreshMotionPaths(){if(model&&motionVisuals)motionVisuals.rebuild(model.spec,state.motion);}
function selectMotion(id){
  if(!MOTIONS.some(m=>m.id===id))return;
  const from=motionFrame||sampleMotion(model.spec,'stand',0);
  state.motion.id=id;state.phase=0;state.motion.transition=reduced?null:{from,elapsed:0};
  if(state.mode!=='motion')setMode('motion');
  $('stage-caption').textContent=motionById(id).description;
  motionPanel.sync();motionPanel.chart();refreshMotionPaths();
  if(state.physics.enabled)physicsPanel.invalidate();
}

function updateDimensions(){
  disposeGroup(dimensionGroup);dimensionGroup.visible=state.dimensions;
  const s=model.spec,L=s.body_length*.001,W=s.body_width*.001,H=model.metrics.height_mm*.001;
  const col='#b0b0b0',r=.0007;
  lineBetween(new THREE.Vector3(-L/2,.015,.22),new THREE.Vector3(L/2,.015,.22),r,col,dimensionGroup);
  for(const x of[-L/2,L/2])lineBetween(new THREE.Vector3(x,.006,.205),new THREE.Vector3(x,.024,.235),r,col,dimensionGroup);
  lineBetween(new THREE.Vector3(-.25,0,0),new THREE.Vector3(-.25,H,0),r,col,dimensionGroup);
  for(const y of[0,H])lineBetween(new THREE.Vector3(-.27,y,0),new THREE.Vector3(-.23,y,0),r,col,dimensionGroup);
  lineBetween(new THREE.Vector3(.24,.014,-W/2),new THREE.Vector3(.24,.014,W/2),r,col,dimensionGroup);
  for(const z of[-W/2,W/2])lineBetween(new THREE.Vector3(.23,.006,z),new THREE.Vector3(.25,.024,z),r,col,dimensionGroup);
  $('dim-length').textContent=`Thân ${s.body_length} mm`;$('dim-height').textContent=`Cao ${fmt(model.metrics.height_mm,0)} mm`;$('dim-width').textContent=`Rộng ${s.body_width} mm`;
}
function projectLabel(id,world){const v=world.clone().project(camera);const el=$(id);el.style.left=(v.x*.5+.5)*stage.clientWidth+'px';el.style.top=(-v.y*.5+.5)*stage.clientHeight+'px';el.style.transform='translate(-50%,-50%)';el.style.display=state.dimensions?'block':'none';}

function convexHull(points){const pts=[...points].sort((a,b)=>a.x-b.x||a.y-b.y);const cross=(o,a,b)=>(a.x-o.x)*(b.y-o.y)-(a.y-o.y)*(b.x-o.x);const low=[],up=[];for(const p of pts){while(low.length>=2&&cross(low.at(-2),low.at(-1),p)<=0)low.pop();low.push(p);}for(const p of pts.reverse()){while(up.length>=2&&cross(up.at(-2),up.at(-1),p)<=0)up.pop();up.push(p);}low.pop();up.pop();return low.concat(up);}
function supportInfo(){
  let sum=new THREE.Vector3(),mass=0;
  for(const item of meshes){const part=model.parts[item.instance.part];const local=CADtoThree(part.com_mm||[0,0,0]);const p=item.root.localToWorld(local);sum.addScaledVector(p,part.mass_kg);mass+=part.mass_kg;}
  const extra=model.spec.payload_kg+model.spec.electronics_mass_kg;sum.addScaledVector(new THREE.Vector3(0,(model.metrics.height_mm-model.spec.body_height/2)*.001,0),extra);mass+=extra;
  const com=sum.divideScalar(mass);const hull=convexHull(feet.map(root=>new THREE.Vector2(root.position.x,root.position.z)));
  let margin=Infinity;for(let i=0;i<hull.length;i++){const a=hull[i],b=hull[(i+1)%hull.length];const dx=b.x-a.x,dz=b.y-a.y;const d=(dx*(com.z-a.y)-dz*(com.x-a.x))/Math.hypot(dx,dz);margin=Math.min(margin,d);}
  return {com,hull,margin};
}
function updateSupport(){
  updateTransforms();disposeGroup(supportGroup);supportGroup.visible=state.mode==='engineering';
  const {com,hull,margin}=supportInfo();const points=hull.map(p=>new THREE.Vector3(p.x,.0015,p.y));
  for(let i=0;i<points.length;i++)lineBetween(points[i],points[(i+1)%points.length],.0009,'#aaaaaa',supportGroup);
  const shape=new THREE.Shape(hull.map(p=>new THREE.Vector2(p.x,-p.y)));const fill=new THREE.Mesh(new THREE.ShapeGeometry(shape),new THREE.MeshBasicMaterial({color:'#aaaaaa',transparent:true,opacity:.12,side:THREE.DoubleSide,depthWrite:false}));fill.rotation.x=-Math.PI/2;fill.position.y=.001;fill.userData.ownedGeometry=true;fill.userData.ownedMaterial=true;supportGroup.add(fill);
  lineBetween(new THREE.Vector3(com.x,.003,com.z),com,.0008,'#ffffff',supportGroup);
  const marker=new THREE.Mesh(new THREE.SphereGeometry(.005,16,12),new THREE.MeshBasicMaterial({color:'#ffffff'}));marker.position.copy(com);marker.userData.ownedGeometry=true;marker.userData.ownedMaterial=true;supportGroup.add(marker);
  const ring=new THREE.Mesh(new THREE.TorusGeometry(.012,.0009,8,32),new THREE.MeshBasicMaterial({color:'#ffffff'}));ring.rotation.x=Math.PI/2;ring.position.set(com.x,.003,com.z);ring.userData.ownedGeometry=true;ring.userData.ownedMaterial=true;supportGroup.add(ring);
  window.__support={margin_mm:margin*1000,com_mm:com.toArray().map(v=>v*1000)};
}

function refreshCADPart(key=cadWorkbench?.selected||'frame'){
  cadGroup.traverse(o=>{if(o.isMesh||o.isLineSegments){if(o.isLineSegments)o.geometry.dispose();o.material.dispose();}});cadGroup.clear();
  const g=geometryCache[key];g.computeBoundingBox();const centre=g.boundingBox.getCenter(new THREE.Vector3());
  const solid=new THREE.Mesh(g,new THREE.MeshPhysicalMaterial({color:'#d0d0d0',metalness:.55,roughness:.3,clearcoat:.3}));solid.position.set(-centre.x,.13-centre.y,-centre.z);solid.castShadow=true;
  const edges=new THREE.LineSegments(new THREE.EdgesGeometry(g,25),new THREE.LineBasicMaterial({color:'#444444',transparent:true,opacity:.65}));edges.position.copy(solid.position);cadGroup.add(solid,edges);
  const size=g.boundingBox.getSize(new THREE.Vector3());const distance=Math.max(size.x,size.y,size.z)*2.8;
  controls.minDistance=.05;cameraTween=null;camera.position.set(distance*.55,.13+distance*.25,distance*.82);controls.target.set(0,.13,0);
}
function selectCADPart(key){if(!state.ready&&state.mode!=='cad')return;refreshCADPart(key);document.querySelector('.machine-name').textContent=model.parts[key].name;}
function setCADPane(pane){if(cadGroup)cadGroup.visible=state.mode==='cad'&&pane==='solid';}
function openCAD(){
  stopTour();setXray(false);setSection(false);setDimensions(false);toggleProof(false);state.mode='cad';state.explosion=0;state.explodeTarget=0;state.turntable=false;
  document.querySelector('.workspace').classList.remove('motion-active');motionVisuals.group.visible=false;$('motion-rail').hidden=true;$('motion-hud').hidden=true;$('motion-options').hidden=true;
  stage.dataset.mode='cad';robot.visible=false;supportGroup.visible=false;cadGroup.visible=true;refreshCADPart();cadWorkbench.enter(model,spec,state.online,state.dirty);
  $('stage-caption').textContent='Khối CAD thật. Kéo để xoay.';
  stage.querySelector('.stage-foot > span').textContent='Kéo để xoay · Cuộn để thu phóng';
  document.querySelector('.machine-name').textContent=model.parts[cadWorkbench.selected].name;$('hero-label').hidden=true;
  resize();
}
function editCAD(key,value){spec[key]=value;updateUI();markDirty();}
function setMode(mode){
  if(mode!=='motion'&&physicsPanel)physicsPanel.suspend();
  if(state.mode==='cad'){controls.minDistance=.45;cadWorkbench.exit();cadGroup.visible=false;robot.visible=true;document.querySelector('.machine-name').innerHTML='Q4<span> / 01</span>';stage.querySelector('.stage-foot > span').textContent='Kéo để xoay · Cuộn để thu phóng · Chọn chi tiết';}
  stage.dataset.mode=mode;
  state.mode=mode;document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
  document.querySelector('.workspace').classList.toggle('motion-active',mode==='motion');$('motion-rail').hidden=mode!=='motion';$('motion-hud').hidden=mode!=='motion';
  if(mode==='motion'){state.explosion=0;setDimensions(false);motionPanel.sync();}
  else state.motion.sequence=false;
  state.explodeTarget=mode==='explode'?Number($('explosion').value):0;
  $('explode-options').hidden=mode!=='explode';$('motion-options').hidden=mode!=='motion';
  const caption={studio:'Cấu trúc thật. Hình học có thể đo.',explode:`${model.metrics.part_count} chi tiết CAD. Một cấu trúc có thể đọc.`,motion:motionById(state.motion.id).description,engineering:'Kiểm khối, công thức và STEP độc lập.'};
  $('stage-caption').textContent=caption[mode];$('hero-label').hidden=mode!=='studio';
  if(mode==='engineering'){state.explosion=0;toggleProof(true);setDimensions(true);updateSupport();}
  else{supportGroup.visible=false;toggleProof(false);if(mode==='explode')setDimensions(false);}
  if(mode==='explode')moveCamera('explode');else moveCamera(mode==='motion'?'motion':'hero');
}
function toggleProof(open=$('proof-panel').hidden){$('proof-panel').hidden=!open;stage.classList.toggle('proof-open',open);if(stage.clientWidth>700&&open)camera.setViewOffset(stage.clientWidth,stage.clientHeight,145,0,stage.clientWidth,stage.clientHeight);else if(state.mode==='motion'&&state.physics.enabled&&innerWidth>820)camera.setViewOffset(stage.clientWidth,stage.clientHeight,80,0,stage.clientWidth,stage.clientHeight);else camera.clearViewOffset();camera.updateProjectionMatrix();}
function setDimensions(on){state.dimensions=on;dimensionGroup.visible=on;$('dimensions').classList.toggle('active',on);}
function setXray(on){state.xray=on;$('xray').classList.toggle('active',on);for(const item of meshes){const mat=item.mesh.material;mat.transparent=on;mat.opacity=on?(item.instance.part==='cover'?.14:.36):1;mat.depthWrite=!on;mat.needsUpdate=true;}clipGroup.traverse(o=>{if(o.isMesh&&!o.userData.instance)o.visible=!on;});}
function setSection(on){state.section=on;clipGroup.clippingPlanes=on?[new THREE.Plane(new THREE.Vector3(0,0,-1),0)]:[];clipGroup.clipShadows=true;$('section-view').classList.toggle('active',on);if(on)toast('Mặt cắt chỉ dùng để xem; STEP vẫn là khối nguyên vẹn.');}
function moveCamera(view){
  const map={motion:[.87,.46,.98],hero:[.66,.38,.74],explode:[1.05,.68,1.23],side:[0,.32,.96],front:[.96,.30,0],top:[.0001,1.02,.001]};
  const p=map[view];if(!p)return;const target=new THREE.Vector3(...p),base=state.physics.frame?.base_position_m;
  if(state.mode==='motion'&&state.physics.enabled&&base)target.add(new THREE.Vector3(base[0],0,-base[1]));
  cameraTween={from:camera.position.clone(),to:target,start:performance.now(),duration:reduced?1:800};
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
}
function resize(){const w=stage.clientWidth,h=stage.clientHeight;const drawer=document.querySelector('.motion-joint-drawer'),parent=innerWidth<=820?$('motion-mobile-joints'):$('motion-hud');if(drawer&&drawer.parentElement!==parent)parent.appendChild(drawer);renderer.setSize(w,h);camera.aspect=w/h;camera.zoom=Math.min(1,Math.max(.55,camera.aspect/1.1))*(state.mode==='motion'&&state.physics.enabled&&innerWidth>820?.82:1);toggleProof(!$('proof-panel').hidden);camera.updateProjectionMatrix();}

function animate(time){
  if(!$('engineering-panel').hidden){lastTime=time;fpsTime=time;frames=0;return;}
  const elapsed=(time-lastTime)/1000||.016,dt=Math.min(elapsed,.05);lastTime=time;
  if(state.mode==='motion'&&!state.physics.enabled){
    if(state.motion.transition&&!state.motion.transition.paused){state.motion.transition.elapsed+=dt;if(state.motion.transition.elapsed>=.65)state.motion.transition=null;}
    if(state.playing){
      state.phase=(state.phase+dt*state.motion.speed/motionById(state.motion.id).duration*TAU)%TAU;
      if(state.motion.sequence){state.motion.sequenceElapsed+=dt;if(state.motion.sequenceElapsed>=5){state.motion.sequenceElapsed=0;selectMotion(MOTIONS[(MOTIONS.findIndex(m=>m.id===state.motion.id)+1)%MOTIONS.length].id);}}
    }
  }
  state.explosion+= (state.explodeTarget-state.explosion)*(reduced?1:1-Math.exp(-Math.min(elapsed,.5)*5));
  if(Math.abs(state.explodeTarget-state.explosion)<.0002)state.explosion=state.explodeTarget;
  if(cameraTween){const t=Math.min(1,(time-cameraTween.start)/cameraTween.duration),smooth=t*t*(3-2*t);camera.position.lerpVectors(cameraTween.from,cameraTween.to,smooth);if(t===1)cameraTween=null;}
  const physical=state.mode==='motion'&&state.physics.enabled&&state.physics.frame;
  if(physical){const p=state.physics.frame.base_position_m,dx=(p[0]-controls.target.x)*(1-Math.exp(-dt*5)),dz=(-p[1]-controls.target.z)*(1-Math.exp(-dt*5));controls.target.x+=dx;controls.target.z+=dz;if(!cameraTween){camera.position.x+=dx;camera.position.z+=dz;}}
  else{controls.target.x*=Math.exp(-dt*5);controls.target.z*=Math.exp(-dt*5);}
  controls.target.y+=( (state.mode==='explode'?.22:state.mode==='motion'?.04:.13)-controls.target.y)*(1-Math.exp(-dt*5));
  controls.autoRotate=state.turntable&&!reduced;controls.autoRotateSpeed=.8;controls.update();updateTransforms();
  const s=model.spec;projectLabel('dim-length',new THREE.Vector3(0,.02,.23));projectLabel('dim-height',new THREE.Vector3(-.25,model.metrics.height_mm*.0005,0));projectLabel('dim-width',new THREE.Vector3(.255,.025,0));
  updateTour(time);physicsPanel.tick(time);if(motionFrame)motionPanel.update(motionFrame,time);renderer.render(scene,camera);frames++;if(time-fpsTime>1000){$('fps').textContent=Math.round(frames*1000/(time-fpsTime))+' fps';frames=0;fpsTime=time;}
}

function updateUI(){
  for(const key of ['body_length','body_width','upper_length','lower_length','payload_kg']){$(key).value=spec[key];$('value-'+key).textContent=key==='payload_kg'?fmt(spec[key],1)+' kg':spec[key];setRangeFill($(key));}
  document.querySelectorAll('[data-material]').forEach(b=>b.classList.toggle('active',b.dataset.material===spec.material));
  $('mass').innerHTML=fmt(model.metrics.mass_kg)+'<small>kg</small>';$('height').innerHTML=fmt(model.metrics.height_mm,0)+'<small>mm</small>';$('part-count').textContent=model.metrics.part_count;
  $('revision').textContent='revision '+model.revision.slice(0,8);$('proof-revision').textContent=model.revision;
  state.dirty=false;$('build-state').classList.remove('dirty');$('build-state').textContent=state.online?'Thông số và mô hình đồng bộ.':'Snapshot: chạy Start.command để dựng lại CAD.';
  $('build').disabled=!state.online;
  if(cadWorkbench?.current)cadWorkbench.render(spec,state.dirty);
  if(!state.online||model.integration)document.querySelectorAll('#spec-form input,#spec-form [data-material],[data-preset],#command,#apply-command').forEach(el=>el.disabled=true);
  if(model.integration){$('build').disabled=true;$('reset').disabled=true;$('build-state').textContent='Cấu hình lắp đã kiểm. Đổi gá trong AI CAD rồi dựng lại cấu hình tích hợp.';}
}
function setRangeFill(el){const pct=100*(el.value-el.min)/(el.max-el.min);el.style.background=`linear-gradient(to right,#222222 ${pct}%,#d9d9d7 ${pct}%)`;}
function markDirty(){state.dirty=true;$('build-state').classList.add('dirty');$('build-state').textContent='Thông số đã đổi. Dựng lại để cập nhật mô hình CAD.';document.querySelectorAll('[data-preset]').forEach(b=>b.classList.remove('active'));if(cadWorkbench?.current)cadWorkbench.dirty(spec);}

function updateProof(){
  const checks=model.proof.checks,passed=checks.filter(c=>c.passed).length;
  $('proof-summary').textContent=`${passed}/${checks.length} kiểm tra đạt`;$('proof-trigger').querySelector('i').style.background=passed===checks.length?'var(--good)':'var(--accent)';
  $('checks').innerHTML=checks.map(c=>`<div class="check ${c.passed?'':'fail'}"><span class="check-icon">${c.passed?'✓':'!'}</span><div><strong>${c.name}</strong><small>${c.method}</small><p>${c.detail}</p></div></div>`).join('');
  $('volume-table').innerHTML=model.proof.analytic.map(a=>`<div class="volume-row"><span>${a.part==='upper'?'Chân trên':'Chân dưới'}</span><strong>${fmt(a.cad_mm3,1)} mm³</strong></div><div class="volume-row"><span>Sai lệch với công thức</span><strong>${(a.relative_error*100).toExponential(2)}%</strong></div>`).join('');
  const r=model.proof.roundtrip;$('roundtrip-detail').innerHTML=r?`<div class="roundtrip-value">${(r.relative_error*100).toExponential(2)}%<span>sai lệch thể tích</span></div><div class="volume-row"><span>Khối đọc lại</span><strong>${r.solid_count}</strong></div>`:'Chưa đọc lại STEP';
}
async function compile(){
  if(state.building)return;if(!state.online){toast('Mở Start.command để chạy kernel CAD.');return;}
  state.building=true;if(state.mode==='cad')cadWorkbench.busy();$('build').disabled=true;$('build').querySelector('span').textContent='Đang dựng và kiểm…';$('build-state').textContent='Python → BREP → công thức → STEP round-trip';$('build-state').classList.remove('dirty');
  try{
    const resp=await fetch('/api/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(spec)});const data=await resp.json();if(!resp.ok)throw new Error(data.error);
    await installModel(data);
    toast(`Đã dựng ${data.metrics.part_count} chi tiết · ${fmt(data.duration_ms/1000,2)} giây · revision ${data.revision.slice(0,8)}`);
  }catch(e){if(cadWorkbench.current)cadWorkbench.result(null,spec,e.message,state.online);$('build-state').textContent=e.message;$('build-state').classList.add('dirty');toast(e.message);}
  finally{state.building=false;$('build').disabled=false;$('build').querySelector('span').textContent='Dựng lại thiết kế';}
}

async function installModel(data,accepted=null){
  if(physicsPanel.session){await physicsPanel.control('pause');state.physics.frame=null;physicsPanel.frame=null;physicsPanel.invalidate();}
  model=data;spec={...data.spec};state.dirty=false;state.explosion=0;assemble(data);updateUI();setXray(state.xray);
  if(state.mode==='engineering')updateSupport();if(cadWorkbench.current)cadWorkbench.result(data,spec,null,state.online);if(state.mode==='cad')refreshCADPart();
  $('build-state').textContent='CAD '+data.revision+' đã dựng và kiểm.';$('build-state').classList.remove('dirty');
  physicsPanel.acceptedProfile=accepted?.actuator_profile||null;physicsPanel.acceptedOperations=accepted?.operations||null;
  if(accepted?.actuator_profile?.torque_limit_nm)$('physics-torque').value=accepted.actuator_profile.torque_limit_nm;
  if(accepted?.operations){$('operations-enabled').checked=true;$('operations-temperature').value=accepted.operations.initial_motor_c;$('operations-soc').value=accepted.operations.initial_soc;$('operations-fault').value=accepted.operations.failed_joint;$('operations-health').value=accepted.operations.joint_health;}
}
async function showSource(tab=sourceTab){
  sourceTab=tab;$('source-modal').hidden=false;document.querySelectorAll('[data-source]').forEach(b=>b.classList.toggle('active',b.dataset.source===tab));
  if(tab==='yaml')$('source-content').textContent=Object.entries(spec).map(([k,v])=>`${k}: ${v}`).join('\n');
  if(tab==='bom')$('source-content').textContent=Object.entries(model.parts).map(([k,p])=>`${p.name}\n  Số lượng: ${p.count}\n  Khối lượng / chi tiết: ${fmt(p.mass_kg*1000,1)} g\n  Cơ sở: ${p.mass_basis}\n  Thể tích CAD: ${fmt(p.volume_mm3,1)} mm³\n`).join('\n')+`\nĐiện tử bổ sung: ${spec.electronics_mass_kg} kg (giả định)\nTải bổ sung: ${spec.payload_kg} kg\n\nRender có chi tiết trang trí không nằm trong STEP.\n\n`+model.limitations.join('\n');
  if(tab==='python'){
    if(!kernelSource){try{kernelSource=window.__FORGE_SOURCE__||(await(await fetch('/api/source')).json()).source;}catch{kernelSource='Mở kernel.py trong bộ mã nguồn để xem compiler đầy đủ.';}}
    $('source-content').textContent=kernelSource;
  }
}

function applyCommand(){
  const text=$('command').value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');let count=0;const next={...spec};
  const rules=[['body_length',/(?:than|body|chieu dai than)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)/],['body_width',/(?:rong|be rong)\s*(?:than)?\s*(?:=|:)?\s*(\d+(?:\.\d+)?)/],['upper_length',/(?:chan tren|upper)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)/],['lower_length',/(?:chan duoi|lower)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)/],['payload_kg',/(?:tai|payload)\s*(?:=|:)?\s*(\d+(?:\.\d+)?)/]];
  for(const [key,re]of rules){const m=text.match(re);if(m){const v=Number(m[1]),el=$(key);if(v<Number(el.min)||v>Number(el.max)){toast(`${key} phải nằm trong ${el.min}–${el.max}.`);return;}next[key]=v;count++;}}
  if(/pa12/.test(text)){next.material='pa12';count++;}else if(/nhom|alum/.test(text)){next.material='aluminium';count++;}else if(/thep|steel/.test(text)){next.material='steel';count++;}
  if(!count){$('command-result').textContent='Chưa hiểu lệnh. Dùng tên thông số và giá trị, ví dụ “thân 360, chân dưới 180, PA12”.';return;}
  spec=next;updateUI();markDirty();$('command-result').textContent=`Đã cập nhật ${count} thông số. Bấm “Dựng lại thiết kế” để chạy kernel.`;
}

function bindUI(){
  $('spec-form').addEventListener('submit',e=>{e.preventDefault();compile();});
  for(const key of ['body_length','body_width','upper_length','lower_length','payload_kg'])$(key).addEventListener('input',e=>{spec[key]=Number(e.target.value);$('value-'+key).textContent=key==='payload_kg'?fmt(spec[key],1)+' kg':spec[key];setRangeFill(e.target);markDirty();});
  document.querySelectorAll('[data-material]').forEach(b=>b.addEventListener('click',()=>{spec.material=b.dataset.material;document.querySelectorAll('[data-material]').forEach(x=>x.classList.toggle('active',x===b));markDirty();}));
  const presets={precision:{body_length:340,body_width:180,upper_length:110,lower_length:140,material:'aluminium',payload_kg:1},light:{body_length:300,body_width:168,upper_length:110,lower_length:126,material:'pa12',payload_kg:.5},reach:{body_length:360,body_width:194,upper_length:140,lower_length:174,material:'aluminium',payload_kg:1}};
  document.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>{Object.assign(spec,presets[b.dataset.preset]);updateUI();markDirty();b.classList.add('active');compile();}));
  document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.mode)));
  document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>moveCamera(b.dataset.view)));
  $('dimensions').addEventListener('click',()=>setDimensions(!state.dimensions));$('xray').addEventListener('click',()=>setXray(!state.xray));
  $('section-view').addEventListener('click',()=>setSection(!state.section));$('tour').addEventListener('click',()=>state.tour?stopTour():startTour());
  $('turntable').addEventListener('click',()=>{state.turntable=!state.turntable;$('turntable').classList.toggle('active',state.turntable);});
  $('fullscreen').addEventListener('click',()=>document.fullscreenElement?document.exitFullscreen():(params.has('record')?document.documentElement:stage).requestFullscreen());
  $('proof-trigger').addEventListener('click',()=>toggleProof($('proof-panel').hidden));$('close-proof').addEventListener('click',()=>toggleProof(false));
  $('explosion').addEventListener('input',e=>{state.explodeTarget=Number(e.target.value);$('explode-value').textContent=Math.round(state.explodeTarget*100)+'%';});
  $('open-source').addEventListener('click',()=>showSource());$('close-source').addEventListener('click',()=>$('source-modal').hidden=true);$('source-modal').addEventListener('click',e=>{if(e.target===$('source-modal'))$('source-modal').hidden=true;});
  document.querySelectorAll('[data-source]').forEach(b=>b.addEventListener('click',()=>showSource(b.dataset.source)));
  $('download-spec').addEventListener('click',()=>download('forge-q4.yaml',Object.entries(spec).map(([k,v])=>`${k}: ${v}`).join('\n'),'text/yaml'));
  $('export-proof').addEventListener('click',()=>download('forge-q4-proof.json',JSON.stringify({revision:model.revision,compiler_hash:model.compiler_hash,spec:model.spec,metrics:model.metrics,proof:model.proof,support_projection:window.__support,limitations:model.limitations},null,2)));
  $('export-step').addEventListener('click',()=>{if(state.dirty){toast('Đặc tả đang khác mô hình. Dựng lại trước khi xuất STEP.');return;}if(window.__FORGE_STEP__){const a=document.createElement('a');a.href=window.__FORGE_STEP__;a.download='forge-q4.step';a.click();}else{const a=document.createElement('a');a.href=model.step_url;a.download='forge-q4.step';a.click();}toast('Đang tải STEP của phiên bản '+model.revision.slice(0,8));});
  $('inject-fault').addEventListener('click',async()=>{
    if(!state.online){$('fault-result').textContent='Cần kernel chạy để tiêm lỗi thật.';return;}
    $('inject-fault').disabled=true;
    try{const r=await fetch('/api/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...model.spec,link_width:18,bore_diameter:10})});const result=await r.json();$('fault-result').textContent=r.status===422?'ĐÃ CHẶN · '+result.error:'Không đạt: kernel đã không chặn đặc tả lỗi.';window.__fault={status:r.status,result};}catch(e){$('fault-result').textContent=e.message;}finally{$('inject-fault').disabled=false;}
  });
  $('apply-command').addEventListener('click',applyCommand);$('command').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();applyCommand();}});
  $('reset').addEventListener('click',async()=>{const defaultData=window.__FORGE_MODEL__||await(await fetch('./default-model.json')).json();spec={...defaultData.spec};updateUI();document.querySelectorAll('[data-preset]').forEach(b=>b.classList.toggle('active',b.dataset.preset==='precision'));if(state.online)compile();});
  renderer.domElement.addEventListener('pointermove',onPointerMove);renderer.domElement.addEventListener('pointerleave',()=>{$('part-tooltip').style.display='none';hover=null;});
  renderer.domElement.addEventListener('pointerdown',e=>{pointerDown=[e.clientX,e.clientY];});
  renderer.domElement.addEventListener('pointerup',e=>{if(pointerDown&&Math.hypot(e.clientX-pointerDown[0],e.clientY-pointerDown[1])<5&&hover){state.selected=hover.userData.instance.id;toast(`${model.parts[hover.userData.part].name} · ${hover.userData.instance.id}`);}pointerDown=null;});
  document.addEventListener('keydown',e=>{if(/INPUT|TEXTAREA/.test(e.target.tagName))return;if(e.key==='Escape'){stopTour();$('source-modal').hidden=true;toggleProof(false);}if(state.mode==='cad')return;if(e.key.toLowerCase()==='d')setDimensions(!state.dimensions);if(e.key.toLowerCase()==='x')setXray(!state.xray);if(e.key.toLowerCase()==='s')setSection(!state.section);if(e.key.toLowerCase()==='e')setMode(state.mode==='explode'?'studio':'explode');if(e.code==='Space'){e.preventDefault();setMode(state.mode==='motion'?'studio':'motion');}});
}
function onPointerMove(e){
  if(state.mode==='cad'){hover=null;$('part-tooltip').style.display='none';return;}
  const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);
  const hits=raycaster.intersectObjects(meshes.map(m=>m.mesh),false);hover=hits[0]?.object||null;
  for(const item of meshes){if(item.mesh.material.emissive)item.mesh.material.emissive.set(item.mesh===hover?'#555555':'#000000');}
  renderer.domElement.style.cursor=hover?'pointer':'grab';const tip=$('part-tooltip');tip.style.display=hover?'block':'none';
  if(hover){const part=model.parts[hover.userData.part];tip.innerHTML=`${part.name}<small>${hover.userData.instance.id}</small><strong>${fmt(part.mass_kg*1000,1)} g</strong><small>${part.mass_basis}</small>`;tip.style.left=Math.min(e.clientX-rect.left+15,rect.width-210)+'px';tip.style.top=Math.min(e.clientY-rect.top+15,rect.height-120)+'px';}
}
const tourShots=[
  {title:'Từ thông số đến hình khối.',desc:'Đặc tả dẫn động 42 chi tiết CAD. Mô hình trên sân khấu được lấy trực tiếp từ BREP.',mode:'studio',view:'hero'},
  {title:'Đọc được từng cơ cấu.',desc:'Tách cấu trúc để thấy thân, pin, actuator và các tay chân. Chọn một chi tiết để xem số đo.',mode:'explode',view:'explode'},
  {title:'Nhìn vào bên trong.',desc:'Mặt cắt hiển thị làm lộ khoang pin và kết cấu rỗng. File STEP giữ nguyên hình khối.',mode:'studio',view:'side',section:true},
  {title:'Bốn chân. Nhiều nhịp.',desc:'Cặp chân chéo luân phiên. Quỹ đạo và góc khớp được giải từ chiều dài CAD.',mode:'motion',view:'hero',motion:'trot'},
  {title:'Một hệ khớp, nhiều động tác.',desc:'Vẫy chân với thân chuyển nhẹ sang phía các chân còn lại.',mode:'motion',view:'front',motion:'wave'},
  {title:'Từ tư thế đến chu kỳ.',desc:'Thu chân, bật nhún và hạ xuống. Minh họa động học, chưa mô phỏng lực.',mode:'motion',view:'side',motion:'jump'},
  {title:'Hình đẹp cần bằng chứng.',desc:'Khối hợp lệ, công thức độc lập, STEP đọc lại và khe hở hình học. Thử đặc tả lỗi để thấy gate chặn.',mode:'engineering',view:'hero'},
];
function startTour(){if(state.physics.enabled)physicsPanel.activate(false);state.tour={start:performance.now(),shot:-1};$('tour').textContent='□ Dừng trình diễn';$('tour-caption').hidden=false;}
function stopTour(){state.tour=null;$('tour').textContent='▷ Trình diễn';$('tour-caption').hidden=true;setSection(false);setMode('studio');setDimensions(false);}
function updateTour(time){if(!state.tour)return;const elapsed=time-state.tour.start,shot=Math.floor(elapsed/6500);if(shot>=tourShots.length){stopTour();return;}if(shot!==state.tour.shot){const s=tourShots[shot];state.tour.shot=shot;setXray(false);setSection(false);setDimensions(false);setMode(s.mode);moveCamera(s.view);if(s.motion){state.playing=true;selectMotion(s.motion);}if(s.section)setSection(true);$('tour-number').textContent=`${shot+1} / ${tourShots.length}`;$('tour-title').textContent=s.title;$('tour-description').textContent=s.desc;}$('tour-progress').style.width=((elapsed%6500)/6500*100)+'%';}
boot();
