"""Customer download integrity, integrated physics, and CAD/HTTP responsiveness."""
import concurrent.futures,hashlib,io,json,os,time,urllib.request,urllib.error,zipfile
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1];URL=os.environ.get('FORGE_TEST_URL','http://127.0.0.1:8767')
checks=[]
def get(path):
 with urllib.request.urlopen(URL+path,timeout=10) as r:return r.status,r.read()
def post(path,data,origin=None):
 h={'Content-Type':'application/json'}
 if origin:h['Origin']=origin
 req=urllib.request.Request(URL+path,json.dumps(data).encode(),h)
 try:
  with urllib.request.urlopen(req,timeout=180) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
m=json.loads((ROOT/'web/default-model.json').read_text())
for key,url in [('step',m['step_url']),('pdf',m['documentation']['pdf_url']),('dossier',m['documentation']['zip_url'])]:
 status,data=get(url);assert status==200
 if key=='step':assert data.startswith(b'ISO-10303-21;')
 elif key=='pdf':assert len(PdfReader(io.BytesIO(data)).pages)==14
 else:
  with zipfile.ZipFile(io.BytesIO(data)) as z:assert z.testzip() is None
 checks.append(dict(check='Legacy download / '+key,passed=True,bytes=len(data)))
assert post('/api/integration/start',{'design_revision':'../../x'})[0]==422
assert post('/api/integration/start',{'design_revision':'ea345ca303a25fdc'},'https://invalid.example')[0]==403
status,data=get('/api/integration/result?revision=88b2de0745b9');r=json.loads(data);assert status==200 and not r['mass_budget_passed']
status,j=post('/api/integration/start',{'design_revision':'ea345ca303a25fdc'});assert status==200
while j['status']=='running':
 time.sleep(.2);j=json.loads(get('/api/integration/job?id='+j['id'])[1])
assert j['status']=='completed',j
code,sim=post('/api/physics/create',{'cad_revision':r['revision'],'motion':'stand'});assert code==200,sim
assert abs(sim['model']['mass_kg']-r['mass_after_kg'])<1e-10 and len(sim['frame']['instances'])==49
assert post('/api/physics/close',{'session':sim['session']})[0]==200
status,archive=get(r['downloads']['package']);assert status==200
with zipfile.ZipFile(io.BytesIO(archive)) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read('forge_q4_description/MANIFEST.json'))
 for name,h in manifest['files'].items():assert hashlib.sha256(z.read('forge_q4_description/'+name)).hexdigest()==h
checks.append(dict(check='Integration HTTP lifecycle, origin/schema rejection, attached physics and export manifests',passed=True))
with concurrent.futures.ThreadPoolExecutor() as pool:
 future=pool.submit(post,'/api/build',{**m['spec'],'body_length':342})
 latency=[]
 while not future.done():
  started=time.monotonic();status,_=get('/api/health');latency.append(time.monotonic()-started);assert status==200
  time.sleep(.2)
 code,cad=future.result();assert code==200,cad
assert len(latency)>2 and max(latency)<2,latency
assert all(c['passed'] for c in cad['proof']['checks'])
checks.append(dict(check='Heavy CAD isolated in subprocess: health remains responsive while BREP/drawings build',passed=True,
 health_requests=len(latency),max_health_latency_s=max(latency),built_revision=cad['revision']))
report=dict(status='passed',checks=checks,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
 ['server.py','tools/cad_worker.py','design/integration.py','robotics/service.py','tests/customer_api_test.py']})
(ROOT/'reports/robotics/customer-api.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
