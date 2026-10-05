"""Integration test against a running localhost CAD server."""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from kernel import DEFAULT
URL=os.environ.get('FORGE_TEST_URL','http://127.0.0.1:8767').rstrip('/')
def post(spec):
    request=urllib.request.Request(URL+'/api/build',json.dumps(spec).encode(),{'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=90) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
results=[]
for name,patch in [('default',{}),('light',dict(body_length=300,body_width=168,upper_length=110,lower_length=126,material='pa12',payload_kg=.5)),('steel',dict(material='steel')),('cad-edit',dict(bore_diameter=14,link_thickness=5))]:
    status,model=post({**DEFAULT,**patch});assert status==200
    assert model['proof']['roundtrip']['solid_count']==42
    assert all(c['passed'] for c in model['proof']['checks'] if c['id']!='mass')
    mass=next(c for c in model['proof']['checks'] if c['id']=='mass')
    assert mass['passed']==(name!='steel')
    with urllib.request.urlopen(URL+model['step_url'],timeout=10) as response:step=response.read()
    assert step.startswith(b'ISO-10303-21;') and b'END-ISO-10303-21;' in step
    results.append(dict(name=name,revision=model['revision'],mass_kg=model['metrics']['mass_kg'],mass_gate=mass['passed'],step_bytes=len(step),upper_volume_mm3=model['parts']['upper']['volume_mm3'],upper_mass_kg=model['parts']['upper']['mass_kg']))
assert results[-1]['revision']!=results[0]['revision']
assert results[-1]['upper_volume_mm3'] < results[0]['upper_volume_mm3']*.7
assert results[-1]['upper_mass_kg'] < results[0]['upper_mass_kg']*.7
status,rejection=post({**DEFAULT,'link_width':18,'bore_diameter':10})
assert status==422 and rejection['gate']=='SPEC_VALIDATION'
out={'status':'passed','variants':results,'fault_injection':{'http_status':status,**rejection}}
(ROOT/'reports/api-tests.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
