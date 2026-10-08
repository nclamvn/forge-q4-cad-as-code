from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import json
import hashlib
import threading
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import yaml
from kernel import ROOT, build, validate, SpecError

LOCK=threading.Lock()
CACHE={}

class ForgeHTTPServer(ThreadingHTTPServer):
    request_queue_size=64

def isolated_build(spec):
    # OCCT can retain the Python GIL during long operations. Keep HTTP/module
    # loading and telemetry responsive while the CAD compiler runs elsewhere.
    with tempfile.TemporaryDirectory(prefix='forge-cad-') as folder:
        job=Path(folder);(job/'spec.json').write_text(json.dumps(spec,allow_nan=False))
        process=subprocess.run([sys.executable,str(ROOT/'tools/cad_worker.py'),str(job)],cwd=ROOT,
                               capture_output=True,timeout=180)
        if process.returncode:
            raise ValueError((job/'error.txt').read_text() if (job/'error.txt').exists() else 'CAD worker failed')
        return json.loads((job/'answer.json').read_text())

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/"web"),**kw)
    def end_headers(self):
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        super().end_headers()
    def send_head(self):
        # Local source edits must not reuse a partially cached ES module graph.
        for header in ('If-Modified-Since','If-None-Match'):
            if header in self.headers:del self.headers[header]
        return super().send_head()
    def translate_path(self,path):
        clean=urlsplit(path).path
        if clean=='/FORGE-Q4.html':return str(ROOT/'FORGE-Q4.html')
        if clean.startswith('/customer-release/'):
            import re
            if re.fullmatch(r'/customer-release/(status.json|verification.json|FORGE-Q4-Customer.zip|llm-evidence.zip|integration.zip|MANIFEST.json)',clean):
                return str(ROOT/clean.lstrip('/'))
            return str(ROOT/'web'/'not-found')
        if clean.startswith('/design-output/'):
            import re
            candidate=(ROOT/clean.lstrip('/')).resolve()
            if re.fullmatch(r'/design-output/[a-f0-9]{16}/[A-Za-z0-9_.-]+',clean) and candidate.is_relative_to(ROOT/'design-output'):return str(candidate)
            return str(ROOT/'web'/'not-found')
        if clean.startswith('/robotics-output/'):
            candidate=(ROOT/clean.lstrip('/')).resolve()
            if candidate.is_relative_to(ROOT/'robotics-output'):return str(candidate)
            return str(ROOT/'web'/'not-found')
        if clean.startswith('/artifacts/'):
            candidate=(ROOT/clean.lstrip('/')).resolve()
            if candidate.is_relative_to(ROOT/'artifacts'):return str(candidate)
            return str(ROOT/'web'/'not-found')
        return super().translate_path(path)
    def json(self,data,status=200):
        out=json.dumps(data,ensure_ascii=False).encode();self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(out)));self.end_headers();self.wfile.write(out)
    def do_GET(self):
        if self.path.startswith('/api/integration/'):
            from design.integration import handle
            if handle(self):return
        if self.path.startswith('/api/benchmark/'):
            from design.benchmark import handle_get
            if handle_get(self):return
        if self.path.startswith('/api/design/'):
            from design.service import handle_get
            if handle_get(self):return
        if self.path.startswith('/api/deployment/'):
            from robotics.deployment import handle_get
            if handle_get(self):return
        if self.path.startswith('/api/engineering/'):
            from robotics.engineering import handle_get
            if handle_get(self):return
        if self.path.startswith(('/api/robotics/','/api/physics/')):
            from robotics.service import handle_get
            if handle_get(self):return
        if urlsplit(self.path).path=='/api/health':
            return self.json({'kernel':'build123d / Open Cascade','status':'ready','version':'0.13.0','llm_runtime':False})
        if urlsplit(self.path).path=='/api/source':
            data=(ROOT/'kernel.py').read_text()
            return self.json({'language':'python','source':data})
        return super().do_GET()
    def do_POST(self):
        if self.path.startswith('/api/integration/'):
            from design.integration import handle
            if handle(self):return
        if self.path.startswith('/api/benchmark/'):
            from design.benchmark import handle_post
            if handle_post(self):return
        if self.path.startswith('/api/design/'):
            from design.service import handle_post
            if handle_post(self):return
        if self.path.startswith('/api/deployment/'):
            from robotics.deployment import handle_post
            if handle_post(self):return
        if self.path.startswith('/api/engineering/'):
            from robotics.engineering import handle_post
            if handle_post(self,CACHE,LOCK):return
        if self.path.startswith(('/api/robotics/','/api/physics/')):
            from robotics.service import handle_post
            if handle_post(self,CACHE):return
        if self.path!='/api/build':return self.json({'error':'Không tìm thấy endpoint.'},404)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=8192:raise SpecError('Đặc tả quá lớn hoặc trống.')
            raw=json.loads(self.rfile.read(size));spec=validate(raw)
            key=json.dumps(spec,sort_keys=True)
            with LOCK:
                if key not in CACHE:CACHE[key]=isolated_build(spec)
                result=CACHE[key]
            return self.json(result)
        except (SpecError,ValueError,TypeError) as e:return self.json({'error':str(e),'gate':'SPEC_VALIDATION'},422)
        except Exception as e:
            import traceback;traceback.print_exc()
            return self.json({'error':f'Kernel không dựng được: {type(e).__name__}: {e}','gate':'CAD_BUILD'},500)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8767);args=parser.parse_args()
    model=json.loads((ROOT/'web/default-model.json').read_text()) if (ROOT/'web/default-model.json').exists() else build(yaml.safe_load((ROOT/'spec.yaml').read_text()))
    docs=model.get('documentation',{})
    snapshot_files=[model.get('step_url',''),docs.get('pdf_url',''),docs.get('zip_url','')]
    snapshot_files.extend(p.get('step_url','') for p in model.get('parts',{}).values())
    snapshot_files.extend(p.get('dxf_url','') for p in docs.get('parts',{}).values())
    snapshot_ready=all(url and (ROOT/url.lstrip('/')).is_file() for url in snapshot_files)
    if not snapshot_ready or model.get('compiler_hash')!=hashlib.sha256((ROOT/'kernel.py').read_bytes()).hexdigest()[:12] or docs.get('generator_hash')!=hashlib.sha256((ROOT/'technical.py').read_bytes()).hexdigest()[:12]:
        model=build(yaml.safe_load((ROOT/'spec.yaml').read_text()))
        (ROOT/'web/default-model.json').write_text(json.dumps(model,ensure_ascii=False))
    CACHE[json.dumps(model['spec'],sort_keys=True)]=model
    print(f'FORGE Q4 → http://127.0.0.1:{args.port}',flush=True)
    ForgeHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
