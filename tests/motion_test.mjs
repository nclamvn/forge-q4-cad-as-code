import assert from 'node:assert/strict';
import fs from 'node:fs';
import {MOTIONS,TAU,sampleMotion,blendMotion,rotate,trajectory} from '../web/motion-engine.js';
import {createHash} from 'node:crypto';
import {MotionPanel} from '../web/motion-panel.js';
const model=JSON.parse(fs.readFileSync(new URL('../web/default-model.json',import.meta.url)));
const spec=model.spec;
const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
let frames=0,worstError=0,minPadBottom=Infinity,minCadVertexY=Infinity;
const variants=[spec,{...spec,upper_length:126,lower_length:140,body_length:284,body_width:168},
  {...spec,upper_length:174,lower_length:194,body_length:360,body_width:208},
  {...spec,upper_length:190,lower_length:110}, {...spec,upper_length:110,lower_length:210}];
// Independent reference: compare home positions to the original CAD assembly,
// not another evaluation of the motion solver's forward-kinematics formula.
const home=sampleMotion(spec,'stand',0,1);
for(const leg of home.legs){
  for(const [suffix,key] of [['upper','upper'],['knee','kneeMotor'],['lower','lower'],['foot','foot']]){
    const inst=model.instances.find(i=>i.id===leg.id+'_'+suffix),[x,y,z]=inst.position_mm;
    assert.ok(distance(leg[key],[x/1000,z/1000,-y/1000])<1e-9,leg.id+'_'+suffix);
  }
  assert.ok(leg.commands.every(v=>Math.abs(v)<1e-10));
}
for(const s of variants)for(const m of MOTIONS)for(const amplitude of [.25,1,1.35]){
  for(let n=0;n<120;n++){
    const f=sampleMotion(s,m.id,n/120*TAU,amplitude);frames++;
    for(const leg of f.legs){
      assert.ok([...leg.worldFoot,...leg.angles,...f.origin,...f.quaternion].every(Number.isFinite));
      assert.ok(Math.abs(distance(leg.upper,leg.kneePoint)-s.upper_length/1000)<1e-10);
      assert.ok(Math.abs(distance(leg.lower,leg.foot)-s.lower_length/1000)<1e-10);
      assert.ok(leg.commands.every(v=>Math.abs(v)<=s.joint_limit_deg*Math.PI/180+1e-10));
      worstError=Math.max(worstError,leg.errorMm);minPadBottom=Math.min(minPadBottom,leg.padBottomMm);
      if(s===spec){assert.ok(leg.errorMm<1e-6,`${m.id} residual ${leg.errorMm}`);assert.ok(leg.padBottomMm>=.99);}
    }
    if(s===spec&&(m.id==='walk'||m.id==='reverse'))assert.ok(f.contactCount>=3);
    if(s===spec&&['stand','crouch','sit','bow','balance'].includes(m.id))assert.equal(f.contactCount,4);
  }
  const first=sampleMotion(s,m.id,0,amplitude),last=sampleMotion(s,m.id,TAU,amplitude);
  assert.ok(distance(first.origin,last.origin)<1e-9);
  for(let j=0;j<4;j++)assert.ok(distance(first.legs[j].worldFoot,last.legs[j].worldFoot)<1e-9,'loop seam '+m.id);
}
// Every choreography is materially distinct from the old, single sinusoid.
const signatures=MOTIONS.map(m=>JSON.stringify([.2,.4,.6].map(p=>sampleMotion(spec,m.id,p*TAU).legs.flatMap(l=>l.worldFoot).map(v=>v.toFixed(6)))));
assert.equal(new Set(signatures).size,MOTIONS.length);
assert.ok(sampleMotion(spec,'wave',.45*TAU).legs[0].worldFoot[1]>.06);
assert.equal(sampleMotion(spec,'jump',.53*TAU).contactCount,0);
// Independent floor check against the tessellated foot from the CAD snapshot.
// The analytic pad support function alone must not be its own only oracle.
const footPositions=model.parts.foot.positions;
for(const m of MOTIONS)for(let n=0;n<60;n++){
  const f=sampleMotion(spec,m.id,n/60*TAU,1.35);
  for(const leg of f.legs)for(let i=0;i<footPositions.length;i+=3){
    const local=rotate(footPositions.slice(i,i+3),leg.footQ);
    const world=rotate(local.map((v,j)=>v+leg.foot[j]),f.quaternion);
    minCadVertexY=Math.min(minCadVertexY,(world[1]+f.origin[1])*1000);
  }
}
assert.ok(minCadVertexY>=.99,'CAD foot vertices penetrate floor');
// Transitions re-solve a linked chain rather than lerping disconnected meshes.
for(const from of MOTIONS)for(const to of MOTIONS){
  const a=sampleMotion(spec,from.id,.43*TAU),b=sampleMotion(spec,to.id,.1*TAU);
  for(const t of [0,.2,.5,.8,1]){
    const f=blendMotion(spec,a,b,t);assert.ok(f.maxErrorMm<1e-6);
    assert.ok(f.legs.every(l=>l.padBottomMm>=.99));
  }
}
const samples=trajectory(spec,'walk',1,2);
assert.equal(samples.at(-1).seconds,MOTIONS.find(m=>m.id==='walk').duration/2);
assert.equal(samples[0].legs.length,4);
// Execute the real UI export method with only the browser download sink stubbed.
// Parse the resulting Blob: test output content, not a duplicate CSV formatter.
const downloads=[],createObjectURL=URL.createObjectURL;
let pendingBlob;
globalThis.document={createElement:()=>({click(){downloads.push({name:this.download,blob:pendingBlob});}})};
URL.createObjectURL=blob=>{pendingBlob=blob;return createObjectURL(blob);};
try{
  const panel={state:{motion:{id:'wave',amplitude:1.35,speed:2}},callbacks:{model:()=>model,message:()=>{}}};
  MotionPanel.prototype.export.call(panel,'json');MotionPanel.prototype.export.call(panel,'csv');
}finally{URL.createObjectURL=createObjectURL;delete globalThis.document;}
const exported=JSON.parse(await downloads[0].blob.text());
assert.equal(exported.cad_revision,model.revision);assert.deepEqual(exported.cad_spec,spec);
assert.equal(exported.sample_rate_hz,60);assert.equal(exported.samples.length,145);
assert.equal(exported.samples.at(-1).seconds,2.4);assert.match(exported.scope,/Not a hardware control program/);
const csv=(await downloads[1].blob.text()).trim().split('\n').map(line=>line.split(','));
assert.equal(csv.length,145*4+1);assert.ok(csv.every(row=>row.length===15));
assert.equal(csv[0][0],'cad_revision');assert.ok(csv.slice(1).every(row=>row[0]===model.revision&&row[1]==='wave'&&row.slice(2).filter((_,i)=>i!==1).every(value=>Number.isFinite(Number(value)))));
const report={status:'passed',cad_revision:model.revision,
  source_sha256:Object.fromEntries(['motion-engine.js','motion-panel.js','motion-visuals.js'].map(name=>[name,createHash('sha256').update(fs.readFileSync(new URL('../web/'+name,import.meta.url))).digest('hex')])),
  motion_count:MOTIONS.length,sampled_frames:frames,spec_variants:variants.length,
  default_ik_residual_bound_mm:0.000001,default_pad_bottom_bound_mm:.99,
  all_variants_max_ik_residual_mm:worstError,all_variants_min_pad_bottom_mm:minPadBottom,
  default_cad_foot_vertex_min_y_mm:minCadVertexY,
  transition_pairs:MOTIONS.length**2,reference:'Original CAD instance placements and link lengths',
  export_check:{formats:['JSON','CSV'],sample_rate_hz:60,frames:145,csv_data_rows:580,csv_columns:15},
  scope:'Kinematics only. These tests do not establish stability, forces, torque, actuator limits or whole-robot collision freedom.'};
fs.mkdirSync(new URL('../reports/motion/',import.meta.url),{recursive:true});
fs.writeFileSync(new URL('../reports/motion/kinematics.json',import.meta.url),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
