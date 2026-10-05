// Optional presentation treatment for recording actual UI interactions.
// No model changes, scripted clicks or simulated builds.
const style=document.createElement('style');
style.textContent=`@media(min-width:1100px){.workspace{height:calc(56.25vw - 78px)!important}}.capture-click{position:fixed;width:38px;height:38px;margin:-19px 0 0 -19px;z-index:10000;pointer-events:none;border:1.5px solid white;border-radius:50%;box-shadow:0 0 0 1px #111,0 0 18px #0006;animation:capturePulse .65s ease-out both}@keyframes capturePulse{0%{transform:scale(.55);opacity:1}100%{transform:scale(1.75);opacity:0}}`;
document.head.append(style);
document.addEventListener('click',e=>{
 const el=e.target.closest('button,input,[data-bom-part]');if(!el)return;
 const b=el.getBoundingClientRect(),dot=document.createElement('i');dot.className='capture-click';
 dot.style.left=(e.clientX||b.x+b.width/2)+'px';dot.style.top=(e.clientY||b.y+b.height/2)+'px';
 document.body.append(dot);setTimeout(()=>dot.remove(),700);
},true);
