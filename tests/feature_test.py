"""Independent volume oracle, 20 feature scenarios and adversarial CAD gates.
Reference graphs are engineer authored; these tests do not measure LLM quality.
"""
import copy,hashlib,json,math,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from design.compiler import *
from design.worker import build,source_hashes
from pypdf import PdfReader
verification=[];cases=[];b,path,_=brief();sample=example(b)
def reject(fn):
    try:fn()
    except (ValueError,TypeError):return
    raise AssertionError('Expected rejection')
def flat():
    p=copy.deepcopy(sample);p['features']=p['features'][:10];p['result']='mounting_plate';return p

def cut(p,kind='circle'):
    base=p['result'];profile=dict(kind='circle',diameter=12) if kind=='circle' else dict(kind='polygon',points=[[-8,-6],[8,-6],[0,8]]) if kind=='polygon' else dict(kind='slot',length=24,width=8)
    origin=[0,24,-1] if kind=='slot' else [0,0,-1]
    p['features']+=[dict(id='window_profile',op='sketch',plane='XY',origin=origin,profile=profile),dict(id='window_tool',op='extrude',sketch='window_profile',amount='thickness+2'),dict(id='window_cut',op='boolean',base=base,tool='window_tool',mode='cut')];p['result']='window_cut';return p

def wall(p,plane='XY',left=False):
    base=p['result']
    if plane=='XZ':origin=[0,33.5,11];profile=dict(kind='rectangle',width=90,height=14);amount=3
    else:origin=[-42 if left else 0,0 if left else 32,4];profile=dict(kind='rectangle',width=3 if left else 90,height=28 if left else 3);amount=12
    p['features']+=[dict(id='wall_profile',op='sketch',plane=plane,origin=origin,profile=profile),dict(id='wall',op='extrude',sketch='wall_profile',amount=amount),dict(id='wall_union',op='boolean',base=base,tool='wall',mode='add')];p['result']='wall_union';return p

new=[('flat plate',flat()),('rounded plate',{**copy.deepcopy(sample),'features':copy.deepcopy(sample['features'][:11]),'result':'edge_finish'}),
 ('side cradle',copy.deepcopy(sample)),('one back wall',wall(flat())),('XZ sketch extrusion',wall(flat(),'XZ')),('one side wall',wall(flat(),left=True)),
 ('circular inspection window',cut(flat())),('polygon inspection window',cut(flat(),'polygon')),('cable slot',cut(flat(),'slot'))]
p=flat();p['features'][0]['profile']=dict(kind='polygon',points=[[-45,-30],[-40,-35],[40,-35],[45,-30],[45,30],[40,35],[-40,35],[-45,30]])
new.append(('octagonal sketch plate',p))

# Independent analytic volume includes the removed bore volumes, outer-corner fillets
# and rectangular-rib top chamfer frustum. It does not read feature instructions.
s,log=evaluate_graph(validate(flat(),b),False)
expected=(90*70-4*math.pi*(2.6**2+2.1**2))*4
assert abs(s.volume-expected)<1e-6
s0,_=evaluate_graph(validate(sample,b),False);s1,_=evaluate_graph(validate(sample,b),True)
expected_cradle=expected-4*(9-math.pi*9/4)*4+2*(3*32*12-(70*.5**2/2-4*.5**3/3))
assert abs(s0.volume-expected_cradle)<1e-6
assert abs(s1.volume-s0.volume)<1e-8
assert list(s1.bounding_box().size)==list(s0.bounding_box().size)==[90.,70.,16.]

transformed=dict(format='forge-feature-design-v1',name='Transform oracle',units='mm',brief_sha256=b['brief_sha256'],parameters={'dummy':1},features=[
    dict(id='profile',op='sketch',plane='XY',origin=[0,0,0],profile=dict(kind='rectangle',width=10,height=20)),
    dict(id='solid',op='extrude',sketch='profile',amount=2),
    dict(id='moved',op='transform',source='solid',translation=[7,9,4],rotation_deg=[0,0,90])],result='moved')
shape,_=evaluate_graph(validate(transformed,b),False);box=shape.bounding_box()
assert abs(shape.volume-400)<1e-8
assert all(abs(a-v)<1e-6 for a,v in zip(box.min,[-3,4,4]))
assert all(abs(a-v)<1e-6 for a,v in zip(box.max,[17,14,6]))
yz=copy.deepcopy(transformed);yz['features']=yz['features'][:2];yz['features'][0]['plane']='YZ';yz['features'][0]['origin']=[3,7,9];yz['result']='solid'
shape,_=evaluate_graph(validate(yz,b),False);assert all(abs(a-v)<1e-6 for a,v in zip(shape.bounding_box().min,[3,2,-1]))
verification.append(dict(check='Independent transform and YZ global-origin/normal extrusion oracle',passed=True))

verification.append(dict(check='Independent plate+bore+fillet+chamfer volume oracle; preview triangulation does not mutate authoritative BREP',passed=True,volume_mm3=s0.volume))

edits=[]
for key,value in [('width',94),('length',72),('sensor_shift_x',-12),('sensor_shift_x',12),('sensor_shift_y',5),('sensor_shift_y',-5),('rib_height',18),('rib_width',2.5),('rib_length',36)]:
    p=copy.deepcopy(sample);p['parameters'][key]=value;edits.append((key+'='+str(value),p))
p=cut(copy.deepcopy(sample),'slot');p['parameters']['sensor_shift_x']=-12;p['features'][-3]['origin'][0]='sensor_shift_x';edits.append(('shift sensor and add dependent slot',p))
for group,items in [('new_structure',new),('edit',edits)]:
    for name,p in items:
        p['name']=name;started=time.perf_counter();program=validate(p,b);shape,_=evaluate_graph(program,False);g,holes,_=checks(shape,program,b,path)
        failed=[v['id'] for v in g if not v['passed']];assert not failed,(name,failed)
        cases.append(dict(group=group,name=name,passed=True,seconds=time.perf_counter()-started,volume_mm3=shape.volume,mass_kg=shape.volume*2700/1e9,features=len(p['features']),program=program))
verification.append(dict(check='10 distinct feature structures + 10 revisions preserve independent sensor/receiving interfaces and geometry gates',passed=True,case_count=len(cases),provenance='engineer_authored_reference_graphs'))

for value in ["__import__('os').system('id')",'a[0]','a.__class__','2**400','1/0','nan']:
    reject(lambda:expression(value,sample['parameters']))
for patch in [dict(units='m'),dict(brief_sha256='stale'),dict(parameters={'width':float('nan')}),dict(python='print(1)')]:reject(lambda:validate({**sample,**patch},b))
p=copy.deepcopy(sample);p['features'][1]['sketch']='future';reject(lambda:validate(p,b))
p=copy.deepcopy(sample);p['features'].append(dict(id='unused',op='sketch',plane='XY',origin=[0,0,0],profile=dict(kind='circle',diameter=8)));reject(lambda:validate(p,b))
p=copy.deepcopy(sample);p['features'][-3]['edges']['at']['value']=999;reject(lambda:evaluate_graph(validate(p,b),False))
for key,value,expected_gate in [('width',120,'envelope'),('sensor_shift_x',25,'sensor_shift'),('thickness',3,'sensor_hole_1')]:
    p=copy.deepcopy(sample);p['parameters'][key]=value;s,_=evaluate_graph(validate(p,b),False);g,_,_=checks(s,p,b,path);assert not next(v['passed'] for v in g if v['id']==expected_gate)
p=copy.deepcopy(sample);p['features'][8]['translations'][0][0]+=5;s,_=evaluate_graph(validate(p,b),False);g,_,_=checks(s,p,b,path);assert not next(v['passed'] for v in g if v['id']=='carrier_hole_1')
p=copy.deepcopy(sample);p['parameters']['sensor_shift_x']=20;s,_=evaluate_graph(validate(p,b),False);g,_,_=checks(s,p,b,path);assert not next(v['passed'] for v in g if v['id']=='sensor_collision')
verification.append(dict(check='Code injection, nonfinite values, stale brief, unknown fields, forward/unused features rejected; missing selectors fail loudly; wrong holes/shift/thickness/envelope detected from BREP',passed=True))

folder=OUTPUT/'test-dossier';folder.mkdir(parents=True,exist_ok=True)
r=build(sample,'fixture-sensor-v1',dict(source='engineer',model='manual',note='Software verification fixture, no LLM'),folder)
assert r['eligible'] and not r['manufacturing_authorized'] and not r['llm_runtime']
pdf=PdfReader(folder/'bracket-A3.pdf');assert len(pdf.pages)==1 and abs(float(pdf.pages[0].mediabox.width)-420*72/25.4)<.01
text=pdf.pages[0].extract_text();assert 'Recipe' in text and 'BREP' in text
with zipfile.ZipFile(folder/'FORGE-AI-CAD.zip') as z:
    assert z.testzip() is None;manifest=json.loads(z.read('MANIFEST.json'))
    for name,h in manifest['files'].items():assert hashlib.sha256(z.read(name)).hexdigest()==h
completed=subprocess.run([sys.executable,str(folder/'reproduce.py')],cwd=folder,capture_output=True,text=True,timeout=30);assert completed.returncode==0,completed.stderr
again=import_step(folder/'reproduced.step');assert abs(again.volume-r['metrics']['volume_mm3'])<1e-6
assembly=import_step(folder/'assembly.step');assert len(assembly.solids())==3
verification.append(dict(check='Same-revision STEP part/3-solid assembly, four DXF, A3 PDF, hashed ZIP and isolated reproduction script validated',passed=True,revision=r['revision'],pdf_pages=1))

out=dict(status='passed',llm_quality_benchmarked=False,hardware_tested=False,checks=verification,scenarios=[{k:v for k,v in c.items() if k!='program'} for c in cases],source_sha256={**source_hashes(),'tests/feature_test.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
(ROOT/'reports/robotics/feature-tests.json').write_text(json.dumps(out,indent=2)+'\n')
examples=dict(format='forge-feature-reference-scenarios-v1',provenance='engineer-authored software fixtures, NOT external LLM trials',cases=[dict(group=c['group'],name=c['name'],program={**c['program'],'brief_sha256':'USE_CURRENT_CONTEXT_BRIEF_SHA256'}) for c in cases])
(ROOT/'docs/examples/feature-scenarios.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,indent=2))
