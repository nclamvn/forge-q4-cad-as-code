import {motionById,LEGS,TAU} from './motion-engine.js';
const $=id=>document.getElementById(id);
const save=(name,text,type)=>{const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);};
export class PhysicsPanel{
  constructor(state,callbacks){
    this.state=state;this.cb=callbacks;this.session=null;this.meta=null;this.frame=null;this.running=false;this.pending=false;this.building=false;this.generation=0;this.last=0;this.history=[];this.available=false;
    $('engine-kinematic').addEventListener('click',()=>this.activate(false));$('engine-physics').addEventListener('click',()=>this.activate(true));
    $('physics-start').addEventListener('click',()=>this.start());$('physics-pause').addEventListener('click',()=>this.control(this.running?'pause':'resume'));
    $('physics-push').addEventListener('click',()=>this.control('push'));$('physics-estop').addEventListener('click',()=>this.control('estop'));
    for(const id of ['physics-terrain','physics-friction','physics-torque','motion-speed','motion-amplitude','operations-enabled','operations-temperature','operations-soc','operations-fault','operations-health'])$(id).addEventListener('input',()=>{if(state.physics.enabled)this.invalidate();});
    document.querySelectorAll('[data-physics-export]').forEach(b=>b.addEventListener('click',()=>this.export(b.dataset.physicsExport)));
    $('play').addEventListener('click',()=>{if(state.physics.enabled)this.control(this.running?'pause':'resume');});
    window.addEventListener('pagehide',()=>{if(this.session)navigator.sendBeacon('/api/physics/close',new Blob([JSON.stringify({session:this.session})],{type:'application/json'}));});
    if(state.online)this.request('/api/robotics/capabilities',null).then(r=>{this.available=r.available;if(!r.available)$('physics-capability').textContent='Cài requirements-simulation.txt để dùng MuJoCo.';}).catch(()=>{});
  }
  async request(url,data){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),45000);
    try{const response=await fetch(url,{method:data===null?'GET':'POST',headers:data===null?{}:{'Content-Type':'application/json'},body:data===null?undefined:JSON.stringify(data),signal:controller.signal});const json=await response.json();if(!response.ok)throw new Error(json.error||'Không nhận được kết quả từ bộ giải.');return json;}
    finally{clearTimeout(timer);}
  }
  activate(on){
    this.state.physics.enabled=on;this.state.playing=false;this.cb.mode();this.generation++;
    if(!on&&this.session){this.request('/api/physics/control',{session:this.session,action:'pause'}).catch(()=>{});this.running=false;}
    document.querySelector('.workspace').classList.toggle('physics-active',on);
    $('engine-kinematic').classList.toggle('active',!on);$('engine-physics').classList.toggle('active',on);
    $('physics-controls').hidden=!on;$('physics-telemetry').hidden=!on;
    for(const id of ['phase','motion-step','motion-home','motion-sequence','motion-csv','motion-json'])$(id).disabled=on;
    $('motion-contact-label').textContent=on?'Chân chịu lực':'Pha đặt chân';$('motion-height-label').textContent=on?'Cao độ thân':'Nâng / hạ thân';$('motion-residual-label').textContent=on?'Xuyên nền tối đa':'Sai lệch IK';
    $('motion-skeleton').textContent=on?'Lực / CoM':'Bộ khớp';
    document.querySelector('.motion-rail h1').innerHTML=on?'Cơ cấu.<br><em>Trong vật lý.</em>':'Chuyển động.<br><em>Trong tầm tay.</em>';
    document.querySelector('.motion-timeline-heading small').textContent=on?'Pha dự kiến của quỹ đạo lệnh':'Nét sáng = pha đặt chân';
    document.querySelector('.motion-boundary').textContent=on?'Tiếp xúc dùng hull convex của CAD. Thông số motor và vật liệu là giả định; chưa xác nhận phần cứng.':'Động học tại chỗ. Chưa mô phỏng lực, điều khiển hoặc kiểm va chạm toàn bộ.';
    if(on){this.state.motion.skeleton=true;$('motion-skeleton').setAttribute('aria-pressed','true');
      if(!this.frame){for(const id of ['motion-contact-count','motion-height-value','motion-residual'])$(id).textContent='—';$('motion-solver-state').textContent='Chưa có kết quả từ bộ giải';}
      if(!this.state.online){$('physics-start').disabled=true;this.message('Vật lý cần Python/MuJoCo. Chạy Start.command với requirements-simulation.txt.');}else this.message(this.session?'Tiếp tục hoặc dựng một lần chạy mới.':'Chọn quỹ đạo và dựng mô hình vật lý từ CAD.');}
    else{document.querySelectorAll('#motion-joint-values output').forEach(el=>{el.classList.remove('joint-limit-exceeded');el.removeAttribute('title');});this.cb.kinematic();}
    if(this.frame&&on)this.apply(this.frame);
  }
  message(text){$('physics-status').textContent=text;}
  invalidate(){
    if(!this.state.physics.enabled)return;
    if(this.building)this.generation++;
    if(this.running)this.control('pause');
    if(this.frame)this.apply(this.frame);
    this.message('Thông số đã đổi. Bấm Dựng và chạy vật lý để áp dụng.');this.state.physics.dirty=true;
  }
  async start(){
    if(this.building||!this.state.online)return;
    if(this.state.dirty||this.state.building){this.message('Dựng CAD với đặc tả mới trước khi tạo mô hình vật lý.');return;}
    this.building=true;this.running=false;const generation=++this.generation;$('physics-start').disabled=true;
    this.message('Đang đọc STEP, tích phân quán tính và tạo mô hình…');
    try{
      if(this.session){await this.request('/api/physics/close',{session:this.session}).catch(()=>{});this.session=null;}
      const result=await this.request('/api/physics/create',{cad_revision:this.cb.model().revision,motion:this.state.motion.id,amplitude:this.state.motion.amplitude,speed:this.state.motion.speed,
        terrain:$('physics-terrain').value,friction:Number($('physics-friction').value),profile:{...(this.acceptedProfile||{}),torque_limit_nm:Number($('physics-torque').value)},
        operations:{...(this.acceptedOperations||{}),enabled:$('operations-enabled').checked,initial_motor_c:Number($('operations-temperature').value),initial_soc:Number($('operations-soc').value),failed_joint:Number($('operations-fault').value),joint_health:Number($('operations-health').value)}});
      if(generation!==this.generation||!this.state.physics.enabled||this.state.mode!=='motion'){await this.request('/api/physics/close',{session:result.session});return;}
      this.session=result.session;this.meta=result.model;this.state.physics.meta=result.model;this.state.physics.dirty=false;this.history=[];this.cb.reset(this.meta,$('physics-terrain').value);
      $('physics-downloads').hidden=false;$('physics-capability').textContent=`MuJoCo / ${Math.round(1/this.meta.profile.timestep_s)} Hz / ${this.meta.mass_kg.toFixed(3)} kg`;
      this.apply(result.frame);await this.control('resume');
      const op=result.frame.operations.profile;$('operations-assumptions').textContent=`Pin ${op.battery_wh} Wh / motor tương đương ${op.no_load_speed_rad_s} rad/s. Giảm mô-men từ ${op.derate_c}°C, ngắt ở ${op.cutoff_c}°C. Mô hình RC và điện năng chưa hiệu chuẩn.`;
      this.message(`CAD ${this.meta.cad_revision.slice(0,8)} → mô hình ${this.meta.model_revision.slice(0,8)}. Motor ${this.meta.profile.torque_limit_nm} Nm là giả định.`);
    }catch(error){this.message('Chưa chạy được: '+error.message);this.running=false;}
    finally{this.building=false;$('physics-start').disabled=!this.state.online;}
  }
  suspend(){if(this.running)this.control('pause');else this.generation++;}
  async control(action){
    if(!this.session)return;
    if(action==='resume'&&this.state.physics.dirty){this.message('Dựng lại mô hình để áp dụng thông số đã đổi.');return;}
    const token=this.session,gen=++this.generation;
    if(action==='pause')this.running=false;
    try{
      const frame=await this.request('/api/physics/control',{session:token,action});
      if(gen!==this.generation||token!==this.session)return;
      this.running=action==='resume'||action==='estop'||(action==='push'&&this.running);this.last=performance.now();this.apply(frame);
      if(action==='estop')this.message('Motor đã ngắt. Trọng lực vẫn tác động; cần dựng lại để bật motor.');
    }catch(error){this.running=false;this.message(error.message);}
  }
  tick(now){
    if(!this.state.physics.enabled||this.state.mode!=='motion'||!this.running||this.pending||this.building||!this.session||now-this.last<40)return;
    const seconds=Math.min(.1,(now-this.last)/1000);this.last=now;this.pending=true;const gen=this.generation,token=this.session;
    this.request('/api/physics/step',{session:token,seconds}).then(frame=>{if(gen===this.generation&&token===this.session)this.apply(frame);})
      .catch(error=>{if(gen===this.generation){this.running=false;this.message('Bộ giải dừng: '+error.message);}}).finally(()=>{this.pending=false;});
  }
  apply(frame){
    this.frame=frame;this.state.physics.frame=frame;
    if(!this.state.physics.enabled)return;
    this.cb.frame(frame);
    $('stage-caption').textContent='CAD → quán tính → lực tiếp xúc. Thân do bộ giải quyết định.';
    const program=motionById(frame.motion);$('motion-title').textContent=program.name;$('motion-period').textContent='MuJoCo';
    $('motion-description').textContent='Thân tự do, servo giới hạn mô-men. Vị trí thân do solver quyết định.';
    $('motion-contact-count').textContent=frame.contact_count+'/4';$('motion-height-value').textContent=Math.round(frame.base_position_m[2]*1000)+' mm';$('motion-residual').textContent=frame.max_penetration_mm.toFixed(2)+' mm';
    $('motion-solver-state').textContent=frame.fall_detected?'Đã phát hiện ngã':frame.estopped?'Motor đã ngắt':frame.status==='paused'?'Đã tạm dừng bộ giải':'Bộ giải lực đang hoạt động';
    $('motion-solver-state').classList.toggle('limited',frame.fall_detected||frame.estopped);
    for(const foot of frame.feet){const el=$('contact-'+foot.id);el.classList.toggle('planted',foot.contact);el.querySelector('small').textContent=foot.normal_force_n.toFixed(1)+' N';}
    for(let i=0;i<frame.joints.length;i++){const leg=LEGS[Math.floor(i/3)],j=i%3,q=frame.joints[i].position_rad;
      const actual=frame.joints[i],value=$('joint-'+leg.id+'-'+j);value.textContent=(q*180/Math.PI).toFixed(1)+'°';
      value.title=`${actual.torque_nm.toFixed(2)} Nm / ${actual.velocity_rad_s.toFixed(2)} rad/s / cữ ${(actual.lower_limit_rad*180/Math.PI).toFixed(1)}…${(actual.upper_limit_rad*180/Math.PI).toFixed(1)}°`;
      value.classList.toggle('joint-limit-exceeded',q<actual.lower_limit_rad||q>actual.upper_limit_rad);
      const bar=$('joint-bar-'+leg.id+'-'+j),v=q/Math.max(Math.abs(actual.lower_limit_rad),Math.abs(actual.upper_limit_rad));
      bar.style.left=(v<0?50+Math.max(-1,v)*50:50)+'%';bar.style.width=Math.min(1,Math.abs(v))*50+'%';}
    $('phase').value=frame.phase*TAU;$('motion-phase-value').textContent=Math.round(frame.phase*100)+'%';
    const marker=$('motion-phase-marker');if(marker){const x=53+frame.phase*360;marker.setAttribute('x1',x);marker.setAttribute('x2',x);}
    $('play').textContent=this.running?'Ⅱ':'▶';$('play').setAttribute('aria-label',this.running?'Tạm dừng bộ giải vật lý':'Tiếp tục bộ giải vật lý');
    $('physics-time').innerHTML=frame.time_s.toFixed(2)+' <small>s</small>';$('physics-attitude').textContent=frame.body_angles_rad.slice(0,2).map(v=>(v*180/Math.PI).toFixed(1)).join(' / ')+'°';
    $('physics-peak').textContent=frame.peak_torque_nm.toFixed(2)+' Nm';$('physics-work').textContent=frame.mechanical_abs_work_j.toFixed(2)+' J';$('physics-collisions').textContent=frame.self_contacts.length;
    $('physics-imu').textContent=frame.imu_accel_m_s2.map(v=>v.toFixed(1)).join(' / ');
    $('operations-live').hidden=!frame.operations?.enabled;
    if(frame.operations?.enabled){const o=frame.operations;
      $('operations-heat').textContent=Math.max(...o.motor_temperature_c).toFixed(1)+' °C';
      $('operations-power').textContent=(o.battery_soc*100).toFixed(1)+'% / '+o.electrical_power_w.toFixed(1)+' W';
      $('operations-tracking').textContent=frame.tracking_rms_rad.toFixed(3)+' rad';
      $('operations-support').textContent=frame.support_margin_m===null?'< 3 chân':(frame.support_margin_m*1000).toFixed(1)+' mm';
      $('operations-drive').textContent=o.cutoff?'Đã ngắt drive':Math.min(...o.torque_factor).toFixed(2)+'× khả dụng';
    }
    $('physics-pause').disabled=false;$('physics-pause').textContent=this.running?'Tạm dừng':'Tiếp tục';$('physics-push').disabled=frame.estopped;$('physics-estop').disabled=frame.estopped;
    if(!this.history.length||frame.time_s>this.history.at(-1).t){this.history.push({t:frame.time_s,forces:frame.feet.map(f=>f.normal_force_n)});if(this.history.length>100)this.history.shift();}
    const max=Math.max(40,...this.history.flatMap(f=>f.forces));
    $('physics-force-chart').innerHTML='<path d="M0 42H180" stroke="#444" fill="none"/>'+LEGS.map((_,j)=>`<polyline points="${this.history.map((f,i)=>`${i/Math.max(1,this.history.length-1)*180},${42-f.forces[j]/max*38}`).join(' ')}" fill="none" stroke="${['#fff','#aaa','#666','#444'][j]}" stroke-width="1"/>`).join('');
  }
  async export(type){
    if(!this.meta)return;
    if(this.meta.cad_revision!==this.cb.model().revision){this.message('Dựng lại vật lý để xuất mô hình cùng revision CAD hiện tại.');return;}
    try{
      if(type==='report'||type==='csv'){
        const report=await this.request('/api/physics/report?session='+this.session,null);
        if(type==='report')save(`Q4-${report.reference.motion}-physics.json`,JSON.stringify(report,null,2),'application/json');
        else{
          const header=['time_s','joint','position_rad','velocity_rad_s','command_rad','torque_nm','base_x_m','base_y_m','base_z_m','contacts','fall_detected','tracking_rms_rad','static_support_margin_m','loaded_slip_m_s','operations_enabled','estimated_motor_c','available_torque_nm','estimated_soc','estimated_power_w','estimated_energy_wh','drive_cutoff'];
          const rows=report.samples.flatMap(f=>f.joints.map((j,i)=>{const o=f.operations;return [f.time_s,j.name,j.position_rad,j.velocity_rad_s,j.command_rad,j.torque_nm,...f.base_position_m,f.contact_count,f.fall_detected?1:0,f.tracking_rms_rad,f.support_margin_m??'',f.loaded_foot_slip_m_s,o.enabled?1:0,...(o.enabled?[o.motor_temperature_c[i],o.available_torque_nm[i],o.battery_soc,o.electrical_power_w,o.electrical_energy_wh,o.cutoff?1:0]:['','','','','',''])].join(',');}));
          save(`Q4-${report.reference.motion}-physics.csv`,header.join(',')+'\n'+rows.join('\n'),'text/csv');
        }
      }else{const a=document.createElement('a');a.href=this.meta.downloads[type];a.download='';a.click();}
    }catch(error){this.message('Không xuất được: '+error.message);}
  }
}
