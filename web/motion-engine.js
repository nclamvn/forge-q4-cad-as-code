/** Kinematic choreography in metres and radians. No force/contact simulation. */
export const TAU = Math.PI * 2;
export const LEGS = [
  {id:'front_left',label:'Trước trái',short:'TT',front:1,side:1},
  {id:'front_right',label:'Trước phải',short:'TP',front:1,side:-1},
  {id:'rear_left',label:'Sau trái',short:'ST',front:-1,side:1},
  {id:'rear_right',label:'Sau phải',short:'SP',front:-1,side:-1},
];
export const MOTIONS = [
  {id:'stand',name:'Đứng quan sát',group:'Tư thế',duration:4,duty:1,offsets:[0,0,0,0],description:'Thân thở nhẹ. Bốn chân giữ nền.'},
  {id:'walk',name:'Bước chậm',group:'Di chuyển',duration:2.4,duty:.76,offsets:[0,.5,.75,.25],description:'Bốn chân đổi lượt. Ba chân ở pha đặt chân.'},
  {id:'trot',name:'Chạy chéo',group:'Di chuyển',duration:1.15,duty:.58,offsets:[0,.5,.5,0],description:'Hai cặp chân chéo luân phiên.'},
  {id:'pace',name:'Bước cùng bên',group:'Di chuyển',duration:1.5,duty:.6,offsets:[0,.5,0,.5],description:'Cặp chân trái và phải đổi nhịp.'},
  {id:'bound',name:'Chạy bật',group:'Di chuyển',duration:1.05,duty:.48,offsets:[0,0,.5,.5],description:'Cặp chân trước và sau phối hợp nhún thân.'},
  {id:'reverse',name:'Lùi bước',group:'Di chuyển',duration:2.1,duty:.76,offsets:[0,.5,.75,.25],description:'Quỹ đạo bước đảo chiều, chân nâng rồi đặt.'},
  {id:'sidestep',name:'Bước ngang',group:'Di chuyển',duration:1.9,duty:.64,offsets:[0,.5,.5,0],description:'Khớp dạng chân mở quỹ đạo theo phương ngang.'},
  {id:'turn',name:'Xoay tại chỗ',group:'Di chuyển',duration:3.2,duty:.65,offsets:[0,.5,.5,0],description:'Thân đổi hướng. Quỹ đạo chân chạy theo cung.'},
  {id:'crouch',name:'Hạ trọng tâm',group:'Tư thế',duration:3.8,duty:1,offsets:[0,0,0,0],description:'Hạ và nâng thân với bàn chân bám cao độ nền.'},
  {id:'sit',name:'Ngồi nghỉ',group:'Tư thế',duration:5,duty:1,offsets:[0,0,0,0],description:'Chân sau gập sâu, thân nghiêng và hạ thấp.'},
  {id:'bow',name:'Cúi chào',group:'Biểu diễn',duration:3.6,duty:1,offsets:[0,0,0,0],description:'Thân cúi về trước, chân giải theo vị trí đặt.'},
  {id:'wave',name:'Vẫy chân',group:'Biểu diễn',duration:4.8,duty:1,offsets:[0,0,0,0],description:'Nhấc chân trước trái và vẫy, thân chuyển nhẹ sang bên.'},
  {id:'balance',name:'Chuyển trọng tâm',group:'Tư thế',duration:4.4,duty:1,offsets:[0,0,0,0],description:'Thân đi vòng nhỏ với bốn bàn chân giữ vị trí.'},
  {id:'dance',name:'Nhịp phối hợp',group:'Biểu diễn',duration:2.2,duty:.68,offsets:[0,.5,.5,0],description:'Nhún, nghiêng và đổi nhịp hai cặp chân chéo.'},
  {id:'jump',name:'Bật nhún',group:'Biểu diễn',duration:3,duty:1,offsets:[0,0,0,0],description:'Thu chân, nâng thân, pha trên không rồi hạ về tư thế CAD.'},
];
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const smooth=v=>{v=clamp(v,0,1);return v*v*v*(v*(v*6-15)+10);};
const add=(a,b)=>a.map((v,i)=>v+b[i]);
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
const lerp=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
const norm=a=>Math.hypot(...a);
export const motionById=id=>MOTIONS.find(m=>m.id===id)||MOTIONS[2];
export function quaternion([x,y,z]){
  const a=Math.sin(x/2),b=Math.cos(x/2),c=Math.sin(y/2),d=Math.cos(y/2),e=Math.sin(z/2),f=Math.cos(z/2);
  return [a*d*f+b*c*e,b*c*f-a*d*e,b*d*e+a*c*f,b*d*f-a*c*e];
}
export function multiplyQuaternion(a,b){
  const [x,y,z,w]=a,[X,Y,Z,W]=b;
  return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z];
}
export function rotate(v,q){
  const [x,y,z,w]=q,[a,b,c]=v;
  const tx=2*(y*c-z*b),ty=2*(z*a-x*c),tz=2*(x*b-y*a);
  return [a+w*tx+y*tz-z*ty,b+w*ty+z*tx-x*tz,c+w*tz+x*ty-y*tx];
}
function conjugate(q){return [-q[0],-q[1],-q[2],q[3]];}
function wrap(v){return Math.atan2(Math.sin(v),Math.cos(v));}
export function dimensions(s){
  const upper=s.upper_length/1000,lower=s.lower_length/1000;
  return {upper,lower,height:(upper+lower)*Math.cos(.62)+.025,length:s.body_length/1000,
    width:s.body_width/1000,gap:(s.link_thickness+3)/1000,limit:s.joint_limit_deg*Math.PI/180};
}
export function homeFeet(spec){
  const d=dimensions(spec);
  return LEGS.map(l=>[l.front*(d.length*.34+(d.lower-d.upper)*Math.sin(.62)),.017,
    -l.side*(d.width/2+.028+d.gap)]);
}
/** Solve roll + signed two-link IK, retaining the CAD's mirrored knee branch. */
export function solveLeg(spec,leg,localTarget){
  const d=dimensions(spec),sx=leg.front,sy=leg.side;
  const anchor=[sx*d.length*.34,d.height-.008,-sy*(d.width/2+.002)];
  const target=sub(localTarget,anchor),offset=.026+d.gap;
  const reach=Math.sqrt(Math.max(.000001,target[1]**2+target[2]**2-offset**2));
  const rollRaw=wrap(Math.atan2(target[2],target[1])-Math.atan2(-sy*offset,-reach));
  const roll=clamp(rollRaw,-Math.min(.5,d.limit),Math.min(.5,d.limit));
  const distance=clamp(Math.hypot(target[0],reach),Math.abs(d.upper-d.lower)+.006,d.upper+d.lower-.004);
  const kneeRaw=sx*Math.acos(clamp((distance**2-d.upper**2-d.lower**2)/(2*d.upper*d.lower),-1,1));
  const knee=clamp(kneeRaw,sx*1.24-d.limit,sx*1.24+d.limit);
  const hipRaw=Math.atan2(target[0],reach)-Math.atan2(d.lower*Math.sin(knee),d.upper+d.lower*Math.cos(knee));
  const hip=clamp(hipRaw,-sx*.62-d.limit,-sx*.62+d.limit);
  const rollQ=quaternion([roll,0,0]);
  const upperQ=multiplyQuaternion(rollQ,quaternion([0,0,hip]));
  const lowerQ=multiplyQuaternion(rollQ,quaternion([0,0,hip+knee]));
  const upper=add(anchor,rotate([0,0,-sy*.026],rollQ));
  const kneePoint=add(upper,rotate([d.upper*Math.sin(hip),-d.upper*Math.cos(hip),0],rollQ));
  const lower=add(kneePoint,rotate([0,0,-sy*d.gap],rollQ));
  const foot=add(lower,rotate([d.lower*Math.sin(hip+knee),-d.lower*Math.cos(hip+knee),0],rollQ));
  const footQ=multiplyQuaternion(rollQ,quaternion([0,0,hip+knee-sx*.62]));
  return {id:leg.id,anchor,upper,kneePoint,lower,foot,rollQ,upperQ,lowerQ,footQ,
    hipMotor:add(upper,rotate([0,0,-sy*.008],rollQ)),
    kneeMotor:add(kneePoint,rotate([0,0,-sy*.008],rollQ)),
    angles:[roll,hip,knee],commands:[roll,hip+sx*.62,knee-sx*1.24],
    limited:Math.abs(roll-rollRaw)>1e-5||Math.abs(knee-kneeRaw)>1e-5||Math.abs(hip-hipRaw)>1e-5||distance!==Math.hypot(target[0],reach)};
}
/** Rounded 26×24×32 mm pad, R6: projection of core box + radius. */
function padHalfHeight(q){const up=rotate([0,1,0],conjugate(q));return .007*Math.abs(up[0])+.010*Math.abs(up[1])+.006*Math.abs(up[2])+.006;}
export function solvePose(spec,body,targets,contacts){
  const d=dimensions(spec),pivot=[0,d.height,0],q=quaternion(body.angles);
  const origin=sub(add(pivot,body.position),rotate(pivot,q)),inverse=conjugate(q);
  const legs=LEGS.map((leg,i)=>{
    // Keep the fixed pad attached to the lower link. Adjust its centre for the
    // pad's rotated support height rather than inventing an extra ankle joint.
    let target=[...targets[i]],solved;
    const lift=Math.max(0,target[1]-.017);
    for(let k=0;k<8;k++){
      solved=solveLeg(spec,leg,rotate(sub(target,origin),inverse));
      const y=.001+padHalfHeight(multiplyQuaternion(q,solved.footQ))+lift;
      if(Math.abs(y-target[1])<1e-8)break;
      target[1]=y;
    }
    solved=solveLeg(spec,leg,rotate(sub(target,origin),inverse));
    const worldFoot=add(origin,rotate(solved.foot,q));
    const worldQ=multiplyQuaternion(q,solved.footQ);
    const padBottom=worldFoot[1]-padHalfHeight(worldQ);
    return {...solved,target,worldFoot,worldKnee:add(origin,rotate(solved.kneePoint,q)),
      worldHip:add(origin,rotate(solved.upper,q)),contact:contacts[i]&&padBottom<.003,
      errorMm:norm(sub(worldFoot,target))*1000,padBottomMm:padBottom*1000};
  });
  return {body,origin,quaternion:q,legs,contactCount:legs.filter(l=>l.contact).length,
    maxErrorMm:Math.max(...legs.map(l=>l.errorMm)),clamped:legs.some(l=>l.limited)};
}
function envelope(p){return Math.sin(Math.PI*p)**2;}
export function gaitSample(phase,duty){
  const p=((phase%1)+1)%1;
  if(p<duty)return {x:.5-smooth(p/duty),lift:0,contact:true};
  const swing=(p-duty)/(1-duty);
  return {x:-.5+smooth(swing),lift:Math.sin(Math.PI*swing)**2,contact:false};
}
export function sampleMotion(spec,id,phase,amplitude=1){
  const program=motionById(id),p=((phase/TAU%1)+1)%1,a=clamp(amplitude,.25,1.35);
  const d=dimensions(spec),scale=Math.min(d.upper,d.lower)/.11;
  const targets=homeFeet(spec),contacts=[true,true,true,true];
  const body={position:[0,0,0],angles:[0,0,0]};
  const wave=Math.sin(TAU*p),pulse=envelope(p);
  if(program.group==='Di chuyển'||id==='dance'){
    const stride=(id==='bound'?.07:id==='walk'?.052:.06)*a*scale;
    const height=(id==='bound'?.031:id==='walk'?.019:.026)*a*scale;
    for(let i=0;i<4;i++){
      const step=gaitSample(p+program.offsets[i],program.duty);
      if(id==='sidestep')targets[i][2]+=step.x*stride;
      else if(id==='turn'){
        const angle=step.x*.38*a;
        const [x,y,z]=targets[i];targets[i]=[x*Math.cos(angle)+z*Math.sin(angle),y,z*Math.cos(angle)-x*Math.sin(angle)];
      }else targets[i][0]+=step.x*stride*(id==='reverse'?-1:1);
      targets[i][1]+=step.lift*height;contacts[i]=step.contact;
    }
    body.position[1]=Math.sin(TAU*p*2)*.0025*a;
    body.angles[2]=id==='bound'?wave*.048*a:Math.sin(TAU*p)*.012*a;
    if(id==='walk'||id==='reverse')body.position[2]=Math.sin(TAU*p)*.003*a;
    if(id==='turn')body.angles[1]=wave*.30*a;
    if(id==='dance'){
      body.position[1]=Math.sin(TAU*p*2)*.012*a;
      body.angles=[wave*.065*a,Math.sin(TAU*p)*.12*a,Math.cos(TAU*p)*.055*a];
    }
  }else if(id==='stand'){
    body.position[1]=pulse*.0018*a;body.angles[1]=wave*.017*a;
  }else if(id==='crouch')body.position[1]=-pulse*.043*a*scale;
  else if(id==='sit'){
    body.position[1]=-pulse*.049*a*scale;body.position[0]=-pulse*.018*a;
    body.angles[2]=pulse*.15*a;
  }else if(id==='bow'){
    body.position[1]=-pulse*.019*a*scale;body.angles[2]=-pulse*.20*a;
  }else if(id==='wave'){
    const hold=smooth(p/.2)*(1-smooth((p-.78)/.22));
    body.position[0]=-.009*hold*a;body.position[2]=.011*hold*a;
    body.position[1]=-.006*hold*a;body.angles[0]=-.025*hold*a;
    targets[0][1]+=.061*hold*a*scale;
    targets[0][0]+=.008*hold*a;
    targets[0][2]+=Math.sin(TAU*p*3)*.016*hold*a;
    contacts[0]=hold<.01;
  }else if(id==='balance'){
    body.position=[Math.sin(TAU*p)*.014*a,pulse*-.004*a,Math.sin(TAU*p*2)*.011*a];
    body.angles=[Math.sin(TAU*p*2)*.032*a,0,wave*.035*a];
  }else if(id==='jump'){
    if(p<.28)body.position[1]=-.035*envelope(p/.56)*a*scale;
    else if(p<.78){
      const u=(p-.28)/.5,flight=envelope(u);
      body.position[1]=(-.035*(1-smooth(u/.17))+.070*flight)*a*scale;
      const lift=(.091*flight)*a*scale;
      for(let i=0;i<4;i++){targets[i][1]+=lift;contacts[i]=flight<.005;}
    }else body.position[1]=-.020*envelope((p-.78)/.22)*a*scale;
  }
  const frame=solvePose(spec,body,targets,contacts);
  return {...frame,id:program.id,phase:p,duration:program.duration,requestedFeet:targets,plannedContacts:contacts};
}
export function blendMotion(spec,from,to,t){
  t=smooth(t);
  const body={position:lerp(from.body.position,to.body.position,t),angles:lerp(from.body.angles,to.body.angles,t)};
  const targets=from.requestedFeet.map((f,i)=>lerp(f,to.requestedFeet[i],t));
  const contacts=targets.map(f=>f[1]<.018);
  return {...solvePose(spec,body,targets,contacts),id:to.id,phase:to.phase,duration:to.duration,requestedFeet:targets,plannedContacts:contacts};
}
export function trajectory(spec,id,amplitude=1,speed=1,hz=60){
  const program=motionById(id),duration=program.duration/speed;
  return Array.from({length:Math.ceil(duration*hz)+1},(_,i)=>{
    const seconds=Math.min(duration,i/hz),frame=sampleMotion(spec,id,seconds/duration*TAU,amplitude);
    return {seconds,body:frame.body,legs:frame.legs.map(l=>({id:l.id,angles_rad:l.angles,offset_from_cad_rad:l.commands,
      foot_mm:l.worldFoot.map(v=>v*1000),planned_contact:frame.plannedContacts[LEGS.findIndex(x=>x.id===l.id)],
      ik_residual_mm:l.errorMm})),max_ik_residual_mm:frame.maxErrorMm};
  });
}
