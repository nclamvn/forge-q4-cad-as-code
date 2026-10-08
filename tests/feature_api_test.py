"""Actual HTTP + isolated CAD subprocess, source/brief-bound adoption and imports."""
import base64,copy,hashlib,json,sys,threading,time,urllib.error,urllib.request,zipfile,io
from pathlib import Path
from http.server import ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server import Handler,CACHE
from design.compiler import ensure_reference
from design import service
m=json.loads((ROOT/'web/default-model.json').read_text());CACHE[json.dumps(m['spec'],sort_keys=True)]=m
class Quiet(Handler):
    def log_message(self,*a):pass
http=ThreadingHTTPServer(('127.0.0.1',0),Quiet);url='http://127.0.0.1:'+str(http.server_port)
threading.Thread(target=http.serve_forever,daemon=True).start();checks=[]
def request(path,raw=None,origin=None,host=None):
    headers={'Content-Type':'application/json'}
    if origin is not None:headers['Origin']=origin
    if host:headers['Host']=host
    req=urllib.request.Request(url+path,data=None if raw is None else json.dumps(raw).encode(),headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=20) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def finish(job):
    limit=time.monotonic()+95
    while time.monotonic()<limit:
        code,j=request('/api/design/job?id='+job['id']);assert code==200
        if j['status'] in ('completed','failed','interrupted'):return j
        time.sleep(.3)
    raise AssertionError('Worker did not complete')
try:
    code,c=request('/api/design/context');assert code==200 and not c['llm_runtime']
    p=c['example'];ref='fixture-sensor-v1';raw=dict(reference=ref,program=p)
    assert request('/api/design/validate',raw)[0]==200
    for origin in ['null','http://example.org','http://127.0.0.1:1']:assert request('/api/design/validate',raw,origin)[0]==403
    assert request('/api/design/context',host='evil.example')[0]==403
    assert request('/api/design/validate',raw,url)[0]==200
    for bad in [{**p,'python':'pass'},{**p,'parameters':{'width':float('nan')}},{**p,'brief_sha256':'stale'}]:assert request('/api/design/validate',{**raw,'program':bad})[0]==422
    code,j=request('/api/design/start',{**raw,'provenance':dict(source='engineer',model='manual',note='API test fixture, no LLM')});assert code==200,j
    assert request('/api/design/start',{**raw,'provenance':dict(source='engineer',model='manual',note='API test fixture, no LLM')})[0]==422
    j=finish(j);assert j['status']=='completed' and j['eligible'],j
    revision=j['revision'];assert request('/api/design/context',dict(reference=ref,program=p,intent='Improve CAD with test evidence',feedback_revision=revision))[1]['feedback']['revision']==revision
    code,r=request('/api/design/result?revision='+revision);assert code==200 and r['current_sources_match']
    assert request('/api/design/adopt',dict(revision=revision,reference=ref,base_revision=None))[1]['manufacturing_authorized'] is False
    with urllib.request.urlopen(url+r['downloads']['package']) as response:archive=response.read()
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        manifest=json.loads(z.read('MANIFEST.json'))
        for name,h in manifest['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==h
    checks.append(dict(check='JSON context, schema/origin/host gates, real bounded worker, one active job, STEP/PDF/DXF archive hashes and explicit geometry-only adoption',passed=True,revision=revision))
    bad=copy.deepcopy(p);bad['features'][8]['translations'][0][0]+=5
    code,j=request('/api/design/start',dict(reference=ref,program=bad,provenance=dict(source='engineer',model='manual',note='Bad receiving hole test')));assert code==200
    j=finish(j);assert j['status']=='completed' and not j['eligible'],j
    assert request('/api/design/adopt',dict(revision=j['revision'],reference=ref,base_revision=revision))[0]==422
    assert request('/api/design/result?revision=../secret')[0]==422
    folder=service.OUTPUT/revision;file=folder/'program.json';original=file.read_bytes()
    try:
        file.write_bytes(original+b' ');assert request('/api/design/result?revision='+revision)[0]==422
    finally:file.write_bytes(original)
    checks.append(dict(check='BREP-detected misaligned receiving bore cannot become baseline; artifact mutation and invalid IDs rejected',passed=True))
    step=(ensure_reference()/'sensor.step').read_bytes();interface=c['brief']['sensor']['interface']
    code,j=request('/api/design/reference',dict(name='Uploaded synthetic STEP',interface=interface,step_base64=base64.b64encode(step).decode()));assert code==200
    j=finish(j);assert j['status']=='completed',j
    imported=j['reference_id'];assert request('/api/design/context?reference='+imported)[1]['brief']['sensor']['provenance']=='user_uploaded_step'
    assert request('/api/design/adopt',dict(revision=revision,reference=imported,base_revision=None))[0]==422
    bad=copy.deepcopy(interface);bad['mount_holes'][0]['x_mm']=0;bad['mount_holes'][0]['y_mm']=0
    code,j=request('/api/design/reference',dict(name='Bad declaration',interface=bad,step_base64=base64.b64encode(step).decode()));assert code==200
    j=finish(j);assert j['status']=='failed' and 'through clearance' in j['message']
    checks.append(dict(check='Actual STEP upload parsed in worker; source bytes hashed, declared voids checked, old brief adoption blocked and false mounting declaration rejected',passed=True))
    out=dict(status='passed',hardware_tested=False,llm_runtime=False,checks=checks,source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['server.py','design/service.py','design/compiler.py','design/worker.py','design/drawings.py','tests/feature_api_test.py']})
    (ROOT/'reports/robotics/feature-api-tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
finally:http.shutdown();http.server_close()
