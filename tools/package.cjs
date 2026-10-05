const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const esbuild=require(process.env.ESBUILD_PATH||'esbuild');
(async()=>{
  const bundle=await esbuild.build({entryPoints:[path.join(root,'web/app.js')],bundle:true,write:false,format:'iife',minify:true,
    alias:{'three/webgpu':path.join(root,'web/vendor/three.webgpu.js'),'three':path.join(root,'web/vendor/three.webgpu.js')},
    legalComments:'inline',target:['chrome120','safari18']});
  const model=JSON.parse(fs.readFileSync(path.join(root,'web/default-model.json'),'utf8'));
  const safe=value=>JSON.stringify(value).replace(/</g,'\\u003c');
  const step=fs.readFileSync(path.join(root,model.step_url.replace(/^\//,''))).toString('base64');
  const urls=[model.documentation.pdf_url,model.documentation.zip_url,...Object.entries(model.parts).flatMap(([k,p])=>[p.step_url,model.documentation.parts[k].dxf_url])];
  const files=Object.fromEntries(urls.map(url=>[url,'data:application/octet-stream;base64,'+fs.readFileSync(path.join(root,url.replace(/^\//,''))).toString('base64')]));
  const globals=`window.__FORGE_FILES__=${safe(files)};window.__FORGE_MODEL__=${safe(model)};window.__FORGE_SOURCE__=${safe(fs.readFileSync(path.join(root,'kernel.py'),'utf8'))};window.__FORGE_STEP__='data:application/step;base64,${step}';`;
  let html=fs.readFileSync(path.join(root,'web/index.html'),'utf8');
  html=html.replace('<link rel="stylesheet" href="style.css">',`<style>${fs.readFileSync(path.join(root,'web/style.css'),'utf8')}</style>`)
    .replace(/<script type="importmap">.*?<\/script>/s,'')
    .replace('<script type="module" src="app.js"></script>',`<script>${globals}\n${bundle.outputFiles[0].text.replace(/<\/script/gi,'<\\/script')}</script>`);
  fs.writeFileSync(path.join(root,'FORGE-Q4.html'),html);
  console.log(`FORGE-Q4.html: ${(Buffer.byteLength(html)/1048576).toFixed(2)} MiB, revision ${model.revision}`);
})();
