const $=id=>document.getElementById(id);
const n=(v,d=1)=>Number(v).toLocaleString('en-US',{maximumFractionDigits:d});
const fields={body_length:['Chiều dài thân',260,400,2],body_width:['Bề rộng thân',150,250,2],body_height:['Chiều cao thân',58,90,1],upper_length:['Tâm tay trên',110,190,1],lower_length:['Tâm tay dưới',110,210,1],link_width:['Bề rộng tay',12,48,1],link_thickness:['Độ dày tay',4,12,.5],bore_diameter:['Ø lỗ',6,16,1]};
function save(name,text,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
export class CADWorkbench{
  constructor(callbacks){
    this.callbacks=callbacks;this.baseline=null;this.current=null;this.selected='frame';this.pane='drawing';this.zoom=1;this.online=false;
    $('cad-open').addEventListener('click',()=>callbacks.open());$('cad-close').addEventListener('click',()=>callbacks.close());
    $('cad-form').addEventListener('submit',e=>{e.preventDefault();callbacks.build();});
    $('cad-fields').addEventListener('input',e=>{if(e.target.dataset.key)callbacks.edit(e.target.dataset.key,Number(e.target.value));});
    $('cad-components').addEventListener('click',e=>{const b=e.target.closest('[data-part]');if(b)this.choose(b.dataset.part);});
    $('cad-example').addEventListener('click',()=>callbacks.example());$('cad-invalid').addEventListener('click',()=>callbacks.invalid());
    $('cad-baseline').addEventListener('click',()=>{this.baseline=this.current;this.render(callbacks.spec(),callbacks.dirty());});
    $('cad-step').addEventListener('click',()=>this.file(this.current.parts[this.selected].step_url,this.current.parts[this.selected].part_number+'.step'));
    $('cad-dxf').addEventListener('click',()=>this.file(this.current.documentation.parts[this.selected].dxf_url,this.current.parts[this.selected].part_number+'-front.dxf'));
    $('cad-svg').addEventListener('click',()=>{if(!this.callbacks.dirty())save(this.current.parts[this.selected].part_number+'.svg',this.current.documentation.parts[this.selected].sheet,'image/svg+xml');});
    $('cad-pdf').addEventListener('click',()=>this.file(this.current.documentation.pdf_url,'FORGE-Q4-CAD-A3.pdf'));
    $('cad-dossier').addEventListener('click',()=>this.file(this.current.documentation.zip_url,'FORGE-Q4-CAD-dossier.zip'));
    $('cad-assembly-step').addEventListener('click',()=>$('export-step').click());$('cad-proof').addEventListener('click',()=>callbacks.proof());$('cad-recipe').addEventListener('click',()=>callbacks.source());
    document.querySelectorAll('[data-cad-pane]').forEach(b=>b.addEventListener('click',()=>{this.pane=b.dataset.cadPane;this.renderPaper();callbacks.pane(this.pane);}));
    addEventListener('resize',()=>this.setZoom(this.zoom));
    $('cad-zoom-in').addEventListener('click',()=>this.setZoom(Math.min(2.5,this.zoom+.25)));$('cad-zoom-out').addEventListener('click',()=>this.setZoom(Math.max(.75,this.zoom-.25)));
    $('cad-paper').addEventListener('click',e=>{const row=e.target.closest('[data-bom-part]');if(row){this.choose(row.dataset.bomPart);this.pane='drawing';this.renderPaper();callbacks.pane(this.pane);}});
    $('cad-paper').addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches('[data-bom-part]')){e.preventDefault();e.target.click();}});
  }
  file(url,name){if(this.callbacks.dirty()){this.callbacks.message('Dựng lại để đồng bộ CAD và bản vẽ trước khi xuất.');return;}const embedded=window.__FORGE_FILES__?.[url];const localPreview=location.protocol==='http:'&&location.hostname==='127.0.0.1';const a=document.createElement('a');a.href=localPreview?url:embedded||url;a.download=name;a.click();}
  enter(model,spec,online,dirty=false){
    this.baseline=model;this.current=model;this.online=online;$('cad-rail').hidden=false;$('cad-panel').hidden=false;$('cad-document').hidden=false;document.querySelector('.workspace').classList.add('cad-active');$('cad-open').classList.add('active');
    this.choose(this.selected);this.render(spec,dirty);$('cad-status').textContent=online?'Sửa tham số, dựng lại CAD và sinh lại hồ sơ bản vẽ.':'Snapshot đầy đủ bản vẽ; mở Start.command để sửa và dựng lại CAD.';if(dirty)this.dirty(spec);
  }
  exit(){document.querySelector('.workspace').classList.remove('cad-active');$('cad-rail').hidden=true;$('cad-panel').hidden=true;$('cad-document').hidden=true;$('cad-open').classList.remove('active');}
  choose(key){
    this.selected=key;const p=this.current.parts[key];$('cad-fields').innerHTML=p.parameter_keys.map(key=>{const [label,min,max,step]=fields[key];return `<label>${label} (mm)<input id="cad-${key}" data-key="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${this.callbacks.spec()[key]}" required></label>`;}).join('')||'<p class="cad-fixed">Hình học cố định của mô hình này. Các kích thước được liệt kê trong hồ sơ bên phải.</p>';
    $('cad-examples').hidden=!['upper','lower'].includes(key);this.render(this.callbacks.spec(),this.callbacks.dirty());this.callbacks.select(key);this.callbacks.pane(this.pane);
  }
  render(spec,dirty){
    if(!this.current)return;const p=this.current.parts[this.selected],b=this.baseline.parts[this.selected];
    $('cad-components').innerHTML=Object.entries(this.current.parts).map(([key,p])=>`<button data-part="${key}" class="${this.selected===key?'active':''}"><span class="cad-component-code">${p.part_number}</span><span>${p.name}</span><small>×${p.count}</small></button>`).join('');
    for(const el of $('cad-fields').querySelectorAll('input'))if(document.activeElement!==el)el.value=spec[el.dataset.key];
    $('cad-part-title').textContent=p.name;$('cad-part-code').textContent=p.part_number;$('cad-part-scope').textContent=p.group+' / '+p.mass_basis;
    $('cad-properties').innerHTML=[['Hợp lệ / số solid',`${p.valid?'Có':'Không'} / ${p.solids}`],['Hộp bao XYZ (mm)',p.bbox_mm.map(v=>n(v,2)).join(' × ')],['Thể tích',n(p.volume_mm3)+' mm³'],['Diện tích bề mặt',n(p.surface_mm2)+' mm²'],['Mặt / cạnh / đỉnh',`${p.faces} / ${p.edges} / ${p.vertices}`],['Khối lượng / bản',n(p.mass_kg*1000)+' g'],['Số lượng / tổng',`${p.count} / ${n(p.mass_kg*1000*p.count)} g`],['Diện tích mặt cắt',n(this.current.documentation.parts[this.selected].section_area_mm2)+' mm²']].map(([a,b])=>`<div><span>${a}</span><strong>${b}</strong></div>`).join('');
    $('cad-design-dimensions').innerHTML=p.dimensions.map(([a,b])=>`<div><span>${a}</span><strong>${typeof b==='number'?n(b,2):b}</strong></div>`).join('');
    $('cad-part-recipe').innerHTML=p.recipe.map(r=>`<li>${r}</li>`).join('');$('cad-notes').innerHTML=p.notes.map(r=>`<p>${r}</p>`).join('');
    const instances=this.current.instances.filter(i=>i.part===this.selected);$('cad-instances').innerHTML=instances.map(i=>`<div><strong>${i.id}</strong><span>XYZ ${i.position_mm.map(v=>n(v,1)).join(' / ')} mm</span><span>Rx/Ry/Rz ${i.rotation_deg.map(v=>n(v,1)).join(' / ')}°</span></div>`).join('');
    const rows=p.parameter_keys.map(key=>[fields[key][0],this.baseline.spec[key],this.current.spec[key]]);rows.push(['V (mm³)',n(b.volume_mm3),n(p.volume_mm3)],['m (g)',n(b.mass_kg*1000),n(p.mass_kg*1000)]);
    $('cad-compare').innerHTML='<thead><tr><th>Thông số</th><th>Mốc</th><th>Hiện tại</th></tr></thead><tbody>'+rows.map(([a,b,c])=>`<tr><td>${a}</td><td>${b}</td><td>${c}</td></tr>`).join('')+'</tbody>';
    const delta=(p.volume_mm3-b.volume_mm3)/b.volume_mm3*100;$('cad-delta').textContent=this.current.revision===this.baseline.revision?'Cùng revision với mốc.':`Thể tích ${delta>0?'+':''}${n(delta)}% so với mốc.`;
    $('cad-revision').textContent=this.current.revision;$('cad-sync').textContent=dirty?'Tham số đang chờ dựng. Khối và bản vẽ vẫn thuộc revision đã dựng.':'Khối, bản vẽ và STEP cùng revision.';
    for(const id of ['cad-step','cad-dxf','cad-svg','cad-pdf','cad-dossier'])$(id).disabled=dirty;
    $('cad-build').disabled=!this.online||!p.parameter_keys.length;for(const el of document.querySelectorAll('#cad-form input,#cad-example,#cad-invalid'))el.disabled=!this.online;
    this.renderPaper();
  }
  renderPaper(){
    if(!this.current)return;const p=this.current.parts[this.selected],doc=this.current.documentation;document.querySelectorAll('[data-cad-pane]').forEach(b=>b.classList.toggle('active',b.dataset.cadPane===this.pane));
    document.querySelector('.stage').classList.toggle('cad-solid',this.pane==='solid');$('cad-paper-scroll').hidden=this.pane==='solid';$('cad-sheet-counter').textContent=this.pane==='drawing'?p.part_number+' / 14 tờ':this.pane==='solid'?p.part_number+' / BREP':this.pane==='bom'?'42 vị trí / 12 loại':this.pane==='assembly'?'Q4-000 / 01':'Q4-001 / 02';
    $('cad-sheet-state').textContent=this.callbacks.dirty()?'Thông số chưa đồng bộ • bản vẽ CAD đã dựng được giữ lại':this.pane==='solid'?'Mesh từ BREP • xoay để kiểm tra chi tiết':'Nét chiếu và mặt cắt từ OCCT • concept, chưa phát hành chế tạo';
    if(this.pane==='solid')return;
    if(this.pane==='bom'){
      $('cad-paper').innerHTML=`<div class="cad-bom-page"><h2>BOM / 42 vị trí lắp ráp</h2><p>Revision ${this.current.revision}. Chọn một dòng để mở hồ sơ chi tiết.</p><table><thead><tr><th>#</th><th>Mã / vị trí</th><th>Chi tiết</th><th>m (g)</th><th>XYZ (mm)</th><th>Cơ sở khối lượng</th></tr></thead><tbody>${this.current.instances.map((i,k)=>{const p=this.current.parts[i.part];return `<tr data-bom-part="${i.part}" tabindex="0"><td>${k+1}</td><td><strong>${p.part_number}</strong><small>${i.id}</small></td><td>${p.name}</td><td>${n(p.mass_kg*1000)}</td><td>${i.position_mm.map(v=>n(v)).join(' / ')}</td><td>${p.mass_basis}</td></tr>`;}).join('')}</tbody></table><p>Điện tử bổ sung ${this.current.spec.electronics_mass_kg} kg và tải ${this.current.spec.payload_kg} kg là giả định, không tạo thêm solid.</p></div>`;
    }else $('cad-paper').innerHTML=this.pane==='assembly'?doc.assembly.sheet:this.pane==='exploded'?doc.assembly.exploded_sheet:doc.parts[this.selected].sheet;
    this.setZoom(this.zoom);
  }
  setZoom(zoom){this.zoom=zoom;$('cad-zoom-value').textContent=Math.round(zoom*100)+'%';const base=Math.max($('cad-paper-scroll').clientWidth-36,this.pane==='bom'?780:innerWidth<=820?700:580);$('cad-paper').style.width=`${base*zoom}px`;}
  dirty(spec){this.render(spec,true);$('cad-status').textContent='Tham số đã đổi. Dựng lại để cập nhật khối và toàn bộ hồ sơ.';}
  busy(){for(const el of document.querySelectorAll('#cad-form input,#cad-form button,#cad-example,#cad-invalid,#cad-baseline,#cad-components button'))el.disabled=true;$('cad-status').textContent='Đang dựng khối, chiếu nét khuất, cắt BREP và xuất 14 tờ A3…';}
  result(model,spec,error,online){this.online=online;if(model)this.current=model;this.render(spec,Boolean(error));$('cad-baseline').disabled=false;$('cad-status').textContent=error?`Đã chặn: ${error} Khối và hồ sơ cũ được giữ.`:`Đã cập nhật 42 khối và 14 tờ A3. ${model.proof.checks.filter(c=>c.passed).length}/6 kiểm tra đạt.`;}
}
