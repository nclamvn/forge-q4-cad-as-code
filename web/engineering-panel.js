const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=(v,n=2)=>Number.isFinite(v)?v.toFixed(n):'—';
function save(name,text,type='application/json'){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([text],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}

export class EngineeringPanel{
  constructor(state,cb){
    this.state=state;this.cb=cb;this.job=null;this.timer=null;this.busy=false;this.undo=null;
    $('engineering-open').addEventListener('click',()=>this.open());$('engineering-close').addEventListener('click',()=>this.close());
    document.querySelectorAll('[data-lab-tab]').forEach(b=>b.addEventListener('click',()=>this.tab(b.dataset.labTab)));
    $('lab-context').addEventListener('click',()=>this.exportContext());$('lab-example').addEventListener('click',()=>this.example());
    $('lab-export-proposal').addEventListener('click',async()=>{if(await this.validate())save('Q4-design-proposal.json',JSON.stringify(this.proposal(),null,2));});
    $('lab-file').addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>32768)throw new Error('Đề xuất cần nhỏ hơn 32 KiB.');$('lab-proposal').value=await file.text();this.message('Đã nhập. Kiểm JSON trước khi chạy.');}catch(e){this.message(e.message);}finally{e.target.value='';}});
    $('lab-validate').addEventListener('click',()=>this.validate());$('lab-run').addEventListener('click',()=>this.start());
    $('lab-cancel').addEventListener('click',()=>this.cancel());$('lab-report').addEventListener('click',()=>{if(this.job)save('Q4-experiment-'+this.job.id+'.json',JSON.stringify(this.job,null,2));});
    $('lab-feedback').addEventListener('click',()=>this.exportContext(true));$('lab-adopt').addEventListener('click',()=>this.adopt());
    $('lab-undo').addEventListener('click',async()=>{if(this.undo){await this.cb.install(this.undo);this.undo=null;$('lab-undo').disabled=true;this.message('Đã trở về baseline; lịch sử thử nghiệm được giữ.');this.baseline();this.render();}});
    $('lab-proposal').addEventListener('input',()=>{this.valid=false;$('lab-diff').replaceChildren();});
    document.addEventListener('keydown',e=>{
      if($('engineering-panel').hidden)return;
      if(e.key==='Escape')this.close();
      if(e.key==='Tab'){const controls=[...$('engineering-panel').querySelectorAll('button,textarea,input,summary,[tabindex="0"]')].filter(el=>!el.disabled&&el.getClientRects().length);
        const first=controls[0],last=controls.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}
    });
  }
  async request(url,data=null){const r=await fetch(url,{method:data===null?'GET':'POST',headers:data===null?{}:{'Content-Type':'application/json'},body:data===null?undefined:JSON.stringify(data)});const j=await r.json();if(!r.ok)throw new Error(j.error||'Không nhận được kết quả.');return j;}
  message(text){$('lab-status').textContent=text;}
  baseline(){const m=this.cb.model();$('lab-revision').textContent=m.revision;$('lab-mass').textContent=number(m.metrics.loaded_mass_kg,3)+' kg';$('lab-base-spec').textContent=JSON.stringify(m.spec,null,2);}
  async open(){
    this.cb.pause();this.baseline();$('engineering-panel').hidden=false;$('engineering-close').focus();
    $('lab-offline').hidden=this.state.online;for(const id of ['lab-context','lab-example','lab-validate','lab-run','lab-export-proposal'])$(id).disabled=!this.state.online;
    if(this.state.online){this.history();if(!$('lab-proposal').value)await this.example();}
    if(this.job&&['queued','running','cancelling'].includes(this.job.status))this.poll();
  }
  close(){$('engineering-panel').hidden=true;$('engineering-open').focus();}
  async load(id){try{this.job=await this.request('/api/engineering/job?id='+encodeURIComponent(id));this.render();this.tab('results');if(['queued','running','cancelling'].includes(this.job.status))this.poll();}catch(e){this.message(e.message);}}
  tab(name){document.querySelectorAll('[data-lab-tab]').forEach(b=>b.setAttribute('aria-selected',b.dataset.labTab===name));document.querySelectorAll('[data-lab-pane]').forEach(p=>p.hidden=p.dataset.labPane!==name);if(name==='history')this.history();}
  current(){if(this.state.dirty||this.state.building)throw new Error('Dựng CAD với thông số đã đổi trước khi xuất context hoặc chạy thử.');return this.cb.model().revision;}
  proposal(){return JSON.parse($('lab-proposal').value);}
  async exportContext(feedback=false){
    try{const data=await this.request('/api/engineering/context',{base_revision:this.current(),intent:$('lab-intent').value,...(feedback&&this.job?{feedback_id:this.job.id}:{})});save('Q4-LLM-context-'+data.context.cad_revision+'.json',JSON.stringify(data,null,2));this.message('Đã xuất context JSON kèm prompt có revision, giới hạn, giả định'+(feedback?' và kết quả thử.':'. Gửi cho LLM, rồi nhập JSON trả về.'));}catch(e){this.message(e.message);}
  }
  async example(){try{const result=await this.request('/api/engineering/context',{base_revision:this.current(),intent:$('lab-intent').value});$('lab-proposal').value=JSON.stringify(result.context.proposal_template,null,2);this.valid=false;this.message('Đề xuất mẫu do người viết: giảm dày tay chân. Chưa được đánh giá.');}catch(e){this.message(e.message);}}
  async validate(){
    try{const j=await this.request('/api/engineering/validate',{base_revision:this.current(),proposal:this.proposal()});this.valid=true;$('lab-diff').innerHTML='<table><thead><tr><th>Tham số CAD</th><th>Baseline</th><th>Đề xuất</th></tr></thead><tbody>'+Object.entries(j.diff).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(v.before)}</td><td>${esc(v.after)}</td></tr>`).join('')+'</tbody></table><p>Đầu vào hợp lệ. Chưa có bằng chứng vận hành.</p>';this.message('JSON hợp lệ; kernel sẽ dựng và kiểm candidate khi chạy thử.');return true;}catch(e){this.valid=false;this.message('Đã chặn: '+e.message);return false;}
  }
  async start(){
    if(this.busy)return;if(!await this.validate())return;
    try{this.busy=true;$('lab-run').disabled=true;this.job=await this.request('/api/engineering/start',{base_revision:this.current(),proposal:this.proposal()});this.render();this.tab('results');this.poll();}catch(e){this.message(e.message);this.busy=false;$('lab-run').disabled=false;}
  }
  async poll(){
    clearTimeout(this.timer);if(!this.job)return;
    try{const token=this.job.id,j=await this.request('/api/engineering/job?id='+token);if(this.job.id!==token)return;this.job=j;this.render();if(['queued','running','cancelling'].includes(j.status)){this.busy=true;this.timer=setTimeout(()=>this.poll(),1100);}else{this.busy=false;$('lab-run').disabled=!this.state.online;this.history();}}catch(e){this.message(e.message);this.busy=false;$('lab-run').disabled=!this.state.online;}
  }
  async cancel(){try{await this.request('/api/engineering/cancel',{id:this.job.id});this.message('Đang hủy; bước dựng CAD hiện tại cần kết thúc trước.');}catch(e){this.message(e.message);}}
  async adopt(){
    if(!this.job?.eligible)return;
    try{const previous=this.cb.model(),data=await this.request('/api/engineering/adopt',{id:this.job.id,base_revision:this.current()});await this.cb.install(data.model,data);this.undo=previous;$('lab-undo').disabled=false;this.baseline();this.message('Đã áp dụng candidate đã qua bộ thử. Vẫn cần kiểm bền, chế tạo và phần cứng.');$('lab-adopt').disabled=true;}catch(e){this.message('Chưa áp dụng: '+e.message);}
  }
  plot(a,b){
    const all=[...(a?.trace||[]),...(b?.trace||[])];if(!all.length)return '';
    const max=Math.max(.3,...all.map(v=>v.base_position_m[2])),end=Math.max(...all.map(v=>v.time_s));
    const line=(r,color,dash)=>r?`<polyline points="${r.trace.map(v=>`${30+v.time_s/end*390},${95-v.base_position_m[2]/max*75}`).join(' ')}" fill="none" stroke="${color}" stroke-width="1.6" ${dash?'stroke-dasharray="4 3"':''}/>`:'';
    return `<svg viewBox="0 0 450 116" role="img" aria-label="Cao độ thân theo thời gian baseline và candidate"><path d="M30 14V96H425" fill="none" stroke="#ccc"/><text x="30" y="10">${number(max*1000,0)} mm</text><text x="400" y="111">${number(end,0)} s</text>${line(a,'#aaa',true)}${line(b,'#111',false)}</svg>`;
  }
  render(){
    const j=this.job;if(!j)return;const active=['queued','running','cancelling'].includes(j.status);
    $('lab-progress').value=j.progress||0;$('lab-job-state').textContent=j.message;$('lab-job-id').textContent=j.id.slice(0,8)+' / '+j.status;
    $('lab-cancel').disabled=!active;$('lab-report').disabled=false;$('lab-feedback').disabled=active;$('lab-adopt').disabled=!j.eligible||this.cb.model().revision!==j.base_revision||this.state.dirty;
    const a=j.models?.baseline,b=j.models?.candidate;
    $('lab-comparison').innerHTML=a&&b?`<div><span>Baseline</span><strong>${number(a.loaded_mass_kg,3)}<small> kg</small></strong><code>${esc(a.cad_revision)}</code></div><div><span>Candidate</span><strong>${number(b.loaded_mass_kg,3)}<small> kg</small></strong><code>${esc(b.cad_revision)}</code></div><div><span>Chênh khối lượng</span><strong>${number((b.loaded_mass_kg-a.loaded_mass_kg)*1000,0)}<small> g</small></strong><p>Có tính tải / chưa kiểm bền</p></div>`:'';
    $('lab-thresholds').textContent=`Tiêu chí đề xuất: tải toàn bộ ≤ ${j.proposal.goals.max_loaded_mass_kg} kg; nghiêng ≤ ${j.proposal.goals.max_tilt_deg}°; RMS bám lệnh ≤ ${j.proposal.goals.max_tracking_rms_rad} rad; xuyên nền ≤ ${j.proposal.goals.max_penetration_mm} mm; cao độ ≥ ${j.proposal.goals.minimum_height_ratio}× home. ${j.proposal.assumptions.join(' ')}`;
    const gates=j.gates||j.cad_checks||[];$('lab-gates').innerHTML=gates.map(g=>`<span class="lab-gate ${g.passed?'pass':'fail'}">${g.passed?'✓':'×'} ${esc(g.id)}${g.actual!==undefined?' / '+esc(number(g.actual,3)):''}</span>`).join('');
    const before=j.trials?.baseline||[],after=j.trials?.candidate||[];
    const ids=[...new Set([...before,...after].map(r=>r.case.id))];
    $('lab-trials').innerHTML=ids.map(id=>{const x=before.find(r=>r.case.id===id),y=after.find(r=>r.case.id===id),m=y?.metrics;
      return `<details class="lab-trial"><summary><b>${esc({stance:'Đứng tải',trot:'Chạy chéo',slope:'Dốc 5°',traction:'Ma sát thấp',disturbance:'Đẩy ngang 35 N'}[id])}</b><span>${x?(x.passed?'Baseline đạt':'Baseline lỗi'):'Đang chờ'}</span><strong class="${y?.passed?'pass':'fail'}">${y?(y.passed?'Candidate đạt':'Candidate lỗi'):'Đang chờ'}</strong></summary>${this.plot(x,y)}<table><thead><tr><th>Phép đo thực / ước tính</th><th>Baseline</th><th>Candidate</th></tr></thead><tbody>${[['max_tilt_deg','Nghiêng lớn nhất (°)',2],['tracking_rms_rad','RMS bám lệnh (rad)',3],['minimum_height_ratio','Cao độ nhỏ nhất / home',3],['peak_torque_nm','Mô-men đỉnh (Nm)',2],['mean_forward_speed_m_s','Tốc độ X trung bình (m/s)',3],['mean_loaded_slip_m_s','Trượt chân chịu tải (m/s)',3],['electrical_energy_wh','Điện năng ước tính (Wh)',4],['peak_motor_c','Nhiệt motor ước tính (°C)',2]].map(([k,label,n])=>`<tr><td>${label}</td><td>${number(x?.metrics[k],n)}</td><td>${number(m?.[k],n)}</td></tr>`).join('')}</tbody></table><div class="lab-trial-gates">${(y?.gates||[]).map(g=>`<span class="${g.passed?'pass':'fail'}">${g.passed?'✓':'×'} ${esc(g.id)} / ${typeof g.actual==='number'?number(g.actual,3):esc(g.actual)}</span>`).join('')}</div></details>`;
    }).join('')||'<p class="lab-empty">Bộ thử sẽ dựng hai thiết kế và chạy 5 điều kiện giống nhau. Kết quả xuất hiện khi mỗi lượt kết thúc.</p>';
    if(j.status==='failed')$('lab-trials').innerHTML=`<p class="lab-empty">Đã dừng: ${esc(j.message)}</p>`;
  }
  async history(){
    if(!this.state.online){$('lab-history').textContent='Lịch sử thử nghiệm cần server Python.';return;}
    try{const r=await this.request('/api/engineering/history');$('lab-history').innerHTML=r.jobs.map(j=>`<button data-experiment="${esc(j.id)}"><span>${esc(j.proposal?.title)}</span><code>${esc(j.id.slice(0,8))} / ${esc(j.status)}</code><small>${j.eligible?'Đạt bộ thử':esc(j.message)}</small></button>`).join('')||'<p class="lab-empty">Chưa có thử nghiệm. Báo cáo được lưu tại server và giữ qua lần khởi động.</p>';
      $('lab-history').querySelectorAll('[data-experiment]').forEach(b=>b.addEventListener('click',()=>this.load(b.dataset.experiment)));
    }catch(e){this.message(e.message);}
  }
}
