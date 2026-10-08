try{const res=await fetch('/customer-release/status.json');if(!res.ok)throw new Error('Gói phát hành chưa được đóng');const r=await res.json();
try{const verify=await fetch('/customer-release/verification.json');if(verify.ok){const v=await verify.json();if(v.release_id===r.release_id)r.clean_install_verified=v.clean_install_verified;}}catch{}
document.getElementById('release-state').textContent='Release '+r.release_id+' · '+(r.package_verified?'Gói đã kiểm hash':'Đang đóng gói')+' · '+(r.clean_install_verified?'Đã kiểm cài sạch':'Chờ kiểm cài sạch')+' · Đối chứng kỹ sư: '+(r.human_comparison_complete?'đã hoàn tất':'chưa thực hiện');
for(const [id,url] of Object.entries(r.routes))document.getElementById(id).href=url;
document.getElementById('downloads').replaceChildren(...Object.entries(r.downloads).map(([label,url])=>{const a=document.createElement('a');a.textContent=label+' ↗';a.href=url;return a;}));
}catch(e){document.getElementById('release-state').textContent=e.message;}
