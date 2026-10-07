import * as THREE from 'three/webgpu';
const ros=v=>new THREE.Vector3(v[0],v[2],-v[1]);
export class PhysicsVisuals{
  constructor(scene){
    this.group=new THREE.Group();scene.add(this.group);this.group.visible=false;
    const material=new THREE.MeshBasicMaterial({color:'#fff',transparent:true,opacity:.7,depthWrite:false,depthTest:false});
    this.forces=Array.from({length:4},()=>{const group=new THREE.Group(),shaft=new THREE.Mesh(new THREE.CylinderGeometry(.001,.001,1,8),material),head=new THREE.Mesh(new THREE.ConeGeometry(.004,.008,8),material);group.add(shaft,head);this.group.add(group);return {group,shaft,head};});
    this.com=new THREE.Mesh(new THREE.SphereGeometry(.004,12,8),material);this.group.add(this.com);
    this.terrain=new THREE.Group();scene.add(this.terrain);this.terrain.visible=false;
    this.trails=new THREE.Group();scene.add(this.trails);this.points=Array.from({length:4},()=>[]);this.lastTime=-1;
    this.lines=Array.from({length:4},(_,i)=>{const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(new Float32Array(160*3),3).setUsage(THREE.DynamicDrawUsage));geometry.setDrawRange(0,0);
      const line=new THREE.Line(geometry,new THREE.LineBasicMaterial({color:['#fff','#aaa','#777','#555'][i],transparent:true,opacity:.6}));line.frustumCulled=false;this.trails.add(line);return line;});
  }
  reset(terrain){
    this.terrain.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material)o.material.dispose();});this.terrain.clear();
    const material=new THREE.MeshStandardMaterial({color:'#131313',roughness:.9});
    const floor=new THREE.Mesh(new THREE.PlaneGeometry(200,200),material),angle=terrain==='ramp'?5*Math.PI/180:0;
    floor.quaternion.setFromUnitVectors(new THREE.Vector3(0,0,1),new THREE.Vector3(Math.sin(angle),Math.cos(angle),0));floor.receiveShadow=true;this.terrain.add(floor);
    const grid=new THREE.GridHelper(200,2000,'#494949','#292929');grid.quaternion.setFromAxisAngle(new THREE.Vector3(0,0,1),-angle);grid.position.y=.0003;grid.material.transparent=true;grid.material.opacity=.25;this.terrain.add(grid);
    this.points=Array.from({length:4},()=>[]);this.lastTime=-1;
    if(terrain==='steps')for(let i=0;i<3;i++){const block=new THREE.Mesh(new THREE.BoxGeometry(.17,.03*(i+1),.6),material);block.position.set(.30+i*.17,.015*(i+1),0);block.receiveShadow=true;block.castShadow=true;this.terrain.add(block);}
  }
  update(frame,active,showForces,showPaths=false){
    this.group.visible=active&&showForces;this.terrain.visible=active;this.trails.visible=active&&showPaths;if(!frame||!active)return;
    if(frame.time_s>this.lastTime){frame.feet.forEach((foot,i)=>{this.points[i].push(ros(foot.position_m));if(this.points[i].length>160)this.points[i].shift();
      const geometry=this.lines[i].geometry,position=geometry.getAttribute('position');this.points[i].forEach((p,j)=>position.setXYZ(j,p.x,p.y,p.z));position.needsUpdate=true;geometry.setDrawRange(0,this.points[i].length);});this.lastTime=frame.time_s;}
    this.com.position.copy(ros(frame.com_m));
    frame.feet.forEach((foot,i)=>{const entry=this.forces[i],v=ros(foot.force_n),length=v.length()*.0012;entry.group.visible=length>.001;
      entry.group.position.copy(ros(foot.position_m));if(length>.001)entry.group.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),v.normalize());
      entry.shaft.scale.y=Math.min(.16,length);entry.shaft.position.y=Math.min(.16,length)/2;entry.head.position.y=Math.min(.16,length)+.004;});
  }
}
