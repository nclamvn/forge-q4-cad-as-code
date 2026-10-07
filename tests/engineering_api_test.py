"""Real HTTP boundary checks, lifecycle cancellation and persisted evidence."""
import hashlib,json,sys,threading,time,urllib.request,urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from server import Handler,CACHE
cad=json.loads((ROOT/'web/default-model.json').read_text());CACHE[json.dumps(cad['spec'],sort_keys=True)]=cad
class Quiet(Handler):
    def log_message(self,*args):pass
http=ThreadingHTTPServer(('127.0.0.1',0),Quiet);url='http://127.0.0.1:'+str(http.server_port)
threading.Thread(target=http.serve_forever,daemon=True).start()
checks=[]
def request(path,data=None,origin=None):
    headers={'Content-Type':'application/json'}
    if origin is not None:headers['Origin']=origin
    req=urllib.request.Request(url+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as err:return err.code,json.load(err)
try:
    status,context=request('/api/engineering/context',{'base_revision':cad['revision'],'intent':'Kiểm CAD'})
    assert status==200 and context['llm_runtime'] is False
    p=context['context']['proposal_template'];raw={'base_revision':cad['revision'],'proposal':p}
    assert request('/api/engineering/validate',raw)[0]==200
    for value in [{**p,'changes':{'link_width':18}},{**p,'changes':{'python':'print(1)'}},{**p,'base_revision':'stale'},{**p,'actuator_profile':{'torque_limit_nm':float('nan')}}]:
        assert request('/api/engineering/validate',{**raw,'proposal':value})[0]==422
    for origin in ['null','http://example.org','http://127.0.0.1:1']:
        assert request('/api/engineering/validate',raw,origin)[0]==403
    assert request('/api/engineering/validate',raw,url)[0]==200
    assert request('/api/engineering/validate',{**raw,'unexpected':1})[0]==422
    assert request('/api/engineering/context',{'base_revision':cad['revision'],'intent':'x'*4001})[0]==422
    checks.append({'check':'JSON exchange, provenance, same-origin and strict finite schema HTTP boundaries','passed':True})
    p['changes']={};p['actuator_profile']={'torque_limit_nm':.25}
    status,j=request('/api/engineering/start',raw);assert status==200
    token=j['id']
    assert request('/api/engineering/start',raw)[0]==422
    assert request('/api/engineering/cancel',{'id':token})[0]==200
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        status,j=request('/api/engineering/job?id='+token)
        assert status==200
        if j['status'] in ('cancelled','failed','completed'):break
        time.sleep(.2)
    assert j['status']=='cancelled' and not j['eligible'],j['message']
    assert request('/api/engineering/adopt',{'id':token,'base_revision':cad['revision']})[0]==422
    assert request('/api/engineering/job?id=../../etc')[0]==422
    status,history=request('/api/engineering/history');assert status==200 and any(v['id']==token for v in history['jobs'])
    checks.append({'check':'Bounded asynchronous job, concurrent run rejected, cancellation persists and cancelled candidate cannot be adopted','passed':True})
    out=dict(status='passed',cad_revision=cad['revision'],checks=checks,source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['server.py','robotics/service.py','robotics/engineering.py','tests/engineering_api_test.py']},llm_runtime=False)
    (ROOT/'reports/robotics/engineering-api-tests.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
finally:http.shutdown();http.server_close()
