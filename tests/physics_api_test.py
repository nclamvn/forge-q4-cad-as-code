"""Real localhost integration: model export, session lifecycle and input gates."""
import hashlib
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
URL=os.environ.get('FORGE_TEST_URL','http://127.0.0.1:8767').rstrip('/')
cad=json.loads((ROOT/'web/default-model.json').read_text());checks=[]

def post(path,body,origin=None):
    headers={'Content-Type':'application/json'}
    if origin:headers['Origin']=origin
    req=urllib.request.Request(URL+path,json.dumps(body).encode(),headers)
    try:
        with urllib.request.urlopen(req,timeout=90) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)

with urllib.request.urlopen(URL+'/api/robotics/capabilities') as r:cap=json.load(r)
assert cap['available'] and not cap['hardware_verified']
code,result=post('/api/physics/create',dict(cad_revision=cad['revision'],motion='stand'));assert code==200,result
token=result['session'];meta=result['model'];assert meta['link_count']==13 and meta['actuated_joint_count']==12
try:
    assert post('/api/physics/step',dict(session=token,seconds=.1))[1]['time_s']==0
    assert post('/api/physics/control',dict(session=token,action='resume'))[0]==200
    for _ in range(30):code,frame=post('/api/physics/step',dict(session=token,seconds=.1));assert code==200
    assert frame['time_s']==3 and frame['contact_count']==4 and not frame['fall_detected']
    assert len(frame['instances'])==42 and max(abs(j['torque_nm']) for j in frame['joints'])<=8
    post('/api/physics/control',dict(session=token,action='pause'))
    assert post('/api/physics/step',dict(session=token,seconds=.1))[1]['time_s']==3
    with urllib.request.urlopen(URL+'/api/physics/report?session='+token) as r:report=json.load(r)
    assert len(report['samples'])==150 and report['record_sample_rate_hz']==50
    with urllib.request.urlopen(URL+meta['downloads']['package']) as r:payload=r.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        assert z.testzip() is None
        manifest=json.loads(z.read('forge_q4_description/MANIFEST.json'))
        for name,sha in manifest['files'].items():assert hashlib.sha256(z.read('forge_q4_description/'+name)).hexdigest()==sha
    checks.append(dict(check='Create/resume/step/pause/report and hashed ROS package download',passed=True,package_bytes=len(payload),record_samples=150))
    for path,body,expected,origin in [
        ('/api/physics/step',dict(session=token,seconds=1),422,None),
        ('/api/physics/step',dict(session=token,seconds=float('nan')),422,None),
        ('/api/physics/step',dict(session='../../etc/passwd',seconds=.1),422,None),
        ('/api/physics/control',dict(session=token,action='shell'),422,None),
        ('/api/physics/create',dict(cad_revision=cad['revision'],profile={'hardware_verified':True}),422,None),
        ('/api/physics/create',dict(cad_revision=cad['revision'],friction=0),422,None),
        ('/api/physics/step',dict(session=token,seconds=.1,extra=1),422,None),
        ('/api/physics/step',dict(session=token,seconds=.1),403,'https://example.com'),
        ('/api/physics/step',dict(session=token,seconds=.1),403,'null'),
    ]:
        status,error=post(path,body,origin);assert status==expected,(status,error)
        checks.append(dict(check=path+' input rejection',http_status=status,error=error['error'],passed=True))
    code,f=post('/api/physics/control',dict(session=token,action='estop'));assert code==200 and f['estopped']
    assert post('/api/physics/control',dict(session=token,action='resume'))[0]==422
finally:
    assert post('/api/physics/close',dict(session=token))[0]==200
assert post('/api/physics/step',dict(session=token,seconds=.1))[0]==422
source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'server.py',ROOT/'robotics/service.py',Path(__file__)]}
out=dict(status='passed',cad_revision=cad['revision'],model_revision=meta['model_revision'],checks=checks,source_sha256=source,hardware_verified=False)
(ROOT/'reports/robotics').mkdir(parents=True,exist_ok=True)
(ROOT/'reports/robotics/api-tests.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
