import * as THREE from 'three/webgpu';
import {sampleMotion,TAU} from './motion-engine.js';
const V=a=>new THREE.Vector3(...a);
export class MotionVisuals{
  constructor(scene){
    this.group=new THREE.Group();this.paths=new THREE.Group();this.skeleton=new THREE.Group();this.contacts=new THREE.Group();
    this.group.add(this.paths,this.skeleton,this.contacts);scene.add(this.group);this.group.visible=false;
    const cylinder=new THREE.CylinderGeometry(.0008,.0008,1,8),sphere=new THREE.SphereGeometry(.003,12,8);
    const material=new THREE.MeshBasicMaterial({color:'#f7f7f4',transparent:true,opacity:.6,depthTest:false,depthWrite:false});
    this.links=Array.from({length:8},()=>{const m=new THREE.Mesh(cylinder,material);m.renderOrder=8;this.skeleton.add(m);return m;});
    this.joints=Array.from({length:12},()=>{const m=new THREE.Mesh(sphere,material);m.renderOrder=9;this.skeleton.add(m);return m;});
    this.markers=Array.from({length:4},()=>{const m=new THREE.Mesh(new THREE.TorusGeometry(.015,.0007,8,40),new THREE.MeshBasicMaterial({color:'#e1e1dc',transparent:true,opacity:.5,depthWrite:false}));m.rotation.x=Math.PI/2;this.contacts.add(m);return m;});
  }
  rebuild(spec,motion){
    const key=JSON.stringify([spec,motion.id,motion.amplitude]);
    if(key===this.pathKey)return;this.pathKey=key;
    for(const child of [...this.paths.children]){child.geometry.dispose();child.material.dispose();this.paths.remove(child);}
    const frames=Array.from({length:97},(_,i)=>sampleMotion(spec,motion.id,i/96*TAU,motion.amplitude));
    for(let i=0;i<4;i++){
      const points=frames.map(f=>V(f.legs[i].worldFoot));
      const curve=new THREE.CatmullRomCurve3(points,false,'centripetal');
      const tube=new THREE.Mesh(new THREE.TubeGeometry(curve,120,.0005,5,false),new THREE.MeshBasicMaterial({color:i===0||i===3?'#b8b8b2':'#70706a',transparent:true,opacity:.5,depthWrite:false}));this.paths.add(tube);
    }
  }
  update(frame,options,active){
    this.group.visible=active;if(!active)return;
    this.paths.visible=options.paths;this.skeleton.visible=options.skeleton;
    const up=new THREE.Vector3(0,1,0);
    for(let i=0;i<4;i++){
      const leg=frame.legs[i],points=[leg.worldHip,leg.worldKnee,leg.worldFoot].map(V);
      for(let j=0;j<2;j++){
        const link=this.links[i*2+j],delta=points[j+1].clone().sub(points[j]);
        link.position.copy(points[j]).add(points[j+1]).multiplyScalar(.5);link.scale.y=delta.length();link.quaternion.setFromUnitVectors(up,delta.normalize());
      }
      for(let j=0;j<3;j++)this.joints[i*3+j].position.copy(points[j]);
      const marker=this.markers[i];marker.position.set(leg.worldFoot[0],.0019,leg.worldFoot[2]);marker.material.opacity=leg.contact?.65:.12;marker.scale.setScalar(leg.contact?1:.8);
    }
  }
}
