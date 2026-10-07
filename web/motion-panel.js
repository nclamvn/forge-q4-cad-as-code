import {MOTIONS,LEGS,TAU,motionById,sampleMotion,trajectory} from './motion-engine.js';
const $=id=>document.getElementById(id);
const degrees=v=>(Math.abs(v)<Math.PI/3600?0:v*180/Math.PI).toFixed(1);
const save=(name,text,type)=>{const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);};
export class MotionPanel{
  constructor(state,callbacks){
    this.state=state;this.callbacks=callbacks;this.last=0;this.group=motionById(state.motion.id).group;
    $('motion-library').innerHTML='<div class="motion-group-tabs" role="tablist" aria-label="Nhóm chuyển động">'+['Di chuyển','Tư thế','Biểu diễn'].map(group=>`<button role="tab" data-motion-group="${group}" aria-selected="false">${group}</button>`).join('')+'</div>'+['Di chuyển','Tư thế','Biểu diễn'].map(group=>`<div class="motion-family" data-family="${group}"><div>${MOTIONS.filter(m=>m.group===group).map(m=>`<button data-motion="${m.id}" aria-pressed="false">${m.name}<span>${m.duration.toFixed(1)} s</span></button>`).join('')}</div></div>`).join('');
    document.querySelectorAll('[data-motion]').forEach(b=>b.addEventListener('click',()=>{this.stopSequence();callbacks.select(b.dataset.motion);}));
    document.querySelectorAll('[data-motion-group]').forEach(b=>b.addEventListener('click',()=>{this.group=b.dataset.motionGroup;this.showGroup();}));
    for(const [id,key] of [['motion-speed','speed'],['motion-amplitude','amplitude']])$(id).addEventListener('input',e=>{
      state.motion[key]=Number(e.target.value);this.sync();callbacks.paths();if(key==='amplitude')this.chart();
    });
    for(const [id,key] of [['motion-paths','paths'],['motion-skeleton','skeleton'],['motion-joints','joints']])$(id).addEventListener('click',()=>{
      state.motion[key]=!state.motion[key];$(id).setAttribute('aria-pressed',String(state.motion[key]));callbacks.paths();
    });
    $('phase').addEventListener('input',e=>{state.playing=false;state.phase=Number(e.target.value);state.motion.transition=null;this.sync();});
    $('play').addEventListener('click',()=>{if(state.physics?.enabled)return;state.playing=!state.playing;if(state.motion.transition)state.motion.transition.paused=!state.playing;this.sync();});
    $('motion-step').addEventListener('click',()=>{state.playing=false;state.motion.transition=null;state.phase=(state.phase+TAU/(motionById(state.motion.id).duration*60))%TAU;this.sync();});
    $('motion-home').addEventListener('click',()=>{this.stopSequence();callbacks.select('stand');state.playing=false;state.phase=0;state.motion.transition=null;this.sync();});
    $('motion-sequence').addEventListener('click',()=>{
      state.motion.sequence=!state.motion.sequence;state.motion.sequenceElapsed=0;
      if(state.motion.sequence){state.playing=true;callbacks.select('walk');}
      this.sync();
    });
    $('motion-csv').addEventListener('click',()=>this.export('csv'));
    $('motion-json').addEventListener('click',()=>this.export('json'));
    $('motion-joint-values').innerHTML=LEGS.map(l=>`<section><h3>${l.label}</h3><div>${['Dạng','Hông','Gối'].map((name,j)=>`<span>${name}<output id="joint-${l.id}-${j}">0.0°</output><i><b id="joint-bar-${l.id}-${j}"></b></i></span>`).join('')}</div></section>`).join('');
    $('motion-contacts').innerHTML=LEGS.map(l=>`<div id="contact-${l.id}"><i></i><span>${l.short}</span><small>Đặt</small></div>`).join('');
    this.sync();this.chart();
  }
  stopSequence(){this.state.motion.sequence=false;this.sync();}
  showGroup(){
    document.querySelectorAll('[data-family]').forEach(el=>el.hidden=el.dataset.family!==this.group);
    document.querySelectorAll('[data-motion-group]').forEach(el=>{const active=el.dataset.motionGroup===this.group;el.setAttribute('aria-selected',String(active));});
  }
  sync(){
    const s=this.state,m=s.motion,p=motionById(m.id);
    if(this.currentId!==m.id){this.group=p.group;this.currentId=m.id;}this.showGroup();
    document.querySelectorAll('[data-motion]').forEach(b=>{b.classList.toggle('active',b.dataset.motion===m.id);b.setAttribute('aria-pressed',String(b.dataset.motion===m.id));});
    $('motion-title').textContent=p.name;$('motion-description').textContent=p.description;
    $('motion-speed').value=m.speed;$('motion-amplitude').value=m.amplitude;
    $('motion-speed-value').textContent=m.speed.toFixed(2)+'×';$('motion-amplitude-value').textContent=Math.round(m.amplitude*100)+'%';
    $('motion-period').textContent=(p.duration/m.speed).toFixed(2)+' s';
    $('play').textContent=s.playing?'Ⅱ':'▶';$('play').setAttribute('aria-label',s.playing?'Tạm dừng chuyển động':'Phát chuyển động');
    $('motion-sequence').textContent=m.sequence?'Dừng chuỗi trình diễn':'Trình diễn 15 động tác';
    $('motion-sequence').classList.toggle('active',m.sequence);
    document.querySelector('.motion-joint-drawer').hidden=!m.joints;
    for(const [id,key] of [['motion-paths','paths'],['motion-skeleton','skeleton'],['motion-joints','joints']])$(id).setAttribute('aria-pressed',String(m[key]));
  }
  chart(){
    const m=this.state.motion,spec=this.callbacks.model().spec,cols=96,width=360,x0=53;
    const data=Array.from({length:cols},(_,i)=>sampleMotion(spec,m.id,(i+.5)/cols*TAU,m.amplitude).plannedContacts);
    let svg='<svg viewBox="0 0 435 65" role="img" aria-label="Lịch đặt và nâng bốn chân trong một chu kỳ">';
    for(let j=0;j<4;j++){
      const y=4+j*15;svg+=`<text x="0" y="${y+8}" fill="#969696" font-size="13">${LEGS[j].short}</text><rect x="${x0}" y="${y}" width="${width}" height="9" fill="#252525"/>`;
      let start=null;
      for(let i=0;i<=cols;i++){
        if(i<cols&&data[i][j]&&start===null)start=i;
        if((i===cols||!data[i][j])&&start!==null){svg+=`<rect x="${x0+start/cols*width}" y="${y}" width="${(i-start)/cols*width}" height="9" fill="#bdbdb8"/>`;start=null;}
      }
    }
    svg+='<line id="motion-phase-marker" x1="53" x2="53" y1="0" y2="65" stroke="#fff" stroke-width="1.5"/></svg>';
    $('motion-footfall').innerHTML=svg;
  }
  update(frame,time){
    if(time-this.last<90)return;this.last=time;
    const s=this.state,m=s.motion;
    if(s.mode!=='motion'||s.physics?.enabled)return;
    if(!document.activeElement?.matches('#phase'))$('phase').value=s.phase;
    $('motion-phase-value').textContent=Math.round(frame.phase*100)+'%';
    const marker=$('motion-phase-marker');if(marker){const x=53+frame.phase*360;marker.setAttribute('x1',x);marker.setAttribute('x2',x);}
    $('motion-contact-count').textContent=frame.contactCount+'/4';
    $('motion-residual').textContent=frame.maxErrorMm<.01?'< 0.01 mm':frame.maxErrorMm.toFixed(2)+' mm';
    $('motion-height-value').textContent=(frame.body.position[1]>=0?'+':'')+Math.round(frame.body.position[1]*1000)+' mm';
    $('motion-solver-state').textContent=frame.clamped?'Cận giới hạn động học':'Trong miền động học';
    $('motion-solver-state').classList.toggle('limited',frame.clamped);
    document.querySelector('.motion-joint-drawer').hidden=!m.joints;
    for(const leg of frame.legs){
      const el=$('contact-'+leg.id);el.classList.toggle('planted',leg.contact);el.querySelector('small').textContent=leg.contact?'Đặt':'Nâng';
      if(m.joints)for(let j=0;j<3;j++){
        $('joint-'+leg.id+'-'+j).textContent=degrees(leg.commands[j])+'°';
        const v=leg.commands[j]/(this.callbacks.model().spec.joint_limit_deg*Math.PI/180),bar=$('joint-bar-'+leg.id+'-'+j);
        bar.style.left=(v<0?50+v*50:50)+'%';bar.style.width=Math.abs(v)*50+'%';
      }
    }
  }
  export(type){
    const model=this.callbacks.model(),m=this.state.motion,samples=trajectory(model.spec,m.id,m.amplitude,m.speed);
    const meta={format:'forge-q4-kinematic-trajectory-v1',cad_revision:model.revision,cad_spec:model.spec,motion:m.id,playback_rate:m.speed,amplitude:m.amplitude,sample_rate_hz:60,
      coordinates:'Three.js: X forward, Y up, Z right; metres for body, millimetres for feet',
      angles:'Radians; joint commands are offsets from the CAD assembly home pose',
      scope:'Kinematic preview only. No force/contact dynamics, actuator calibration, torque or collision certification. Not a hardware control program.'};
    if(type==='json')save(`Q4-${m.id}-trajectory.json`,JSON.stringify({...meta,samples},null,2),'application/json');
    else{
      const header=['cad_revision','motion','seconds','leg','roll_rad','hip_rad','knee_rad','roll_offset_rad','hip_offset_rad','knee_offset_rad','foot_x_mm','foot_y_mm','foot_z_mm','planned_contact','ik_residual_mm'];
      const rows=samples.flatMap(f=>f.legs.map(l=>[model.revision,m.id,f.seconds,l.id,...l.angles_rad,...l.offset_from_cad_rad,...l.foot_mm,l.planned_contact?1:0,l.ik_residual_mm].join(',')));
      save(`Q4-${m.id}-kinematic-preview.csv`,header.join(',')+'\n'+rows.join('\n'),'text/csv');
    }
    this.callbacks.message(`Đã xuất chu kỳ ${motionById(m.id).name}. Quỹ đạo minh họa, chưa dùng điều khiển robot thật.`);
  }
}
